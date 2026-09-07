#pragma once
// ═══════════════════════════════════════════════════════════════════
// BalanceBot — configuration centralisée (pins + constantes)
// Carte : LilyGo T-Display-S3-Touch (ESP32-S3R8, 16MB, 8MB OPI PSRAM)
// Référence pinout : repo officiel Xinyuan-LilyGO/T-Display-S3
// Ce fichier est la SOURCE UNIQUE des affectations. Les modules le
// lisent ; aucun agent ne doit le modifier sans validation Hermes.
// ═══════════════════════════════════════════════════════════════════

// ── Écran / Touch (occupés — ne pas réutiliser) ────────────────────
#define PIN_LCD_BL      38
#define PIN_LCD_D0      39
#define PIN_LCD_D1      40
#define PIN_LCD_D2      41
#define PIN_LCD_D3      42
#define PIN_LCD_D4      45
#define PIN_LCD_D5      46
#define PIN_LCD_D6      47
#define PIN_LCD_D7      48
#define PIN_POWER_ON    15     // DOIT être HIGH avant usage écran
#define PIN_LCD_RES     5
#define PIN_LCD_CS      6
#define PIN_LCD_DC      7
#define PIN_LCD_WR      8
#define PIN_LCD_RD      9
#define PIN_BUTTON_1    0      // BOOT
#define PIN_BUTTON_2    14
#define PIN_BAT_VOLT    4      // ADC batterie (USB débranché)
#define PIN_TOUCH_INT   16
#define PIN_TOUCH_RES   21

// ── I2C (IMU MPU6050 — bus Qwiic/STEMMA) ───────────────────────────
#define PIN_IIC_SCL     17
#define PIN_IIC_SDA     18

// ── Servos (GPIO libres) ───────────────────────────────────────────
// Mécanique v2 : plus de roues. Les GPIO 1 et 2 pilotent maintenant les
// deux PIEDS EN ARC (foot_arc.stl) sur des SG90 STANDARD 180° — voir
// feet.cpp et chassis/FIT_NOTES.md §9. Les broches sont inchangées, seuls
// les noms suivent la mécanique.
#define SERVO_FOOT_L    1      // pied gauche — SG90 standard (position 0-180°)
#define SERVO_FOOT_R    2      // pied droit  — SG90 standard (position 0-180°)
#define SERVO_HEAD_PAN  3      // tête : rotation horizontale (SG90 standard)
#define SERVO_HEAD_TILT 10     // tête : inclinaison (SG90 standard)

// ── Ultrason HC-SR04 ───────────────────────────────────────────────
#define PIN_US_TRIG     11
#define PIN_US_ECHO     12

// ── Constantes robot ───────────────────────────────────────────────
#define BALANCE_LOOP_HZ 200    // fréquence de la boucle d'équilibre
#define HEAD_PAN_MIN    0      // degrés
#define HEAD_PAN_MAX    180
#define HEAD_TILT_MIN   20     // éviter de viser le sol
#define HEAD_TILT_MAX   90
#define US_MAX_CM       150    // portée utile du HC-SR04
#define US_STOP_CM      25     // distance d'arrêt d'urgence
// Seuil « batterie faible » d'une cellule LiPo 1S : sous 3.5 V la cellule
// n'a plus qu'environ 10-15 % de charge et sa tension s'effondre vite sous
// l'appel de courant des servos. À distinguer de « pas de batterie » (USB
// seul), signalé par batteryV = -1 (cf. battery.cpp).
#define BAT_LOW_V       3.5f
