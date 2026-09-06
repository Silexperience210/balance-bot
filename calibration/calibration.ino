// ═══════════════════════════════════════════════════════════════════
// Calibration écran 240×320 plein panneau — T-Display S3 Touch
// Compilation avec -DUSER_SETUP_LOADED + defines 240×320 (flags CLI)
// ═══════════════════════════════════════════════════════════════════
#include <Arduino.h>
#include "TFT_eSPI.h"
#define TOUCH_MODULES_CST_SELF
#include "TouchLib.h"
#include "Wire.h"

#define PIN_IIC_SCL 17
#define PIN_IIC_SDA 18
#define PIN_TOUCH_RES 21

TFT_eSPI tft = TFT_eSPI();
TouchLib touch(Wire, PIN_IIC_SDA, PIN_IIC_SCL, CTS820_SLAVE_ADDRESS, PIN_TOUCH_RES);

void setup() {
  Serial.begin(115200);
  delay(200);
  pinMode(15, OUTPUT);  // Power ON
  digitalWrite(15, HIGH);
  delay(100);

  tft.init();
  tft.setRotation(0);  // portrait 240×320 si le define passe
  tft.fillScreen(TFT_WHITE);   // test 1 : remplit TOUT l'écran ?
  delay(2000);
  tft.fillScreen(TFT_RED);     // test 2
  delay(2000);
  tft.fillScreen(TFT_BLACK);

  Wire.begin(PIN_IIC_SDA, PIN_IIC_SCL);
  bool ok = touch.init();

  tft.setTextSize(1);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  char buf[64];
  snprintf(buf, sizeof(buf), "W=%d H=%d", tft.width(), tft.height());
  tft.drawString(buf, 0, 0);
  tft.drawString(ok ? "TOUCH OK" : "TOUCH FAIL", 0, 12);
  tft.drawString("Blanc = 240x320 plein ?", 0, 30);
  tft.drawString("Touche les 4 COINS", 0, 60);
  tft.drawString("et lis x,y en GROS", 0, 72);
}

void loop() {
  if (touch.read()) {
    uint8_t n = touch.getPointNum();
    if (n > 0) {
      TP_Point p = touch.getPoint(0);
      tft.fillRect(0, 100, 240, 120, TFT_BLACK);
      tft.setTextSize(3);
      tft.setTextColor(TFT_GREEN, TFT_BLACK);
      char buf[24];
      snprintf(buf, sizeof(buf), "x=%d", p.x);
      tft.drawString(buf, 5, 110);
      snprintf(buf, sizeof(buf), "y=%d", p.y);
      tft.drawString(buf, 5, 155);
      tft.fillCircle(p.x, p.y, 3, TFT_ORANGE);
      Serial.printf("touch x=%d y=%d p=%d n=%d\n", p.x, p.y, p.pressure, n);
    }
  }
  delay(10);
}
