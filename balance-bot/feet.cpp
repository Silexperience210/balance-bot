// ═══════════════════════════════════════════════════════════════════
// BalanceBot — module A · pieds en arc (SG90 position OU servo continu)
//
// Mécanique (chassis/NOTES_v3.md) : plus de roues. Chaque pied est
// un arc de cercle de rayon R = 32.5 mm, ouverture 200°, vissé sur le
// palonnier du servo. L'arc ROULE sur le sol : quand le servo tourne de
// φ, le robot se déplace de R·φ (32.5 mm par radian, soit 0.567 mm par
// degré de pied).
//
// NEUTRE MÉCANIQUE — décision documentée :
//   servo à 90° (kServoNeutralDeg) = milieu de l'arc vers le bas =
//   point de contact exactement sous l'axe = robot vertical.
//   C'est la position d'assemblage imposée par NOTES_v3.md. On pose
//   donc « angle de pied = 0 » ⇔ « servo = 90° », et l'angle de repos
//   du robot droit vaut 0.0°.
//
// DÉBATTEMENT — l'arc couvre ±100° autour du bas, le servo ±90° : il
// reste 10° de marge mécanique. La butée DURE interne de ce module est
// volontairement plus serrée (±kFootHardDeg = 45°) : c'est un garde-fou
// de dernier recours. La limite fine, qui dépend du tangage courant,
// est calculée par balance.cpp (le pied et le corps consomment le même
// arc : contact ≈ φ + θ).
//
// DEUX MATÉRIELS, un seul module — choisis par FEET_MODE_CONTINUOUS
// (config.h) :
//   • mode POSITION (=0, SG90 standard) : le servo ne connaît que la
//     POSITION. Ce module intègre la vitesse demandée par le PID (°/s)
//     en position (°), au dt réel, et écrit l'angle.
//   • mode CONTINU (=1, servo 360°) : le servo ne connaît que la
//     VITESSE (1500 µs = arrêt). La consigne du PID est déjà une
//     vitesse : elle part DIRECTEMENT au servo. L'équilibre y devient
//     réellement tenable, le moteur fournissant un couple continu.
// Dans LES DEUX cas φ (position du pied) reste intégré ici : l'arc a une
// course finie même quand le moteur n'en a plus, et c'est φ que lisent la
// butée dure interne et le soft clamp de balance.cpp (Feet::angleAvg()).
// ═══════════════════════════════════════════════════════════════════
#include "feet.h"
#include "config.h"

#include <ESP32Servo.h>

namespace {

// ── CALIBRATION servo — à ajuster servo par servo ──────────────────
// Plage d'impulsion d'un SG90 STANDARD sur 0..180°. On pilote en
// microsecondes (et non en write(deg) entier) pour ne pas perdre la
// résolution du pied : 11.1 µs/° ici contre 1° de quantification.
//   1. flasher, robot désactivé : les deux pieds doivent être au repos,
//      milieu de l'arc pile sous l'axe (robot droit) ;
//   2. si un pied est décalé, corriger d'abord le calage du palonnier
//      (4 positions à 90°), puis affiner avec kTrimDegL/R.
constexpr float kServoMinUs   = 500.0f;    // 0°
constexpr float kServoMaxUs   = 2500.0f;   // 180°
constexpr float kServoNeutralDeg = 90.0f;  // pied à 0° (cf. en-tête)
constexpr float kTrimDegL = 0.0f;          // retouche fine du neutre (°)
constexpr float kTrimDegR = 0.0f;

// Sens : +1 si un angle de pied POSITIF (= pousse vers l'avant) demande
// un angle de servo croissant. Les deux servos sont montés en miroir
// (chassis : le gauche est le droit tourné de 180° autour de Y), d'où
// l'inversion du gauche.
constexpr float kDirL = -1.0f;
constexpr float kDirR = +1.0f;

// ── Bornes de sécurité ─────────────────────────────────────────────
constexpr float kFootHardDeg = FOOT_HARD_DEG;  // butée dure — SOURCE : config.h
constexpr float kSpeedMaxDegS = 400.0f;    // au-delà, un SG90 ne suit pas
// Bornes de dt, identiques à balance.cpp : protection contre les hoquets
// de boucle (un dt aberrant ferait sauter le pied d'un bloc).
constexpr float kDtMinS = 0.0005f;
constexpr float kDtMaxS = 0.050f;

Servo s_left;
Servo s_right;
bool  s_ready = false;

// Position des pieds dans le repère ROBOT (0 = repos, + = avant).
float s_footL = 0.0f;
float s_footR = 0.0f;

unsigned long s_lastMicros = 0;

inline float clampf(float v, float lo, float hi) {
  return v < lo ? lo : (v > hi ? hi : v);
}

// angle de pied (repère robot) → impulsion µs pour un servo donné
inline int footToUs(float footDeg, float dir, float trimDeg) {
  const float servoDeg =
      clampf(kServoNeutralDeg + dir * footDeg + trimDeg, 0.0f, 180.0f);
  const float us = kServoMinUs + servoDeg * (kServoMaxUs - kServoMinUs) / 180.0f;
  return (int)lroundf(us);
}

// Écrit les deux positions courantes sur les servos.
void writePositions() {
  s_left.writeMicroseconds(footToUs(s_footL, kDirL, kTrimDegL));
  s_right.writeMicroseconds(footToUs(s_footR, kDirR, kTrimDegR));
}

#if FEET_MODE_CONTINUOUS
// ── CALIBRATION servo à ROTATION CONTINUE ──────────────────────────
// Un servo 360° interprète l'impulsion comme une VITESSE : 1500 µs =
// arrêt, plus court = un sens, plus long = l'autre, saturation vers
// ±500 µs d'écart. Il n'y a AUCUN asservissement de position dedans.
//
// kUsPerDegS — conversion vitesse de pied (°/s) → écart au neutre (µs).
//   Valeur par défaut 1.0 : les ±400 °/s de kSpeedMaxDegS occupent alors
//   ±400 µs, soit à peu près toute la plage utile. À CALIBRER au premier
//   test réel : envoyer une consigne à pleine vitesse et vérifier que le
//   servo tourne à son maximum sans écrêter, c.-à-d. que la commande
//   consomme ~±400-500 µs. Un servo plus lent (moins de °/s à pleine
//   commande) demande un kUsPerDegS PLUS GRAND.
// kTrimUsL/R — le « 1500 µs » réel n'est jamais exact : sans consigne, un
//   servo continu rampe doucement. Après montage, corriger ici jusqu'à
//   l'arrêt franc, servo par servo (typiquement quelques dizaines de µs).
// kDeadbandDegS — sous ce seuil on écrit le neutre EXACT : une consigne
//   minuscule ne fait pas tourner le servo mais le fait vibrer/dériver.
constexpr float kNeutralUs    = 1500.0f;
constexpr float kUsPerDegS    = 1.0f;
constexpr float kTrimUsL      = 0.0f;
constexpr float kTrimUsR      = 0.0f;
constexpr float kDeadbandDegS = 5.0f;
constexpr float kCmdMaxUs     = 500.0f;   // saturation de la plage servo

// vitesse de pied (repère robot, °/s) → impulsion µs pour un servo donné.
// Le sens (kDirL/kDirR) reste celui du montage en miroir : il s'applique
// à la vitesse exactement comme il s'appliquait à la position.
inline int speedToUs(float vDegS, float dir, float trimUs) {
  float cmdUs = 0.0f;
  if (fabsf(vDegS) >= kDeadbandDegS) {
    cmdUs = clampf(dir * vDegS * kUsPerDegS, -kCmdMaxUs, kCmdMaxUs);
  }
  return (int)lroundf(kNeutralUs + trimUs + cmdUs);
}

// Écrit les deux vitesses courantes sur les servos.
void writeSpeeds(float vL, float vR) {
  s_left.writeMicroseconds(speedToUs(vL, kDirL, kTrimUsL));
  s_right.writeMicroseconds(speedToUs(vR, kDirR, kTrimUsR));
}

// Arrêt franc des deux servos (neutre + trim).
void writeNeutral() { writeSpeeds(0.0f, 0.0f); }
#endif // FEET_MODE_CONTINUOUS

} // namespace

namespace Feet {

bool begin() {
  // Timers 0 et 1 pour les pieds ; 2 et 3 restent libres pour la tête
  // (module C). Inchangé par rapport à wheels.cpp.
  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);

  s_left.setPeriodHertz(50);            // 50 Hz = période 20 ms des SG90
  s_right.setPeriodHertz(50);

  s_left.attach(SERVO_FOOT_L, (int)kServoMinUs, (int)kServoMaxUs);
  s_right.attach(SERVO_FOOT_R, (int)kServoMinUs, (int)kServoMaxUs);
  // attach() renvoie le n° de canal PWM, qui peut valoir 0 légitimement :
  // c'est attached() qui dit si le pin a bien été pris.
  s_ready = s_left.attached() && s_right.attached();

  s_footL = 0.0f;
  s_footR = 0.0f;
  s_lastMicros = micros();
#if FEET_MODE_CONTINUOUS
  if (s_ready) writeNeutral();          // servos à l'arrêt dès le boot
#else
  if (s_ready) writePositions();        // robot droit dès le boot
#endif
  return s_ready;
}

void driveFootSpeed(int leftDegS, int rightDegS) {
  if (!s_ready) return;

  const unsigned long now = micros();
  float dt = (now - s_lastMicros) * 1e-6f;   // non signé : gère le rollover
  s_lastMicros = now;
  dt = clampf(dt, kDtMinS, kDtMaxS);

  float vL = clampf((float)leftDegS,  -kSpeedMaxDegS, kSpeedMaxDegS);
  float vR = clampf((float)rightDegS, -kSpeedMaxDegS, kSpeedMaxDegS);

  // Intégration de φ — conservée dans les DEUX modes : en continu elle ne
  // pilote plus le servo, mais elle reste la seule mesure de la course
  // consommée sur l'arc (butée dure ci-dessous, soft clamp de balance.cpp).
  s_footL = clampf(s_footL + vL * dt, -kFootHardDeg, kFootHardDeg);
  s_footR = clampf(s_footR + vR * dt, -kFootHardDeg, kFootHardDeg);

#if FEET_MODE_CONTINUOUS
  // En position, écrêter φ suffisait à arrêter le pied à la butée. En
  // continu le moteur, lui, continuerait de tourner : il faut couper
  // explicitement la commande qui pousse au-delà.
  if (s_footL >=  kFootHardDeg && vL > 0.0f) vL = 0.0f;
  if (s_footL <= -kFootHardDeg && vL < 0.0f) vL = 0.0f;
  if (s_footR >=  kFootHardDeg && vR > 0.0f) vR = 0.0f;
  if (s_footR <= -kFootHardDeg && vR < 0.0f) vR = 0.0f;
  writeSpeeds(vL, vR);
#else
  writePositions();
#endif
}

void stop() {
  if (!s_ready) return;
  s_lastMicros = micros();
#if FEET_MODE_CONTINUOUS
  // Continu : « la dernière position » n'existe pas — la seule commande
  // d'arrêt est le neutre 1500 µs. φ reste à sa valeur : le pied ne
  // bouge plus, la course consommée sur l'arc non plus.
  writeNeutral();
#else
  // Position CONSERVÉE : un retour au neutre ferait basculer le robot.
  // On réécrit quand même la consigne pour que le servo tienne son
  // couple, et on repart d'un dt propre au prochain driveFootSpeed().
  writePositions();
#endif
}

void recenterNow() {
  if (!s_ready) return;
  s_footL = 0.0f;
  s_footR = 0.0f;
  s_lastMicros = micros();
#if FEET_MODE_CONTINUOUS
  // Continu : rien à « ramener » physiquement — le servo n'a pas de
  // position de consigne, et faire tourner les pieds pour rejoindre un
  // zéro qu'on ne mesure pas n'aurait aucun sens. On remet seulement le
  // compteur de course φ à zéro, SANS écrire : l'appelant tient le robot
  // à la main après une chute et les servos sont déjà au neutre (stop()
  // via halt()). Le zéro de φ est donc conventionnel — il est redéfini
  // « ici, maintenant », ce qui est exactement ce que veut le soft clamp.
#else
  writePositions();
#endif
}

float angleL()   { return s_footL; }
float angleR()   { return s_footR; }
float angleAvg() { return 0.5f * (s_footL + s_footR); }

bool ready() { return s_ready; }

} // namespace Feet
