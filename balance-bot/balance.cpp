// ═══════════════════════════════════════════════════════════════════
// BalanceBot — module A · boucle d'équilibre (API publique Balance::)
//
// Pendule inversé : le robot reste debout en déplaçant son point
// d'appui sous son centre de gravité. Il penche vers l'avant ⇒ les
// roues avancent pour « rattraper » la chute, et réciproquement.
//
//   pitch (IMU) ──► erreur = consigne − pitch ──► PID ──► vitesse roues
//                                        ▲
//                    cmdForward (UI) ────┘  (avancer = incliner la consigne)
//                    cmdTurn    (UI) ─────► différentiel gauche/droite
//
// Cadencé à BALANCE_LOOP_HZ (200 Hz) par le .ino ; aucun delay() ici.
// ═══════════════════════════════════════════════════════════════════
#include <Arduino.h>

#include "config.h"
#include "interfaces.h"
#include "imu.h"
#include "wheels.h"

namespace {

// ═══════════════════ RÉGLAGE PID — commencer ici ═══════════════════
// Unités : erreur en degrés, sortie en « vitesse roue » (-90..+90,
// 90 = pleine vitesse). Gains de départ pour un châssis léger sur
// SG90 rotation continue — à affiner sur le robot réel.
//
// Procédure de réglage (robot tenu à la main, Ki = Kd = 0) :
//   1. monter Kp jusqu'à ce que le robot réagisse vif mais oscille ;
//   2. monter Kd pour amortir l'oscillation (trop → tremblement aigu) ;
//   3. monter Ki juste assez pour effacer la dérive lente / la pente.
constexpr float kKp = 8.0f;    // vitesse par degré d'erreur
constexpr float kKi = 20.0f;   // vitesse par (degré · seconde) d'erreur
constexpr float kKd = 0.35f;   // vitesse par (degré / seconde) — sur le gyro

// Consigne d'équilibre : angle auquel le robot tient réellement debout.
// Décaler de quelques dixièmes si le robot dérive toujours du même côté.
constexpr float kSetpointDeg = 0.0f;

// ── Anti-windup ────────────────────────────────────────────────────
// Le terme intégral est borné en unités de sortie, et gelé quand la
// commande sature : sinon il se charge pendant une chute et renvoie le
// robot de l'autre côté au redressement.
constexpr float kIntegralMax = 25.0f;

// ── Morts-zones ────────────────────────────────────────────────────
// Erreur : sous ce seuil on considère le robot vertical (pas de P/I),
// évite le tremblement permanent dû au bruit de l'IMU.
constexpr float kErrDeadbandDeg = 0.25f;
// Sortie : un SG90 ne bouge pas sous ~8 unités mais grésille. En
// dessous de kOutDeadband on coupe franchement ; au-dessus on relève
// la commande à kOutMinDrive pour franchir le frottement sec.
constexpr float kOutDeadband  = 2.0f;
constexpr float kOutMinDrive  = 8.0f;
constexpr float kOutMax       = 90.0f;

// ── Pilotage depuis l'UI ───────────────────────────────────────────
// Avancer = incliner la consigne dans le sens de la marche.
// 100 (plein gaz) → 6° d'inclinaison : au-delà le robot décroche.
constexpr float kTiltPerCmd  = 0.06f;   // ° par unité de cmdForward
constexpr float kTurnPerCmd  = 0.30f;   // unités de sortie par unité de cmdTurn
constexpr float kCmdSlewPerS = 200.0f;  // lissage des consignes UI (unités/s)

// ── Sécurité ───────────────────────────────────────────────────────
constexpr float        kFallAngleDeg    = 45.0f;  // au-delà : chute
constexpr float        kRecoverAngleDeg = 10.0f;  // redressé sous cet angle…
constexpr unsigned long kRecoverHoldMs  = 700;    // …et stable ce temps-là
constexpr float        kDtMinS = 0.0005f;         // bornes de dt (protection
constexpr float        kDtMaxS = 0.050f;          //  contre les hoquets)

// ═══════════════════════════════════════════════════════════════════

// PID minimal, dérivée prise sur la MESURE (gyro) et non sur l'erreur :
// pas de « derivative kick » quand l'UI change la consigne, et le gyro
// donne la vitesse angulaire sans dériver numériquement un signal bruité.
struct Pid {
  float integral = 0.0f;

  void reset() { integral = 0.0f; }

  float update(float error, float rateDps, float dt) {
    const float p = kKp * error;
    const float d = -kKd * rateDps;

    // Intégration conditionnelle : on n'accumule que si la sortie qui
    // en résulterait reste dans la plage utile (anti-windup).
    const float candidate =
        constrain(integral + kKi * error * dt, -kIntegralMax, kIntegralMax);
    const float rawWithCandidate = p + candidate + d;
    if (fabsf(rawWithCandidate) < kOutMax || (rawWithCandidate * error) < 0.0f) {
      integral = candidate;
    }
    return p + integral + d;
  }
};

Pid   s_pid;
bool  s_enabled   = false;
bool  s_imuOk     = false;
bool  s_fallen    = false;         // verrou de chute (le robot ne se débat pas)
float s_fwdSmooth = 0.0f;          // consignes UI lissées
float s_turnSmooth= 0.0f;
unsigned long s_lastMicros   = 0;
unsigned long s_uprightSince = 0;  // début de la fenêtre de redressement

inline float slew(float current, float target, float maxStep) {
  const float delta = target - current;
  if (delta >  maxStep) return current + maxStep;
  if (delta < -maxStep) return current - maxStep;
  return target;
}

// Coupe tout : roues au neutre, intégrateur vidé, état partagé à jour.
void halt() {
  Wheels::stop();
  s_pid.reset();
  s_fwdSmooth = 0.0f;
  s_turnSmooth = 0.0f;
  g_state.balancing = false;
}

// Applique la mort-zone de sortie (frottement sec des SG90).
inline float shapeOutput(float out) {
  if (fabsf(out) < kOutDeadband) return 0.0f;
  const float sign = (out > 0.0f) ? 1.0f : -1.0f;
  const float mag  = kOutMinDrive +
                     (fabsf(out) - kOutDeadband) *
                     (kOutMax - kOutMinDrive) / (kOutMax - kOutDeadband);
  return sign * constrain(mag, 0.0f, kOutMax);
}

} // namespace

namespace Balance {

bool begin() {
  s_enabled = false;
  s_fallen  = false;
  s_lastMicros = micros();

  // Les roues d'abord : même sans IMU on veut pouvoir les tenir au
  // neutre (et l'UI reste utilisable en mode démo).
  Wheels::begin();
  Wheels::stop();

  s_imuOk = Imu::begin();
  if (!s_imuOk) {
    g_state.balancing = false;
    g_state.pitchDeg  = 0.0f;
    return false;                    // → le .ino annonce « mode démo UI »
  }

  // Calibration du neutre : biais gyro mesuré robot posé, immobile.
  Imu::calibrate();
  g_state.pitchDeg = Imu::pitchDeg();
  return true;
}

void loop() {
  // Le .ino appelle loop() en continu (200 Hz). L'asservissement ne
  // s'active que si isEnabled(), mais la MESURE IMU a toujours lieu :
  // le PITCH affiché par l'UI doit vivre même robot posé à l'arrêt.

  // ── Fréquence RÉELLE d'appel (debug UI) ─────────────────────────
  // Compte les appels sur une fenêtre glissante de 1 s. Si l'UI ou la
  // tête (mêmes ressources I2C/CPU) ralentissent la loop, on le voit ici.
  {
    static unsigned long s_count = 0;
    static unsigned long s_winMs = millis();
    s_count++;
    const unsigned long nowMs = millis();
    const unsigned long span = nowMs - s_winMs;
    if (span >= 1000) {
      g_state.balanceHz = s_count * 1000.0f / (float)span;
      s_count = 0;
      s_winMs = nowMs;
    }
  }

  const bool want = isEnabled();
  if (!s_enabled && want) {          // front montant : on repart propre
    s_pid.reset();
    s_lastMicros = micros();
    s_uprightSince = 0;
  }
  s_enabled = want;

  if (!s_imuOk) {
    halt();
    return;
  }

  // ── dt réel (le .ino cadence à ~5 ms, mais ne le suppose pas) ────
  const unsigned long now = micros();
  float dt = (now - s_lastMicros) * 1e-6f;   // le calcul non signé gère le rollover
  s_lastMicros = now;
  dt = constrain(dt, kDtMinS, kDtMaxS);

  // ── Mesure ───────────────────────────────────────────────────────
  Imu::update(dt);                   // trame perdue : l'angle précédent tient
  const float pitch = Imu::pitchDeg();
  const float rate  = Imu::pitchRateDps();
  g_state.pitchDeg  = pitch;

  // À l'arrêt (équilibre OFF) : on a mesuré pour l'affichage, on ne
  // pilote rien. Pas de halt() non plus : roues déjà au neutre.
  if (!s_enabled) return;

  // ── Sécurité : chute ─────────────────────────────────────────────
  if (fabsf(pitch) > kFallAngleDeg) {
    s_fallen = true;
    s_uprightSince = 0;
    halt();                          // roues au neutre : pas de gigotage au sol
    return;
  }
  if (s_fallen) {
    // Redressement manuel : il faut être vertical ET stable un moment
    // avant de relancer l'asservissement.
    if (fabsf(pitch) < kRecoverAngleDeg) {
      const unsigned long ms = millis();
      if (s_uprightSince == 0) s_uprightSince = ms;
      if (ms - s_uprightSince >= kRecoverHoldMs) {
        s_fallen = false;
        s_pid.reset();
      }
    } else {
      s_uprightSince = 0;
    }
    if (s_fallen) { halt(); return; }
  }

  // ── Consignes UI (lissées : un cran brutal fait décrocher) ───────
  int cmdFwd = constrain(g_state.cmdForward, -100, 100);
  const int cmdTurn = constrain(g_state.cmdTurn, -100, 100);
  // Obstacle détecté par le module C : on interdit la marche avant,
  // la marche arrière et l'équilibre restent actifs.
  if (g_state.obstacleWarn && cmdFwd > 0) cmdFwd = 0;

  const float maxStep = kCmdSlewPerS * dt;
  s_fwdSmooth  = slew(s_fwdSmooth,  (float)cmdFwd,  maxStep);
  s_turnSmooth = slew(s_turnSmooth, (float)cmdTurn, maxStep);

  // ── PID ──────────────────────────────────────────────────────────
  // Pour avancer, le robot doit d'abord se pencher vers l'avant :
  // on décale la consigne d'angle, le PID fait le reste.
  const float setpoint = kSetpointDeg + s_fwdSmooth * kTiltPerCmd;
  float error = setpoint - pitch;
  if (fabsf(error) < kErrDeadbandDeg) error = 0.0f;   // mort-zone d'erreur

  float out = s_pid.update(error, rate, dt);
  out = constrain(out, -kOutMax, kOutMax);
  out = shapeOutput(out);

  // ── Différentiel de rotation ─────────────────────────────────────
  const float turn = s_turnSmooth * kTurnPerCmd;
  const float left  = constrain(out + turn, -kOutMax, kOutMax);
  const float right = constrain(out - turn, -kOutMax, kOutMax);

  Wheels::driveSigned((int)lroundf(left), (int)lroundf(right));
  g_state.balancing = true;
}

void setEnabled(bool on) {
  s_enabled = on;
  g_state.cmdEnabled = on;           // miroir pour l'UI (module B)
  if (on) {
    s_pid.reset();
    s_fallen = false;
    s_uprightSince = 0;
    s_lastMicros = micros();
  } else {
    halt();
  }
}

// L'UI peut activer le mode auto en écrivant g_state.cmdEnabled sans
// passer par setEnabled() : les deux sources sont acceptées, sinon le
// .ino n'appellerait jamais loop().
bool isEnabled() { return s_enabled || g_state.cmdEnabled; }

// Verrou de chute : vrai tant que le robot n'a pas été redressé et tenu
// vertical kRecoverHoldMs. L'UI s'en sert pour afficher « CHUTE » (et
// pour ne PAS confondre avec un simple obstacle).
bool isFallen() { return s_fallen; }

bool imuOk() { return s_imuOk; }

} // namespace Balance
