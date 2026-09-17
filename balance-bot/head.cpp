// ═══════════════════════════════════════════════════════════════════
// BalanceBot — Module C : Tête pan/tilt + Ultrason + Évitement (head.cpp)
// Carte : LilyGo T-Display-S3-Touch (ESP32-S3)
// Implémente le namespace Head selon interfaces.h
//
// Tourne sur le cœur 1 (loop()) : le pulseIn() bloquant de l'ultrason
// (jusqu'à 9,5 ms) ne concerne plus la boucle d'équilibre (cœur 0) quand
// BALANCE_SPLIT_CORES=1. La cadence adaptative 200/1000 ms est conservée.
//
// CE QUE LE ROBOT NE SAIT PAS FAIRE : il n'a ni cap (pas de magnétomètre,
// le yaw gyro dérive), ni odométrie fiable (pas d'encodeur, φ est une
// intégration de consigne), ni carte. « Tourner de 90° » ou « contourner »
// n'ont donc aucun sens pour lui. L'évitement se limite à : ralentir,
// reculer doucement, pivoter du côté qui était libre PENDANT que
// l'ultrason confirme, et reprendre quand ça se dégage.
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
static int sideFromPan(int panDeg);

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

// Angle (pan) où l'obstacle a été vu : c'est ce qui donne le CÔTÉ à
// l'évitement (updateAvoidance). -1 = aucun obstacle en cours.
static int obstacleSeenAngle = -1;

// ── Évitement d'obstacle (état, cœur 1) ────────────────────────────
// Machine à états publiée dans g_state.avoid* et consommée par
// balance.cpp AVANT le lissage des consignes — jamais sur le PID.
//   LIBRE    : rien à moins de US_SLOW_CM → avoidFwdMax = 100.
//   RALENTI  : US_STOP_CM ≤ d < US_SLOW_CM → marche avant plafonnée.
//   RECUL    : d < US_STOP_CM → recul doux + pivot vers le côté libre,
//              borné à AVOID_BACK_MAX_MS (capteur masqué, coin…).
//   PIVOT    : recul épuisé, obstacle toujours là → on ne recule plus,
//              on pivote seulement.
// Sortie de RECUL/PIVOT avec hystérésis : d > US_CLEAR_CM (ou plus
// d'écho du tout), sinon un obstacle à 25,0 cm ferait clignoter l'état.
// Le côté est VERROUILLÉ à l'entrée en RECUL : la tête continue de
// balayer, l'angle « vu » ne doit pas changer d'avis en cours de manœuvre.
enum AvoidPhase : uint8_t { AV_LIBRE = 0, AV_RALENTI = 1, AV_RECUL = 2, AV_PIVOT = 3 };
static AvoidPhase    avoidPhase   = AV_LIBRE;
static unsigned long avoidSinceMs = 0;   // entrée dans RECUL
static int           avoidSide    = 0;   // côté verrouillé (-1 / +1)

// Côté de l'obstacle d'après l'angle de tête : pan < 90 d'un côté, > 90
// de l'autre. Le sens mécanique (quel côté est « gauche ») n'est pas
// connu ici : AVOID_TURN_SIGN (config.h) le règle au premier essai réel.
static int sideFromPan(int panDeg) {
  const int d = panDeg - 90;
  if (d >  AVOID_SIDE_DEAD_DEG) return +1;
  if (d < -AVOID_SIDE_DEAD_DEG) return -1;
  return 0;                                   // en face : côté par défaut
}

static void publishAvoid(int fwdMax, int turn) {
  g_state.avoidFwdMax = fwdMax;
  g_state.avoidTurn   = turn;
  g_state.avoidPhase  = (uint8_t)avoidPhase;
}

static void updateAvoidance() {
  // Uniquement quand le robot tient debout : posé ou tenu à la main (mode
  // démo, chute), aucune consigne d'évitement — balance.cpp ne la lirait
  // pas de toute façon (chemin d'équilibre seulement).
  if (!g_state.balancing) {
    avoidPhase = AV_LIBRE;
    publishAvoid(100, 0);
    return;
  }
  const unsigned long now = millis();
  const float d = g_state.obstacleCm;         // -1 = pas d'écho
  const bool  seen = (d >= 0.0f);

  switch (avoidPhase) {
    case AV_LIBRE:
    case AV_RALENTI:
      if (g_state.obstacleWarn) {                    // d < US_STOP_CM
        avoidPhase   = AV_RECUL;
        avoidSinceMs = now;
        int side = (obstacleSeenAngle >= 0) ? sideFromPan(obstacleSeenAngle) : 0;
        if (side == 0) side = AVOID_DEFAULT_SIDE;
        // Obstacle vu à droite (+1) → pivoter à gauche : -side, au signe
        // mécanique près.
        avoidSide = -side * AVOID_TURN_SIGN;
      } else if (g_state.obstacleSlow) {
        avoidPhase = AV_RALENTI;
      } else {
        avoidPhase = AV_LIBRE;
      }
      break;
    case AV_RECUL:
    case AV_PIVOT:
      if (!seen || d > US_CLEAR_CM) {                // passage dégagé
        avoidPhase = g_state.obstacleSlow ? AV_RALENTI : AV_LIBRE;
      } else if (avoidPhase == AV_RECUL && now - avoidSinceMs >= AVOID_BACK_MAX_MS) {
        avoidPhase = AV_PIVOT;                       // on ne recule pas à l'infini
      }
      break;
  }

  switch (avoidPhase) {
    case AV_LIBRE:   publishAvoid(100, 0); break;
    case AV_RALENTI: publishAvoid(AVOID_SLOW_CMD, 0); break;
    case AV_RECUL:   publishAvoid(-AVOID_BACK_CMD, avoidSide * AVOID_TURN_CMD); break;
    case AV_PIVOT:   publishAvoid(0, avoidSide * AVOID_TURN_CMD); break;
  }
}

// ── Initialisation ───────────────────────────────────────────────────
bool Head::begin() {
  // Timers 2 et 3 : les 0 et 1 sont pris par les pieds (feet.cpp).
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

  // 3. Évitement : machine à états (50 Hz, comme la tête)
  updateAvoidance();
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

  // Mesure ECHO : timeout aligné sur la portée UTILE (US_MAX_CM = 150 cm
  // → 150 × 58 = 8,7 ms) + marge. pulseIn() est BLOQUANT : ces
  // millisecondes sont prises sur la boucle d'équilibre (5 ms par cycle),
  // donc on ne bloque pas 12 ms pour une distance qu'on jetterait ensuite.
  static constexpr unsigned long kEchoTimeoutUs = (unsigned long)US_MAX_CM * 58UL + 800UL;
  unsigned long duration = pulseIn(PIN_US_ECHO, HIGH, kEchoTimeoutUs);

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
    g_state.obstacleSlow = false;
    g_state.obstacleSide = 0;
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
  g_state.obstacleSlow = (smoothedDistance >= US_STOP_CM && smoothedDistance < US_SLOW_CM);

  // Suivi de l'angle où l'obstacle a été vu (premier écho sous US_STOP_CM
  // dans le balayage courant) → côté publié pour l'évitement.
  if (g_state.obstacleWarn) {
    if (obstacleSeenAngle < 0) obstacleSeenAngle = g_state.headPanDeg;
  } else {
    obstacleSeenAngle = -1;
  }
  g_state.obstacleSide = (obstacleSeenAngle >= 0) ? (int8_t)sideFromPan(obstacleSeenAngle) : 0;

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
    // Mode équilibre : tilt ramené au centre (vitesse bornée) ; pan en
    // balayage ÉTROIT ±HEAD_BALANCE_SWEEP_DEG autour de 90° (0 = tête
    // fixe, comportement d'avant) — c'est ce balayage qui donne un CÔTÉ
    // à l'obstacle pour l'évitement. Tête légère, 30 °/s : négligeable
    // pour l'équilibre.
    const float panStep  = PAN_SPEED_DEG * dt;
    const float tiltStep = TILT_SPEED_DEG * dt;
    tiltPos += constrain(60.0f - tiltPos, -tiltStep, tiltStep);
    constexpr float kLo = 90.0f - HEAD_BALANCE_SWEEP_DEG;
    constexpr float kHi = 90.0f + HEAD_BALANCE_SWEEP_DEG;
    if (HEAD_BALANCE_SWEEP_DEG <= 0 || panPos < kLo - panStep || panPos > kHi + panStep) {
      // hors de la fenêtre (on vient du balayage large) : retour au centre
      panPos += constrain(90.0f - panPos, -panStep, panStep);
    } else {
      panPos += PAN_SPEED_DEG * panDir * dt;
      if (panPos <= kLo)      { panPos = kLo; panDir = 1; }
      else if (panPos >= kHi) { panPos = kHi; panDir = -1; }
    }
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

  // N'écrire que si la valeur CHANGE : réécrire la même position 50×/s
  // fait vibrer/ronronner un SG90 pour rien (tilt immobile en équilibre →
  // aucune écriture ; le pan n'écrit qu'à chaque degré franchi).
  static int lastPan = -1, lastTilt = -1;
  if (g_state.headPanDeg != lastPan)   { lastPan  = g_state.headPanDeg;  servoPan.write(lastPan); }
  if (g_state.headTiltDeg != lastTilt) { lastTilt = g_state.headTiltDeg; servoTilt.write(lastTilt); }
}
