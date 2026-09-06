#!/bin/bash
# Build + upload BalanceBot — T-Display S3 Touch, panneau ST7789
# Les defines (USER_SETUP_LOADED) reproduisent le Setup206 officiel LilyGo
# sans toucher à la lib TFT_eSPI partagée.
#
# RÉSOLUTION : le panneau physique fait 170×320 (et NON 240×320). La RAM du
# ST7789 fait 240 colonnes, mais le verre n'en expose que 170, centrées :
# d'où CGRAM_OFFSET, qui fait appliquer par TFT_eSPI le décalage de 35 px
# (ST7789_Rotation.h : `_init_width == 170` → colstart/rowstart = 35).
# Sans lui + avec TFT_WIDTH=240, tout était dessiné hors du verre.
set -e
cd "$(dirname "$0")"

FQBN="esp32:esp32:esp32s3:USBMode=hwcdc,FlashSize=16M,PSRAM=opi"
FLAGS="-DUSER_SETUP_LOADED -DST7789_DRIVER -DINIT_SEQUENCE_3 -DCGRAM_OFFSET -DTFT_RGB_ORDER=TFT_RGB -DTFT_INVERSION_ON -DTFT_PARALLEL_8_BIT -DTFT_WIDTH=170 -DTFT_HEIGHT=320 -DTFT_CS=6 -DTFT_DC=7 -DTFT_RST=5 -DTFT_WR=8 -DTFT_RD=9 -DTFT_D0=39 -DTFT_D1=40 -DTFT_D2=41 -DTFT_D3=42 -DTFT_D4=45 -DTFT_D5=46 -DTFT_D6=47 -DTFT_D7=48 -DTFT_BL=38 -DTFT_BACKLIGHT_ON=HIGH -DLOAD_GLCD -DLOAD_FONT2 -DLOAD_FONT4 -DLOAD_FONT6 -DLOAD_FONT7 -DLOAD_FONT8 -DLOAD_GFXFF -DSMOOTH_FONT"

PORT="${1:-/dev/ttyACM0}"
arduino-cli compile --fqbn "$FQBN" --build-property "compiler.cpp.extra_flags=$FLAGS" .
arduino-cli upload -p "$PORT" --fqbn "$FQBN" .
echo "=== build + upload OK sur $PORT ==="
