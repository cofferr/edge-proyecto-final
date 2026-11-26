/*
  RF3 - Nodo remoto LoRaWAN (OTAA) con DHT22 + PIR, deep sleep.   (v3 final: deep sleep + PIR activos)
  Libreria: RadioLib 8.0.0, "DHT sensor library" (Adafruit) + Adafruit Unified Sensor.
  Placa: ESP32 Dev Module.  MONITOR SERIE A 115200 BAUDIOS.

  ESTADO: revisado contra el codigo fuente de RadioLib 8.0.0; NO compilado con la toolchain del ESP32
  ni probado en hardware (ver notas de entrega).

  MODOS DE DEPURACION (poner en 1 para aislar problemas):
    DEBUG_NO_SLEEP    = 1 -> nunca entra en deep sleep: el nodo queda despierto y envia cada PERIODO_S.
    DEBUG_NO_PIR_WAKE = 1 -> el PIR no dispara envios ni despierta del sleep (solo periodico).
  Valores finales: 0/0. Si algo falla, volver a 1/1 y subir de nivel: 1/0 -> 0/1 -> 0/0.
*/
#include <Arduino.h>
#include <SPI.h>
#include <RadioLib.h>
#include <DHT.h>
#include <Preferences.h>
#include <sys/time.h>
#include "esp_sleep.h"
#include "esp_system.h"

#define DEBUG_NO_SLEEP     0
#define DEBUG_NO_PIR_WAKE  0

// ---------- CREDENCIALES (deben coincidir con lorawan_ns.py) ----------
static const uint64_t JOIN_EUI = 0x0000000000000001ULL;
static const uint64_t DEV_EUI  = 0x70B3D57ED0000001ULL;
static uint8_t APP_KEY[16] = {0x2B,0x7E,0x15,0x16,0x28,0xAE,0xD2,0xA6,0xAB,0xF7,0x15,0x88,0x09,0xCF,0x4F,0x3C};

// ---------- PARAMETROS ----------
#define PERIODO_S          60      // demo: 60 s. Version "real": 300 (5 min)
#define MIN_GAP_PIR_S      10      // separacion minima entre envios disparados por PIR
#define PIR_WARMUP_S       60      // calentamiento del PIR tras alimentarlo (solo si el PIR se usa)
#define PIR_LOW_TIMEOUT_MS 15000   // maximo que se espera a que el PIR baje antes de dormir
#define DHT_SETTLE_MS      1500
#define FPORT              1
#define DR_UPLINK          5       // DR5 = SF7/BW125 en EU433

// ---------- PINES ----------
#define PIN_DHT  27
#define PIN_PIR  33                // RTC GPIO: puede despertar del deep sleep
#define PIN_NSS  5
#define PIN_SCK  18
#define PIN_MISO 19
#define PIN_MOSI 23
#define PIN_RST  14
#define PIN_DIO0 26
// DIO1 no existe en el Ra-01: se pasa RADIOLIB_NC (verificado en el codigo de RadioLib, ver notas)

DHT dht(PIN_DHT, DHT22);
SX1278 radio = new Module(PIN_NSS, PIN_DIO0, PIN_RST, RADIOLIB_NC);
LoRaWANBand_t banda;               // copia de EU433 reducida a un canal
LoRaWANNode* node = nullptr;
bool nodoListo = false;

// ---------- estado que sobrevive al deep sleep (RTC) ----------
RTC_DATA_ATTR uint8_t  rtcSession[RADIOLIB_LORAWAN_SESSION_BUF_SIZE];
RTC_DATA_ATTR bool     rtcSessionValida = false;
RTC_DATA_ATTR uint16_t contador = 0;
RTC_DATA_ATTR uint32_t bootCount = 0;
RTC_DATA_ATTR uint64_t proxReporteMs = 0;
RTC_DATA_ATTR uint64_t ultimoPirMs = 0;
RTC_DATA_ATTR bool     hayPir = false;
Preferences prefs;                 // nonces: sobreviven a perdida total de energia

// ---------- utilidades ----------
static uint64_t nowMs() {          // el reloj del sistema sigue contando en deep sleep (RTC)
  struct timeval tv; gettimeofday(&tv, NULL);
  return (uint64_t)tv.tv_sec * 1000ULL + tv.tv_usec / 1000;
}
static const char* resetStr(esp_reset_reason_t r) {
  switch (r) {
    case ESP_RST_POWERON: return "POWERON"; case ESP_RST_EXT: return "EXT(EN)"; case ESP_RST_SW: return "SW";
    case ESP_RST_PANIC: return "PANIC(crash)"; case ESP_RST_INT_WDT: return "INT_WDT"; case ESP_RST_TASK_WDT: return "TASK_WDT";
    case ESP_RST_WDT: return "WDT"; case ESP_RST_DEEPSLEEP: return "DEEPSLEEP"; case ESP_RST_BROWNOUT: return "BROWNOUT";
    default: return "OTRO";
  }
}
static const char* wakeStr(esp_sleep_wakeup_cause_t c) {
  switch (c) {
    case ESP_SLEEP_WAKEUP_UNDEFINED: return "ninguno (arranque normal)"; case ESP_SLEEP_WAKEUP_TIMER: return "TEMPORIZADOR";
    case ESP_SLEEP_WAKEUP_EXT0: return "PIR (EXT0)"; default: return "otro";
  }
}
// callbacks de persistencia (rellenan con ceros si no hay datos, para que RadioLib descarte el buffer)
void cbStorePersist(uint8_t* b, size_t n) { prefs.begin("lw", false); prefs.putBytes("p", b, n); prefs.end(); }
void cbRestorePersist(uint8_t* b, size_t n) {
  memset(b, 0, n);
  prefs.begin("lw", false);        // false: evita el error "NOT_FOUND" en el primer arranque
  if (prefs.getBytesLength("p") == n) prefs.getBytes("p", b, n);
  prefs.end();
}
void cbStoreSession(uint8_t* b, size_t n) { memcpy(rtcSession, b, n); rtcSessionValida = true; }
void cbRestoreSession(uint8_t* b, size_t n) { if (rtcSessionValida) memcpy(b, rtcSession, n); else memset(b, 0, n); }

bool esperarPirBajo(uint32_t timeoutMs) {          // con timeout: nunca se queda colgado
  uint32_t t0 = millis();
  while (digitalRead(PIN_PIR)) {
    if (millis() - t0 > timeoutMs) return false;
    delay(50);
  }
  return true;
}

void armarPayload(uint8_t* p, uint8_t mov) {
  delay(DHT_SETTLE_MS);
  float t = NAN, h = NAN;
  for (int i = 0; i < 3 && (isnan(t) || isnan(h)); i++) {
    h = dht.readHumidity(); t = dht.readTemperature();
    if (isnan(t) || isnan(h)) delay(600);
  }
  Serial.printf("[DHT] t=%.2f h=%.2f mov=%u\n", t, h, mov);
  int16_t  ti = isnan(t) ? 0x7FFF : (int16_t)lroundf(t * 100);
  uint16_t hi = isnan(h) ? 0xFFFF : (uint16_t)lroundf(h * 100);
  p[0] = ti & 0xFF; p[1] = ti >> 8;
  p[2] = hi & 0xFF; p[3] = hi >> 8;
  p[4] = mov;
  p[5] = contador & 0xFF; p[6] = contador >> 8;
}

void dormir() {
#if DEBUG_NO_SLEEP
  return;
#else
  if (!esperarPirBajo(PIR_LOW_TIMEOUT_MS)) Serial.println("[SLEEP] PIR sigue en HIGH: se duerme SOLO con temporizador");
  int64_t rem = (int64_t)proxReporteMs - (int64_t)nowMs();
  if (rem < 1000) rem = 1000;
  if (rem > (int64_t)PERIODO_S * 1000) rem = (int64_t)PERIODO_S * 1000;
  esp_sleep_enable_timer_wakeup((uint64_t)rem * 1000ULL);
  bool pirArmado = false;
#if !DEBUG_NO_PIR_WAKE
  if (!digitalRead(PIN_PIR)) { esp_sleep_enable_ext0_wakeup((gpio_num_t)PIN_PIR, 1); pirArmado = true; }  // ext0 es por NIVEL: solo se arma con el PIR en LOW
#endif
  if (!pirArmado) esp_sleep_disable_wakeup_source(ESP_SLEEP_WAKEUP_EXT0);
  if (nodoListo) radio.sleep();
  Serial.printf("[SLEEP] entrando en deep sleep %lld ms, despertar por PIR=%s\n", (long long)rem, pirArmado ? "SI" : "NO");
  Serial.flush();
  esp_deep_sleep_start();
#endif
}

// ---------- radio + LoRaWAN ----------
bool iniciarNodo() {
  if (nodoListo) return true;
  SPI.begin(PIN_SCK, PIN_MISO, PIN_MOSI, PIN_NSS);
  ConfigLoRa_t cfg;                                // los valores por defecto (434 MHz, SF9, CR4/7, sync 0x12) NO sirven:
  cfg.frequency       = 433175000;                 // se fijan explicitamente a los del canal LoRaWAN usado
  cfg.bandwidth       = 125000;
  cfg.spreadingFactor = 7;
  cfg.codingRate      = 5;
  cfg.syncWord        = RADIOLIB_LORAWAN_LORA_SYNC_WORD;   // 0x34
  cfg.power           = 10;
  cfg.preambleLength  = 8;
  int16_t st = radio.begin(cfg);
  Serial.printf("[RADIO] begin -> %d %s\n", st, st == RADIOLIB_ERR_NONE ? "(OK, chip 0x12 detectado)" : "(FALLO: revisar cableado SPI/NSS/RST)");
  if (st != RADIOLIB_ERR_NONE) return false;

  banda = EU433;
  for (int i = 0; i < 3; i++) { banda.txFreqs[i].freq = 4331750; banda.txFreqs[i].dr = DR_UPLINK; }  // unidades de 100 Hz
  node = new LoRaWANNode(&radio, &banda);
  node->setCallbackStorePersistence(cbStorePersist);
  node->setCallbackRestorePersistence(cbRestorePersist);
  node->setCallbackStoreSession(cbStoreSession);
  node->setCallbackRestoreSession(cbRestoreSession);
  node->beginOTAA(JOIN_EUI, DEV_EUI, APP_KEY, APP_KEY);      // NwkKey = AppKey (LoRaWAN 1.0.x)
  node->setDatarate(DR_UPLINK);                              // tasa de join/uplink: SF7
  int16_t lb = node->loadBuffers();
  Serial.printf("[LW] loadBuffers -> %d (0=sesion restaurada; <0 normal si no habia sesion guardada)\n", lb);
  nodoListo = true;
  return true;
}

bool unirse() {
  Serial.println("[LW] activateOTAA...");
  int16_t st = node->activateOTAA();
  if (st == RADIOLIB_LORAWAN_NEW_SESSION)           Serial.println("[LW] JOIN nuevo OK");
  else if (st == RADIOLIB_LORAWAN_SESSION_RESTORED) Serial.println("[LW] Sesion restaurada");
  else {
    Serial.printf("[LW] Join FALLO (%d)%s\n", st, st == RADIOLIB_ERR_NO_JOIN_ACCEPT ? " = no llego join-accept (ver servidor/front-end)" : "");
    rtcSessionValida = false;
    return false;
  }
  node->setADR(false);                                       // el servidor minimo no gestiona MAC commands
  node->setDatarate(DR_UPLINK);
  Serial.printf("[LW] DevAddr=%08lX FCntUp=%lu activada=%d\n", (unsigned long)node->getDevAddr(), (unsigned long)node->getFCntUp(), node->isActivated());
  return true;
}

void enviar(uint8_t mov) {
  uint8_t payload[7];
  armarPayload(payload, mov);
  int16_t st = node->sendReceive(payload, sizeof(payload), FPORT);   // sin confirmar
  if (st >= 0) {
    Serial.printf("[TX] uplink #%u OK (ToA %lu ms, FCntUp ahora %lu, downlink en ventana %d)\n",
                  contador, (unsigned long)node->getLastToA(), (unsigned long)node->getFCntUp(), st);
    contador++;
  } else {
    Serial.printf("[TX] FALLO %d\n", st);
    if (st != RADIOLIB_ERR_UPLINK_UNAVAILABLE) { node->clearSession(); rtcSessionValida = false; Serial.println("[TX] sesion descartada: se reunira en el proximo ciclo"); }
  }
}

void ciclo(bool periodico, bool pirOk) {
  if (periodico) proxReporteMs = nowMs() + (uint64_t)PERIODO_S * 1000;
  if (pirOk) { ultimoPirMs = nowMs(); hayPir = true; }
  if (!iniciarNodo()) return;
  if (!node->isActivated() && !unirse()) return;
  enviar(pirOk ? 1 : (digitalRead(PIN_PIR) ? 1 : 0));
}

void setup() {
  Serial.begin(115200);
  delay(300);
  bootCount++;
  esp_reset_reason_t rr = esp_reset_reason();
  esp_sleep_wakeup_cause_t causa = esp_sleep_get_wakeup_cause();
  Serial.printf("\n\n=== RF3 v2 arranque #%lu | reset: %s | despertar: %s | t=%llu ms ===\n",
                (unsigned long)bootCount, resetStr(rr), wakeStr(causa), (unsigned long long)nowMs());
  Serial.printf("[CFG] DEBUG_NO_SLEEP=%d DEBUG_NO_PIR_WAKE=%d PERIODO=%d s | PIR ahora=%d\n", DEBUG_NO_SLEEP, DEBUG_NO_PIR_WAKE, PERIODO_S, digitalRead(PIN_PIR));
  pinMode(PIN_PIR, INPUT);
  dht.begin();

  bool primerArranque = (causa == ESP_SLEEP_WAKEUP_UNDEFINED);
  if (primerArranque) { proxReporteMs = 0; hayPir = false; contador = 0; rtcSessionValida = false; }
#if !DEBUG_NO_PIR_WAKE
  if (primerArranque) { Serial.printf("[PIR] calentando %d s...\n", PIR_WARMUP_S); delay(PIR_WARMUP_S * 1000UL); }
#endif

  uint64_t now = nowMs();
  if (!primerArranque && proxReporteMs > now + (uint64_t)PERIODO_S * 2000) proxReporteMs = now;   // reloj incoherente: resincronizar
  bool timerWake = (causa == ESP_SLEEP_WAKEUP_TIMER);
  bool pirWake   = (causa == ESP_SLEEP_WAKEUP_EXT0);
  bool periodico = primerArranque || timerWake || now >= proxReporteMs;
  bool pirOk     = pirWake && (!hayPir || (now - ultimoPirMs) >= (uint64_t)MIN_GAP_PIR_S * 1000);
  if (pirWake && !pirOk) Serial.printf("[PIR] evento ignorado: %llu ms desde el ultimo (minimo %d s)\n", (unsigned long long)(now - ultimoPirMs), MIN_GAP_PIR_S);

  if (periodico || pirOk) ciclo(periodico, pirOk);
  dormir();            // no retorna salvo DEBUG_NO_SLEEP
  Serial.println("[DEBUG] sin deep sleep: continuo en loop()");
}

void loop() {
#if DEBUG_NO_SLEEP
  static bool pirPrev = false;
  uint64_t now = nowMs();
  bool periodico = now >= proxReporteMs;
  bool pirNow = digitalRead(PIN_PIR);
#if !DEBUG_NO_PIR_WAKE
  bool pirOk = pirNow && !pirPrev && (!hayPir || (now - ultimoPirMs) >= (uint64_t)MIN_GAP_PIR_S * 1000);
#else
  bool pirOk = false;
#endif
  pirPrev = pirNow;
  if (periodico || pirOk) ciclo(periodico, pirOk);
  delay(50);
#endif
}