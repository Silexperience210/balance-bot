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
//   tft.setRotation(3) + touch.setRotation(1).
// ATTENTION : le setRotation(1) de TouchLib ne fait QUE transposer x↔y
// (ModulesCSTSelf.tpp) — il aligne les axes sans fixer leur sens. Le sens
// de l'axe long du CST816 est opposé à l'axe x écran : le miroir horizontal
// est appliqué explicitement dans readTouch() (kTouchMirrorX). Voir
// TOUCH_REVIEW.md §1 — sans ce miroir, appuyer sur AVANT/GAUCHE armait le
// robot. Aucune combinaison de setRotation ne peut produire une réflexion.
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

// Orientation du tactile — cf. TOUCH_REVIEW.md §1.
// TouchLib::setRotation(1) fait UNIQUEMENT un échange x↔y (transposition,
// ModulesCSTSelf.tpp:100-104). Une transposition aligne les axes mais ne
// fixe pas leur SENS, et aucune rotation (ni tft.setRotation, ni TouchLib)
// ne peut annuler une réflexion : il faut la poser en dur. Mesuré par le
// protocole des 4 coins : l'axe long du CST816 est orienté à l'inverse de
// l'axe x écran en rotation 3 (MADCTL = MV|MY).
static constexpr bool kTouchMirrorX = true;
static constexpr bool kTouchMirrorY = false;

// Diagnostic tactile (exposé par Ui::touchDebug() / GET /api/touch).
// RÉMANENT : readTouch() remet g_touchX à -1 au relâchement, or une requête
// HTTP arrive toujours après que le doigt est parti. On conserve donc le
// dernier point VALIDE, brut ET transformé. g_touchSeq compte les fronts
// montants : il prouve que la valeur lue vient bien du tap qu'on vient de
// faire et pas du précédent.
static int16_t  g_touchRawX  = -1, g_touchRawY  = -1;
static int16_t  g_touchLastX = -1, g_touchLastY = -1;
static uint32_t g_touchSeq   = 0;

// Verrou d'appui : positionné à chaque changement de mode AUTO ↔ MANUEL pour
// que le doigt déjà posé ne soit pas relu comme un nouvel appui (sans lui,
// le tap sur STOP ré-armait le robot 16 ms plus tard, et l'armement au doigt
// ouvrait l'écran STOP — FACE_REVIEW.md constats 2 et 7).
static bool g_touchLatch = false;

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
// Caches du rendu incrémental de l'écran de COMMANDE (déplacés au niveau
// fichier pour pouvoir être réinitialisés au retour du visage).
static int     g_lastWeb = -1, g_lastFoot = -9999, g_lastHz = -1;
static uint8_t g_lastDbgUi = 255, g_lastDbgHead = 255;

static void resetManualCaches() {
  g_lastPitch = 0; g_lastBat = 0.0f; g_lastObs = -1; g_lastState = -1;
  g_lastMode = ""; g_lastWarn = false; g_lastArmed = false;
  g_lastWeb = -1; g_lastFoot = -9999; g_lastHz = -1;
  g_lastDbgUi = 255; g_lastDbgHead = 255;
}

// ── Helpers de rendu ───────────────────────────────────────────────

// Efface puis écrit un texte (taille 1) dans une zone
static void updateLabel(int x, int y, int w, const char* s, uint16_t color) {
  g_tft.fillRect(x, y, w, 9, C_BG);
  g_tft.setTextColor(color, C_BG);
  g_tft.setTextSize(1);
  g_tft.setCursor(x, y);
  g_tft.print(s);
}

// ══════════════════════════════════════════════════════════════════
// VISAGE (mode AUTO) — géométrie validée par rendus avant flash :
// amande à paupière haute quasi droite et ventre bombé, gros iris,
// inclinaison vers l'intérieur pour l'air fâché. Voir FIRMWARE_REVIEW.md.
// ══════════════════════════════════════════════════════════════════
namespace {

constexpr int   FACE_CY   = 84;
constexpr int   EYE_W     = 104;     // taille réduite : le bus parallèle
constexpr int   EYE_H     = 68;      // coûte ~2,5 Mpx/s (mesuré) — garder
constexpr int   EYE_GAP   = 118;     // les yeux grands mais pas énormes
constexpr int   FACE_CX_L = (WIDTH - EYE_GAP - 1) / 2;   // 100 : symétrie
constexpr int   FACE_CX_R = WIDTH - 1 - FACE_CX_L;       // 219 : parfaite
                                                         // autour de 159,5
constexpr float LID_TOP   = 0.28f;   // part de la hauteur au-dessus de l'axe
constexpr float EXP_TOP   = 1.00f;   // 1.0 = paupière haute franche
constexpr float EXP_BOT   = 0.62f;   // ventre bombé, coins acérés
constexpr float IRIS_R    = 0.52f;   // rayon de l'iris / ventre bas

// Zones tactiles du mode AUTO (le visage remplit l'écran, le STOP le remplace)
constexpr int STOP_X = 60, STOP_Y = 40, STOP_W = 200, STOP_H = 92;

// Cadences du visage : assez fluide à l'œil, sans manger la boucle 200 Hz
constexpr unsigned long kFaceHz     = 20;       // 50 ms entre deux images
constexpr unsigned long kStopHoldMs = 6000;     // écran STOP avant retour au visage

enum FaceExpr : uint8_t {
  FX_CALME, FX_PENCHE, FX_MEFIANT, FX_ENERVE, FX_SURPRISE, FX_CONTENT, FX_CLIN, FX_CHUTE
};

struct FaceFrame {
  FaceExpr expr   = FX_CALME;
  float    gaze   = 0.0f;     // décalage horizontal du regard (px)
  bool     blink  = false;
  bool     red    = false;    // teinte colère
};

// Remplissage de polygone par balayage (le visage n'a que 2 polygones).
void fillPoly(const int16_t* xs, const int16_t* ys, int n, uint16_t color) {
  int16_t ymin = ys[0], ymax = ys[0];
  for (int i = 1; i < n; i++) {
    if (ys[i] < ymin) ymin = ys[i];
    if (ys[i] > ymax) ymax = ys[i];
  }
  for (int y = ymin; y <= ymax; y++) {
    int16_t xi[8];
    int cnt = 0;
    for (int i = 0, j = n - 1; i < n; j = i++) {
      const int16_t yi = ys[i], yj = ys[j];
      if ((yi > y) != (yj > y) && cnt < 8) {
        const float t = (float)(y - yi) / (float)(yj - yi);
        xi[cnt++] = (int16_t)lroundf(xs[i] + t * (float)(xs[j] - xs[i]));
      }
    }
    for (int a = 1; a < cnt; a++) {
      for (int b = a; b > 0 && xi[b - 1] > xi[b]; b--) {
        const int16_t tmp = xi[b - 1]; xi[b - 1] = xi[b]; xi[b] = tmp;
      }
    }
    for (int a = 0; a + 1 < cnt; a += 2) {
      g_tft.drawFastHLine(xi[a], y, xi[a + 1] - xi[a] + 1, color);
    }
  }
}

// Points d'une amande (œil) dans le repère écran. inn = +1 œil gauche.
constexpr int kEyeN   = 16;              // 17 points par lèvre
constexpr int kEyePts = 2 * (kEyeN + 1); // 34 points écrits
static_assert(kEyePts <= 40, "xs/ys trop petits pour faceEyePoints()");

void faceEyePoints(int cx, int cy, int w, int h, float angDeg, int inn,
                   int16_t* xs, int16_t* ys, int& n) {
  const float ht = h * LID_TOP, hb = h * (1.0f - LID_TOP);
  const float a = angDeg * 0.017453293f;  // évite le double émulé de DEG_TO_RAD
  const float ca = cosf(a), sa = sinf(a);
  int k = 0;
  const int N = kEyeN;
  for (int i = 0; i <= N; i++) {          // paupière haute
    const float t = -1.0f + 2.0f * i / N;
    const float x = t * w * 0.5f;
    const float y = -ht * powf(fmaxf(0.0f, 1.0f - t * t), EXP_TOP);
    xs[k] = (int16_t)lroundf(cx + inn * (x * ca - y * sa));
    ys[k] = (int16_t)lroundf(cy + (x * sa + y * ca));
    k++;
  }
  for (int i = 0; i <= N; i++) {          // paupière basse
    const float t = 1.0f - 2.0f * i / N;
    const float x = t * w * 0.5f;
    const float y = hb * powf(fmaxf(0.0f, 1.0f - t * t), EXP_BOT);
    xs[k] = (int16_t)lroundf(cx + inn * (x * ca - y * sa));
    ys[k] = (int16_t)lroundf(cy + (x * sa + y * ca));
    k++;
  }
  n = k;
}

// Géométrie de l'iris d'un œil (pour ne redessiner QUE lui quand le regard
// bouge : le contour de l'amande ne change qu'au changement d'expression).
struct IrisGeom {
  int  x = 0, y = 0, r = 0, w = 0, inn = 1;
  bool slit = false;
  bool valid = false;
};

// Style géométrique d'un œil selon l'expression (partagé par le dessin et
// le calcul de la position de l'iris).
struct EyeStyle { int w, h; float ang; bool slit; int gazeMax; };

EyeStyle faceStyle(const FaceFrame& f) {
  EyeStyle s{EYE_W, EYE_H, 6.0f, false, 18};
  switch (f.expr) {
    case FX_PENCHE:   s.ang = 13.0f; s.h = 57; break;
    case FX_MEFIANT:  s.ang = 15.0f; s.h = 44; s.slit = true; s.gazeMax = 6; break;
    case FX_ENERVE:   s.ang = 26.0f; s.h = 27; s.slit = true; s.gazeMax = 6; break;
    case FX_SURPRISE: s.ang = 3.0f;  s.w = 100; s.h = 76; s.gazeMax = 10; break;
    case FX_CONTENT:  s.ang = 4.0f;  s.w = 95;  s.h = 55; break;
    case FX_CLIN:     s.ang = 4.0f;  s.w = 100; s.h = 73; s.gazeMax = 10; break;
    default: break;                                  // FX_CALME
  }
  if (f.blink) s.h = 8;
  return s;
}

// Géométrie de l'iris SANS rien dessiner (pour le déplacement incrémental).
IrisGeom faceIrisGeom(int cx, int inn, const FaceFrame& f) {
  IrisGeom g;
  if (f.blink) return g;                             // œil fermé : pas d'iris
  if (f.expr == FX_CHUTE || f.expr == FX_CONTENT) return g;
  if (f.expr == FX_CLIN && inn == +1) return g;      // œil gauche fermé
  const EyeStyle s = faceStyle(f);
  const int hb = (int)(s.h * (1.0f - LID_TOP));
  g.r     = (int)(hb * IRIS_R);
  g.w     = max(2, g.r / 4);
  g.slit  = s.slit;
  g.inn   = inn;
  g.x     = cx + (int)constrain(f.gaze, (float)-s.gazeMax, (float)s.gazeMax);
  g.y     = FACE_CY + (int)(hb * 0.30f);
  g.valid = true;
  return g;
}

// Un œil complet (amande pleine + iris + pupille/reflet). *out reçoit la
// géométrie de l'iris pour les déplacements suivants.
void faceDrawEye(int cx, int inn, const FaceFrame& f, IrisGeom* out) {
  int16_t xs[40], ys[40];
  int n = 0;
  const uint16_t col = f.red ? C_RED : C_ORANGE;
  if (out) out->valid = false;

  const EyeStyle st = faceStyle(f);
  const int   w   = st.w;
  const int   h   = st.h;
  const float ang = st.ang;
  const bool  slit = st.slit;

  faceEyePoints(cx, FACE_CY, w, h, ang, inn, xs, ys, n);
  fillPoly(xs, ys, n, col);

  if (f.blink) return;                               // œil fermé : rien de plus

  if (f.expr == FX_CHUTE) {                          // X par-dessus l'amande
    g_tft.drawLine(cx - 17, FACE_CY - 17, cx + 17, FACE_CY + 17, C_TEXT);
    g_tft.drawLine(cx + 17, FACE_CY - 17, cx - 17, FACE_CY + 17, C_TEXT);
    g_tft.drawLine(cx - 18, FACE_CY - 17, cx + 18, FACE_CY + 17, C_TEXT);
    g_tft.drawLine(cx + 18, FACE_CY - 17, cx - 18, FACE_CY + 17, C_TEXT);
    return;
  }
  if (f.expr == FX_CONTENT) {                        // yeux rieurs : arc ∩ noir
    // TFT_eSPI : 0° = 6 h, sens horaire → 90..270 = moitié HAUTE du cercle
    g_tft.drawArc(cx, FACE_CY + 6, w / 2 - 8, w / 2 - 18, 90, 270, C_BG, C_BG);
    return;
  }

  // Iris (gros, comme les références) logé dans le ventre bas
  const int hb = (int)(h * (1.0f - LID_TOP));
  const int r = (int)(hb * IRIS_R);
  const int gx = (int)constrain(f.gaze, (float)-st.gazeMax, (float)st.gazeMax);
  // Le regard n'est PAS mirroité (inn ne sert qu'à la forme de l'amande et
  // au reflet) : sinon les deux iris convergent et le visage louche.
  // L'amplitude est bornée par expression (gazeMax) pour que l'iris reste
  // dans l'amande : sinon son effacement incrémental peint de l'orange sur
  // le fond (FACE_REVIEW.md constat 10).
  const int ix = cx + gx;
  const int iy = FACE_CY + (int)(hb * 0.30f);
  if (out) { out->x = ix; out->y = iy; out->r = r; out->slit = slit; out->inn = inn; out->valid = true; }
  if (slit) {
    const int ww = max(2, r / 4);
    if (out) out->w = ww;
    g_tft.fillRect(ix - ww, iy - r, 2 * ww + 1, 2 * r + 1, C_BG);
  } else {
    g_tft.fillCircle(ix, iy, r, C_BG);
    g_tft.fillCircle(ix - inn * r / 2, iy - r / 2, max(2, r / 5), col);  // reflet
  }
}

// Déplacement de l'iris seul : on repeint l'ancien à la couleur de l'œil
// (ce qui efface aussi son reflet) puis on dessine le nouveau. Coût ~2
// disques au lieu d'un redraw complet de la bande (mesuré : 28 ms → <1 ms).
void faceMoveIris(const IrisGeom& oldG, const IrisGeom& newG, uint16_t col) {
  if (!oldG.valid) return;
  if (oldG.slit) g_tft.fillRect(oldG.x - oldG.w, oldG.y - oldG.r, 2 * oldG.w + 1, 2 * oldG.r + 1, col);
  else           g_tft.fillCircle(oldG.x, oldG.y, oldG.r, col);
  if (!newG.valid) return;                           // iris disparu : effacé, c'est tout
  if (newG.slit) {
    g_tft.fillRect(newG.x - newG.w, newG.y - newG.r, 2 * newG.w + 1, 2 * newG.r + 1, C_BG);
  } else {
    g_tft.fillCircle(newG.x, newG.y, newG.r, C_BG);
    g_tft.fillCircle(newG.x - newG.inn * newG.r / 2, newG.y - newG.r / 2,
                     max(2, newG.r / 5), col);
  }
}

void faceDraw(const FaceFrame& f, IrisGeom* outL, IrisGeom* outR) {
  // Effacer SEULEMENT les deux zones d'yeux (et non toute la bande) : le bus
  // parallèle coûte ~2,5 Mpx/s. Boîte recalculée sur les vraies enveloppes
  // (max mesuré : Δy = -22,8 … +54,6 ; Δx = ±51,7) → Δy = -30 … +57, soit
  // 120x88 px, ~8,4 ms pour les deux. L'ancienne boîte (hauteur 100, haut à
  // -56) coupait le bas de CALME/SURPRISE/CLIN et laissait un résidu orange.
  g_tft.fillRect(FACE_CX_L - 60, FACE_CY - 30, 120, 88, C_BG);
  g_tft.fillRect(FACE_CX_R - 60, FACE_CY - 30, 120, 88, C_BG);
  const uint16_t col = f.red ? C_RED : C_ORANGE;
  if (f.expr == FX_CLIN) {                            // clin d'œil : gauche fermé
    g_tft.fillRect(FACE_CX_L - 34, FACE_CY - 2, 68, 4, col);
    faceDrawEye(FACE_CX_R, -1, f, outR);
    if (outL) outL->valid = false;
    return;
  }
  faceDrawEye(FACE_CX_L, +1, f, outL);
  faceDrawEye(FACE_CX_R, -1, f, outR);
}

// Écran STOP : dessiné en DEUX images (l'écran peut s'ouvrir pendant que le
// robot équilibre ; un fillScreen coûterait ~22 ms d'un coup).
void faceStopStep0() {                                // 1) efface les yeux
  g_tft.fillRect(FACE_CX_L - 60, FACE_CY - 30, 120, 88, C_BG);
  g_tft.fillRect(FACE_CX_R - 60, FACE_CY - 30, 120, 88, C_BG);
}

void faceStopStep1() {                                // 2) bouton + textes
  g_tft.fillRoundRect(STOP_X, STOP_Y, STOP_W, STOP_H, 16, C_ORANGE);
  g_tft.setTextDatum(MC_DATUM);
  g_tft.setTextColor(C_BG, C_ORANGE);
  g_tft.setTextSize(4);
  g_tft.drawString("STOP", STOP_X + STOP_W / 2, STOP_Y + STOP_H / 2);
  g_tft.setTextSize(1);
  g_tft.setTextDatum(TL_DATUM);
  char b[40];
  snprintf(b, sizeof(b), "PITCH %+.1f deg   %d Hz", g_state.pitchDeg,
           (int)(g_state.balanceHz + 0.5f));
  g_tft.setTextColor(C_DARK, C_BG);
  g_tft.drawString(b, 6, 8);
  g_tft.drawString("retour au visage", 60, 146);
  g_tft.fillRect(STOP_X, 160, STOP_W, 4, C_DARK);     // fond de barre
}

// Seule la barre (200x4 px = 800 px → 0,3 ms) change pendant les 6 s.
void faceUpdateStopBar(unsigned long resteMs) {
  const int bw = constrain((int)(STOP_W * (resteMs / (float)kStopHoldMs)), 0, STOP_W);
  g_tft.fillRect(STOP_X, 160, bw, 4, C_ORANGE);
  g_tft.fillRect(STOP_X + bw, 160, STOP_W - bw, 4, C_DARK);
}

// Le regard est quantifié par pas de 2 px (une seule fois, à la source) :
// deux fois moins de redessins d'iris pour un déplacement visuellement
// identique.
inline int gazeQ(float g) { return ((int)g / 2) * 2; }

// Expression courante + instant d'entrée : sert à l'hystérésis et à la durée
// de maintien minimale (FACE_REVIEW.md constat 5). Sans elles, le bruit gyro
// faisait changer d'expression plusieurs fois par seconde → un redraw complet
// de 14 ms à chaque image, soit ~280 ms/s volés à la boucle d'équilibre.
FaceExpr      s_exprCur   = FX_CALME;
unsigned long s_exprSince = 0;
constexpr unsigned long kExprHoldMs = 400;

// État émotionnel déduit du robot (aucun timer décoratif : tout est mesuré)
FaceFrame faceCompute() {
  FaceFrame f;
  const float pitch = g_state.pitchDeg;
  const float rate  = Balance::pitchRateDps();
  const float foot  = 0.5f * (g_state.footLDeg + g_state.footRDeg);
  const float ap    = fabsf(pitch), ar = fabsf(rate);
  // Seuils de sortie élargis quand on est déjà « content » : bande morte.
  const bool content = (s_exprCur == FX_CONTENT);

  if (!Balance::imuOk())          f.expr = FX_CHUTE;        // IMU muette
  else if (Balance::isFallen())   f.expr = FX_CHUTE;
  else if (g_state.batteryLow)  { f.expr = FX_MEFIANT; f.red = true; }
  else if (ar > 60.0f)            f.expr = FX_SURPRISE;
  else if (ap > 8.0f || ar > 40.0f) { f.expr = FX_ENERVE; f.red = true; }
  else if (g_state.obstacleWarn || fabsf(foot) > 20.0f) f.expr = FX_MEFIANT;
  else if (ap < (content ? 2.5f : 1.5f) && ar < (content ? 12.0f : 6.0f)) f.expr = FX_CONTENT;
  else if (ap > 3.0f)             f.expr = FX_PENCHE;
  else                            f.expr = FX_CALME;

  f.gaze = (float)gazeQ(constrain(pitch * 1.6f, -18.0f, 18.0f));  // suit le tangage
  return f;
}

// État du visage (blinks, clin d'œil de récupération, preview web)
unsigned long s_nextBlink = 0, s_blinkUntil = 0, s_winkUntil = 0, s_winkCooldown = 0;
bool          s_wasFallen = false;
FaceFrame     s_lastFrame;
// Aperçu web : écrit depuis la tâche du banc (cœur 0), lu par la boucle
// (cœur 1) → volatile, et s_faceForced publié EN DERNIER.
volatile bool          s_faceForced  = false;
volatile FaceExpr      s_forcedExpr  = FX_CALME;
volatile unsigned long s_forcedUntil = 0;
volatile bool          s_forcedSweep = false;   // aperçu : fait balayer le regard

// ── État du mode AUTO ──────────────────────────────────────────────
// Hoisté hors de uiAutoLoop() : faceEnter() doit pouvoir le réinitialiser
// sur le front MANUEL → AUTO (FACE_REVIEW.md constats 1, 2, 4, 7, 12).
bool          s_stopShown  = false;
uint8_t       s_stopStep   = 0;      // dessin du STOP en 2 images
unsigned long s_stopUntil  = 0;
unsigned long s_lastDraw   = 0;
bool          s_prevTouch  = false;
bool          s_drawnValid = false;
FaceFrame     s_drawn;
IrisGeom      s_irisL, s_irisR;
uint8_t       s_clearStep  = 0;      // effacement du pourtour en 4 bandes

// Entrée en mode AUTO : on repart d'un écran propre et d'un doigt « neutre ».
void faceEnter() {
  s_stopShown   = false;
  s_stopStep    = 0;
  s_drawnValid  = false;             // sinon le visage n'était pas redessiné
  s_lastDraw    = 0;
  s_clearStep   = 0;
  s_irisL.valid = s_irisR.valid = false;
  g_state.cmdForward = 0;            // aucune consigne héritée du mode MANUEL
  g_state.cmdTurn    = 0;
  g_touchLatch  = true;              // l'appui d'armement n'est pas un « tap »
}

// Sortie du mode AUTO : même verrou, pour que le doigt qui vient de toucher
// STOP ne soit pas relu comme un appui sur une flèche (le robot se ré-armait).
void faceLeave() {
  g_touchLatch = true;
  resetManualCaches();
}

bool sameFrame(const FaceFrame& a, const FaceFrame& b) {
  return a.expr == b.expr && a.red == b.red && a.blink == b.blink &&
         gazeQ(a.gaze) == gazeQ(b.gaze);
}

void readTouch() {
  const bool wasTouched = g_touchedRaw;
  g_touchedRaw = false;
  g_touchX = -1; g_touchY = -1;
  if (!g_touch || !g_touch->read()) return;

  // MULTI-TOUCH : le contrôleur peut annoncer 2 points ; on ne garde QUE le
  // point 0. getPoint(1) est de toute façon inutilisable : TouchLib le lit
  // dans raw_data[16..18] alors que le tampon fait 13 octets
  // (CSTSelfConstants.h:66-71 vs ModulesCSTSelf.tpp:128) — lecture hors
  // tableau. Ne pas « améliorer » cette fonction en itérant sur les points.
  if (g_touch->getPointNum() == 0) return;
  const TP_Point p = g_touch->getPoint(0);

  // Trame poubelle : le CST816 émet régulièrement (4095, 4095) = 0xFFF, son
  // motif « pas de donnée » — mesuré au banc (tools/touch_log.json, 3 trames
  // sur 11). Sans ce rejet, chaque trame fantôme passait pour un appui et
  // ouvrait l'écran STOP en mode AUTO. Marge large (WIDTH+40) pour ne pas
  // jeter un vrai tap sur le bord du verre.
  if (p.x > WIDTH + 40 || p.y > HEIGHT + 40) return;

  // ── Repère brut → repère écran (paysage 320×170, tft.setRotation(3)) ──
  // Le point sort de TouchLib DÉJÀ transposé par son setRotation(1) :
  // p.x court le long des 320 px, p.y en travers des 170 px. Mais la
  // transposition est une RÉFLEXION : elle met les axes en face l'un de
  // l'autre sans rien dire de leur sens. Le sens de l'axe long du CST816
  // est opposé à celui de l'axe x écran en rotation 3 : il faut donc un
  // miroir horizontal explicite (kTouchMirrorX). Aucune rotation ne peut le
  // faire à notre place — une rotation ne produit jamais une réflexion.
  // Symptôme d'origine : appuyer sur AVANT/GAUCHE tombait dans la zone du
  // bouton ÉQUILIBRE et ARMAIT le robot (TOUCH_REVIEW.md §1.7, C1).
  //
  // Bornage AVANT le miroir : une valeur aberrante (parasite I²C, bord du
  // verre ; p.x/p.y font 12 bits, jusqu'à 4095) est d'abord ramenée dans le
  // gabarit, donc son miroir y reste.
  int32_t x = constrain((int32_t)p.x, 0, WIDTH  - 1);   // 0..319
  int32_t y = constrain((int32_t)p.y, 0, HEIGHT - 1);   // 0..169
  if (kTouchMirrorX) x = (WIDTH  - 1) - x;
  if (kTouchMirrorY) y = (HEIGHT - 1) - y;

  g_touchedRaw = true;
  g_touchX = (int16_t)x;
  g_touchY = (int16_t)y;

  // Diagnostic : brut tel que rendu par TouchLib + transformé (lu par
  // /api/touch). PAS de Serial.printf ici : cette fonction tourne à 60 Hz
  // dans la boucle d'équilibre, et une écriture USB-CDC bloque dès que
  // l'hôte ne draine pas le port — c'est exactement le genre d'appel qui
  // peut figer la boucle.
  g_touchRawX  = (int16_t)p.x;  g_touchRawY  = (int16_t)p.y;
  g_touchLastX = g_touchX;      g_touchLastY = g_touchY;
  if (!wasTouched) g_touchSeq++;

  // Verrou de changement de mode : on consomme l'appui en cours jusqu'au
  // relâchement (le point reste mémorisé pour le diagnostic).
  if (g_touchLatch) {
    if (!g_touchedRaw) g_touchLatch = false;         // relâché : on reprend
    else { g_touchedRaw = false; g_touchX = g_touchY = -1; }
  }
}

// Mode AUTO : le visage occupe l'écran. Un tap ouvre l'écran STOP (retour
// automatique au visage) ; toucher STOP coupe l'équilibre. Les flèches de
// démo n'ont pas de sens ici : le robot est un balancier, pas un marcheur.
void uiAutoLoop() {
  const unsigned long now = millis();

  readTouch();
  const bool tap = g_touchedRaw && !s_prevTouch;
  s_prevTouch = g_touchedRaw;

  // Entrée en AUTO : effacer le pourtour de l'écran en 4 bandes (une par
  // image) pour ne jamais dépasser le budget de 15 ms — un fillScreen coûte
  // ~22 ms, et les deux zones d'yeux sont effacées par faceDraw().
  if (s_clearStep < 4) {
    switch (s_clearStep) {
      case 0: g_tft.fillRect(0,   0, WIDTH, 54, C_BG); break;   // bandeau + labels
      case 1: g_tft.fillRect(0, 142, WIDTH, 28, C_BG); break;   // bas des boutons
      case 2: g_tft.fillRect(0,  54, 41, 88, C_BG); break;      // bord gauche
      case 3: g_tft.fillRect(279, 54, 41, 88, C_BG); break;     // bord droit
    }
    s_clearStep++;
  }

  if (s_stopShown) {
    if (tap && g_touchX >= STOP_X && g_touchX < STOP_X + STOP_W &&
        g_touchY >= STOP_Y && g_touchY < STOP_Y + STOP_H) {
      g_state.cmdEnabled = false;                   // STOP = désarmement
      s_stopShown = false; s_drawnValid = false;
      return;
    }
    if ((long)(now - s_stopUntil) >= 0) {           // fin du sursis
      s_stopShown = false; s_drawnValid = false; return;
    }
    if (s_stopStep < 2) {                            // dessin en 2 images
      if (s_stopStep == 0) faceStopStep0(); else faceStopStep1();
      s_stopStep++;
      s_lastDraw = now;
      return;
    }
    if (now - s_lastDraw >= 200) {                   // seule la barre se vide
      s_lastDraw = now;
      faceUpdateStopBar(s_stopUntil - now);
    }
    return;
  }

  if (tap) {
    if (!Balance::isEnabled()) {                     // aperçu web : le tap rend la main
      s_faceForced = false;
      s_drawnValid = false;
      return;
    }
    s_stopShown = true;                              // tap → écran STOP
    s_stopUntil = now + kStopHoldMs;
    s_stopStep  = 0;
    s_lastDraw  = 0;
    return;
  }

  if (now - s_lastDraw < (1000 / kFaceHz)) return;  // 20 Hz max
  s_lastDraw = now;

  FaceFrame f;
  if (s_faceForced && now < s_forcedUntil) {
    f.expr = s_forcedExpr;
    f.red  = (s_forcedExpr == FX_ENERVE);
    if (s_forcedSweep) f.gaze = 18.0f * sinf(now * 0.004f);   // test du suivi
  } else {
    f = faceCompute();
  }

  // Durée de maintien minimale d'une expression (la chute passe tout de
  // suite) : le bruit gyro ne déclenche plus un redraw complet par image.
  if (f.expr != s_exprCur) {
    if (f.expr == FX_CHUTE || (long)(now - s_exprSince) >= (long)kExprHoldMs) {
      s_exprCur   = f.expr;
      s_exprSince = now;
    } else {
      f.expr = s_exprCur;
      f.red  = (f.expr == FX_ENERVE);
    }
  }

  // Clignements : un toutes les 3 à 6 s, 90 ms
  if ((long)(now - s_nextBlink) >= 0) {
    s_blinkUntil = now + 90;
    s_nextBlink  = now + 3000 + (now % 3000);
  }
  f.blink = now < s_blinkUntil;

  // Clin d'œil après une récupération (rare : 1×/30 s max)
  if (s_wasFallen && !Balance::isFallen() && (long)(now - s_winkCooldown) >= 0) {
    s_winkUntil    = now + 700;
    s_winkCooldown = now + 30000;
  }
  s_wasFallen = Balance::isFallen();
  if (now < s_winkUntil) f.expr = FX_CLIN;

  if (s_drawnValid && sameFrame(f, s_drawn)) return;

  // Rendu incrémental : le contour de l'amande ne change qu'au changement
  // d'expression ou de clignotement ; sinon SEUL l'iris se déplace
  // (mesuré : 14 ms pour un redraw complet → <1 ms pour un déplacement).
  const bool structChanged = !s_drawnValid || f.expr != s_drawn.expr ||
                             f.red != s_drawn.red || f.blink != s_drawn.blink;
  if (structChanged) {
    s_drawn = f;
    s_drawnValid = true;
    faceDraw(f, &s_irisL, &s_irisR);
    return;
  }
  if (gazeQ(f.gaze) == gazeQ(s_drawn.gaze)) return;  // rien n'a bougé
  s_drawn.gaze = f.gaze;
  const IrisGeom nl = faceIrisGeom(FACE_CX_L, +1, f);
  const IrisGeom nr = faceIrisGeom(FACE_CX_R, -1, f);
  const uint16_t col = f.red ? C_RED : C_ORANGE;
  faceMoveIris(s_irisL, nl, col);
  faceMoveIris(s_irisR, nr, col);
  s_irisL = nl;
  s_irisR = nr;
}

}  // namespace

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
  g_tft.drawString("PIED", 166, 54);   // angle moyen des pieds en arc
  g_tft.setTextColor(C_TEXT, C_BG);
  g_tft.drawString("0.0 deg", 48, 32);
  g_tft.drawString("0.00 V", 48, 44);
  g_tft.drawString("--", 206, 32);
  g_tft.drawString("MANUEL", 206, 44);
  g_tft.drawString("P:+0 deg", 206, 54);

  // Boutons
  for (int i = 0; i < g_zoneCount; i++) drawButton(i);
}

// Diagnostic tactile — cf. TOUCH_REVIEW.md §4.
Ui::TouchDebug Ui::touchDebug() {
  Ui::TouchDebug d;
  d.down = g_touchedRaw;
  d.rawX = g_touchRawX; d.rawY = g_touchRawY;
  d.x = g_touchLastX;   d.y = g_touchLastY;
  d.seq = g_touchSeq;
  d.mirrorX = kTouchMirrorX; d.mirrorY = kTouchMirrorY;
  return d;
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
  } else {
    g_touch->setRotation(1);  // aligne le repère touch sur le paysage
  }

  // Le tactile peut manquer (nappe débranchée) : l'écran reste utile en
  // télémétrie, et les flèches de consigne deviennent simplement inertes
  // (Ui::loop() remet les consignes à zéro tant que g_touch est nul). On
  // ne condamne donc PAS tout l'affichage à cause du touch.
  g_initialized = true;
  drawStatic();
  if (!g_touch) updateLabel(160, 8, 70, "TOUCH KO", C_RED);
  Serial.println(g_touch ? "UI TOUCH  : OK"
                         : "UI TOUCH  : ABSENT — télémétrie seule, boutons inertes");
  return true;
}

// ── loop() ────────────────────────────────────────────────────────
void Ui::loop() {
  if (!g_initialized) return;

  // ── 0. Mode AUTO (ou aperçu web) : le visage occupe l'écran ──────
  static bool s_wasAuto = false;
  const bool autoMode = Balance::isEnabled() ||
                        (s_faceForced && millis() < s_forcedUntil);
  if (autoMode) {
    if (!s_wasAuto) { s_wasAuto = true; faceEnter(); }   // front MANUEL → AUTO
    uiAutoLoop();
    return;
  }
  if (s_wasAuto) {                    // retour du visage : écran à redessiner
    s_wasAuto = false;
    faceLeave();                      // verrou tactile + caches du mode MANUEL
    drawStatic();
  }

  // ── 1. Lecture tactile (repère aligné dans readTouch : miroir X) ──
  readTouch();

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
        // Bascule le DRAPEAU d'armement : la boucle d'équilibre applique
        // (arrêt propre sur front descendant) et reste la SEULE à écrire
        // sur les servos. isEnabled() renvoie la demande → le bouton se
        // redessine immédiatement.
        g_state.cmdEnabled = !Balance::isEnabled();
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

  // 4a bis. Voyant du banc de réglage web : « WEB » vert dès qu'un
  // téléphone dialogue avec la carte (droite du titre, avant « IDLE »).
  {
    const int web = Tuner::active() ? 1 : 0;
    if (web != g_lastWeb) {
      g_lastWeb = web;
      updateLabel(136, 8, 20, web ? "WEB" : "", C_GREEN);
    }
  }

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

  // 4b bis. Angle moyen des pieds en arc — sert à voir venir la butée
  // (±45° côté firmware) et à vérifier que le recentrage fait son
  // travail : en équilibre stable, P doit osciller autour de 0.
  {
    const int foot = (g_state.footLDeg + g_state.footRDeg) / 2;
    if (foot != g_lastFoot) {
      g_lastFoot = foot;
      char b[16];
      snprintf(b, sizeof(b), "P:%+d deg", foot);
      updateLabel(206, 54, 76, b, abs(foot) >= 30 ? C_ORANGE : C_TEXT);
    }
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
  else if (g_state.batteryLow)   state = 5;   // armement refusé (cf. balance.cpp)
  else if (g_state.obstacleWarn) state = 4;
  else if (g_state.balancing)    state = 1;
  else if (Balance::isEnabled()) state = 3;
  if (state != g_lastState) {
    g_lastState = state;
    const char* s = "IDLE";
    uint16_t col = C_DARK;
    switch (state) {
      case 1: s = "BALANCING";   col = C_GREEN;  break;
      case 2: s = "CHUTE";       col = C_RED;    break;
      case 3: s = "ARME";        col = C_ORANGE; break;
      case 4: s = "OBST.";       col = C_ORANGE; break;
      case 5: s = "BAT. FAIBLE"; col = C_RED;    break;
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
    int hz = static_cast<int>(g_state.balanceHz + 0.5f);
    if (hz != g_lastHz || g_state.dbgUiMs != g_lastDbgUi || g_state.dbgHeadMs != g_lastDbgHead) {
      g_lastHz = hz;
      g_lastDbgUi = g_state.dbgUiMs;
      g_lastDbgHead = g_state.dbgHeadMs;
      uint16_t col = hz >= 180 ? C_GREEN : (hz >= 100 ? C_ORANGE : C_RED);
      char b[24];
      if (hz <= 0) snprintf(b, sizeof(b), "B:-- U:%u H:%u", g_lastDbgUi, g_lastDbgHead);
      else         snprintf(b, sizeof(b), "B:%d U:%u H:%u", hz, g_lastDbgUi, g_lastDbgHead);
      updateLabel(6, 54, 150, b, col);
    }
  }
}

// Aperçu du visage SANS armer (banc web) : sert à valider les expressions
// sur l'écran réel sans risque. expr = index (0..7 : calme, penché,
// méfiant, énervé, surprise, content, clin d'œil, chute), ms = durée.
void Ui::previewFace(uint8_t expr, unsigned long ms, bool sweep) {
  s_forcedExpr  = (FaceExpr)constrain((int)expr, 0, (int)FX_CHUTE);
  s_forcedSweep = sweep;
  // 60 s maxi : sans borne, /api/face?t=100000 confisquait l'écran pendant
  // 27 h et rendait l'écran MANUEL inaccessible (FACE_REVIEW.md constat 9).
  s_forcedUntil = millis() + (ms > 60000UL ? 60000UL : ms);
  s_faceForced  = true;              // publié EN DERNIER (cœur 0 → cœur 1)
}
