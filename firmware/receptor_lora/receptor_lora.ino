/*
  Front-end de radio LoRa <-> USB serie (receptor conectado al Mac).
  Libreria: "LoRa" de Sandeep Mistry. Placa: ESP32 Dev Module. Serie a 115200.

  No interpreta LoRaWAN: solo es el "frontal de radio" del servidor de red (lorawan_ns.py).
    RX (radio): escucha 433.175 MHz, SF7, BW125, CR4/5, sync 0x34 -> imprime
                RX <hex> <rssi> <snr> <ms>
    TX (Mac):   recibe  TX <retardo_ms> <hex>  y transmite esa trama (IQ invertido, sin CRC)
                cuando pasan <retardo_ms> desde el fin de la ultima trama recibida.
  Respuestas: TXOK / ERR <motivo>.

  !! No compilado/probado al escribirlo.
*/
#include <SPI.h>
#include <LoRa.h>

#define PIN_NSS  5
#define PIN_RST  4      // ESP32 de 30 pines en protoboard (ajusta si usas otro: 14)
#define PIN_DIO0 16     // (ajusta si usas otro: 26)
#define PIN_SCK 18
#define PIN_MISO 19
#define PIN_MOSI 23

#define FREQ 433175000L

bool     txPendiente = false;
uint32_t txCuando = 0, ultimaRx = 0;
uint8_t  txBuf[64];
int      txLen = 0;

void modoRx() { LoRa.enableCrc(); LoRa.disableInvertIQ(); LoRa.receive(); }

void setup() {
  Serial.begin(115200);
  SPI.begin(PIN_SCK, PIN_MISO, PIN_MOSI, PIN_NSS);
  LoRa.setPins(PIN_NSS, PIN_RST, PIN_DIO0);
  if (!LoRa.begin(FREQ)) { Serial.println("ERR radio no inicia"); while (1) delay(1000); }
  LoRa.setSpreadingFactor(7);
  LoRa.setSignalBandwidth(125000);
  LoRa.setCodingRate4(5);
  LoRa.setPreambleLength(8);
  LoRa.setSyncWord(0x34);            // sync word publica LoRaWAN
  LoRa.setTxPower(14);
  modoRx();
  Serial.println("READY frontend 433.175MHz SF7 BW125");
}

static int hexVal(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  return -1;
}

void procesarLinea(String l) {
  l.trim();
  if (!l.startsWith("TX ")) return;
  int sp = l.indexOf(' ', 3);
  if (sp < 0) { Serial.println("ERR formato"); return; }
  uint32_t retardo = l.substring(3, sp).toInt();
  String hex = l.substring(sp + 1);
  int n = hex.length() / 2;
  if (n <= 0 || n > (int)sizeof(txBuf)) { Serial.println("ERR longitud"); return; }
  for (int i = 0; i < n; i++) {
    int a = hexVal(hex[2 * i]), b = hexVal(hex[2 * i + 1]);
    if (a < 0 || b < 0) { Serial.println("ERR hex"); return; }
    txBuf[i] = (a << 4) | b;
  }
  txLen = n;
  txCuando = ultimaRx + retardo;
  if ((int32_t)(txCuando - millis()) < 0) { Serial.println("ERR tarde"); return; }
  txPendiente = true;
}

void loop() {
  // 1) recepcion
  int tam = LoRa.parsePacket();
  if (tam > 0) {
    ultimaRx = millis();
    uint8_t buf[256]; int n = 0;
    while (LoRa.available() && n < 256) buf[n++] = LoRa.read();
    Serial.print("RX ");
    for (int i = 0; i < n; i++) Serial.printf("%02x", buf[i]);
    Serial.printf(" %d %.1f %lu\n", LoRa.packetRssi(), LoRa.packetSnr(), (unsigned long)ultimaRx);
  }
  // 2) comandos de la Mac
  static String linea;
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') { procesarLinea(linea); linea = ""; }
    else if (c != '\r' && linea.length() < 300) linea += c;
  }
  // 3) transmision programada (ventana RX1 del nodo)
  if (txPendiente && (int32_t)(millis() - txCuando) >= 0) {
    txPendiente = false;
    LoRa.idle();
    LoRa.disableCrc();
    LoRa.enableInvertIQ();           // los downlinks LoRaWAN van con IQ invertido
    LoRa.beginPacket();
    LoRa.write(txBuf, txLen);
    LoRa.endPacket();                // bloqueante hasta terminar
    Serial.println("TXOK");
    modoRx();
  }
}