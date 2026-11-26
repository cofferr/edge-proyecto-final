// =====================================================================
// Nodo de visión (RF2): ESP32-CAM (cámara RHYX M21-45 / GC2145) + PIR
// - La cámara solo captura cuando el PIR detecta movimiento.
// - Sin color: se captura en YUV422 y se toma solo la luminancia (Y).
// - Cámara sin JPEG por hardware: el JPEG (en gris) se codifica por software
//   al final de cada evento, de modo que la foto ya esté lista para el gateway.
// - El fondo de referencia se toma una vez al arrancar (escena vacía)
//   y se puede repetir con /recalibrate.
// =====================================================================
#include "esp_camera.h"
#include "img_converters.h"
#include <WiFi.h>
#include <WebServer.h>
#include <ESPmDNS.h>

// ---------- Red ----------
const char *WIFI_SSID = "NETWORK";
const char *WIFI_PASS = "PASSWORD";
const char *HOSTNAME  = "nodocam";          // accesible como nodocam.local

// ---------- Pines AI-Thinker ESP32-CAM ----------
#define PWDN_GPIO_NUM   32
#define RESET_GPIO_NUM  -1
#define XCLK_GPIO_NUM    0
#define SIOD_GPIO_NUM   26
#define SIOC_GPIO_NUM   27
#define Y9_GPIO_NUM     35
#define Y8_GPIO_NUM     34
#define Y7_GPIO_NUM     39
#define Y6_GPIO_NUM     36
#define Y5_GPIO_NUM     21
#define Y4_GPIO_NUM     19
#define Y3_GPIO_NUM     18
#define Y2_GPIO_NUM      5
#define VSYNC_GPIO_NUM  25
#define HREF_GPIO_NUM   23
#define PCLK_GPIO_NUM   22
const int PIN_PIR = 13;                      // OUT del HC-SR501 (3,3 V)

// ---------- Parámetros ajustables ----------
const uint32_t XCLK_HZ = 20000000;           // Si hay errores EV-EOF-OVF, bajar a 10000000
const int ANCHO = 320, ALTO = 240, NPIX = ANCHO * ALTO;
// Posición del byte de luminancia (Y) en cada par de bytes YUV422:
//   0 -> YUYV (Y en bytes pares)   1 -> UYVY (Y en bytes impares)
// Si la foto sale lavada, sin contraste o con aspecto raro, probar el otro valor.
const int      OFFSET_Y             = 0;
const uint32_t PIR_CALENTAMIENTO_MS = 60000; // El HC-SR501 se estabiliza en 30-60 s
const uint32_t ENFRIAMIENTO_MS      = 8000;  // Pausa mínima entre eventos
const int      FRAMES_ESTABILIZAR   = 20;    // Fotogramas descartados (auto-exposición)
const int      FRAMES_FONDO         = 8;     // Fotogramas promediados para el fondo
const int      FRAMES_RUIDO         = 5;     // Fotogramas para estimar el ruido
const float    K_RUIDO              = 4.0f;  // Umbral = media + K * sigma del ruido
const int      UMBRAL_MIN = 20, UMBRAL_MAX = 80;
const bool     USAR_OTSU            = false; // false: umbral por ruido; true: Otsu
const float    AREA_MIN_PCT         = 1.0f;  // Menos que esto: ruido u objeto irrelevante
const float    AREA_MAX_PCT         = 60.0f; // Más que esto: cambio global de luz
const uint8_t  JPEG_CALIDAD         = 80;
const bool     FOTO_SIEMPRE         = true;  // true: foto en todo evento del PIR (RF2)
                                             // false: solo si el nodo confirma el objeto

// ---------- Búferes (en PSRAM) ----------
uint8_t *gris, *fondo, *mascara, *tmp;
uint32_t histo[256];
bool fondoListo = false;
float ruidoMedia = 0, ruidoSigma = 0;

// ---------- Estado del último evento ----------
struct Evento {
  uint32_t n = 0, confirmados = 0, descartados = 0;
  bool confirmado = false;
  const char *motivo = "none";
  float areaPct = 0;
  int x0 = 0, y0 = 0, x1 = 0, y1 = 0, cx = 0, cy = 0;
  int umbralRuido = 0, umbralOtsu = 0, umbralUsado = 0;
  uint32_t tCapUs = 0, tGrisUs = 0, tDiffUs = 0, tMorfoUs = 0, tMetUs = 0, tProcUs = 0, tJpgUs = 0;
  uint32_t tMs = 0;
  size_t fotoBytes = 0, mascaraBytes = 0;
} ev;

uint8_t *fotoJpg = nullptr, *maskJpg = nullptr;
size_t fotoLen = 0, maskLen = 0;

WebServer server(80);
bool pirPrev = false;
uint32_t ultimoEvento = 0;

// ---------------------------------------------------------------------
bool iniciarCamara() {
  camera_config_t c = {};
  c.ledc_channel = LEDC_CHANNEL_0;
  c.ledc_timer   = LEDC_TIMER_0;
  c.pin_d0 = Y2_GPIO_NUM; c.pin_d1 = Y3_GPIO_NUM; c.pin_d2 = Y4_GPIO_NUM; c.pin_d3 = Y5_GPIO_NUM;
  c.pin_d4 = Y6_GPIO_NUM; c.pin_d5 = Y7_GPIO_NUM; c.pin_d6 = Y8_GPIO_NUM; c.pin_d7 = Y9_GPIO_NUM;
  c.pin_xclk = XCLK_GPIO_NUM; c.pin_pclk = PCLK_GPIO_NUM;
  c.pin_vsync = VSYNC_GPIO_NUM; c.pin_href = HREF_GPIO_NUM;
  c.pin_sccb_sda = SIOD_GPIO_NUM; c.pin_sccb_scl = SIOC_GPIO_NUM;  // core 2.x: pin_sscb_*
  c.pin_pwdn = PWDN_GPIO_NUM; c.pin_reset = RESET_GPIO_NUM;
  c.xclk_freq_hz = XCLK_HZ;
  c.pixel_format = PIXFORMAT_YUV422;         // Se usará solo la luminancia (Y)
  c.frame_size   = FRAMESIZE_QVGA;           // 320x240
  c.jpeg_quality = 12;                       // No se usa
  c.fb_count     = 1;
  c.fb_location  = CAMERA_FB_IN_PSRAM;
  c.grab_mode    = CAMERA_GRAB_WHEN_EMPTY;
  esp_err_t err = esp_camera_init(&c);
  if (err != ESP_OK) { Serial.printf("Error al iniciar la camara: 0x%x\n", err); return false; }
  return true;
}

// Con un solo búfer, el primer fotograma tras un reposo es antiguo: se descarta.
camera_fb_t *capturaFresca() {
  camera_fb_t *fb = esp_camera_fb_get();
  if (fb) esp_camera_fb_return(fb);
  return esp_camera_fb_get();
}

// YUV422 -> gris: se copia solo el byte de luminancia de cada par (sin conversión de color).
bool aGris(camera_fb_t *fb) {
  if (fb->len < (size_t)NPIX * 2) return false;
  const uint8_t *src = fb->buf + OFFSET_Y;
  for (int i = 0; i < NPIX; i++) gris[i] = src[2 * i];
  return true;
}

// Captura un fotograma (consecutivo) y lo deja en 'gris'.
bool capturarGris() {
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) return false;
  bool ok = aGris(fb);
  esp_camera_fb_return(fb);
  return ok;
}

// Toma el fondo de referencia (promedio de varios fotogramas) y mide el ruido de la
// escena. Debe ejecutarse con la escena vacía.
bool calibrarFondo() {
  Serial.println("Calibrando fondo: mantener la escena vacia...");
  fondoListo = false;
  camera_fb_t *fb0 = capturaFresca();        // descarta el fotograma antiguo
  if (fb0) esp_camera_fb_return(fb0);
  for (int i = 0; i < FRAMES_ESTABILIZAR; i++) {   // deja estabilizar la auto-exposición
    camera_fb_t *f = esp_camera_fb_get();
    if (f) esp_camera_fb_return(f);
  }

  uint16_t *acum = (uint16_t *)ps_malloc(NPIX * sizeof(uint16_t));
  if (!acum) return false;
  memset(acum, 0, NPIX * sizeof(uint16_t));
  for (int k = 0; k < FRAMES_FONDO; k++) {
    if (!capturarGris()) { free(acum); return false; }
    for (int i = 0; i < NPIX; i++) acum[i] += gris[i];
  }
  for (int i = 0; i < NPIX; i++) fondo[i] = (uint8_t)(acum[i] / FRAMES_FONDO);
  free(acum);

  // Ruido: |fotograma - fondo| sobre escena estática
  uint64_t s = 0, s2 = 0;
  for (int k = 0; k < FRAMES_RUIDO; k++) {
    if (!capturarGris()) return false;
    for (int i = 0; i < NPIX; i++) {
      int d = (int)gris[i] - (int)fondo[i];
      int ad = d < 0 ? -d : d;
      s += ad; s2 += (uint64_t)ad * ad;
    }
  }
  double n = (double)NPIX * FRAMES_RUIDO;
  double media = s / n;
  double varianza = s2 / n - media * media;
  ruidoMedia = (float)media;
  ruidoSigma = varianza > 0 ? (float)sqrt(varianza) : 0;
  fondoListo = true;
  Serial.printf("Fondo listo. Ruido: media=%.2f sigma=%.2f -> umbral=%d\n",
                ruidoMedia, ruidoSigma, (int)(ruidoMedia + K_RUIDO * ruidoSigma + 0.5f));
  return true;
}

int umbralDesdeRuido() {
  int t = (int)(ruidoMedia + K_RUIDO * ruidoSigma + 0.5f);
  return t < UMBRAL_MIN ? UMBRAL_MIN : (t > UMBRAL_MAX ? UMBRAL_MAX : t);
}

// Método de Otsu sobre el histograma de la diferencia.
int otsu(const uint32_t *h, uint32_t total) {
  double suma = 0;
  for (int t = 0; t < 256; t++) suma += (double)t * h[t];
  double sumaB = 0, wB = 0, varMax = 0;
  int umbral = 0;
  for (int t = 0; t < 256; t++) {
    wB += h[t];
    if (wB == 0) continue;
    double wF = total - wB;
    if (wF == 0) break;
    sumaB += (double)t * h[t];
    double mB = sumaB / wB, mF = (suma - sumaB) / wF;
    double v = wB * wF * (mB - mF) * (mB - mF);
    if (v > varMax) { varMax = v; umbral = t; }
  }
  return umbral;
}

// Erosión (mínimo) o dilatación (máximo) con elemento 3x3, separable y en sitio.
void morfo3x3(uint8_t *img, bool erosion) {
  auto op = [erosion](uint8_t a, uint8_t b) -> uint8_t {
    return erosion ? (a < b ? a : b) : (a > b ? a : b);
  };
  for (int y = 0; y < ALTO; y++) {
    int f = y * ANCHO;
    for (int x = 0; x < ANCHO; x++) {
      uint8_t v = img[f + x];
      if (x > 0)         v = op(v, img[f + x - 1]);
      if (x < ANCHO - 1) v = op(v, img[f + x + 1]);
      tmp[f + x] = v;
    }
  }
  for (int y = 0; y < ALTO; y++) {
    for (int x = 0; x < ANCHO; x++) {
      uint8_t v = tmp[y * ANCHO + x];
      if (y > 0)        v = op(v, tmp[(y - 1) * ANCHO + x]);
      if (y < ALTO - 1) v = op(v, tmp[(y + 1) * ANCHO + x]);
      img[y * ANCHO + x] = v;
    }
  }
}

// ---------------------------------------------------------------------
// Pipeline: captura -> gris -> diferencia -> umbral -> morfología -> decisión -> JPEG
void procesarEvento(const char *origen) {
  ev.n++;
  ev.tMs = millis();
  uint32_t t = micros();
  camera_fb_t *fb = capturaFresca();
  ev.tCapUs = micros() - t;
  if (!fb) { ev.confirmado = false; ev.motivo = "capture_error"; ev.descartados++; return; }

  // 1) Luminancia (el fotograma de la cámara se libera enseguida)
  t = micros();
  bool ok = aGris(fb);
  esp_camera_fb_return(fb);
  ev.tGrisUs = micros() - t;
  if (!ok || !fondoListo) {
    ev.confirmado = false; ev.motivo = !ok ? "conversion_error" : "no_background"; ev.descartados++;
    return;
  }

  // 2) Diferencia con el fondo + histograma, 3) umbralización
  t = micros();
  memset(histo, 0, sizeof(histo));
  for (int i = 0; i < NPIX; i++) {
    int d = (int)gris[i] - (int)fondo[i];
    if (d < 0) d = -d;
    mascara[i] = (uint8_t)d;
    histo[d]++;
  }
  ev.umbralRuido = umbralDesdeRuido();
  ev.umbralOtsu  = otsu(histo, NPIX);
  ev.umbralUsado = USAR_OTSU ? ev.umbralOtsu : ev.umbralRuido;
  for (int i = 0; i < NPIX; i++) mascara[i] = mascara[i] > ev.umbralUsado ? 255 : 0;
  ev.tDiffUs = micros() - t;

  // 4) Morfología: apertura (elimina ruido) y cierre (rellena huecos)
  t = micros();
  morfo3x3(mascara, true);  morfo3x3(mascara, false);   // apertura
  morfo3x3(mascara, false); morfo3x3(mascara, true);    // cierre
  ev.tMorfoUs = micros() - t;

  // 5) Métricas: área, caja envolvente y centroide
  t = micros();
  uint32_t cnt = 0; uint64_t sx = 0, sy = 0;
  int x0 = ANCHO, y0 = ALTO, x1 = -1, y1 = -1;
  for (int y = 0; y < ALTO; y++) {
    for (int x = 0; x < ANCHO; x++) {
      if (mascara[y * ANCHO + x]) {
        cnt++; sx += x; sy += y;
        if (x < x0) x0 = x;
        if (x > x1) x1 = x;
        if (y < y0) y0 = y;
        if (y > y1) y1 = y;
      }
    }
  }
  ev.areaPct = 100.0f * cnt / NPIX;
  ev.x0 = cnt ? x0 : 0; ev.y0 = cnt ? y0 : 0; ev.x1 = cnt ? x1 : 0; ev.y1 = cnt ? y1 : 0;
  ev.cx = cnt ? (int)(sx / cnt) : 0; ev.cy = cnt ? (int)(sy / cnt) : 0;
  ev.tMetUs = micros() - t;
  ev.tProcUs = ev.tGrisUs + ev.tDiffUs + ev.tMorfoUs + ev.tMetUs;

  // 6) Decisión local del nodo
  if (ev.areaPct < AREA_MIN_PCT)      { ev.confirmado = false; ev.motivo = "area_low"; }
  else if (ev.areaPct > AREA_MAX_PCT) { ev.confirmado = false; ev.motivo = "global_light_change"; }
  else                                { ev.confirmado = true;  ev.motivo = "ok"; }
  if (ev.confirmado) ev.confirmados++; else ev.descartados++;

  // 7) JPEG en gris por software (la cámara no comprime): foto y máscara
  t = micros();
  if (ev.confirmado || FOTO_SIEMPRE) {
    uint8_t *f = nullptr, *m = nullptr; size_t fl = 0, ml = 0;
    bool okF = fmt2jpg(gris, NPIX, ANCHO, ALTO, PIXFORMAT_GRAYSCALE, JPEG_CALIDAD, &f, &fl);
    bool okM = fmt2jpg(mascara, NPIX, ANCHO, ALTO, PIXFORMAT_GRAYSCALE, JPEG_CALIDAD, &m, &ml);
    if (okF) { if (fotoJpg) free(fotoJpg); fotoJpg = f; fotoLen = fl; ev.fotoBytes = fl; }
    if (okM) { if (maskJpg) free(maskJpg); maskJpg = m; maskLen = ml; ev.mascaraBytes = ml; }
  }
  ev.tJpgUs = micros() - t;

  Serial.printf("[%s] #%lu %s | area=%.2f%% | umbral=%d (ruido=%d, otsu=%d) | t_proc=%lu us (morfo=%lu) | jpeg=%lu us | foto=%u B\n",
                origen, ev.n, ev.motivo, ev.areaPct, ev.umbralUsado, ev.umbralRuido, ev.umbralOtsu,
                ev.tProcUs, ev.tMorfoUs, ev.tJpgUs, (unsigned)ev.fotoBytes);
}

// ---------------------------------------------------------------------
// Servidor HTTP (para el gateway)
String jsonStatus() {
  char b[1100];
  snprintf(b, sizeof(b),
    "{\"node\":\"esp32cam-vision\",\"uptime_s\":%lu,\"pir\":%d,\"warming_up\":%s,\"background_ready\":%s,"
    "\"events\":%lu,\"confirmed\":%lu,\"discarded\":%lu,"
    "\"noise\":{\"mean\":%.2f,\"sigma\":%.2f},"
    "\"last\":{\"confirmed\":%s,\"reason\":\"%s\",\"area_pct\":%.2f,"
    "\"bbox\":[%d,%d,%d,%d],\"centroid\":[%d,%d],"
    "\"threshold_noise\":%d,\"threshold_otsu\":%d,\"threshold_used\":%d,\"t_ms\":%lu,"
    "\"t_capture_us\":%lu,\"t_gray_us\":%lu,\"t_diff_us\":%lu,\"t_morph_us\":%lu,\"t_metrics_us\":%lu,"
    "\"t_proc_us\":%lu,\"t_jpeg_us\":%lu,\"photo_bytes\":%u,\"mask_bytes\":%u}}",
    millis() / 1000, digitalRead(PIN_PIR), millis() < PIR_CALENTAMIENTO_MS ? "true" : "false",
    fondoListo ? "true" : "false", ev.n, ev.confirmados, ev.descartados, ruidoMedia, ruidoSigma,
    ev.confirmado ? "true" : "false", ev.motivo, ev.areaPct, ev.x0, ev.y0, ev.x1, ev.y1, ev.cx, ev.cy,
    ev.umbralRuido, ev.umbralOtsu, ev.umbralUsado, ev.tMs, ev.tCapUs, ev.tGrisUs, ev.tDiffUs,
    ev.tMorfoUs, ev.tMetUs, ev.tProcUs, ev.tJpgUs, (unsigned)ev.fotoBytes, (unsigned)ev.mascaraBytes);
  return String(b);
}

void servirJpeg(uint8_t *buf, size_t len) {
  if (!buf || !len) { server.send(404, "text/plain", "no image"); return; }
  server.sendHeader("Cache-Control", "no-store");
  server.send_P(200, "image/jpeg", (PGM_P)buf, len);
}

void iniciarServidor() {
  server.on("/status", []() { server.send(200, "application/json", jsonStatus()); });
  server.on("/photo", []() { servirJpeg(fotoJpg, fotoLen); });
  server.on("/mask", []() { servirJpeg(maskJpg, maskLen); });
  server.on("/histogram", []() {
    String s; s.reserve(2200); s = "{\"bins\":[";
    for (int i = 0; i < 256; i++) { s += histo[i]; if (i < 255) s += ","; }
    s += "]}";
    server.send(200, "application/json", s);
  });
  // Dispara el procesamiento sin PIR (pruebas)
  server.on("/trigger", []() { procesarEvento("manual"); server.send(200, "application/json", jsonStatus()); });
  // Vuelve a tomar el fondo (escena vacía); tarda unos segundos
  server.on("/recalibrate", []() {
    bool ok = calibrarFondo();
    server.send(ok ? 200 : 500, "application/json", jsonStatus());
  });
  server.begin();
}

// ---------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("\nNodo de vision: ESP32-CAM (GC2145) + PIR, solo luminancia");
  pinMode(PIN_PIR, INPUT_PULLDOWN);          // Lee 0 si el PIR no está conectado

  if (!psramFound()) { Serial.println("ERROR: PSRAM no habilitada en el IDE"); while (true) delay(1000); }
  gris    = (uint8_t *)ps_malloc(NPIX);
  fondo   = (uint8_t *)ps_malloc(NPIX);
  mascara = (uint8_t *)ps_malloc(NPIX);
  tmp     = (uint8_t *)ps_malloc(NPIX);
  if (!gris || !fondo || !mascara || !tmp) { Serial.println("ERROR: sin memoria"); while (true) delay(1000); }

  if (!iniciarCamara()) { while (true) delay(1000); }
  sensor_t *s = esp_camera_sensor_get();
  Serial.printf("Sensor PID: 0x%04X (GC2145 = 0x2145)\n", s->id.PID);
  camera_fb_t *fb = capturaFresca();
  if (fb) {
    Serial.printf("Fotograma: %dx%d, %u bytes (esperado %d en YUV422)\n",
                  fb->width, fb->height, (unsigned)fb->len, NPIX * 2);
    if (fb->width != ANCHO || fb->height != ALTO) Serial.println("AVISO: resolucion distinta de 320x240");
    // Diagnóstico del orden de bytes: media de los bytes pares e impares.
    // El byte de crominancia (U/V) suele quedar cerca de 128; el de luminancia varía con la escena.
    uint64_t sp = 0, si = 0;
    for (int i = 0; i < NPIX; i++) { sp += fb->buf[2 * i]; si += fb->buf[2 * i + 1]; }
    Serial.printf("Media bytes pares=%.1f impares=%.1f (OFFSET_Y actual=%d)\n",
                  (double)sp / NPIX, (double)si / NPIX, OFFSET_Y);
    esp_camera_fb_return(fb);
  } else {
    Serial.println("ERROR: no se pudo capturar");
  }

  // Fondo de referencia con la escena vacía (única vez al arrancar)
  if (!calibrarFondo()) Serial.println("AVISO: calibracion fallida, usar /recalibrate");

  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);                       // Menor latencia (luego se revisa por energía)
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Conectando a Wi-Fi");
  uint32_t t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 20000) { delay(500); Serial.print("."); }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\nIP: %s\n", WiFi.localIP().toString().c_str());
    if (MDNS.begin(HOSTNAME)) Serial.printf("mDNS: http://%s.local\n", HOSTNAME);
    iniciarServidor();
  } else {
    Serial.println("\nERROR: sin Wi-Fi");
  }
}

void loop() {
  server.handleClient();
  uint32_t ahora = millis();
  bool pir = digitalRead(PIN_PIR);
  bool calentando = ahora < PIR_CALENTAMIENTO_MS;

  // Flanco de subida del PIR: única condición que dispara una captura
  if (pir && !pirPrev && !calentando && ahora - ultimoEvento >= ENFRIAMIENTO_MS) {
    ultimoEvento = ahora;
    procesarEvento("PIR");
  }
  pirPrev = pir;
  delay(5);
}