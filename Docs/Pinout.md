# Pinout – Streamer v0.07a1 (wersja minimalna)

## Raspberry Pi – sygnały krytyczne

| Funkcja                | BCM  | Pin fizyczny | Typ        | Uwagi |
|------------------------|------|--------------|------------|-------|
| I2C SDA (OLED)         | 2    | 3            | I2C        | OLED + przyszły MCP23017 |
| I2C SCL (OLED)         | 3    | 5            | I2C        | jw. |
| GND                    | —    | 6            | Masa       | Wspólna masa |
| 1-Wire (DS18B20)       | 4    | 7            | 1-Wire     | Czujniki temperatury |
| Enkoder A              | 17   | 11           | GPIO       | Enkoder 1 – sygnał A |
| Enkoder B              | 27   | 13           | GPIO       | Enkoder 1 – sygnał B |
| Enkoder SW             | 22   | 15           | GPIO       | Klik enkodera |
| IR odbiornik           | 25   | 22           | GPIO       | TSOP / VS1838B |
| GND                    | —    | 9/14/20/25   | Masa       | Użyj kilku dla stabilności |

## OLED
- Magistrala I2C (SDA/SCL)
- Adres: 0x3C

## MPD
- Standardowa konfiguracja `/etc/mpd.conf`
- Upewnić się, że `/etc/default/mpd` zawiera:  
  `MPDCONF=/etc/mpd.conf`

## Rezerwa
- GPIO12/13/18 – sprzętowe PWM (RGB w przyszłości)
- GPIO23/24 – przekaźniki / STBY wzmacniacza
- GPIO5/6/16/26 – wolne GPIO pod MCP23017 INT, przyciski, LED itp.
