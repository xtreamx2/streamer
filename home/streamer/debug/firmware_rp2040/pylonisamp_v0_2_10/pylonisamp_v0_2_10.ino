/**
 * PylonisAmp — Firmware RP2040
 * Wersja: v0.2.20 (RAW RGB565 + UTF-8)
 */

#include <Arduino.h>
#include <ArduinoJson.h>
#include <TFT_eSPI.h>
#include <Adafruit_NeoPixel.h>
#define QOI_IMPLEMENTATION
#include "qoi.h"

#define FW_VER "v0.2.20"
#define BAUD_RATE 1000000
#define NUM_LEDS 8
#define PIN_WS2812 2
#define PIN_TFT_BL 22

#define PYLONIS_BLUE  0x249E
#define PYLONIS_DARK  0x0841

TFT_eSPI tft = TFT_eSPI();
Adafruit_NeoPixel ring(NUM_LEDS, PIN_WS2812, NEO_GRB + NEO_KHZ800);
TFT_eSprite bottomBar = TFT_eSprite(&tft);
TFT_eSprite spectrumSprite = TFT_eSprite(&tft);

// ZMIENNE DLA OBRAZU (Nowy protokół RAW RGB565)
uint32_t img_total_size = 0; 
uint32_t img_received_size = 0;
bool receiving_img = false;
uint32_t last_img_byte_ms = 0;

// Bufor na jedną linię (240 pikseli * 2 bajty = 480 bajtów)
uint16_t line_buffer[240];

uint32_t last_hb_rx = 0, last_hb_tx = 0, last_touch_ms = 0;
uint32_t radio_start_ms = 0;
bool rpi_connected = false, was_disconnected = true;

char np_station[64] = "RADIO", np_title[128] = "Czekam...", np_artist[128] = "", np_time[16] = "00:00";
int np_volume = 0;
String display_mode = "spectrum";

uint32_t led_timer = 0;
int fade_val = 0, current_led = 0;
bool fading_in = true;

void update_leds();
void handle_json(String line);
void draw_meters(JsonArray data);
void draw_full_ui();
void draw_fast_bottom();
void check_touch();

void setup() {
  Serial.begin(BAUD_RATE);
  Serial.setTimeout(50);

  ring.begin();
  ring.setBrightness(25);
  ring.show();

  pinMode(PIN_TFT_BL, OUTPUT);
  digitalWrite(PIN_TFT_BL, HIGH);

  tft.init();
  tft.setRotation(1);
  tft.fillScreen(TFT_BLACK);
  
  // Konfiguracja dla UTF-8 i RGB565 (Little-Endian)
  tft.decodeUTF8(true);
  tft.setSwapBytes(false);

  uint16_t calData[5] = { 280, 3500, 350, 3300, 6 };
  tft.setTouch(calData);

  bottomBar.createSprite(480, 60);
  spectrumSprite.createSprite(235, 100);

  tft.setTextColor(PYLONIS_BLUE, TFT_BLACK);
  tft.setTextDatum(MC_DATUM);
  tft.drawString("Pylonis Amp", 240, 130, 4);

  Serial.print("{\"evt\":\"ready\",\"fw\":\"");
  Serial.print(FW_VER);
  Serial.println("\"}");
}

void loop() {
  check_touch();

  while (Serial.available() > 0) {
    if (receiving_img) {
      tft.setAddrWindow(0, 40, 240, 240);
      for (int y = 0; y < 240; y++) {
        uint32_t start_row = millis();
        while (Serial.available() < 480 && millis() - start_row < 100) {
           check_touch(); // Reaguj na dotyk podczas odbierania linii
        }
        size_t read_now = Serial.readBytes((char*)line_buffer, 480);
        if (read_now == 480) {
          tft.pushColors(line_buffer, 240);
        } else {
          receiving_img = false;
          break;
        }
        last_img_byte_ms = millis();
      }
      receiving_img = false; 
      Serial.println("{\"evt\":\"img_ok\"}");
    } else {
      // Reszta Twojej logiki JSON (bez zmian)
      static String inputBuffer = "";
      char c = Serial.read();
      if (c == '\n') {
        if (inputBuffer.startsWith("{")) handle_json(inputBuffer);
        inputBuffer = "";
      } else if (c != '\r') {
        inputBuffer += c;
      }
      if (inputBuffer.length() > 1024) inputBuffer = "";
    }
  }

  if (receiving_img && (millis() - last_img_byte_ms > 1500)) {
    receiving_img = false;
  }

  if (millis() - last_hb_tx > 3000) {
    Serial.println("{\"evt\":\"hb\"}");
    last_hb_tx = millis();
  }

  update_leds();
  check_touch();
}

void handle_json(String line) {
  // FUTURE v0.3 - ENCODER & MENU
  /* 
  if (strcmp(cmd, "menu_up") == 0) { ... }
  */
  JsonDocument doc;
  if (deserializeJson(doc, line)) return;
  const char* cmd = doc["cmd"] | "";

  if (strcmp(cmd, "img_qoi") == 0) {
    img_total_size = doc["size"];
    receiving_img = true;
    
    uint8_t* qoi_buffer = (uint8_t*)malloc(img_total_size);
    if (qoi_buffer) {
        // Czytaj dane binarne bezpośrednio
        size_t read_bytes = Serial.readBytes(qoi_buffer, img_total_size);
        if (read_bytes == img_total_size) {
            qoi_desc desc;
            // Dekoduj do formatu RGBA (4 bajty na piksel)
            uint8_t* rgba_data = (uint8_t*)qoi_decode(qoi_buffer, img_total_size, &desc, 4);
            if (rgba_data) {
                // RPi przesyła QOI z kolorem, tft.pushImage potrzebuje formatu RGB565 (2 bajty)
                // Używamy bufora line_buffer do konwersji w locie
                for (int y = 0; y < 240; y++) {
                    for (int x = 0; x < 240; x++) {
                        int idx = (y * 240 + x) * 4;
                        uint8_t r = rgba_data[idx];
                        uint8_t g = rgba_data[idx+1];
                        uint8_t b = rgba_data[idx+2];
                        line_buffer[x] = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3);
                    }
                    tft.pushImage(0, 40 + y, 240, 1, line_buffer);
                }
                free(rgba_data);
            }
        }
        free(qoi_buffer);
    }
    receiving_img = false;
    Serial.println("{\"evt\":\"img_ok\"}");
    return;
  }

  if (strcmp(cmd, "img_end") == 0) {
    receiving_img = false;
    Serial.println("{\"evt\":\"img_ok\"}");
    return;
  }

  if (strcmp(cmd, "state") == 0 || strcmp(cmd, "tick") == 0) {
    rpi_connected = true; last_hb_rx = millis();
    if (doc.containsKey("title")) strncpy(np_title, doc["title"], 127);
    if (doc.containsKey("artist")) strncpy(np_artist, doc["artist"], 127);
    if (doc.containsKey("station")) strncpy(np_station, doc["station"], 63);
    if (doc.containsKey("volume")) np_volume = doc["volume"];
    if (doc.containsKey("time")) strncpy(np_time, doc["time"], 15);
    if (doc.containsKey("mode")) display_mode = doc["mode"].as<String>();

    if (was_disconnected) { tft.fillScreen(TFT_BLACK); was_disconnected = false; }
    if (strcmp(np_station, "RADIO") == 0 && radio_start_ms == 0) radio_start_ms = millis();
    
    draw_full_ui();
    draw_fast_bottom();
  }

  if (strcmp(cmd, "meters") == 0) draw_meters(doc["data"]);
}

void update_leds() {
  uint32_t now = millis();
  static uint32_t last_led_move = 0;
  
  // Przesunięcie diody co 500ms
  if (now - last_led_move > 500) {
    last_led_move = now;
    current_led = (current_led + 1) % NUM_LEDS;
  }

  uint32_t cycle_ms = now % 2000;
  int v = 0;
  if (cycle_ms < 1000) v = map(cycle_ms, 0, 1000, 10, 60);
  else v = map(cycle_ms, 1000, 2000, 60, 10);

  ring.clear();
  for(int i=0; i<NUM_LEDS; i++) {
    int bri = (i == current_led) ? v : v/5;
    ring.setPixelColor(i, ring.Color(0, bri/2, bri));
  }
  ring.show();
}

void draw_meters(JsonArray data) {
  if (display_mode == "none") {
      spectrumSprite.fillSprite(TFT_BLACK);
      spectrumSprite.pushSprite(245, 180);
      return;
  }
  spectrumSprite.fillSprite(TFT_BLACK);
  if (display_mode == "uv") {
    int l = map(constrain(data[0].as<int>(), -60, 0), -60, 0, 0, 90);
    int r = map(constrain(data[1].as<int>(), -60, 0), -60, 0, 0, 90);
    spectrumSprite.fillRect(20, 90-l, 80, l, PYLONIS_BLUE);
    spectrumSprite.fillRect(135, 90-r, 80, r, PYLONIS_BLUE);
  } else {
    for (int i = 0; i < min((int)data.size(), 32); i++) {
      int h = map(constrain(data[i].as<int>(), -60, 0), -60, 0, 0, 90);
      spectrumSprite.fillRect(i * 7, 90 - h, 5, h, PYLONIS_BLUE);
    }
  }
  spectrumSprite.pushSprite(245, 180);
}

void draw_full_ui() {
  tft.fillRect(0, 0, 480, 38, PYLONIS_DARK);
  tft.drawFastHLine(0, 38, 480, TFT_DARKGREY);
  tft.setTextColor(PYLONIS_BLUE, PYLONIS_DARK);
  tft.setTextDatum(MC_DATUM);
  tft.setCursor(240 - (tft.textWidth(np_station, 2) / 2), 11);
  tft.print(np_station);

  tft.fillRect(245, 40, 235, 120, TFT_BLACK);
  
  tft.setTextColor(TFT_DARKGREY, TFT_BLACK); 
  tft.setCursor(248, 48); tft.print("ARTYSTA");
  tft.setTextColor(TFT_WHITE, TFT_BLACK); 
  tft.setCursor(248, 62); tft.print(np_artist);

  tft.setTextColor(TFT_DARKGREY, TFT_BLACK); 
  tft.setCursor(248, 105); tft.print("TYTUŁ");
  tft.setTextColor(TFT_YELLOW, TFT_BLACK); 
  tft.setCursor(248, 124); tft.print(np_title);
}

void draw_fast_bottom() {
  bottomBar.fillSprite(TFT_BLACK);
  char vbuf[12]; snprintf(vbuf, sizeof(vbuf), "VOL %d%%", np_volume);
  
  char tbuf[16];
  if (strcmp(np_station, "RADIO") == 0) {
    uint32_t sec = (millis() - radio_start_ms) / 1000;
    snprintf(tbuf, sizeof(tbuf), "%02d:%02d", (sec / 60) % 99, sec % 60);
  } else {
    strncpy(tbuf, np_time, 15);
  }

  bottomBar.setTextColor(TFT_WHITE, TFT_BLACK);
  bottomBar.setTextDatum(ML_DATUM); bottomBar.drawString(tbuf, 12, 18, 4);
  bottomBar.setTextDatum(MR_DATUM); bottomBar.drawString(vbuf, 468, 18, 4);
  bottomBar.pushSprite(0, 282);
}

void check_touch() {
  uint16_t tx, ty;
  if (tft.getTouch(&tx, &ty)) {
    if (millis() - last_touch_ms > 400) {
      last_touch_ms = millis();
      
      // Cykliczna zmiana trybu
      if (display_mode == "spectrum") display_mode = "uv";
      else if (display_mode == "uv") display_mode = "none";
      else display_mode = "spectrum";
      
      Serial.printf("{\"evt\":\"touch\",\"x\":%d,\"y\":%d,\"mode\":\"%s\"}\n", tx, ty, display_mode.c_str());
      
      // Odśwież UI
      draw_full_ui();
      draw_fast_bottom();
    }
  }
}
