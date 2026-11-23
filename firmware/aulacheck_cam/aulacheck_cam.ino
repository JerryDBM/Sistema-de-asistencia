/*
  AulaCheck · Estación ESP32-CAM por WiFi
  ---------------------------------------
  Convierte una ESP32-CAM (AI-Thinker, cámara OV2640) en la estación de
  lectura de AulaCheck. La placa NO lee el QR: solo toma fotos y enciende los
  LED. La interfaz PySide6 del docente pide las fotos por WiFi, lee el QR con
  OpenCV, consulta la API FastAPI y le dice a la placa qué LED encender.

  Direcciones que ofrece la placa (puerto 80):

    /                  página de prueba: vista en vivo y botones de los LED
    /capture           una foto JPEG nueva
    /status            estado en JSON (cámara, IP, señal WiFi)
    /led?state=...     green | red | orange | off | test
    /flash?on=1|0      enciende o apaga el LED blanco de la placa

  Cómo cargarlo (Arduino IDE 2.x):
    1. Boards Manager: instalar "esp32" de Espressif Systems.
    2. Tools > Board > esp32 > "AI Thinker ESP32-CAM".
    3. Tools > Port: el COM de la base ESP32-CAM-MB.
    4. Escribir abajo el nombre y la clave de la red WiFi (WIFI_SSID y
       WIFI_PASSWORD) y pulsar Upload. Si se queda en "Connecting....",
       mantener IO0, pulsar RST y soltar IO0.
    5. Abrir el Serial Monitor a 115200 baudios y pulsar RST: la placa
       muestra su dirección IP. Esa dirección se escribe en la interfaz.

  Importante: la ESP32 solo se conecta a redes WiFi de 2,4 GHz con clave
  normal (WPA2 personal). No sirve una red con página de inicio de sesión
  ni con usuario y contraseña institucional. El computador y la placa deben
  estar en la MISMA red; un punto de acceso del celular funciona bien.
*/

#include <WiFi.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include "esp_camera.h"
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"

// ===================== CONFIGURACIÓN (cambiar aquí) =========================

// Red WiFi de 2,4 GHz. La misma a la que está conectado el computador.
const char *WIFI_SSID = "iPhone";
const char *WIFI_PASSWORD = "28242325";

// Nombre de la placa en la red. Permite usar http://aulacheck-cam.local
// en lugar de la IP (si el computador lo admite).
const char *HOSTNAME = "aulacheck-cam";

// LED del resultado en la protoboard (cada uno con su resistencia de 220 Ω).
// GPIO 13, 14 y 15 están libres porque no se usa la tarjeta microSD.
#define LED_VERDE_PIN 13    // asistencia válida
#define LED_ROJO_PIN 14     // rechazada, fuera de tolerancia o QR inválido
#define LED_NARANJA_PIN 15  // el estudiante ya estaba registrado

// Buzzer opcional. -1 = sin buzzer. Para usarlo, poner 2 y conectarlo a
// través de un transistor (no directo al pin).
#define BUZZER_PIN -1

// Tiempo que queda encendido el LED del resultado.
#define RESULTADO_MS 2000

// Si la imagen se ve al revés, cambiar a 1.
#define H_MIRROR 0
#define VFLIP 0

// ============================================================================

#define FLASH_LED_PIN 4    // LED blanco de la placa
#define STATUS_LED_PIN 33  // LED rojo pequeño de la placa (se enciende en LOW)

// Pines de la cámara OV2640 en la placa AI-Thinker ESP32-CAM.
#define PWDN_GPIO_NUM 32
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM 0
#define SIOD_GPIO_NUM 26
#define SIOC_GPIO_NUM 27
#define Y9_GPIO_NUM 35
#define Y8_GPIO_NUM 34
#define Y7_GPIO_NUM 39
#define Y6_GPIO_NUM 36
#define Y5_GPIO_NUM 21
#define Y4_GPIO_NUM 19
#define Y3_GPIO_NUM 18
#define Y2_GPIO_NUM 5
#define VSYNC_GPIO_NUM 25
#define HREF_GPIO_NUM 23
#define PCLK_GPIO_NUM 22

WebServer server(80);

// Indica si la cámara logró inicializarse y puede entregar fotos.
static bool cameraReady = false;
// Señala si hay varios búferes y se puede pedir directamente la foto más nueva.
static bool grabLatest = false;
// Guarda el código del último error que devolvió el controlador de cámara.
static esp_err_t cameraError = ESP_OK;
// Recuerda si la luz blanca auxiliar está encendida.
static bool flashOn = false;
// Evita repetir avisos en serie mientras la placa pierde y recupera WiFi.
static bool wasConnected = false;
// Momento del último intento de reconectar la red.
static unsigned long lastReconnectAttempt = 0;

// Estado del LED de resultado y del buzzer (sin delay, para no bloquear).
static unsigned long resultadoHasta = 0;
#if BUZZER_PIN >= 0
static int cambiosBuzzer = 0;              // encendidos + apagados pendientes
static unsigned long proximoCambioBuzzer = 0;
static bool buzzerEncendido = false;
static unsigned long duracionPitido = 120;
#endif

// ---------------------------------------------------------------- cámara ---
static bool initCamera() {
  // Completa la configuración de pines y calidad antes de iniciar la cámara.
  camera_config_t config = {};
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  if (psramFound()) {
    // 640x480: suficiente detalle para leer un QR en la pantalla del celular.
    config.frame_size = FRAMESIZE_VGA;
    config.jpeg_quality = 12;  // 0-63, menor = mejor calidad y más bytes
    config.fb_count = 2;
    config.fb_location = CAMERA_FB_IN_PSRAM;
    config.grab_mode = CAMERA_GRAB_LATEST;
    grabLatest = true;
  } else {
    config.frame_size = FRAMESIZE_QVGA;
    config.jpeg_quality = 12;
    config.fb_count = 1;
    config.fb_location = CAMERA_FB_IN_DRAM;
    config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
    grabLatest = false;
  }

  cameraError = esp_camera_init(&config);
  if (cameraError != ESP_OK) {
    return false;
  }

  sensor_t *sensor = esp_camera_sensor_get();
  if (sensor) {
    sensor->set_hmirror(sensor, H_MIRROR);
    sensor->set_vflip(sensor, VFLIP);
  }
  return true;
}

// ------------------------------------------------------------------- LED ---
static void apagarLedsResultado() {
  // Apaga los tres indicadores de resultado para evitar colores simultáneos.
  digitalWrite(LED_VERDE_PIN, LOW);
  digitalWrite(LED_ROJO_PIN, LOW);
  digitalWrite(LED_NARANJA_PIN, LOW);
}

static void programarPitidos(int cantidad, unsigned long duracion) {
  // Programa sonidos cortos sin detener el ciclo principal de la placa.
#if BUZZER_PIN >= 0
  cambiosBuzzer = cantidad * 2;
  duracionPitido = duracion;
  proximoCambioBuzzer = millis();
#else
  (void)cantidad;
  (void)duracion;
#endif
}

// pin = LED a encender (-1 para ninguno); pitidos = cuántos sonidos.
static void mostrarResultado(int pin, int pitidos, unsigned long duracion) {
  // Limpia el resultado anterior y activa la luz y sonido que corresponden.
  apagarLedsResultado();
  if (pin >= 0) {
    digitalWrite(pin, HIGH);
    resultadoHasta = millis() + RESULTADO_MS;
  } else {
    resultadoHasta = 0;
  }
  programarPitidos(pitidos, duracion);
}

static void actualizarSalidas() {
  // Revisa si ya se cumplió el tiempo para apagar una luz o cambiar el buzzer.
  unsigned long ahora = millis();
  if (resultadoHasta != 0 && (long)(ahora - resultadoHasta) >= 0) {
    apagarLedsResultado();
    resultadoHasta = 0;
  }
#if BUZZER_PIN >= 0
  if (cambiosBuzzer > 0 && (long)(ahora - proximoCambioBuzzer) >= 0) {
    buzzerEncendido = !buzzerEncendido;
    digitalWrite(BUZZER_PIN, buzzerEncendido ? HIGH : LOW);
    cambiosBuzzer--;
    proximoCambioBuzzer = ahora + (buzzerEncendido ? duracionPitido : 90);
    if (cambiosBuzzer == 0) {
      buzzerEncendido = false;
      digitalWrite(BUZZER_PIN, LOW);
    }
  }
#endif
}

// ------------------------------------------------------------- servidor ---
static void enviarCabecerasComunes() {
  // Permite que el programa docente lea la respuesta y evita reutilizar fotos viejas.
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.sendHeader("Cache-Control", "no-store");
}

static void handleCapture() {
  // Atiende la solicitud de una foto nueva que hizo el computador del docente.
  enviarCabecerasComunes();
  if (!cameraReady) {
    server.send(503, "application/json", "{\"error\":\"camera_init\"}");
    return;
  }

  camera_fb_t *fb = nullptr;
  if (!grabLatest) {
    // Con un solo búfer, la primera foto puede ser vieja: se descarta.
    fb = esp_camera_fb_get();
    if (fb) esp_camera_fb_return(fb);
  }
  fb = esp_camera_fb_get();
  if (!fb) {
    server.send(503, "application/json", "{\"error\":\"capture_failed\"}");
    return;
  }
  if (fb->format != PIXFORMAT_JPEG || fb->len == 0) {
    esp_camera_fb_return(fb);
    server.send(500, "application/json", "{\"error\":\"not_jpeg\"}");
    return;
  }

  server.setContentLength(fb->len);
  server.send(200, "image/jpeg", "");
  server.sendContent((const char *)fb->buf, fb->len);
  esp_camera_fb_return(fb);
}

static void handleStatus() {
  // Informa si la cámara funciona, cuál es la IP de la placa y qué tan fuerte es el WiFi.
  enviarCabecerasComunes();
  char json[256];
  snprintf(json, sizeof(json),
           "{\"camera\":%s,\"camera_error\":\"0x%x\",\"ip\":\"%s\",\"rssi\":%d,"
           "\"psram\":%s,\"flash\":%s,\"uptime_s\":%lu}",
           cameraReady ? "true" : "false", (unsigned)cameraError,
           WiFi.localIP().toString().c_str(), WiFi.RSSI(),
           psramFound() ? "true" : "false", flashOn ? "true" : "false",
           millis() / 1000UL);
  server.send(200, "application/json", json);
}

static void handleLed() {
  // Lee el color solicitado por URL y activa la luz o patrón de prueba correspondiente.
  enviarCabecerasComunes();
  String state = server.arg("state");
  state.toLowerCase();

  if (state == "green") {
    mostrarResultado(LED_VERDE_PIN, 1, 150);   // un pitido corto
  } else if (state == "red") {
    mostrarResultado(LED_ROJO_PIN, 1, 600);    // un pitido largo
  } else if (state == "orange") {
    mostrarResultado(LED_NARANJA_PIN, 2, 120); // dos pitidos cortos
  } else if (state == "off") {
    mostrarResultado(-1, 0, 0);
  } else if (state == "test") {
    // Enciende los tres LED uno por uno para revisar el cableado.
    int pines[3] = {LED_VERDE_PIN, LED_ROJO_PIN, LED_NARANJA_PIN};
    for (int i = 0; i < 3; i++) {
      apagarLedsResultado();
      digitalWrite(pines[i], HIGH);
      delay(450);
    }
    mostrarResultado(-1, 1, 100);
  } else {
    server.send(400, "application/json",
                "{\"error\":\"state debe ser green, red, orange, off o test\"}");
    return;
  }
  server.send(200, "application/json", "{\"ok\":true}");
}

static void handleFlash() {
  // Cambia el estado de la luz blanca integrada según el parámetro recibido.
  enviarCabecerasComunes();
  flashOn = server.arg("on") == "1";
  digitalWrite(FLASH_LED_PIN, flashOn ? HIGH : LOW);
  server.send(200, "application/json", flashOn ? "{\"flash\":true}" : "{\"flash\":false}");
}

static const char PAGINA[] PROGMEM = R"HTML(<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AulaCheck · ESP32-CAM</title>
<style>
body{font-family:Segoe UI,Arial,sans-serif;background:#F4F7FB;color:#172033;margin:20px}
img{width:100%;max-width:640px;border-radius:10px;background:#000;display:block}
button{border:none;border-radius:8px;padding:10px 14px;margin:6px 6px 0 0;font-weight:700;cursor:pointer}
.g{background:#DDF7E8;color:#18794E}.r{background:#FCE8E7;color:#B42318}
.o{background:#FFF1DB;color:#B54708}.n{background:#EAF0FF;color:#315BD0}
#s{color:#6B778C;font-size:13px;margin-top:10px}
</style></head><body>
<h2>AulaCheck · Estación ESP32-CAM</h2>
<img id="v" alt="Vista de la cámara">
<div>
<button class="g" onclick="led('green')">LED verde</button>
<button class="r" onclick="led('red')">LED rojo</button>
<button class="o" onclick="led('orange')">LED naranja</button>
<button class="n" onclick="led('test')">Probar los 3</button>
<button class="n" onclick="flash()">Flash</button>
</div>
<div id="s">Cargando…</div>
<script>
let f=false;
function led(s){fetch('/led?state='+s)}
function flash(){f=!f;fetch('/flash?on='+(f?1:0))}
const v=document.getElementById('v');
function next(){v.src='/capture?t='+Date.now()}
v.onload=()=>setTimeout(next,150);v.onerror=()=>setTimeout(next,1000);next();
setInterval(()=>fetch('/status').then(r=>r.json()).then(j=>{
document.getElementById('s').textContent='IP '+j.ip+' · señal '+j.rssi+' dBm · cámara '+(j.camera?'lista':'con error '+j.camera_error)
}).catch(()=>{}),2000);
</script></body></html>)HTML";

static void handleRoot() {
  // Muestra una página sencilla para probar la foto, la luz y el estado de la placa.
  server.send(200, "text/html; charset=utf-8", PAGINA);
}

static void handleNotFound() {
  // Responde con un mensaje cuando alguien solicita una ruta que no existe.
  enviarCabecerasComunes();
  server.send(404, "application/json", "{\"error\":\"ruta no encontrada\"}");
}

// ----------------------------------------------------------------- WiFi ---
static void anunciarConexion() {
  // Muestra en el monitor serial la IP y la dirección local de la cámara.
  Serial.println();
  Serial.println("WiFi conectado.");
  Serial.print("  Dirección para la interfaz: http://");
  Serial.println(WiFi.localIP());
  Serial.print("  También puede probar:       http://");
  Serial.print(HOSTNAME);
  Serial.println(".local");
  Serial.print("  Señal: ");
  Serial.print(WiFi.RSSI());
  Serial.println(" dBm");
}

static void conectarWifi() {
  // Intenta conectar la placa a la red configurada y registra el resultado.
  WiFi.mode(WIFI_STA);
  WiFi.setHostname(HOSTNAME);
  WiFi.setSleep(false);  // respuestas más rápidas
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  Serial.print("Conectando a la red \"");
  Serial.print(WIFI_SSID);
  Serial.print("\"");
  unsigned long inicio = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - inicio < 20000) {
    digitalWrite(STATUS_LED_PIN, !digitalRead(STATUS_LED_PIN));  // parpadeo
    Serial.print(".");
    delay(500);
  }
  digitalWrite(STATUS_LED_PIN, HIGH);  // apagado (lógica invertida)

  if (WiFi.status() == WL_CONNECTED) {
    wasConnected = true;
    anunciarConexion();
  } else {
    Serial.println();
    Serial.println("No se pudo conectar al WiFi. Revise WIFI_SSID y WIFI_PASSWORD,");
    Serial.println("que la red sea de 2,4 GHz y que no pida inicio de sesión.");
    Serial.println("La placa seguirá intentando cada 5 segundos.");
  }
}

// ---------------------------------------------------------------- setup ---
void setup() {
  // Configura pines, cámara, WiFi y rutas web una vez al encender la placa.
  // Evita reinicios por caídas de voltaje al encender la cámara y el WiFi.
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);

  Serial.begin(115200);
  Serial.println();
  Serial.println("AulaCheck · Estación ESP32-CAM");

  pinMode(LED_VERDE_PIN, OUTPUT);
  pinMode(LED_ROJO_PIN, OUTPUT);
  pinMode(LED_NARANJA_PIN, OUTPUT);
  apagarLedsResultado();
#if BUZZER_PIN >= 0
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);
#endif
  pinMode(FLASH_LED_PIN, OUTPUT);
  digitalWrite(FLASH_LED_PIN, LOW);
  pinMode(STATUS_LED_PIN, OUTPUT);
  digitalWrite(STATUS_LED_PIN, HIGH);

  cameraReady = initCamera();
  digitalWrite(FLASH_LED_PIN, LOW);
  if (cameraReady) {
    Serial.println(psramFound() ? "Cámara lista (640x480, PSRAM)." : "Cámara lista (320x240, sin PSRAM).");
  } else {
    Serial.printf("ERROR: no se pudo iniciar la cámara (0x%x). Revise el cable plano y pulse RST.\n",
                  (unsigned)cameraError);
  }

  conectarWifi();

  if (MDNS.begin(HOSTNAME)) {
    MDNS.addService("http", "tcp", 80);
  }

  server.on("/", HTTP_GET, handleRoot);
  server.on("/capture", HTTP_GET, handleCapture);
  server.on("/status", HTTP_GET, handleStatus);
  server.on("/led", HTTP_GET, handleLed);
  server.on("/flash", HTTP_GET, handleFlash);
  server.onNotFound(handleNotFound);
  server.begin();

  // Saludo: los tres LED se encienden un momento al arrancar.
  digitalWrite(LED_VERDE_PIN, HIGH);
  digitalWrite(LED_ROJO_PIN, HIGH);
  digitalWrite(LED_NARANJA_PIN, HIGH);
  delay(400);
  apagarLedsResultado();
}

// ----------------------------------------------------------------- loop ---
void loop() {
  // Atiende solicitudes web y actualiza luces, sonidos y reconexión sin detenerse.
  server.handleClient();
  actualizarSalidas();

  bool conectado = WiFi.status() == WL_CONNECTED;
  if (conectado && !wasConnected) {
    wasConnected = true;
    anunciarConexion();
  } else if (!conectado) {
    if (wasConnected) {
      wasConnected = false;
      Serial.println("Se perdió el WiFi. Reintentando…");
    }
    if (millis() - lastReconnectAttempt > 5000) {
      lastReconnectAttempt = millis();
      WiFi.reconnect();
    }
  }
  delay(1);
}
