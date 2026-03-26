/**
 * PylonisAmp — Firmware RP2040
 * Wersja: v0.1.0
 *
 * Komunikacja UART z Raspberry Pi
 * Port:  Serial1 (GPIO0=TX, GPIO1=RX)
 * Baud:  115200, 8N1
 *
 * Wymagane biblioteki (Library Manager):
 *   - ArduinoJson  by Benoit Blanchon  (wersja 6.x)
 *
 * Board: Raspberry Pi Pico (earle-philhower/arduino-pico)
 *
 * Na ten moment:
 *   - heartbeat co 500ms
 *   - obsługa wszystkich komend z RPi (logowanie przez USB Serial)
 *   - detekcja zerwania połączenia
 *   - miganie LED jako diagnostyka
 */

#include <Arduino.h>
#include <ArduinoJson.h>

// ── Piny ──────────────────────────────────────────────────────────
#define PIN_UART_TX   0    // GPIO0 → RX Raspberry Pi
#define PIN_UART_RX   1    // GPIO1 ← TX Raspberry Pi


// ── Stałe ─────────────────────────────────────────────────────────
#define FW_VERSION      "0.1.0"
#define UART_BAUD       115200
#define HB_INTERVAL_MS  500    // wysyłaj HB co 500ms
#define HB_TIMEOUT_MS   1500   // 3 × 500ms bez HB od RPi = rozłączono

// ── Zmienne stanu ─────────────────────────────────────────────────
bool     rpi_connected   = false;
uint32_t last_hb_rx      = 0;   // czas ostatniego HB od RPi
uint32_t last_hb_tx      = 0;   // czas ostatniego HB do RPi
uint32_t cnt_hb_sent     = 0;
uint32_t cnt_hb_recv     = 0;
String   rx_buf          = "";


// ════════════════════════════════════════════════════════════════════
void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  blink(2, 200);   // sygnalizacja startu

  // USB Serial — Arduino IDE Serial Monitor (debug)
  Serial.begin(115200);
  delay(300);
  Serial.println();
  Serial.println("╔══════════════════════════════════════╗");
  Serial.println("║   PylonisAmp Firmware v" FW_VERSION "        ║");
  Serial.println("║   UART debug mode                    ║");
  Serial.println("╚══════════════════════════════════════╝");
  Serial.print("[UART] TX=GPIO"); Serial.print(PIN_UART_TX);
  Serial.print("  RX=GPIO");      Serial.print(PIN_UART_RX);
  Serial.print("  BAUD=");        Serial.println(UART_BAUD);

  // UART z RPi
  Serial1.setTX(PIN_UART_TX);
  Serial1.setRX(PIN_UART_RX);
  Serial1.begin(UART_BAUD);

  delay(100);
  tx_ready();   // poinformuj RPi o starcie
}


// ════════════════════════════════════════════════════════════════════
void loop() {
  uint32_t now = millis();

  // 1. Odbierz i przetwórz dane z UART
  rx_process();

  // 2. Wyślij heartbeat
  if (now - last_hb_tx >= HB_INTERVAL_MS) {
    tx_hb();
    last_hb_tx = now;
  }

  // 3. Sprawdź timeout połączenia
  connection_watchdog();
}


// ════════════════════════════════════════════════════════════════════
// ODBIÓR — czytaj bajty, składaj linie, parsuj JSON
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
    } else if (c >= 0x20) {   // ignoruj znaki sterujące oprócz \n
      rx_buf += c;
      if (rx_buf.length() > 512) {
        Serial.println("[WARN] Bufor RX przepełniony — czyszczę");
        tx_uart_overflow();
        rx_buf = "";
      }
    }
  }
}

void rx_handle_line(const String &line) {
  Serial.print("[RX] "); Serial.println(line);

  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, line);
  if (err) {
    Serial.print("[WARN] JSON parse error: ");
    Serial.println(err.c_str());
    return;
  }

  const char* cmd = doc["cmd"] | "";
  if (strlen(cmd) == 0) return;

  // ── hb ──────────────────────────────────────────────────────
  if (strcmp(cmd, "hb") == 0) {
    last_hb_rx = millis();
    cnt_hb_recv++;
    if (!rpi_connected) {
      rpi_connected = true;
      Serial.println("[INFO] *** RPi POŁĄCZONE ***");
      blink(3, 100);
    }
    // odpowiedz
    JsonDocument resp;
    resp["evt"] = "hb";
    resp["ok"]  = 1;
    tx_json(resp);
    return;
  }

  // ── state ────────────────────────────────────────────────────
  if (strcmp(cmd, "state") == 0) {
    Serial.print("[STATE] src=");    Serial.print(doc["source"] | "?");
    Serial.print("  title=");        Serial.print(doc["title"]  | "");
    Serial.print("  artist=");       Serial.print(doc["artist"] | "");
    Serial.print("  vol=");          Serial.print(doc["volume"] | 0);
    Serial.print("  state=");        Serial.print(doc["state"]  | "?");
    Serial.print("  muted=");        Serial.println(doc["muted"] ? "yes" : "no");
    return;
  }

  // ── volume ───────────────────────────────────────────────────
  if (strcmp(cmd, "volume") == 0) {
    Serial.print("[VOLUME] "); Serial.println(doc["value"] | 0);
    return;
  }

  // ── mute ─────────────────────────────────────────────────────
  if (strcmp(cmd, "mute") == 0) {
    Serial.print("[MUTE] ");
    Serial.println((doc["value"] | false) ? "ON" : "OFF");
    return;
  }

  // ── event ────────────────────────────────────────────────────
  if (strcmp(cmd, "event") == 0) {
    const char* type  = doc["type"]  | "?";
    const char* level = doc["level"] | "info";
    const char* msg   = doc["msg"]   | "";
    Serial.print("[EVENT] type="); Serial.print(type);
    Serial.print("  level=");      Serial.print(level);
    if (strlen(msg) > 0) { Serial.print("  msg="); Serial.print(msg); }
    Serial.println();

    if (strcmp(type, "sleep")    == 0) Serial.println("[TODO] → deep sleep");
    if (strcmp(type, "wake")     == 0) Serial.println("[TODO] → wake up");
    if (strcmp(type, "shutdown") == 0) { Serial.println("[TODO] → shutdown"); blink(5, 200); }
    if (strcmp(type, "reboot")   == 0) Serial.println("[TODO] → reboot");
    return;
  }

  // ── cover_check ──────────────────────────────────────────────
  if (strcmp(cmd, "cover_check") == 0) {
    const char* id = doc["id"] | "";
    Serial.print("[COVER_CHECK] id="); Serial.println(id);
    // TODO v0.2: sprawdź kartę SD
    JsonDocument resp;
    resp["evt"] = "cover_miss";
    resp["id"]  = id;
    tx_json(resp);
    return;
  }

  // ── cover_show ───────────────────────────────────────────────
  if (strcmp(cmd, "cover_show") == 0) {
    Serial.print("[COVER_SHOW] id="); Serial.println(doc["id"] | "");
    // TODO v0.2: wyświetl z SD
    return;
  }

  Serial.print("[WARN] Nieznana komenda: "); Serial.println(cmd);
}


// ════════════════════════════════════════════════════════════════════
// WATCHDOG — detekcja utraty połączenia
// ════════════════════════════════════════════════════════════════════
void connection_watchdog() {
  if (!rpi_connected) return;

  uint32_t gap = millis() - last_hb_rx;
  if (gap > HB_TIMEOUT_MS) {
    rpi_connected = false;
    Serial.print("[ERROR] *** RPi ROZŁĄCZONE — brak HB przez ");
    Serial.print(gap); Serial.println("ms ***");
    Serial.print("[STAT]  HB wysłane="); Serial.print(cnt_hb_sent);
    Serial.print("  odebrane=");         Serial.println(cnt_hb_recv);
    blink(6, 80);
  }
}


// ════════════════════════════════════════════════════════════════════
// WYSYŁANIE
// ════════════════════════════════════════════════════════════════════
void tx_json(JsonDocument &doc) {
  String out;
  serializeJson(doc, out);
  Serial1.println(out);
  Serial.print("[TX] "); Serial.println(out);
}

void tx_hb() {
  JsonDocument doc;
  doc["evt"] = "hb";
  doc["ok"]  = 1;
  tx_json(doc);
  cnt_hb_sent++;
}

void tx_ready() {
  JsonDocument doc;
  doc["evt"]     = "ready";
  doc["fw"]      = FW_VERSION;
  doc["display"] = "none";
  doc["touch"]   = "none";
  tx_json(doc);
  Serial.println("[INFO] Wysłano ready");
}

void tx_uart_overflow() {
  JsonDocument doc;
  doc["evt"] = "uart_overflow";
  tx_json(doc);
}


// ════════════════════════════════════════════════════════════════════
// DIAGNOSTYKA
// ════════════════════════════════════════════════════════════════════
void blink(int times, int ms) {
  for (int i = 0; i < times; i++) {
    digitalWrite(LED_BUILTIN, HIGH); delay(ms);
    digitalWrite(LED_BUILTIN, LOW);  delay(ms);
  }
}
