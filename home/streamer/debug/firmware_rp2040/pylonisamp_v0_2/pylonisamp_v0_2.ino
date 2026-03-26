/**
 * PylonisAmp — Firmware RP2040
 * Wersja: v0.2.0
 *
 * UART komunikacja z RPi + ILI9488 LCD + WS2812 Ring
 *
 * Wymagane biblioteki:
 *   - ArduinoJson    by Benoit Blanchon  (6.x)
 *   - TFT_eSPI       by Bodmer
 *   - Adafruit NeoPixel
 *
 * WAŻNE: Skopiuj User_Setup.h do Arduino/libraries/TFT_eSPI/
 *
 * Piny:
 *   GPIO0  = UART TX → RPi
 *   GPIO1  = UART RX ← RPi
 *   GPIO2  = WS2812 Ring data
 *   GPIO13 = TOUCH_CS
 *   GPIO16 = TFT_MISO
 *   GPIO17 = TFT_CS
 *   GPIO18 = TFT_SCLK
 *   GPIO19 = TFT_MOSI
 *   GPIO20 = TFT_DC
 *   GPIO21 = TFT_RST
 *   GPIO22 = TFT_BL (backlight)
 *   GPIO25 = LED wbudowana
 */

#include <Arduino.h>
#include <ArduinoJson.h>
#include <TFT_eSPI.h>
#include <Adafruit_NeoPixel.h>

// ── Piny ──────────────────────────────────────────────────────────
#define PIN_UART_TX     0
#define PIN_UART_RX     1
#define PIN_WS2812      2
#define PIN_TFT_BL      22

// ── Konfiguracja ──────────────────────────────────────────────────
#define FW_VERSION      "0.2.0"
#define UART_BAUD       115200
#define HB_INTERVAL_MS  500
#define HB_TIMEOUT_MS   1500

#define RING_LEDS       8
#define RING_BRIGHTNESS 40    // 0-255, na start cicho

// ── Kolory LCD (RGB565) ───────────────────────────────────────────
#define C_BG        0x0810    // #0d0f14 tło
#define C_BG2       0x1129    // #111520 panel
#define C_BLUE      0x1699    // #2d8cf0
#define C_ORANGE    0xF806    // #f0820d
#define C_TEXT      0xF51E    // #e8eaf0
#define C_TEXT2     0x845D    // #8899bb
#define C_TEXT3     0x4A69    // #4a5270
#define C_GREEN     0x2264    // #22c55e
#define C_RED       0xEF24    // #ef4444
#define C_YELLOW    0xEB00    // #eab308
#define C_BORDER    0x2525    // #252c42

// ── Obiekty ───────────────────────────────────────────────────────
TFT_eSPI          tft;
Adafruit_NeoPixel ring(RING_LEDS, PIN_WS2812, NEO_GRB + NEO_KHZ800);

// ── Stan systemu ──────────────────────────────────────────────────
struct State {
  char   source[16]  = "radio";
  char   title[128]  = "";
  char   artist[64]  = "";
  int    volume      = 0;
  char   state[16]   = "stopped";
  bool   muted       = false;
  bool   rpi_conn    = false;
  bool   sleeping    = false;
  char   event[32]   = "";      // ostatnie zdarzenie do wyświetlenia
  uint8_t event_level = 0;      // 0=info 1=warn 2=error
};
State sys;

// ── UART ──────────────────────────────────────────────────────────
bool     rpi_connected   = false;
uint32_t last_hb_rx      = 0;
uint32_t last_hb_tx      = 0;
uint32_t cnt_hb_sent     = 0;
uint32_t cnt_hb_recv     = 0;
String   rx_buf          = "";

// ── Ring LED animacja ─────────────────────────────────────────────
enum RingMode {
  RING_OFF,
  RING_PULSE,       // wolne pulsowanie — playing
  RING_CHASE,       // chase — buffering
  RING_VOLUME,      // fill N/8 — zmiana głośności
  RING_ERROR,       // szybkie miganie — błąd
  RING_SLEEP,       // 1 dioda dim — sleep
  RING_WAKE,        // rozświetlenie od 0 do pełna
  RING_MUTE,        // wszystkie dim czerwone
};
RingMode  ring_mode        = RING_OFF;
uint32_t  ring_last_update = 0;
float     ring_pulse_val   = 0.0f;
float     ring_pulse_dir   = 1.0f;
uint8_t   ring_chase_pos   = 0;
uint32_t  ring_vol_until   = 0;   // pokaż volume przez 2s
RingMode  ring_prev_mode   = RING_OFF;

// ── LCD odświeżanie ───────────────────────────────────────────────
uint32_t last_lcd_update   = 0;
char     last_title[128]   = "";
char     last_artist[64]   = "";
int      last_volume       = -1;
bool     last_muted        = false;
bool     last_conn         = false;
char     last_state[16]    = "";
char     last_event[32]    = "";


// ════════════════════════════════════════════════════════════════════
void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  pinMode(PIN_TFT_BL, OUTPUT);
  digitalWrite(PIN_TFT_BL, LOW);   // backlight off na start
  blink(2, 150);

  // USB Serial (debug)
  Serial.begin(115200);
  delay(300);
  Serial.println("[PylonisAmp v" FW_VERSION "] Start");

  // UART z RPi
  Serial1.setTX(PIN_UART_TX);
  Serial1.setRX(PIN_UART_RX);
  Serial1.begin(UART_BAUD);

  // Ring LED
  ring.begin();
  ring.setBrightness(RING_BRIGHTNESS);
  ring.clear();
  ring.show();

  // LCD init
  tft.init();
  tft.setRotation(1);          // poziomo 480×320
  tft.fillScreen(C_BG);
  digitalWrite(PIN_TFT_BL, HIGH);   // backlight on

  // Splash screen
  draw_splash();
  delay(1500);

  // Główny ekran
  draw_base();

  // Powiadom RPi
  delay(100);
  tx_ready();

  ring_set(RING_PULSE);
}


// ════════════════════════════════════════════════════════════════════
void loop() {
  uint32_t now = millis();

  // UART
  rx_process();

  if (now - last_hb_tx >= HB_INTERVAL_MS) {
    tx_hb();
    last_hb_tx = now;
  }
  connection_watchdog();

  // Ring animacja
  ring_update();

  // LCD odświeżanie (co 200ms jeśli coś się zmieniło)
  if (now - last_lcd_update >= 200) {
    lcd_update();
    last_lcd_update = now;
  }
}


// ════════════════════════════════════════════════════════════════════
// LCD — rysowanie
// ════════════════════════════════════════════════════════════════════

void draw_splash() {
  tft.fillScreen(C_BG);
  tft.setTextDatum(MC_DATUM);
  tft.setTextColor(C_BLUE, C_BG);
  tft.drawString("PylonisAmp", 240, 140, 4);
  tft.setTextColor(C_TEXT3, C_BG);
  tft.drawString("v" FW_VERSION, 240, 175, 2);
}

void draw_base() {
  tft.fillScreen(C_BG);

  // ── Topbar (0,0,480,44) ──
  tft.fillRect(0, 0, 480, 44, C_BG2);
  tft.drawFastHLine(0, 44, 480, C_BORDER);

  // ── Panel połączenia — prawy górny ──
  draw_conn_indicator();

  // ── Okładka placeholder (lewy panel 0,44,240,240) ──
  tft.fillRect(0, 44, 240, 240, C_BG2);
  tft.drawRect(0, 44, 240, 240, C_BORDER);
  // Ikona noty muzycznej w środku
  tft.setTextDatum(MC_DATUM);
  tft.setTextColor(C_TEXT3, C_BG2);
  tft.drawString("~", 120, 164, 4);

  // ── Panel info (prawy 240,44,240,240) ──
  tft.fillRect(240, 44, 240, 240, C_BG);
  tft.drawRect(240, 44, 240, 240, C_BORDER);

  // ── Pasek głośności (0,284,480,36) ──
  tft.fillRect(0, 284, 480, 36, C_BG2);
  tft.drawFastHLine(0, 284, 480, C_BORDER);

  // Etykieta VOL
  tft.setTextDatum(ML_DATUM);
  tft.setTextColor(C_TEXT3, C_BG2);
  tft.drawString("VOL", 8, 302, 2);

  // Etykieta źródła
  draw_source_badge();
}

void draw_conn_indicator() {
  uint16_t col = rpi_connected ? C_GREEN : C_RED;
  const char* txt = rpi_connected ? "RPi OK" : "RPi --";
  tft.fillRect(340, 8, 130, 28, C_BG2);
  tft.setTextDatum(MR_DATUM);
  tft.setTextColor(col, C_BG2);
  tft.drawString(txt, 470, 22, 2);
  // Kropka statusu
  tft.fillCircle(350, 22, 5, col);
}

void draw_source_badge() {
  tft.fillRect(8, 8, 100, 28, C_BG2);
  tft.setTextDatum(ML_DATUM);
  tft.setTextColor(C_BLUE, C_BG2);
  // Nazwa źródła uppercase
  char src_up[16];
  strncpy(src_up, sys.source, 15);
  for (int i = 0; src_up[i]; i++) src_up[i] = toupper(src_up[i]);
  tft.drawString(src_up, 12, 22, 2);
}

void lcd_update() {
  bool changed = false;

  // Połączenie
  if (rpi_connected != last_conn) {
    last_conn = rpi_connected;
    draw_conn_indicator();
    changed = true;

    if (!rpi_connected) {
      // Duży napis na środku
      tft.fillRect(240, 44, 240, 240, C_BG);
      tft.setTextDatum(MC_DATUM);
      tft.setTextColor(C_RED, C_BG);
      tft.drawString("RPi offline", 360, 144, 2);
    }
  }

  if (sys.sleeping) return;   // w sleep nie aktualizuj reszty

  // Tytuł
  if (strcmp(sys.title, last_title) != 0) {
    strncpy(last_title, sys.title, 127);
    draw_title();
    changed = true;
  }

  // Artysta
  if (strcmp(sys.artist, last_artist) != 0) {
    strncpy(last_artist, sys.artist, 63);
    draw_artist();
    changed = true;
  }

  // Głośność
  if (sys.volume != last_volume || sys.muted != last_muted) {
    last_volume = sys.volume;
    last_muted  = sys.muted;
    draw_volume();
    changed = true;
  }

  // Stan (playing/stopped/buffering)
  if (strcmp(sys.state, last_state) != 0) {
    strncpy(last_state, sys.state, 15);
    draw_state_indicator();
    changed = true;
  }

  // Event banner
  if (strcmp(sys.event, last_event) != 0) {
    strncpy(last_event, sys.event, 31);
    draw_event_banner();
    changed = true;
  }
}

void draw_title() {
  // Obszar tytułu: 244,60,232,40
  tft.fillRect(244, 60, 232, 40, C_BG);
  tft.setTextDatum(TL_DATUM);
  tft.setTextColor(C_TEXT, C_BG);

  // Skróć jeśli za długi
  String t = String(sys.title);
  if (t.length() > 22) t = t.substring(0, 20) + "..";
  tft.drawString(t.c_str(), 248, 64, 2);
}

void draw_artist() {
  // Obszar artysty: 244,104,232,28
  tft.fillRect(244, 104, 232, 28, C_BG);
  tft.setTextDatum(TL_DATUM);
  tft.setTextColor(C_TEXT2, C_BG);

  String a = String(sys.artist);
  if (a.length() > 22) a = a.substring(0, 20) + "..";
  tft.drawString(a.c_str(), 248, 108, 2);
}

void draw_volume() {
  // Pasek głośności: 40,290,400,14
  int bar_w = sys.muted ? 0 : map(sys.volume, 0, 100, 0, 400);
  uint16_t col = sys.muted ? C_RED : C_BLUE;

  tft.fillRect(40, 290, 400, 14, C_BORDER);
  if (bar_w > 0) tft.fillRect(40, 290, bar_w, 14, col);

  // Wartość liczbowa
  tft.fillRect(448, 286, 30, 22, C_BG2);
  tft.setTextDatum(MR_DATUM);
  tft.setTextColor(sys.muted ? C_RED : C_TEXT, C_BG2);
  if (sys.muted) {
    tft.drawString("MUTE", 478, 297, 2);
  } else {
    tft.drawString(String(sys.volume).c_str(), 478, 297, 2);
  }
}

void draw_state_indicator() {
  // Kółko stanu: lewy panel, prawy dolny róg
  uint16_t col = C_TEXT3;
  if (strcmp(sys.state, "playing")   == 0) col = C_GREEN;
  if (strcmp(sys.state, "buffering") == 0) col = C_YELLOW;
  if (strcmp(sys.state, "stopped")   == 0) col = C_RED;

  tft.fillCircle(220, 270, 8, col);
}

void draw_event_banner() {
  // Banner zdarzeń: 0,256,240,28
  tft.fillRect(0, 256, 240, 28, C_BG2);
  if (strlen(sys.event) == 0) return;

  uint16_t col = C_TEXT2;
  if (sys.event_level == 1) col = C_YELLOW;
  if (sys.event_level == 2) col = C_RED;

  tft.setTextDatum(ML_DATUM);
  tft.setTextColor(col, C_BG2);
  tft.drawString(sys.event, 8, 270, 1);
}

void draw_sleep_screen() {
  tft.fillScreen(C_BG);
  tft.setTextDatum(MC_DATUM);
  tft.setTextColor(C_TEXT3, C_BG);
  tft.drawString("sleep", 240, 160, 2);
  digitalWrite(PIN_TFT_BL, LOW);
}

void draw_wake_screen() {
  digitalWrite(PIN_TFT_BL, HIGH);
  draw_base();
  // Wymusz pełne odświeżenie
  last_title[0]  = '\0';
  last_artist[0] = '\0';
  last_volume    = -1;
  last_state[0]  = '\0';
  last_event[0]  = '\0';
  last_conn      = !rpi_connected;
}


// ════════════════════════════════════════════════════════════════════
// RING LED
// ════════════════════════════════════════════════════════════════════

void ring_set(RingMode mode) {
  ring_prev_mode = ring_mode;
  ring_mode      = mode;
  ring_chase_pos = 0;
  ring_pulse_val = 0.0f;
}

void ring_update() {
  uint32_t now = millis();
  if (now - ring_last_update < 30) return;   // ~33fps
  ring_last_update = now;

  // Wróć do poprzedniego trybu po pokazaniu volume
  if (ring_mode == RING_VOLUME && now > ring_vol_until) {
    ring_set(ring_prev_mode);
  }

  switch (ring_mode) {

    case RING_OFF:
      ring.clear();
      ring.show();
      break;

    case RING_PULSE: {
      // Wolne pulsowanie niebieskie
      ring_pulse_val += ring_pulse_dir * 0.02f;
      if (ring_pulse_val >= 1.0f) { ring_pulse_val = 1.0f; ring_pulse_dir = -1.0f; }
      if (ring_pulse_val <= 0.1f) { ring_pulse_val = 0.1f; ring_pulse_dir =  1.0f; }
      uint8_t b = (uint8_t)(ring_pulse_val * 180);
      for (int i = 0; i < RING_LEDS; i++)
        ring.setPixelColor(i, ring.Color(0, 60, b));
      ring.show();
      break;
    }

    case RING_CHASE: {
      // Chase żółty — buffering
      ring.clear();
      ring.setPixelColor(ring_chase_pos % RING_LEDS, ring.Color(180, 160, 0));
      ring.setPixelColor((ring_chase_pos + 1) % RING_LEDS, ring.Color(60, 50, 0));
      ring.show();
      if (++ring_chase_pos >= RING_LEDS) ring_chase_pos = 0;
      break;
    }

    case RING_VOLUME: {
      // Fill N/8 proporcjonalnie do głośności — biały
      ring.clear();
      int lit = map(sys.volume, 0, 100, 0, RING_LEDS);
      for (int i = 0; i < lit; i++)
        ring.setPixelColor(i, ring.Color(200, 200, 200));
      ring.show();
      break;
    }

    case RING_MUTE: {
      // Wszystkie dim czerwone
      for (int i = 0; i < RING_LEDS; i++)
        ring.setPixelColor(i, ring.Color(60, 0, 0));
      ring.show();
      break;
    }

    case RING_ERROR: {
      // Szybkie miganie czerwone
      static bool tog = false;
      tog = !tog;
      for (int i = 0; i < RING_LEDS; i++)
        ring.setPixelColor(i, tog ? ring.Color(200, 0, 0) : ring.Color(0, 0, 0));
      ring.show();
      break;
    }

    case RING_SLEEP: {
      // 1 dioda bardzo cicha — granatowa
      ring.clear();
      ring.setPixelColor(0, ring.Color(0, 0, 8));
      ring.show();
      break;
    }

    case RING_WAKE: {
      // Rozświetlenie
      ring_pulse_val += 0.05f;
      if (ring_pulse_val >= 1.0f) {
        ring_pulse_val = 1.0f;
        ring_set(RING_PULSE);
      }
      uint8_t b = (uint8_t)(ring_pulse_val * 180);
      for (int i = 0; i < RING_LEDS; i++)
        ring.setPixelColor(i, ring.Color(0, 60, b));
      ring.show();
      break;
    }
  }
}


// ════════════════════════════════════════════════════════════════════
// UART — odbiór
// ════════════════════════════════════════════════════════════════════

void rx_process() {
  while (Serial1.available()) {
    char c = Serial1.read();
    if (c == '\n') {
      rx_buf.trim();
      if (rx_buf.length() > 0) {
        rx_handle_line(rx_buf);
        rx_buf = "";
      }
    } else if (c >= 0x20) {
      rx_buf += c;
      if (rx_buf.length() > 512) {
        Serial.println("[WARN] RX overflow");
        tx_uart_overflow();
        rx_buf = "";
      }
    }
  }
}

void rx_handle_line(const String &line) {
  Serial.print("[RX] "); Serial.println(line);

  JsonDocument doc;
  if (deserializeJson(doc, line) != DeserializationError::Ok) {
    Serial.println("[WARN] JSON error");
    return;
  }

  const char* cmd = doc["cmd"] | "";
  if (!strlen(cmd)) return;

  // ── hb ──────────────────────────────────────────────────────
  if (strcmp(cmd, "hb") == 0) {
    last_hb_rx = millis();
    cnt_hb_recv++;
    if (!rpi_connected) {
      rpi_connected   = true;
      sys.rpi_conn    = true;
      Serial.println("[INFO] RPi POŁĄCZONE");
      blink(3, 80);
    }
    JsonDocument r;
    r["evt"] = "hb"; r["ok"] = 1;
    tx_json(r);
    return;
  }

  // ── state ────────────────────────────────────────────────────
  if (strcmp(cmd, "state") == 0) {
    strncpy(sys.source, doc["source"] | "radio", 15);
    strncpy(sys.title,  doc["title"]  | "",      127);
    strncpy(sys.artist, doc["artist"] | "",       63);
    strncpy(sys.state,  doc["state"]  | "?",      15);
    sys.volume = doc["volume"] | 0;
    sys.muted  = doc["muted"]  | false;
    draw_source_badge();

    // Ring: playing=pulse, buffering=chase, stopped=off
    if (strcmp(sys.state, "playing")   == 0) ring_set(RING_PULSE);
    if (strcmp(sys.state, "buffering") == 0) ring_set(RING_CHASE);
    if (strcmp(sys.state, "stopped")   == 0) ring_set(RING_OFF);
    if (sys.muted) ring_set(RING_MUTE);
    return;
  }

  // ── volume ───────────────────────────────────────────────────
  if (strcmp(cmd, "volume") == 0) {
    sys.volume    = doc["value"] | 0;
    ring_prev_mode = ring_mode;
    ring_set(RING_VOLUME);
    ring_vol_until = millis() + 2000;   // pokaż przez 2s
    return;
  }

  // ── mute ─────────────────────────────────────────────────────
  if (strcmp(cmd, "mute") == 0) {
    sys.muted = doc["value"] | false;
    ring_set(sys.muted ? RING_MUTE : RING_PULSE);
    return;
  }

  // ── event ────────────────────────────────────────────────────
  if (strcmp(cmd, "event") == 0) {
    const char* type  = doc["type"]  | "";
    const char* level = doc["level"] | "info";
    const char* msg   = doc["msg"]   | "";

    // Poziom
    sys.event_level = 0;
    if (strcmp(level, "warn")  == 0) sys.event_level = 1;
    if (strcmp(level, "error") == 0) sys.event_level = 2;

    if (strcmp(type, "sleep") == 0) {
      sys.sleeping = true;
      ring_set(RING_SLEEP);
      draw_sleep_screen();
      return;
    }
    if (strcmp(type, "wake") == 0) {
      sys.sleeping = false;
      ring_set(RING_WAKE);
      draw_wake_screen();
      return;
    }
    if (strcmp(type, "shutdown") == 0) {
      ring_set(RING_ERROR);
      tft.fillScreen(C_BG);
      tft.setTextDatum(MC_DATUM);
      tft.setTextColor(C_RED, C_BG);
      tft.drawString("Shutting down...", 240, 160, 4);
      return;
    }
    if (strcmp(type, "radio_error") == 0) {
      strncpy(sys.event, strlen(msg) ? msg : "Stream error", 31);
      ring_set(RING_ERROR);
      return;
    }
    if (strcmp(type, "radio_buffering") == 0) {
      strncpy(sys.event, "Buffering...", 31);
      ring_set(RING_CHASE);
      return;
    }
    if (strcmp(type, "radio_ok") == 0) {
      sys.event[0] = '\0';
      ring_set(RING_PULSE);
      return;
    }
    if (strcmp(type, "bt_connected") == 0) {
      snprintf(sys.event, 31, "BT: %s", strlen(msg) ? msg : "connected");
      return;
    }
    if (strcmp(type, "bt_disconnected") == 0) {
      strncpy(sys.event, "BT disconnected", 31);
      ring_set(RING_ERROR);
      return;
    }
    if (strcmp(type, "network_lost") == 0) {
      strncpy(sys.event, "No network", 31);
      sys.event_level = 2;
      return;
    }
    if (strcmp(type, "network_ok") == 0) {
      sys.event[0] = '\0';
      return;
    }

    // Inne zdarzenia — pokaż msg jeśli jest
    if (strlen(msg) > 0) strncpy(sys.event, msg, 31);
    return;
  }

  // ── cover_check ──────────────────────────────────────────────
  if (strcmp(cmd, "cover_check") == 0) {
    const char* id = doc["id"] | "";
    // TODO v0.3: sprawdź SD
    JsonDocument r;
    r["evt"] = "cover_miss"; r["id"] = id;
    tx_json(r);
    return;
  }

  Serial.print("[WARN] Nieznana komenda: "); Serial.println(cmd);
}


// ════════════════════════════════════════════════════════════════════
// UART — wysyłanie
// ════════════════════════════════════════════════════════════════════

void tx_json(JsonDocument &doc) {
  String out;
  serializeJson(doc, out);
  Serial1.println(out);
  Serial.print("[TX] "); Serial.println(out);
}

void tx_hb() {
  JsonDocument d;
  d["evt"] = "hb"; d["ok"] = 1;
  tx_json(d);
  cnt_hb_sent++;
}

void tx_ready() {
  JsonDocument d;
  d["evt"]     = "ready";
  d["fw"]      = FW_VERSION;
  d["display"] = "ILI9488";
  d["touch"]   = "TC2046";
  tx_json(d);
  Serial.println("[INFO] Wysłano ready");
}

void tx_uart_overflow() {
  JsonDocument d;
  d["evt"] = "uart_overflow";
  tx_json(d);
}


// ════════════════════════════════════════════════════════════════════
// WATCHDOG
// ════════════════════════════════════════════════════════════════════

void connection_watchdog() {
  if (!rpi_connected) return;
  if (millis() - last_hb_rx > HB_TIMEOUT_MS) {
    rpi_connected = false;
    sys.rpi_conn  = false;
    Serial.println("[ERROR] RPi ROZŁĄCZONE");
    ring_set(RING_ERROR);
  }
}


// ════════════════════════════════════════════════════════════════════
// UTILS
// ════════════════════════════════════════════════════════════════════

void blink(int n, int ms) {
  for (int i = 0; i < n; i++) {
    digitalWrite(LED_BUILTIN, HIGH); delay(ms);
    digitalWrite(LED_BUILTIN, LOW);  delay(ms);
  }
}
