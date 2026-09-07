// ═══════════════════════════════════════════════════════════════════
// BalanceBot — module A · pieds en arc sur SG90 STANDARD (position)
//
// Mécanique (chassis/FIT_NOTES.md §9) : plus de roues. Chaque pied est
// un arc de cercle de rayon R = 32.5 mm, ouverture 200°, vissé sur le
// palonnier du servo. L'arc ROULE sur le sol : quand le servo tourne de
// φ, le robot se déplace de R·φ (32.5 mm par radian, soit 0.567 mm par
// degré de pied).
//
// NEUTRE MÉCANIQUE — décision documentée :
//   servo à 90° (kServoNeutralDeg) = milieu de l'arc vers le bas =
//   point de contact exactement sous l'axe = robot vertical.
//   C'est la position d'assemblage imposée par FIT_NOTES §9. On pose
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
// Le servo ne connaît que la POSITION : ce module intègre la vitesse
// demandée par le PID (°/s) en position (°), au dt réel.
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
// l'inversion du gauche — même convention que l'ancien wheels.cpp.
constexpr float kDirL = -1.0f;
constexpr float kDirR = +1.0f;

// ── Bornes de sécurité ─────────────────────────────────────────────
constexpr float kFootHardDeg = 45.0f;      // butée dure interne (voir en-tête)
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
  if (s_ready) writePositions();        // robot droit dès le boot
  return s_ready;
}

void driveFootSpeed(int leftDegS, int rightDegS) {
  if (!s_ready) return;

  const unsigned long now = micros();
  float dt = (now - s_lastMicros) * 1e-6f;   // non signé : gère le rollover
  s_lastMicros = now;
  dt = clampf(dt, kDtMinS, kDtMaxS);

  const float vL = clampf((float)leftDegS,  -kSpeedMaxDegS, kSpeedMaxDegS);
  const float vR = clampf((float)rightDegS, -kSpeedMaxDegS, kSpeedMaxDegS);

  s_footL = clampf(s_footL + vL * dt, -kFootHardDeg, kFootHardDeg);
  s_footR = clampf(s_footR + vR * dt, -kFootHardDeg, kFootHardDeg);

  writePositions();
}

void stop() {
  if (!s_ready) return;
  // Position CONSERVÉE : un retour au neutre ferait basculer le robot.
  // On réécrit quand même la consigne pour que le servo tienne son
  // couple, et on repart d'un dt propre au prochain driveFootSpeed().
  s_lastMicros = micros();
  writePositions();
}

void recenterNow() {
  if (!s_ready) return;
  s_footL = 0.0f;
  s_footR = 0.0f;
  s_lastMicros = micros();
  writePositions();
}

float angleL()   { return s_footL; }
float angleR()   { return s_footR; }
float angleAvg() { return 0.5f * (s_footL + s_footR); }

bool ready() { return s_ready; }

} // namespace Feet
