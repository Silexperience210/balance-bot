// ═══════════════════════════════════════════════════════════════════
// BalanceBot — Module C : Tête pan/tilt + Ultrason (head.cpp)
// Carte : LilyGo T-Display-S3-Touch (ESP32-S3)
// Implémente le namespace Head selon interfaces.h
// ═══════════════════════════════════════════════════════════════════

#include "interfaces.h"
#include <ESP32Servo.h>

// ── Configuration (lue depuis config.h) ─────────────────────────────
// Les constantes ci-dessous sont définies dans config.h et incluses ci-dessous.
#include "config.h"

// ── État interne du module ──────────────────────────────────────────
static Servo servoPan;
static Servo servoTilt;

// Prototypes internes (membres du namespace Head, définis plus bas)
namespace Head {
  bool measureUltrasonic();  // true si écho reçu (obstacle), false si timeout
  void handleHeadMovement();
}

// Lissage ultrason : moyenne glissante exponentielle. usAvg EST la distance
// lissée (et non une somme) : usAvg += (mesure - usAvg) / N.
static float usAvg = 0.0f;
static const int US_SMOOTH_COUNT = 5;  // nombre d'échantillons
static int usSampleCount = 0;          // 0 = moyenne pas encore amorcée

// Balayage de tête (mode démo). La position est tenue en FLOAT ici :
// g_state.headPanDeg/headTiltDeg sont des int, un incrément fractionnaire y
// serait tronqué à 0 et la tête ne bougerait jamais.
static float panPos = 90.0f;
static float tiltPos = 60.0f;
static unsigned long lastMoveMs = 0;
static int panDir = 1;  // 1 = horaire, -1 = antihoraire
static int tiltDir = 1; // 1 = haut, -1 = bas
static const float PAN_SPEED_DEG = 30.0f;   // 30°/s
static const float TILT_SPEED_DEG = 30.0f;  // 30°/s

// Angle où l'obstacle a été vu (pour évitement futur)
static int obstacleSeenAngle = -1;

// ── Initialisation ───────────────────────────────────────────────────
bool Head::begin() {
  // Timers 2 et 3 : les 0 et 1 sont pris par les roues (wheels.cpp).
  ESP32PWM::allocateTimer(2);
  ESP32PWM::allocateTimer(3);
  servoPan.setPeriodHertz(50);   // 50 Hz = période 20 ms des SG90
  servoTilt.setPeriodHertz(50);

  // Initialisation des servos
  servoPan.attach(SERVO_HEAD_PAN, 500, 2500);  // plage large pour SG90
  servoTilt.attach(SERVO_HEAD_TILT, 500, 2500);
  // attach() renvoie le canal PWM (0 est un canal valide) : c'est attached()
  // qui dit si le pin a réellement été pris.
  const bool servosOk = servoPan.attached() && servoTilt.attached();

  // Position de centre (pan 90°, tilt 60°)
  if (servosOk) {
    servoPan.write(90);
    servoTilt.write(60);
  }

  // Petit délai pour que les servos s'installent
  delay(100);

  // Configuration HC-SR04
  pinMode(PIN_US_TRIG, OUTPUT);
  pinMode(PIN_US_ECHO, INPUT);  // IMPORTANT : HC-SR04 ECHO sort en 5V !
  // Sur ESP32-S3, les pins 5V-tolerant sont limités. Le câblage réel doit
  // utiliser un pont diviseur résistif (ex: 1kΩ / 2kΩ) sur la ligne ECHO
  // pour ramener le niveau à 3.3V. En alternative, lire en INPUT avec
  // une résistance de pull-down externe.
  // Câblage recommandé : ECHO HC-SR04 → 1kΩ → GND, joint 1kΩ/2kΩ → PIN_US_ECHO

  // Reset HC-SR04
  digitalWrite(PIN_US_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_US_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_US_TRIG, LOW);

  // Reset lissage
  usAvg = 0.0f;
  usSampleCount = 0;

  // Reset balayage
  panPos = 90.0f;
  tiltPos = 60.0f;
  g_state.headPanDeg = 90;
  g_state.headTiltDeg = 60;
  lastMoveMs = millis();
  panDir = 1;
  tiltDir = 1;

  return servosOk;
}

// ── Boucle principale ───────────────────────────────────────────────
void Head::loop() {
  // 1. Mesure ultrason — cadence ADAPTATIVE pour ne pas voler du temps à
  // la boucle d'équilibre (200 Hz) : le pulseIn est bloquant. Au repos
  // (aucun écho : pas d'obstacle OU capteur absent) on espace à 1 s après
  // 3 échecs consécutifs ; dès qu'un écho revient, on repasse à 200 ms.
  static unsigned long lastUsMeasureMs = 0;
  static int usFailStreak = 0;
  const unsigned long interval = (usFailStreak >= 3) ? 1000UL : 200UL;
  if (millis() - lastUsMeasureMs >= interval) {
    lastUsMeasureMs = millis();
    if (measureUltrasonic()) usFailStreak = 0;
    else                     usFailStreak++;
  }

  // 2. Gestion du balayage de tête
  handleHeadMovement();
}

// ── Mesure ultrason avec lissage ────────────────────────────────────
// Mesure ultrason. Retourne true si un écho a été reçu (obstacle détecté
// dans la portée), false si timeout (rien devant OU capteur absent).
bool Head::measureUltrasonic() {
  // Déclenchement : impulsion 10 µs HIGH
  digitalWrite(PIN_US_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_US_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_US_TRIG, LOW);

  // Mesure ECHO : timeout 12000 µs ≈ 2 m (suffisant pour l'évitement d'un
  // petit robot ; un timeout long bloquerait la boucle d'équilibre).
  unsigned long duration = pulseIn(PIN_US_ECHO, HIGH, 12000);

  float distanceCm = -1.0f;
  if (duration > 0) {
    distanceCm = duration / 58.0f;  // µs → cm
  }

  // Timeout : rien dans la portée (ou capteur absent). On N'INJECTE PAS le
  // -1 dans la moyenne — il la tirerait vers le négatif et un obstacle réel
  // mettrait plusieurs mesures à réapparaître. On garde la moyenne en l'état
  // pour le prochain écho, mais on n'affiche plus de distance.
  if (distanceCm < 0.0f) {
    g_state.obstacleCm = -1.0f;
    g_state.obstacleWarn = false;
    obstacleSeenAngle = -1;
    return false;
  }

  // Lissage : moyenne glissante exponentielle sur US_SMOOTH_COUNT échantillons
  // (usAvg est la distance elle-même, pas 5× la distance).
  if (usSampleCount == 0) usAvg = distanceCm;   // amorçage sur la 1re mesure
  else                    usAvg += (distanceCm - usAvg) / US_SMOOTH_COUNT;
  if (usSampleCount < US_SMOOTH_COUNT) usSampleCount++;

  const float smoothedDistance = usAvg;

  // Mise à jour de l'état global
  g_state.obstacleCm = smoothedDistance;
  g_state.obstacleWarn = (smoothedDistance < US_STOP_CM);

  // Suivi de l'angle où l'obstacle a été vu
  if (g_state.obstacleWarn) {
    if (obstacleSeenAngle < 0) obstacleSeenAngle = g_state.headPanDeg;
  } else {
    obstacleSeenAngle = -1;
  }

  // Clamp à la portée utile
  if (smoothedDistance > US_MAX_CM) {
    g_state.obstacleCm = -1.0f;  // hors portée
  }

  return true;
}

// ── Gestion du mouvement de la tête ─────────────────────────────────
void Head::handleHeadMovement() {
  // Déplacement en degrés/seconde : la fonction est appelée à 50 Hz par le
  // .ino, chaque pas vaut donc ~0,6° — d'où la position en float.
  const unsigned long now = millis();
  float dt = (now - lastMoveMs) / 1000.0f;
  lastMoveMs = now;
  if (dt <= 0.0f) return;
  if (dt > 0.1f) dt = 0.1f;   // borne après une pause (boot, blocage)

  if (g_state.balancing) {
    // Mode équilibre : tête centrée et fixe, ramenée à vitesse bornée.
    const float panStep  = PAN_SPEED_DEG * dt;
    const float tiltStep = TILT_SPEED_DEG * dt;
    panPos  += constrain(90.0f - panPos,  -panStep,  panStep);
    tiltPos += constrain(60.0f - tiltPos, -tiltStep, tiltStep);
  } else {
    // Mode démo (robot au sol) : balayage continu pan puis tilt.
    panPos += PAN_SPEED_DEG * panDir * dt;
    if (panPos <= HEAD_PAN_MIN)      { panPos = HEAD_PAN_MIN; panDir = 1; }
    else if (panPos >= HEAD_PAN_MAX) { panPos = HEAD_PAN_MAX; panDir = -1; }

    tiltPos += TILT_SPEED_DEG * tiltDir * dt;
    if (tiltPos <= HEAD_TILT_MIN)      { tiltPos = HEAD_TILT_MIN; tiltDir = 1; }
    else if (tiltPos >= HEAD_TILT_MAX) { tiltPos = HEAD_TILT_MAX; tiltDir = -1; }
  }

  // Publier l'arrondi : g_state est en int (affichage UI + écriture servo).
  g_state.headPanDeg  = (int)lroundf(panPos);
  g_state.headTiltDeg = (int)lroundf(tiltPos);

  servoPan.write(g_state.headPanDeg);
  servoTilt.write(g_state.headTiltDeg);
}
