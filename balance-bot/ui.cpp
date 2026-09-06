// ═══════════════════════════════════════════════════════════════════
// BalanceBot — UI tactile (module B) · v5 PAYSAGE 320×170
// LilyGo T-Display-S3-Touch : ESP32-S3, ST7789 170×320 → paysage 320×170
//
// RÉSOLUTION RÉELLE : 170×320 (le verre n'expose que 170 des 240 colonnes
// de la RAM du ST7789). Les defines 240×320 précédents faisaient dessiner
// l'UI hors du verre : l'en-tête et le bas de l'écran étaient invisibles.
// Voir build.sh (TFT_WIDTH=170 + CGRAM_OFFSET).
//
// Combinaison officielle LilyGo (exemples touch_test / usb_hid_pad) :
//   tft.setRotation(3) + touch.setRotation(1)  → coordonnées directes
// et séquence d'init ST7789V custom (LCD_MODULE_CMD_1) envoyée après
// tft.init() : requise par les panneaux de la 2ᵉ révision.
//
// Anti-clignotement : fond dessiné UNE fois (drawStatic), la boucle ne met
// à jour que les zones qui changent. Jamais de fillScreen en boucle.
// ═══════════════════════════════════════════════════════════════════

#include "ui.h"
#include "TFT_eSPI.h"
// TouchLib : modèle du chip AVANT l'include (CST816 = cartes récentes)
#define TOUCH_MODULES_CST_SELF
#include "TouchLib.h"
#include "Wire.h"
#include "config.h"
#include "interfaces.h"
#include <string.h>

// ── Configuration (paysage) ────────────────────────────────────────
#define WIDTH  320
#define HEIGHT 170

// Séquence d'init ST7789V spécifique LilyGo (cf. exemple touch_test).
// Le 2ᵉ modèle d'écran vendu sous la même référence en a besoin pour
// afficher correctement ; elle est envoyée APRÈS tft.init().
#define LCD_MODULE_CMD_1

// Couleurs
#define C_BG       TFT_BLACK
#define C_TEXT     TFT_WHITE
#define C_ORANGE   TFT_ORANGE
#define C_GREEN    TFT_GREEN
#define C_RED      TFT_RED
#define C_DARK     TFT_DARKGREY

// ── Écran ──────────────────────────────────────────────────────────
static TFT_eSPI g_tft;

#if defined(LCD_MODULE_CMD_1)
typedef struct {
  uint8_t cmd;
  uint8_t data[14];
  uint8_t len;   // bit 7 = attendre 120 ms après la commande
} lcd_cmd_t;

static const lcd_cmd_t lcd_st7789v[] = {
  {0x11, {0}, 0 | 0x80},
  {0x3A, {0X05}, 1},
  {0xB2, {0X0B, 0X0B, 0X00, 0X33, 0X33}, 5},
  {0xB7, {0X75}, 1},
  {0xBB, {0X28}, 1},
  {0xC0, {0X2C}, 1},
  {0xC2, {0X01}, 1},
  {0xC3, {0X1F}, 1},
  {0xC6, {0X13}, 1},
  {0xD0, {0XA7}, 1},
  {0xD0, {0XA4, 0XA1}, 2},
  {0xD6, {0XA1}, 1},
  {0xE0, {0XF0, 0X05, 0X0A, 0X06, 0X06, 0X03, 0X2B, 0X32, 0X43, 0X36, 0X11, 0X10, 0X2B, 0X32}, 14},
  {0xE1, {0XF0, 0X08, 0X0C, 0X0B, 0X09, 0X24, 0X2B, 0X22, 0X43, 0X38, 0X15, 0X16, 0X2F, 0X37}, 14},
};

static void sendPanelInitSequence() {
  for (uint8_t i = 0; i < (sizeof(lcd_st7789v) / sizeof(lcd_cmd_t)); i++) {
    g_tft.writecommand(lcd_st7789v[i].cmd);
    for (int j = 0; j < (lcd_st7789v[i].len & 0x7f); j++) {
      g_tft.writedata(lcd_st7789v[i].data[j]);
    }
    if (lcd_st7789v[i].len & 0x80) delay(120);
  }
}
#endif

// ── Touch ──────────────────────────────────────────────────────────
static TouchLib* g_touch = nullptr;
static bool     g_touchedRaw = false;
static int16_t  g_touchX = -1, g_touchY = -1;

// ── Boutons tactiles ──────────────────────────────────────────────
struct TouchZone {
  int16_t x, y, w, h;
  bool   pressed;
  bool   lastPressed;
  bool   renderedPressed;  // état dessiné (redessin seulement au changement)
};

// Disposition paysage 320×170 : croix directionnelle 2×2 à gauche,
// gros bouton ÉQUILIBRE pleine hauteur à droite. Tout tient dans
// y = 66..162, sous le bandeau télémétrie.
static TouchZone g_zones[] = {
  {  12,  66,  88, 46, false, false, false }, // 0 AVANT   (^)
  { 108,  66,  88, 46, false, false, false }, // 1 ARRIÈRE (v)
  {  12, 116,  88, 46, false, false, false }, // 2 GAUCHE  (<)
  { 108, 116,  88, 46, false, false, false }, // 3 DROITE  (>)
  { 208,  66, 100, 96, false, false, false }, // 4 toggle équilibre
};
static const int g_zoneCount = sizeof(g_zones) / sizeof(g_zones[0]);

// ── État UI ────────────────────────────────────────────────────────
static bool g_initialized = false;
static int  g_lastPitch = 0;
static float g_lastBat = 0.0f;
static int  g_lastObs = -1;
static int  g_lastState = -1;
static const char* g_lastMode = "";
static bool g_lastWarn = false;
static bool g_lastArmed = false;   // état ARMÉ dessiné sur le bouton 4

// ── Helpers de rendu ───────────────────────────────────────────────

// Efface puis écrit un texte (taille 1) dans une zone
static void updateLabel(int x, int y, int w, const char* s, uint16_t color) {
  g_tft.fillRect(x, y, w, 9, C_BG);
  g_tft.setTextColor(color, C_BG);
  g_tft.setTextSize(1);
  g_tft.setCursor(x, y);
  g_tft.print(s);
}

// Redessine le bouton i en entier.
// Le bouton 4 reflète l'état ARMÉ (Balance::isEnabled()) et NON
// g_state.balancing : ce dernier retombe à false à chaque chute alors que
// l'asservissement reste armé — le bouton affichait alors « EQUIL. » et
// un appui RÉ-ARMAIT au lieu de couper (STOP inopérant).
static void drawButton(int i) {
  TouchZone& z = g_zones[i];
  bool on = z.pressed;
  const bool armed = Balance::isEnabled();
  uint16_t col;
  if (i == 4) col = on ? C_ORANGE : (armed ? C_GREEN : C_DARK);
  else        col = on ? C_ORANGE : C_DARK;

  g_tft.fillRoundRect(z.x, z.y, z.w, z.h, 8, col);
  g_tft.drawRoundRect(z.x, z.y, z.w, z.h, 8, C_TEXT);

  int cx = z.x + z.w / 2;
  int cy = z.y + z.h / 2;
  uint16_t glyph = on ? C_TEXT : C_ORANGE;
  if (i == 0) g_tft.fillTriangle(cx - 12, cy + 8, cx + 12, cy + 8, cx, cy - 12, glyph);
  else if (i == 1) g_tft.fillTriangle(cx - 12, cy - 8, cx + 12, cy - 8, cx, cy + 12, glyph);
  else if (i == 2) g_tft.fillTriangle(cx + 8, cy - 12, cx + 8, cy + 12, cx - 12, cy, glyph);
  else if (i == 3) g_tft.fillTriangle(cx - 8, cy - 12, cx - 8, cy + 12, cx + 12, cy, glyph);
  else {
    g_tft.setTextDatum(MC_DATUM);
    g_tft.setTextColor(on || !armed ? C_TEXT : C_BG, col);
    g_tft.setTextSize(2);  // 6 car. × 12 px = 72 px < 100 px de large
    g_tft.drawString(armed ? "STOP" : "EQUIL.", cx, cy);
    g_tft.setTextSize(1);
    g_tft.setTextDatum(TL_DATUM);
    g_lastArmed = armed;
  }
  z.renderedPressed = on;
}

// Dessin initial complet
static void drawStatic() {
  g_tft.fillScreen(C_BG);

  // Header — "BALANCEBOT" taille 2 (12 px/car.) : 10 car. = 120 px
  g_tft.setTextDatum(TL_DATUM);
  g_tft.setTextColor(C_ORANGE, C_BG);
  g_tft.setTextSize(2);
  g_tft.drawString("BALANCEBOT", 6, 2);
  g_tft.setTextSize(1);
  g_tft.setTextColor(C_DARK, C_BG);
  g_tft.drawString("IDLE", 240, 8);

  // Séparateur (le bandeau d'alerte obstacle se dessine juste dessous)
  g_tft.drawFastHLine(6, 22, WIDTH - 12, C_DARK);

  // Télémétrie (labels + valeurs initiales) — 2 colonnes, 2 lignes
  g_tft.setTextColor(C_DARK, C_BG);
  g_tft.drawString("PITCH", 6, 32);
  g_tft.drawString("BAT", 6, 44);
  g_tft.drawString("OBS", 166, 32);
  g_tft.drawString("MODE", 166, 44);
  g_tft.setTextColor(C_TEXT, C_BG);
  g_tft.drawString("0.0 deg", 48, 32);
  g_tft.drawString("0.00 V", 48, 44);
  g_tft.drawString("--", 206, 32);
  g_tft.drawString("MANUEL", 206, 44);

  // Boutons
  for (int i = 0; i < g_zoneCount; i++) drawButton(i);
}

// ── begin() ────────────────────────────────────────────────────────
bool Ui::begin() {
  g_tft.init();
#if defined(LCD_MODULE_CMD_1)
  sendPanelInitSequence();  // avant setRotation : ne touche pas au MADCTL
#endif
  g_tft.setRotation(3);  // PAYSAGE 320×170 (combinaison officielle LilyGo)
  g_tft.fillScreen(C_BG);

  Wire.begin(PIN_IIC_SDA, PIN_IIC_SCL);

  g_touch = new TouchLib(Wire, PIN_IIC_SDA, PIN_IIC_SCL, CTS820_SLAVE_ADDRESS, PIN_TOUCH_RES);
  if (!g_touch->init()) {
    delete g_touch;
    g_touch = nullptr;
    g_tft.setTextColor(C_RED, C_BG);
    g_tft.setTextSize(2);
    g_tft.drawString("TOUCH ABSENT", 88, 80);
    return false;
  }
  g_touch->setRotation(1);  // aligne le repère touch sur le paysage

  g_initialized = true;
  drawStatic();
  return true;
}

// ── loop() ────────────────────────────────────────────────────────
void Ui::loop() {
  if (!g_initialized) return;

  // ── 1. Lecture tactile (coordonnées déjà alignées par setRotation) ──
  g_touchedRaw = false;
  g_touchX = -1; g_touchY = -1;
  if (g_touch && g_touch->read()) {
    uint8_t n = g_touch->getPointNum();
    if (n > 0) {
      TP_Point p = g_touch->getPoint(0);
      g_touchedRaw = true;
      g_touchX = static_cast<int16_t>(p.x);
      g_touchY = static_cast<int16_t>(p.y);
    }
  }

  // ── 2. Zones : front montant / relâchement ─────────────────────
  // On mémorise si une zone DIRECTIONNELLE est effectivement tenue : le
  // relâchement d'une commande, c'est « plus aucun bouton sous le doigt »,
  // pas « plus de doigt sur l'écran ». Sinon un doigt qui glisse hors du
  // bouton en restant posé laissait cmdForward/cmdTurn bloqués.
  bool dirHeld = false;
  for (int i = 0; i < g_zoneCount; i++) {
    TouchZone& z = g_zones[i];
    bool inZone = g_touchedRaw &&
                  g_touchX >= z.x && g_touchX < z.x + z.w &&
                  g_touchY >= z.y && g_touchY < z.y + z.h;
    if (inZone && !z.pressed) {
      z.pressed = true;
      z.lastPressed = true;
    } else if (!inZone) {
      z.pressed = false;
    }
    if (inZone && i < 4) dirHeld = true;
  }

  // ── 3. Actions (front montant) ─────────────────────────────────
  for (int i = 0; i < g_zoneCount; i++) {
    TouchZone& z = g_zones[i];
    if (z.lastPressed) {
      if (i == 0)      { g_state.cmdForward = 100; g_state.cmdTurn = 0; }
      else if (i == 1) { g_state.cmdForward = -100; g_state.cmdTurn = 0; }
      else if (i == 2) { g_state.cmdForward = 0; g_state.cmdTurn = -100; }
      else if (i == 3) { g_state.cmdForward = 0; g_state.cmdTurn = 100; }
      else if (i == 4) {
        // Bascule sur l'état ARMÉ réel. setEnabled(false) coupe tout
        // (halt + roues au neutre) et le verrou tient : Balance::loop()
        // sort immédiatement tant que l'utilisateur n'a pas ré-armé.
        const bool armed = Balance::isEnabled();
        Balance::setEnabled(!armed);
        g_state.cmdForward = 0;
        g_state.cmdTurn = 0;
      }
      z.lastPressed = false;
    }
  }

  // Retour au neutre dès qu'aucune flèche n'est sous le doigt
  if (!dirHeld && (g_state.cmdForward != 0 || g_state.cmdTurn != 0)) {
    g_state.cmdForward = 0;
    g_state.cmdTurn = 0;
  }

  // ── 4. Rendu incrémental ───────────────────────────────────────

  // 4a. Boutons dont l'état pressé a changé (+ bouton 4 si l'armement
  // a changé ailleurs qu'à l'appui : sécurité, ré-arme auto, etc.)
  for (int i = 0; i < g_zoneCount; i++) {
    if (g_zones[i].pressed != g_zones[i].renderedPressed) drawButton(i);
  }
  if (Balance::isEnabled() != g_lastArmed) drawButton(4);

  // 4b. Télémétrie
  int pitch = static_cast<int>(g_state.pitchDeg * 10);
  if (pitch != g_lastPitch) {
    g_lastPitch = pitch;
    char b[16];
    // Signe explicite : pitch/10 vaut 0 entre -0.9° et -0.1°, le « - »
    // serait perdu (−0,5° affiché « 0.5 deg »).
    snprintf(b, sizeof(b), "%s%d.%d deg", (pitch < 0 && pitch > -10) ? "-" : "",
             pitch / 10, abs(pitch % 10));
    updateLabel(48, 32, 76, b, C_TEXT);
  }

  float bat = g_state.batteryV;
  if (bat != g_lastBat) {
    g_lastBat = bat;
    char b[16];
    // batteryV < 0 = aucune batterie plausible (alimentation USB seule) :
    // à distinguer d'une batterie réellement à plat.
    if (bat < 0.0f) snprintf(b, sizeof(b), "USB");
    else            snprintf(b, sizeof(b), "%.2f V", bat);
    updateLabel(48, 44, 76, b,
                bat < 0.0f ? C_DARK : (g_state.batteryLow ? C_RED : C_TEXT));
  }

  int obs = static_cast<int>(g_state.obstacleCm);
  if (obs != g_lastObs) {
    g_lastObs = obs;
    char b[16];
    if (obs < 0) snprintf(b, sizeof(b), "--");
    else         snprintf(b, sizeof(b), "%d cm", obs);
    updateLabel(206, 32, 60, b, obs >= 0 && obs < 100 ? C_ORANGE : C_TEXT);
  }

  // 4c. Mode
  const char* mode = Balance::isEnabled() ? "AUTO" : "MANUEL";
  if (strcmp(mode, g_lastMode) != 0) {
    g_lastMode = mode;
    updateLabel(206, 44, 60, mode, C_TEXT);
  }

  // 4d. État principal — « CHUTE » signale la VRAIE chute (verrou de
  // Balance), pas un obstacle : l'obstacle a son propre état « OBST. ».
  int state = 0;
  if (Balance::isEnabled() && Balance::isFallen()) state = 2;
  else if (g_state.obstacleWarn) state = 4;
  else if (g_state.balancing)    state = 1;
  else if (Balance::isEnabled()) state = 3;
  if (state != g_lastState) {
    g_lastState = state;
    const char* s = "IDLE";
    uint16_t col = C_DARK;
    switch (state) {
      case 1: s = "BALANCING"; col = C_GREEN;  break;
      case 2: s = "CHUTE";     col = C_RED;    break;
      case 3: s = "ARME";      col = C_ORANGE; break;
      case 4: s = "OBST.";     col = C_ORANGE; break;
    }
    updateLabel(240, 8, 74, s, col);
  }

  // 4e. Virage de l'état obstacle : le bandeau clignote seulement en warn
  if (g_state.obstacleWarn != g_lastWarn) {
    g_lastWarn = g_state.obstacleWarn;
    if (g_state.obstacleWarn) {
      g_tft.fillRect(6, 24, WIDTH - 12, 3, C_RED);
    } else {
      g_tft.fillRect(6, 24, WIDTH - 12, 3, C_BG);
      updateLabel(166, 32, 34, "OBS", C_DARK);
      updateLabel(206, 32, 60, "--", C_TEXT);
      g_lastObs = -9999;  // force la re-écriture de la valeur
    }
  }

  // 4f. Diagnostic : fréquence réelle + pire temps UI/tête (ms).
  // Vert = 200 Hz tenus · orange = dégradé · rouge = lent. Le « U: » et
  // « H: » montrent qui bloque (ex. U:12 = un cycle UI a pris 12 ms).
  {
    static int s_lastHz = -1;
    static uint8_t s_lastUi = 255, s_lastHead = 255;
    int hz = static_cast<int>(g_state.balanceHz + 0.5f);
    if (hz != s_lastHz || g_state.dbgUiMs != s_lastUi || g_state.dbgHeadMs != s_lastHead) {
      s_lastHz = hz;
      s_lastUi = g_state.dbgUiMs;
      s_lastHead = g_state.dbgHeadMs;
      uint16_t col = hz >= 180 ? C_GREEN : (hz >= 100 ? C_ORANGE : C_RED);
      char b[24];
      if (hz <= 0) snprintf(b, sizeof(b), "B:-- U:%u H:%u", s_lastUi, s_lastHead);
      else         snprintf(b, sizeof(b), "B:%d U:%u H:%u", hz, s_lastUi, s_lastHead);
      updateLabel(6, 54, 150, b, col);
    }
  }
}
