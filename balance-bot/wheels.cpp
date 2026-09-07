// ═══════════════════════════════════════════════════════════════════
// BalanceBot — module A · roues SG90 « rotation continue »
//
// Un SG90 modifié n'asservit plus la position mais la VITESSE :
//   1500 µs ≈ arrêt · 2000 µs = pleine vitesse dans un sens
//   1000 µs = pleine vitesse dans l'autre.
// Le vrai point d'arrêt dépend du potentiomètre interne de chaque
// servo : c'est kNeutralUsL / kNeutralUsR qu'on règle à la main
// (cf. procédure de calibration en bas de fichier).
//
// Les deux roues sont montées en miroir : à commande identique elles
// tournent en sens opposé dans le repère du robot. L'inversion de la
// roue gauche est faite ICI, une fois pour toutes, pour que balance.cpp
// raisonne en « avant / arrière » du robot.
// ═══════════════════════════════════════════════════════════════════
#include "wheels.h"
#include "config.h"

#include <ESP32Servo.h>

namespace {

// ── CALIBRATION — à ajuster servo par servo ────────────────────────
// Point d'arrêt réel de chaque roue (µs). Procédure :
//   1. flasher, laisser le robot désactivé (roues au neutre),
//   2. si une roue rampe, décaler sa constante de ±5 µs jusqu'à l'arrêt,
//   3. si elle ne s'arrête jamais, régler le potentiomètre du SG90.
constexpr int kNeutralUsL = 1500;
constexpr int kNeutralUsR = 1500;

// Débattement autour du neutre. 500 µs = pleine vitesse.
constexpr int kSpanUs   = 500;
constexpr int kMinUs    = 1000;   // butées absolues envoyées au servo
constexpr int kMaxUs    = 2000;

// Sens de rotation : +1 si une impulsion > neutre fait avancer le robot.
// Inverser si une roue part à l'envers après montage.
constexpr int kDirL = -1;         // roue gauche montée en miroir
constexpr int kDirR = +1;

// Amplitude max de la commande signée acceptée (domaine PID).
constexpr int kSpeedMax = 90;

Servo s_left;
Servo s_right;
bool  s_ready = false;

inline int clampi(int v, int lo, int hi) { return v < lo ? lo : (v > hi ? hi : v); }

// vitesse signée (-90..+90, avant = positif) → impulsion µs
inline int speedToUs(int speed, int neutralUs, int dir) {
  speed = clampi(speed, -kSpeedMax, kSpeedMax);
  const int us = neutralUs + dir * (speed * kSpanUs) / kSpeedMax;
  return clampi(us, kMinUs, kMaxUs);
}

} // namespace

namespace Wheels {

bool begin() {
  // Timers 0 et 1 pour les roues ; 2 et 3 restent libres pour la tête
  // (module C). Un timer LEDC/MCPWM par paire de servos.
  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);

  s_left.setPeriodHertz(50);          // 50 Hz = période 20 ms des SG90
  s_right.setPeriodHertz(50);

  s_left.attach(SERVO_WHEEL_L, kMinUs, kMaxUs);
  s_right.attach(SERVO_WHEEL_R, kMinUs, kMaxUs);
  // attach() renvoie le n° de canal PWM, qui peut valoir 0 légitimement :
  // c'est attached() qui dit si le pin a bien été pris.
  s_ready = s_left.attached() && s_right.attached();

  stop();                             // jamais de démarrage roues vives
  return s_ready;
}

void driveSigned(int leftSpeed, int rightSpeed) {
  if (!s_ready) return;
  s_left.writeMicroseconds(speedToUs(leftSpeed,  kNeutralUsL, kDirL));
  s_right.writeMicroseconds(speedToUs(rightSpeed, kNeutralUsR, kDirR));
}

void stop() {
  if (!s_ready) return;
  s_left.writeMicroseconds(kNeutralUsL);
  s_right.writeMicroseconds(kNeutralUsR);
}

bool ready() { return s_ready; }

} // namespace Wheels
