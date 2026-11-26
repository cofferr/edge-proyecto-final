#include <DHT.h>
#include <NimBLEDevice.h>

#define SERVICE_UUID "7f3c1a10-5d2b-4e8a-9c41-2b6f0d3e8a01"
#define CHAR_UUID    "7f3c1a11-5d2b-4e8a-9c41-2b6f0d3e8a01"

// --- Pines ---
// El DHT22 necesita un GPIO bidireccional: NO puede ser 34-39 (solo entrada).
const int PIN_DHT   = 26;
// Salida analógica del sensor capacitivo. 34 pertenece a ADC1 (compatible con la radio).
const int PIN_SUELO = 34;

// --- Temporización y muestreo ---
const unsigned long PERIODO_MS = 2000;  // Periodo de envío (2 s para calibrar; luego se sube)
const int MUESTRAS_SUELO = 16;          // Promedio para reducir el ruido del ADC

DHT dht(PIN_DHT, DHT22);
NimBLECharacteristic *pChar;
bool conectado = false;

uint8_t trama[7];
float temp = NAN, hum = NAN;
unsigned long ultimaTrama = 0, ultimaLecturaDHT = 0;
unsigned long dhtOk = 0, dhtFallos = 0;  // Diagnóstico de fiabilidad del DHT22

class Callbacks : public NimBLEServerCallbacks {
  void onConnect(NimBLEServer *s, NimBLEConnInfo &info) override {
    conectado = true;
    Serial.println("Gateway conectado");
  }
  void onDisconnect(NimBLEServer *s, NimBLEConnInfo &info, int reason) override {
    conectado = false;
    Serial.println("Gateway desconectado");
    NimBLEDevice::startAdvertising();
  }
};

// Trama de 7 bytes (little-endian):
// [0-1] temp x100 (int16) | [2-3] hum x100 (uint16) | [4-5] suelo en mV (uint16) | [6] mov
// El campo de suelo lleva milivoltios (lectura calibrada de fábrica del ADC),
// no el valor crudo. La conversión a % se hace en el gateway con los mV de
// "seco" y "húmedo" medidos en la calibración. 0xFFFF queda reservado como "sin dato".
void armarTrama(float t, float h, uint16_t sueloMv, uint8_t mov) {
  int16_t  tt = (int16_t)lroundf(t * 100);
  uint16_t hh = (uint16_t)lroundf(h * 100);
  trama[0] = tt & 0xFF;      trama[1] = (tt >> 8) & 0xFF;
  trama[2] = hh & 0xFF;      trama[3] = (hh >> 8) & 0xFF;
  trama[4] = sueloMv & 0xFF; trama[5] = (sueloMv >> 8) & 0xFF;
  trama[6] = mov;
}

// Promedia varias lecturas del ADC: devuelve valor crudo (0-4095) y milivoltios.
void leerSuelo(uint16_t &raw, uint16_t &mv) {
  uint32_t acumRaw = 0, acumMv = 0;
  for (int i = 0; i < MUESTRAS_SUELO; i++) {
    acumRaw += analogRead(PIN_SUELO);
    acumMv  += analogReadMilliVolts(PIN_SUELO);
    delay(2);
  }
  raw = acumRaw / MUESTRAS_SUELO;
  mv  = acumMv  / MUESTRAS_SUELO;
}

void enviarTrama(uint16_t sueloRaw, uint16_t sueloMv) {
  // El suelo se reporta siempre por serie (útil para calibrar aunque falle el DHT22)
  Serial.printf("Suelo: raw=%u | %u mV", sueloRaw, sueloMv);

  if (isnan(temp) || isnan(hum)) {
    Serial.printf(" | DHT22 sin lectura valida (ok=%lu, fallos=%lu)\n", dhtOk, dhtFallos);
    return;
  }

  armarTrama(temp, hum, sueloMv, 0);  // mov = 0: este nodo no tiene PIR
  pChar->setValue(trama, 7);
  if (conectado) pChar->notify();

  Serial.print(" | Temp: "); Serial.print(temp);
  Serial.print(" C | Hum: "); Serial.print(hum);
  Serial.printf(" %% | DHT ok=%lu fallos=%lu | Trama: ", dhtOk, dhtFallos);
  for (int i = 0; i < 7; i++) Serial.printf("%02X ", trama[i]);
  Serial.println();
}

void setup() {
  Serial.begin(115200);
  Serial.println("Nodo ambiental: DHT22 + humedad de suelo (NimBLE)");

  dht.begin();
  analogReadResolution(12);
  analogSetPinAttenuation(PIN_SUELO, ADC_11db);  // Rango completo hasta ~3,3 V

  NimBLEDevice::init("EstacionESP32");
  NimBLEServer *server = NimBLEDevice::createServer();
  server->setCallbacks(new Callbacks());
  NimBLEService *servicio = server->createService(SERVICE_UUID);
  pChar = servicio->createCharacteristic(CHAR_UUID,
            NIMBLE_PROPERTY::READ | NIMBLE_PROPERTY::NOTIFY);
  servicio->start();
  Serial.println("Servidor BLE listo: EstacionESP32");

  NimBLEAdvertising *adv = NimBLEDevice::getAdvertising();
  adv->addServiceUUID(SERVICE_UUID);

  NimBLEAdvertisementData respuesta;
  respuesta.setName("EstacionESP32");
  adv->setScanResponseData(respuesta);
  adv->enableScanResponse(true);
  adv->start();
}

void loop() {
  unsigned long ahora = millis();

  // El DHT22 admite como máximo una lectura cada 2 s
  if (ahora - ultimaLecturaDHT >= 2000) {
    ultimaLecturaDHT = ahora;
    float t = dht.readTemperature(), h = dht.readHumidity();
    if (!isnan(t) && !isnan(h)) { temp = t; hum = h; dhtOk++; }
    else dhtFallos++;
  }

  if (ahora - ultimaTrama >= PERIODO_MS) {
    ultimaTrama = ahora;
    uint16_t raw, mv;
    leerSuelo(raw, mv);
    enviarTrama(raw, mv);
  }
  delay(20);
}