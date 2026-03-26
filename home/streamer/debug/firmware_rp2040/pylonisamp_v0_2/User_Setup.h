// PylonisAmp — TFT_eSPI User Setup
// Skopiuj ten plik do:
// Arduino/libraries/TFT_eSPI/User_Setup.h
// (nadpisz istniejący)

#define USER_SETUP_INFO "PylonisAmp_Setup"

#define ILI9488_DRIVER

#define TFT_MISO 16
#define TFT_MOSI 19
#define TFT_SCLK 18
#define TFT_CS   17
#define TFT_DC   20
#define TFT_RST  21
#define TFT_BL   22

#define TOUCH_CS 13

#define TFT_SPI_PORT 0

#define LOAD_GLCD
#define LOAD_FONT2
#define LOAD_FONT4
#define LOAD_GFXFF
#define SMOOTH_FONT

#define SPI_FREQUENCY       27000000
#define SPI_READ_FREQUENCY  20000000
#define SPI_TOUCH_FREQUENCY  2500000
