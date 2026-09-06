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

// Lissage ultrason : moyenne glissante
static float usSum = 0.0f;
static const int US_SMOOTH_COUNT = 5;  // nombre d'échantillons
static int usSampleCount = 0;

// Balayage de tête (mode démo)
static unsigned long lastPanMoveMs = 0;
static unsigned long lastTiltMoveMs = 0;
static int panDir = 1;  // 1 = horaire, -1 = antihoraire
static int tiltDir = 1; // 1 = haut, -1 = bas
static const int PAN_SPEED_DEG = 30;   // 30°/s
static const int TILT_SPEED_DEG = 15;  // 15°/s (plus lent pour stabilité)
static const int BALANCE_SCAN_INTERVAL_MS = 500; // rescan toutes les 500ms en mode équilibre

// Angle où l'obstacle a été vu (pour évitement futur)
static int obstacleSeenAngle = -1;

// ── Initialisation ───────────────────────────────────────────────────
bool Head::begin() {
  // Initialisation des servos
  servoPan.attach(SERVO_HEAD_PAN, 500, 2500);  // plage large pour SG90
  servoTilt.attach(SERVO_HEAD_TILT, 500, 2500);

  // Position de centre (pan 90°, tilt 60°)
  servoPan.write(90.0f);
  servoTilt.write(60.0f);

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
  usSum = 0.0f;
  usSampleCount = 0;

  // Reset balayage
  lastPanMoveMs = millis();
  lastTiltMoveMs = millis();
  panDir = 1;
  tiltDir = 1;

  return true;
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

  // Lissage : moyenne glissante
  usSum += distanceCm - usSum / US_SMOOTH_COUNT;
  float smoothedDistance = usSum;

  // Mise à jour de l'état global
  g_state.obstacleCm = smoothedDistance;
  g_state.obstacleWarn = (smoothedDistance >= 0.0f && smoothedDistance < US_STOP_CM);

  // Suivi de l'angle où l'obstacle a été vu
  if (g_state.obstacleWarn && obstacleSeenAngle < 0) {
    obstacleSeenAngle = g_state.headPanDeg;
  }

  // Clamp à la portée utile
  if (smoothedDistance > US_MAX_CM) {
    g_state.obstacleCm = -1.0f;  // hors portée
  }

  return duration > 0;
}

// ── Gestion du mouvement de la tête ─────────────────────────────────
void Head::handleHeadMovement() {
  bool inBalanceMode = g_state.balancing;

  // En mode équilibre : tête centrée et fixe (sauf scan périodique)
  if (inBalanceMode) {
    // Centrer la tête
    int targetPan = 90;
    int targetTilt = 60;

    // Scan périodique en mode équilibre — le balayage est assuré par le
    // mouvement continu de handleHeadMovement() (scan() a été supprimé).
    static unsigned long lastBalanceScanMs = 0;
    if (millis() - lastBalanceScanMs >= BALANCE_SCAN_INTERVAL_MS) {
      lastBalanceScanMs = millis();
    }

    // Mouvement doux vers la position cible
    float panError = targetPan - g_state.headPanDeg;
    float tiltError = targetTilt - g_state.headTiltDeg;

    // Proportionnel simple pour éviter les saccades
    float panStep = constrain(panError * 0.5f, -PAN_SPEED_DEG, PAN_SPEED_DEG);
    float tiltStep = constrain(tiltError * 0.5f, -TILT_SPEED_DEG, TILT_SPEED_DEG);

    g_state.headPanDeg += panStep;
    g_state.headTiltDeg += tiltStep;

    // Appliquer les positions
    servoPan.write(g_state.headPanDeg);
    servoTilt.write(g_state.headTiltDeg);

    return;
  }

  // Mode démo (robot au sol, balancing=false) : balayage lent
  unsigned long now = millis();

  // Pan horizontal : 0 → 180 → 0
  if (now - lastPanMoveMs >= 1000) {  // 1000ms / 180° ≈ 5.5°/s (ajusté pour fluidité)
    lastPanMoveMs = now;

    g_state.headPanDeg += PAN_SPEED_DEG * panDir * 0.033f;  // 30°/s → degrés par 1000ms
    g_state.headPanDeg = constrain(g_state.headPanDeg, HEAD_PAN_MIN, HEAD_PAN_MAX);

    if (g_state.headPanDeg <= HEAD_PAN_MIN) {
      panDir = 1;
      g_state.headPanDeg = HEAD_PAN_MIN;
    } else if (g_state.headPanDeg >= HEAD_PAN_MAX) {
      panDir = -1;
      g_state.headPanDeg = HEAD_PAN_MAX;
    }
  }

  // Tilt vertical : 20 → 90 → 20 (plus lent pour stabilité)
  if (now - lastTiltMoveMs >= 1500) {  // intervalle plus long
    lastTiltMoveMs = now;

    g_state.headTiltDeg += TILT_SPEED_DEG * tiltDir * 0.067f;  // 15°/s
    g_state.headTiltDeg = constrain(g_state.headTiltDeg, HEAD_TILT_MIN, HEAD_TILT_MAX);

    if (g_state.headTiltDeg <= HEAD_TILT_MIN) {
      tiltDir = 1;
      g_state.headTiltDeg = HEAD_TILT_MIN;
    } else if (g_state.headTiltDeg >= HEAD_TILT_MAX) {
      tiltDir = -1;
      g_state.headTiltDeg = HEAD_TILT_MAX;
    }
  }

  // Appliquer les positions
  servoPan.write(g_state.headPanDeg);
  servoTilt.write(g_state.headTiltDeg);
}
