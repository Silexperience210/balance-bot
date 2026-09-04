// ═══════════════════════════════════════════════════════════════════
// BalanceBot — UI tactile (module B)
// LilyGo T-Display-S3-Touch : ESP32-S3, ST7789 170×320 portrait
// ═══════════════════════════════════════════════════════════════════

#include "ui.h"
#include "TFT_eSPI.h"
// TouchLib exige le modèle du chip AVANT l'include :
// CST328 (mutuel) = T-Display S3 Touch standard · CST816 (self) = autres versions
#define TOUCH_MODULES_CST_MUTUAL
#include "TouchLib.h"
#include "Wire.h"
#include "config.h"
#include "interfaces.h"
#include <string.h>

// ── Configuration ──────────────────────────────────────────────────
#define WIDTH  170
#define HEIGHT 320

// Couleurs
#define C_BG       TFT_BLACK
#define C_TEXT     TFT_WHITE
#define C_ORANGE   TFT_ORANGE
#define C_GREEN    TFT_GREEN
#define C_RED      TFT_RED
#define C_DARK     TFT_DARKGREY

// ── Écran ──────────────────────────────────────────────────────────
static TFT_eSPI g_tft;

// ── Touch (TouchLib — CST816, API officielle) ──────────────────────
// L'adresse du CST816 est CTS820_SLAVE_ADDRESS ou CTS328 selon version.
// L'exemple officiel (touch_test) utilise CTS328_SLAVE_ADDRESS pour le
// T-Display-S3 Touch — on essaie CTS328 puis CTS820.
static TouchLib* g_touch = nullptr;

// État tactile brut (lu à chaque loop)
static bool  g_touchedRaw = false;
static int16_t g_touchX = -1, g_touchY = -1;

// ── Boutons tactiles (zones rectangulaires) ──────────────────────
struct TouchZone {
  int16_t x, y, w, h;
  bool   pressed;
  bool   lastPressed;
};

static TouchZone g_zones[] = {
  { 20,  80, 50, 40, false, false },  // AVANT
  { 100, 80, 50, 40, false, false },  // ARRIÈRE
  { 20, 140, 50, 40, false, false },  // GAUCHE
  { 100, 140, 50, 40, false, false }, // DROITE
  { 65, 200, 40, 40, false, false },  // O
};

static const int g_zoneCount = sizeof(g_zones) / sizeof(g_zones[0]);

// ── État UI ────────────────────────────────────────────────────────
static bool g_initialized = false;
static int  g_lastPitch = 0;
static float g_lastBat = 0.0f;
static int  g_lastObs = -1;
static int  g_lastState = 0;
static char g_statusLine[32] = "";

// ── begin() ────────────────────────────────────────────────────────
bool Ui::begin() {
  // Init écran TFT (Setup206 LilyGo T-Display S3 déjà actif)
  g_tft.init();
  g_tft.setRotation(0);  // portrait 170×320
  g_tft.fillScreen(C_BG);

  // Init I2C pour le touch
  Wire.begin(PIN_IIC_SDA, PIN_IIC_SCL);

  // Init touch : CST328 (chip du T-Display S3 Touch, module mutual)
  g_touch = new TouchLib(Wire, PIN_IIC_SDA, PIN_IIC_SCL, CTS328_SLAVE_ADDRESS, PIN_TOUCH_RES);
  if (!g_touch->init()) {
    delete g_touch;
    g_touch = nullptr;
    g_tft.setTextColor(C_RED, C_BG);
    g_tft.setTextSize(1);
    g_tft.drawString("TOUCH ABSENT", 10, 150);
    return false;
  }

  g_initialized = true;
  return true;
}

// ── loop() ────────────────────────────────────────────────────────
void Ui::loop() {
  if (!g_initialized) return;

  // ── 1. Mise à jour des données télémétrie ──────────────────────
  bool pitchChanged = false;
  bool batChanged = false;
  bool obsChanged = false;
  bool stateChanged = false;

  int pitch = static_cast<int>(g_state.pitchDeg * 10);
  if (pitch != g_lastPitch) {
    g_lastPitch = pitch;
    pitchChanged = true;
  }

  float bat = g_state.batteryV;
  if (bat != g_lastBat) {
    g_lastBat = bat;
    batChanged = true;
  }

  int obs = static_cast<int>(g_state.obstacleCm);
  if (obs != g_lastObs) {
    g_lastObs = obs;
    obsChanged = true;
  }

  int state = 0;
  if (g_state.balancing) state = 1;
  else if (g_state.obstacleWarn) state = 2;
  else if (g_state.cmdEnabled) state = 3;
  if (state != g_lastState) {
    g_lastState = state;
    stateChanged = true;
  }

  // ── 2. Gestion tactile ──────────────────────────────────────────
  // Lit l'état brut du touch (API TouchLib officielle)
  g_touchedRaw = false;
  g_touchX = -1; g_touchY = -1;
  if (g_touch && g_touch->read()) {
    uint8_t n = g_touch->getPointNum();
    if (n > 0) {
      TP_Point p = g_touch->getPoint(0);
      g_touchedRaw = true;
      g_touchX = p.x;
      g_touchY = p.y;
    }
  }

  // Détection des appuis sur zones (front montant par zone)
  bool anyTouched = false;
  for (int i = 0; i < g_zoneCount; i++) {
    TouchZone& z = g_zones[i];
    bool inZone = g_touchedRaw &&
                  g_touchX >= z.x && g_touchX < z.x + z.w &&
                  g_touchY >= z.y && g_touchY < z.y + z.h;
    if (inZone && !z.pressed) {
      z.pressed = true;
      z.lastPressed = true;  // action au front montant
      anyTouched = true;
    } else if (!inZone) {
      z.pressed = false;
    }
  }

  // ── 3. Traitement des actions ──────────────────────────────────
  for (int i = 0; i < g_zoneCount; i++) {
    TouchZone& z = g_zones[i];
    if (z.lastPressed) {
      if (i == 0) { g_state.cmdForward = 100; g_state.cmdTurn = 0; }
      else if (i == 1) { g_state.cmdForward = -100; g_state.cmdTurn = 0; }
      else if (i == 2) { g_state.cmdForward = 0; g_state.cmdTurn = -100; }
      else if (i == 3) { g_state.cmdForward = 0; g_state.cmdTurn = 100; }
      else if (i == 4) { g_state.balancing = !g_state.balancing; Balance::setEnabled(g_state.balancing); }
      z.lastPressed = false;
    }
  }
  // Relâchement : retour au neutre des commandes
  bool anyPressedNow = false;
  for (int i = 0; i < g_zoneCount; i++) {
    if (g_zones[i].pressed) { anyPressedNow = true; break; }
  }
  if (!anyPressedNow && !g_touchedRaw) {
    if (g_state.cmdForward != 0 || g_state.cmdTurn != 0) {
      bool cmdZoneHeld = false;
      for (int i = 0; i < 4; i++) if (g_zones[i].pressed) cmdZoneHeld = true;
      if (!cmdZoneHeld) { g_state.cmdForward = 0; g_state.cmdTurn = 0; }
    }
  }

  // ── 4. Rendu ────────────────────────────────────────────────────
  if (pitchChanged || batChanged || obsChanged || stateChanged || anyTouched) {
    g_tft.fillScreen(C_BG);
  }

  // Header
  g_tft.setTextColor(C_ORANGE, C_BG);
  g_tft.setTextSize(2);
  g_tft.drawString("| BALANCEBOT", 0, 10);

  // État
  g_tft.setTextColor(C_TEXT, C_BG);
  g_tft.setTextSize(1);
  const char* stateStr = "";
  switch (g_lastState) {
    case 1: stateStr = "BALANCING"; g_tft.setTextColor(C_GREEN, C_BG); break;
    case 2: stateStr = "CHUTE";    g_tft.setTextColor(C_RED, C_BG);  break;
    case 3: stateStr = "DÉMO";     g_tft.setTextColor(C_ORANGE, C_BG); break;
    default: stateStr = "IDLE";    g_tft.setTextColor(C_DARK, C_BG);  break;
  }
  g_tft.drawString(stateStr, 0, 22);

  // Bandeau obstacle
  if (g_state.obstacleWarn) {
    static bool flash = true;
    if (!flash) { flash = true; g_tft.fillRect(0, 28, WIDTH, 12, C_RED); }
    else { flash = false; g_tft.fillRect(0, 28, WIDTH, 12, C_BG); }
    g_tft.setTextColor(C_RED, C_BG);
    g_tft.drawString("! OBSTACLE", 0, 36);
  }

  // Télémétrie
  g_tft.setTextColor(C_TEXT, C_BG);
  g_tft.setTextSize(1);
  g_tft.drawString("PITCH:", 0, 52);
  g_tft.drawString(String(g_lastPitch / 10.0f, 1) + "°", 40, 52);

  g_tft.drawString("BAT:", 0, 64);
  g_tft.drawString(String(g_lastBat, 2) + " V", 40, 64);

  g_tft.drawString("OBS:", 0, 76);
  if (g_lastObs < 0) {
    g_tft.drawString("—", 40, 76);
  } else {
    g_tft.drawString(String(g_lastObs) + " cm", 40, 76);
  }

  // Boutons
  for (int i = 0; i < g_zoneCount; i++) {
    TouchZone& z = g_zones[i];
    int x = z.x, y = z.y, w = z.w, h = z.h;
    g_tft.fillRoundRect(x, y, w, h, 8, g_zones[i].pressed ? C_ORANGE : C_DARK);
    g_tft.drawRoundRect(x, y, w, h, 8, C_TEXT);
    g_tft.setTextSize(1);
    if (i == 0) { g_tft.setTextColor(C_ORANGE, C_BG); g_tft.drawString("^", x + 25, y + 18); }
    else if (i == 1) { g_tft.setTextColor(C_ORANGE, C_BG); g_tft.drawString("v", x + 25, y + 18); }
    else if (i == 2) { g_tft.setTextColor(C_ORANGE, C_BG); g_tft.drawString("<", x + 25, y + 18); }
    else if (i == 3) { g_tft.setTextColor(C_ORANGE, C_BG); g_tft.drawString(">", x + 25, y + 18); }
    else if (i == 4) { g_tft.setTextColor(C_TEXT, C_BG); g_tft.drawString("O", x + 15, y + 18); }
  }

  // Footer
  g_tft.setTextColor(C_TEXT, C_BG);
  g_tft.setTextSize(1);
  const char* mode = g_state.cmdEnabled ? "AUTO" : "MANUEL";
  g_tft.drawString(mode, 0, 280);

  // Ligne d'état (g_statusLine est global, rempli par setStatusLine)
  if (g_statusLine[0]) {
    g_tft.setTextColor(C_ORANGE, C_BG);
    g_tft.setTextSize(1);
    g_tft.drawString(g_statusLine, 0, 292);
  }
}

// ── setStatusLine() ────────────────────────────────────────────────
void Ui::setStatusLine(const char* text) {
  if (!text || !text[0]) return;
  strncpy(g_statusLine, text, sizeof(g_statusLine) - 1);
  g_statusLine[sizeof(g_statusLine) - 1] = '\0';

  if (g_initialized) {
    g_tft.fillRect(0, 288, WIDTH, 24, C_BG);
    g_tft.setTextColor(C_ORANGE, C_BG);
    g_tft.setTextSize(1);
    g_tft.drawString(g_statusLine, 0, 292);
  }
}
