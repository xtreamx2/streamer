/**
 * PylonisAmp — Firmware RP2040
 * Wersja: v0.2.4-usb
 * Transport: USB CDC
 * Wyświetlacz: ILI9488 480x320 (TFT_eSPI)
 * Touch: TC2046 rezystancyjny
 * LED: 8x WS2812B
 */

#include <Arduino.h>
#include <ArduinoJson.h>
#include <TFT_eSPI.h>
#include <Adafruit_NeoPixel.h>

// ── Piny ────────────────────────────────────────
#define PIN_WS2812    2
#define PIN_TFT_BL   22
#define TOUCH_CS     13   // z User_Setup.h

// ── Konfiguracja ────────────────────────────────
#define FW_VERSION   "v0.2.4-usb"
#define NUM_LEDS     8
#define HB_TIMEOUT   10000
#define HB_INTERVAL  3000

TFT_eSPI tft = TFT_eSPI();
Adafruit_NeoPixel ring(NUM_LEDS, PIN_WS2812, NEO_GRB + NEO_KHZ800);

// Statyczny bufor RGB565 dla okładki 240x240
static uint16_t img_buffer[240 * 240];

uint32_t last_hb_rx = 0;
uint32_t last_hb_tx = 0;
bool rpi_connected   = false;

// Stan odtwarzania (do wyświetlenia)
char np_title[128]  = "---";
char np_artist[128] = "";
char np_source[32]  = "radio";
int  np_volume      = 0;

// Touch debounce
uint32_t last_touch_ms = 0;
#define TOUCH_DEBOUNCE 500

// ── Setup ────────────────────────────────────────
void setup() {
  Serial.begin(115200); // USB CDC

  tft.init();
  tft.setRotation(1);   // 480x320 poziomo
  tft.fillScreen(TFT_BLACK);

  pinMode(PIN_TFT_BL, OUTPUT);
  digitalWrite(PIN_TFT_BL, HIGH);

  ring.begin();
  ring.setBrightness(40);
  ring.show();

  // Splash
  tft.setTextColor(TFT_CYAN, TFT_BLACK);
  tft.setTextDatum(MC_DATUM);
  tft.drawString("PYLONIS AMP", 240, 140, 4);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.drawString(FW_VERSION, 240, 180, 2);
  tft.setTextColor(TFT_DARKGREY, TFT_BLACK);
  tft.drawString("Czekam na Pi...", 240, 210, 2);

  last_hb_rx = millis();

  // Sygnał gotowości
  Serial.println("{\"evt\":\"ready\",\"fw\":\"" FW_VERSION "\"}");
}

// ── Loop ─────────────────────────────────────────
void loop() {
  // Odczyt JSON z Pi
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.length() > 0) handle_json(line);
  }

  // Heartbeat do Pi
  if (millis() - last_hb_tx > HB_INTERVAL) {
    Serial.println("{\"evt\":\"hb\",\"ok\":1}");
    last_hb_tx = millis();
  }

  // Watchdog połączenia
  connection_watchdog();

  // Touch polling (TC2046 przez TFT_eSPI)
  if (rpi_connected) check_touch();
}

// ── Obsługa komend ───────────────────────────────
void handle_json(String& line) {
  StaticJsonDocument<1024> doc;
  if (deserializeJson(doc, line)) return;

  const char* cmd = doc["cmd"] | "";

  // Heartbeat
  if (strcmp(cmd, "hb") == 0) {
    rpi_connected = true;
    last_hb_rx = millis();
    return;
  }

  // OTA bootloader
  if (strcmp(cmd, "reboot_bootloader") == 0) {
    tft.fillScreen(TFT_BLACK);
    tft.setTextColor(TFT_YELLOW, TFT_BLACK);
    tft.setTextDatum(MC_DATUM);
    tft.drawString("BOOTLOADER MODE", 240, 140, 4);
    tft.drawString("Wgraj plik .uf2", 240, 180, 2);
    delay(500);
    rp2040.rebootToBootloader();
    return;
  }

  // Okładka RGB565
  if (strcmp(cmd, "img_start") == 0) {
    uint32_t sz = doc["size"] | 0;
    if (sz == 0 || sz > sizeof(img_buffer)) return;
    Serial.setTimeout(5000);
    size_t got = Serial.readBytes((char*)img_buffer, sz);
    Serial.setTimeout(1000);
    if (got == sz) {
      tft.pushImage(0, 0, 240, 240, img_buffer);
    } else {
      Serial.println("{\"evt\":\"img_err\",\"msg\":\"timeout\"}");
    }
    return;
  }

  // Stan systemu
  if (strcmp(cmd, "state") == 0) {
    rpi_connected = true;
    last_hb_rx = millis();
    if (doc.containsKey("source")) strncpy(np_source, doc["source"] | "", 31);
    if (doc.containsKey("volume")) np_volume = doc["volume"] | 0;
    if (doc.containsKey("title"))  strncpy(np_title,  doc["title"]  | "---", 127);
    if (doc.containsKey("artist")) strncpy(np_artist, doc["artist"] | "", 127);
    draw_now_playing();
    return;
  }

  // LED Ring
  if (strcmp(cmd, "led") == 0) {
    JsonArray data = doc["data"];
    for (int i = 0; i < min((int)data.size(), NUM_LEDS); i++) {
      uint8_t v = data[i];
      ring.setPixelColor(i, ring.Color(0, v/4, v));
    }
    ring.show();
    return;
  }
}

// ── UI ───────────────────────────────────────────
void draw_now_playing() {
  // Okładka placeholder (prawy obszar 480-240=240px szeroki)
  int tx = 245, ty = 10, tw = 228, th = 300;

  // Źródło
  tft.fillRoundRect(tx, ty, tw, 36, 6, 0x0841);
  tft.drawRoundRect(tx, ty, tw, 36, 6, TFT_DARKGREY);
  tft.setTextColor(TFT_CYAN, 0x0841);
  tft.setTextDatum(ML_DATUM);
  tft.drawString(np_source, tx+10, ty+18, 2);

  // Artysta
  tft.fillRect(tx, ty+46, tw, 20, TFT_BLACK);
  tft.setTextColor(TFT_DARKGREY, TFT_BLACK);
  tft.setTextDatum(ML_DATUM);
  tft.drawString(np_artist, tx+4, ty+56, 2);

  // Tytuł
  tft.fillRect(tx, ty+70, tw, 24, TFT_BLACK);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.setTextDatum(ML_DATUM);
  tft.drawString(np_title, tx+4, ty+82, 2);

  // Pasek głośności
  int bw = map(np_volume, 0, 100, 0, tw-4);
  tft.fillRect(tx+2, ty+104, tw-4, 6, 0x0841);
  tft.fillRoundRect(tx+2, ty+104, bw, 6, 2, TFT_BLUE);

  // Napis VOL
  tft.setTextColor(TFT_DARKGREY, TFT_BLACK);
  char vbuf[8]; snprintf(vbuf, sizeof(vbuf), "VOL %d", np_volume);
  tft.drawString(vbuf, tx+4, ty+118, 1);
}

void draw_disconnected() {
  tft.fillScreen(TFT_BLACK);
  tft.setTextColor(TFT_RED, TFT_BLACK);
  tft.setTextDatum(MC_DATUM);
  tft.drawString("DISCONNECTED", 240, 140, 4);
  tft.setTextColor(TFT_DARKGREY, TFT_BLACK);
  tft.drawString("Sprawdz kabel USB", 240, 175, 2);
  for (int i = 0; i < NUM_LEDS; i++)
    ring.setPixelColor(i, ring.Color(30, 0, 0));
  ring.show();
}

// ── Touch ────────────────────────────────────────
void check_touch() {
  uint16_t tx, ty;
  if (tft.getTouch(&tx, &ty)) {
    uint32_t now = millis();
    if (now - last_touch_ms < TOUCH_DEBOUNCE) return;
    last_touch_ms = now;

    // Wyślij event dotyku do Pi
    StaticJsonDocument<128> doc;
    doc["evt"] = "touch";
    doc["x"]   = tx;
    doc["y"]   = ty;
    serializeJson(doc, Serial);
    Serial.println();

    // Wizualny feedback - mignięcie
    tft.fillCircle(tx, ty, 8, TFT_CYAN);
    delay(80);
    tft.fillCircle(tx, ty, 8, TFT_BLACK);
  }
}

// ── Watchdog ─────────────────────────────────────
void connection_watchdog() {
  if (rpi_connected && (millis() - last_hb_rx > HB_TIMEOUT)) {
    rpi_connected = false;
    draw_disconnected();
  }
}
