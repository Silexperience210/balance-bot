// ═══════════════════════════════════════════════════════════════════
// BalanceBot — module A · boucle d'équilibre (API publique Balance::)
//
// Pendule inversé : le robot reste debout en déplaçant son point
// d'appui sous son centre de gravité. Il penche vers l'avant ⇒ les
// pieds roulent vers l'avant pour « rattraper » la chute, et
// réciproquement.
//
//   pitch (IMU) ──► erreur = consigne − pitch ──► PID ──► vitesse PIED
//                                        ▲                    │
//                    cmdForward (UI) ────┘                    ▼
//                    cmdTurn    (UI) ─────► différentiel   Feet:: (position)
//                    recentrage  ─────────┘  (θ_ref lent)
//
// MÉCANIQUE v2 : plus de roues, deux PIEDS EN ARC sur SG90 standard.
// Un servo de position a un DÉBATTEMENT FINI : le PID ne peut plus
// tourner indéfiniment. Deux mécanismes s'ajoutent donc ici :
//   · un soft clamp qui annule la vitesse AVANT la butée ;
//   · une boucle de recentrage lente (2 Hz) qui incline légèrement la
//     consigne pour faire rouler le robot et ramener les pieds vers 0
//     (le « marcher sur place »). Elle ne court-circuite JAMAIS le PID.
//
// Cadencé à BALANCE_LOOP_HZ (200 Hz) par le .ino ; aucun delay() ici.
// ═══════════════════════════════════════════════════════════════════
#include <Arduino.h>

#include "config.h"
#include "interfaces.h"
#include "imu.h"
#include "feet.h"

namespace {

// ═══════════════════ RÉGLAGE PID — commencer ici ═══════════════════
// Unités : erreur en degrés, sortie en « vitesse de pied » (-90..+90,
// convertie en °/s par kOutToFootDegS). Gains de départ pour un châssis
// léger — à affiner sur le robot réel.
//
// Procédure de réglage (robot tenu à la main, Ki = Kd = 0) :
//   1. monter Kp jusqu'à ce que le robot réagisse vif mais oscille ;
//   2. monter Kd pour amortir l'oscillation (trop → tremblement aigu) ;
//   3. monter Ki juste assez pour effacer la dérive lente / la pente.
//
// Gains validés en simulation 1D (sim/, θ̈ = (g/h)·sinθ − (R/h)·φ̈·cosθ,
// h = 80 mm, R = 32.5 mm, servo 1er ordre τ = 50 ms limité à 250 °/s,
// contrôleur copié à l'identique depuis ce fichier).
//
// Condition de stabilité : la commande agit en VITESSE de pied, donc le
// terme intégral est ce qui fournit la position de pied compensant la
// gravité. Il faut Ki > g/R ≈ 9.81 / 0.0325 ≈ 301 s⁻² pour que le point
// de contact rattrape le CoM ; en dessous, le robot tombe quelle que
// soit la valeur de Kp. L'ancien Ki = 20 (hérité du design « roues »,
// jamais testé) est 15× trop faible → chute systématique en sim.
constexpr float kKp = 25.0f;   // vitesse par degré d'erreur
constexpr float kKi = 500.0f;  // vitesse par (degré · seconde) — cf. Ki > g/R
constexpr float kKd = 0.5f;    // vitesse par (degré / seconde) — sur le gyro

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
// Sortie : plus de mort-zone ni de relèvement (shapeOutput) — c'était
// une compensation du frottement sec des SG90 en rotation continue. En
// commande de POSITION, ce saut 0→8 se traduirait par un bond du pied
// de plusieurs dixièmes de degré à chaque cycle : nuisible.
constexpr float kOutMax       = 90.0f;

// ── Sortie PID → vitesse de pied ───────────────────────────────────
// Le domaine du PID (-90..+90) est lu comme des °/s de pied. À 1.0,
// pleine commande = 90 °/s ; l'arc a un rayon de 32.5 mm, soit
// 0.567 mm de déplacement au sol par degré → 51 mm/s au maximum.
// C'est le PREMIER bouton à monter si le robot est trop lent à se
// rattraper : un SG90 tient ~300 °/s à vide, donc jusqu'à ~3.0.
constexpr float kOutToFootDegS = 1.0f;

// ── Butée des pieds (débattement fini du servo de position) ────────
// Le pied ET le corps consomment le même arc : le point de contact se
// trouve à ≈ (φ + θ) du milieu de l'arc. La limite utile dépend donc
// du tangage courant. L'arc couvre ±100°, le servo ±90° :
//   limite = 90° − |θ| − marge, plafonnée par la butée dure de feet.cpp.
// La marge (9°) couvre le retard du servo et l'incertitude de calage
// du palonnier (4 positions à 90° : jusqu'à quelques degrés d'erreur).
constexpr float kFootMarginDeg = 9.0f;
constexpr float kFootHardDeg   = 45.0f;   // = butée dure de feet.cpp
// Le soft clamp s'ouvre progressivement sur les 10 derniers degrés :
// une coupure franche exciterait le pendule.
constexpr float kFootTaperDeg  = 10.0f;

// ── Boucle de recentrage (« marcher sur place ») ───────────────────
// Si les pieds dérivent, on incline très légèrement la consigne dans
// le sens OPPOSÉ : le robot roule dans cette direction et les pieds
// reviennent vers 0. Cadence 2 Hz — plusieurs décades sous le PID, qui
// garde donc toujours l'autorité sur l'équilibre.
constexpr unsigned long kRecenterPeriodMs = 500;   // 2 Hz
constexpr float        kRecenterDeadDeg  = 15.0f;  // en deçà : rien à faire
constexpr unsigned long kRecenterHoldMs  = 300;    // …et il faut durer
constexpr float        kRecenterTrimMax  = 1.0f;   // ±1° de consigne, pas plus
constexpr float        kRecenterRateDegS = 0.30f;  // charge : ~3.3 s pour ±1°
constexpr float        kRecenterDecayDegS= 0.20f;  // retour à 0 une fois recentré
constexpr float        kFootPanicDeg     = 40.0f;  // butée imminente → halt()

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

// ── Mode démo (équilibre OFF) ──────────────────────────────────────
// Sert à VALIDER LA MÉCANIQUE sans asservissement : les flèches de l'UI
// font rouler les pieds lentement dans une plage volontairement étroite
// (le robot est tenu à la main ou couché). Aucune sécurité d'équilibre
// n'est active ici, d'où les valeurs timides.
constexpr float kDemoSpeedDegS = 20.0f;   // à plein cmdForward
constexpr float kDemoTurnDegS  = 12.0f;   // différentiel, à plein cmdTurn
constexpr float kDemoLimitDeg  = 15.0f;   // débattement autorisé en démo

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

float         s_recenterTrim = 0.0f;  // décalage lent de θ_ref (°), borné ±1
unsigned long s_recenterLast = 0;     // dernier passage de la boucle 2 Hz
unsigned long s_footOutSince = 0;     // depuis quand |pied| dépasse le seuil

inline float slew(float current, float target, float maxStep) {
  const float delta = target - current;
  if (delta >  maxStep) return current + maxStep;
  if (delta < -maxStep) return current - maxStep;
  return target;
}

// Coupe tout : pieds freinés SUR PLACE (surtout pas de retour au neutre,
// qui ferait basculer un robot debout), intégrateurs vidés, état à jour.
void halt() {
  Feet::stop();
  s_pid.reset();
  s_fwdSmooth = 0.0f;
  s_turnSmooth = 0.0f;
  s_recenterTrim = 0.0f;
  s_footOutSince = 0;
  g_state.balancing = false;
}

// Recopie la position des pieds dans l'état partagé (affichage UI).
inline void publishFeet() {
  g_state.footLDeg = (int)lroundf(Feet::angleL());
  g_state.footRDeg = (int)lroundf(Feet::angleR());
}

// Soft clamp de butée : réduit la vitesse demandée à mesure que le pied
// approche de sa limite, et seulement si la commande pousse ENCORE plus
// loin. Rentrer vers le centre reste toujours à pleine autorité.
inline float limitTowardStop(float out, float footAvg, float pitch) {
  const float limit = fminf(kFootHardDeg, 90.0f - fabsf(pitch) - kFootMarginDeg);
  if (out * footAvg <= 0.0f) return out;          // on revient vers 0 : libre
  const float headroom = limit - fabsf(footAvg);
  const float k = constrain(headroom / kFootTaperDeg, 0.0f, 1.0f);
  return out * k;
}

// Boucle de recentrage, appelée à 2 Hz. Renvoie false si les pieds sont
// si loin que la butée est imminente (l'appelant coupe alors tout).
// N'agit QUE sur la consigne d'angle : le PID garde la main.
bool recenterStep(float footAvg, float dtRec) {
  const unsigned long ms = millis();

  if (fabsf(footAvg) > kFootPanicDeg) return false;

  if (fabsf(footAvg) > kRecenterDeadDeg) {
    if (s_footOutSince == 0) s_footOutSince = ms;
    if (ms - s_footOutSince >= kRecenterHoldMs) {
      // Pieds partis vers l'avant ⇒ il faut ROULER EN ARRIÈRE pour les
      // ramener ⇒ pencher en arrière ⇒ consigne négative. D'où le signe
      // opposé à footAvg.
      const float dir = (footAvg > 0.0f) ? -1.0f : 1.0f;
      s_recenterTrim = constrain(s_recenterTrim + dir * kRecenterRateDegS * dtRec,
                                 -kRecenterTrimMax, kRecenterTrimMax);
    }
  } else {
    // Recentré : on relâche le décalage, sinon le robot garderait une
    // inclinaison permanente et repartirait dans l'autre sens.
    s_footOutSince = 0;
    const float step = kRecenterDecayDegS * dtRec;
    if (fabsf(s_recenterTrim) <= step) s_recenterTrim = 0.0f;
    else s_recenterTrim -= (s_recenterTrim > 0.0f ? step : -step);
  }
  return true;
}

// Mode démo (équilibre OFF) : les flèches de l'UI font rouler les pieds
// lentement, dans ±kDemoLimitDeg. Sert à valider la mécanique — aucun
// asservissement, la priorité reste l'équilibre statique.
void demoStep() {
  const int cmdFwd  = constrain(g_state.cmdForward, -100, 100);
  const int cmdTurn = constrain(g_state.cmdTurn, -100, 100);

  if (cmdFwd == 0 && cmdTurn == 0) {
    Feet::stop();                    // maintien sur place, pas de retour neutre
    publishFeet();
    return;
  }

  const float fwd  = cmdFwd  * kDemoSpeedDegS / 100.0f;
  const float turn = cmdTurn * kDemoTurnDegS  / 100.0f;
  float vL = fwd + turn;
  float vR = fwd - turn;

  // Butée de démo : on annule la composante qui pousserait au-delà.
  if (Feet::angleL() >  kDemoLimitDeg && vL > 0.0f) vL = 0.0f;
  if (Feet::angleL() < -kDemoLimitDeg && vL < 0.0f) vL = 0.0f;
  if (Feet::angleR() >  kDemoLimitDeg && vR > 0.0f) vR = 0.0f;
  if (Feet::angleR() < -kDemoLimitDeg && vR < 0.0f) vR = 0.0f;

  Feet::driveFootSpeed((int)lroundf(vL), (int)lroundf(vR));
  publishFeet();
}

} // namespace

namespace Balance {

bool begin() {
  s_enabled = false;
  s_fallen  = false;
  s_lastMicros = micros();
  s_recenterLast = millis();
  s_recenterTrim = 0.0f;
  s_footOutSince = 0;

  // Les pieds d'abord : même sans IMU on veut les poser au repos (robot
  // droit), et l'UI reste utilisable en mode démo.
  Feet::begin();
  publishFeet();

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
    // Armement par g_state.cmdEnabled (l'UI n'appelle pas forcément
    // setEnabled) : sans ça, s_recenterLast daterait de la dernière
    // désactivation et le premier pas de recentrage verrait un dt de
    // plusieurs secondes — soit ±1° de consigne d'un coup.
    s_recenterLast = millis();
    s_recenterTrim = 0.0f;
    s_footOutSince = 0;
  }
  s_enabled = want;

  if (!s_imuOk) {
    // Pas d'IMU : aucun équilibre possible, mais la mécanique reste
    // pilotable en démo par les flèches de l'UI.
    halt();
    demoStep();
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
  // pilote pas l'équilibre — seul le mode démo peut bouger les pieds.
  if (!s_enabled) {
    demoStep();
    return;
  }

  // ── Sécurité : chute ─────────────────────────────────────────────
  if (fabsf(pitch) > kFallAngleDeg) {
    s_fallen = true;
    s_uprightSince = 0;
    halt();                          // pieds figés : pas de gigotage au sol
    publishFeet();
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
        // Le robot est tenu droit à la main : c'est le SEUL moment où
        // ramener les pieds au neutre est sans danger — et c'est
        // indispensable, sinon on ré-arme avec des pieds déjà en butée.
        Feet::recenterNow();
        s_recenterLast = millis();
      }
    } else {
      s_uprightSince = 0;
    }
    if (s_fallen) { halt(); publishFeet(); return; }
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

  // ── Recentrage des pieds (2 Hz, en marge du PID) ─────────────────
  // Le débattement du servo est fini : sans cette boucle le pied part
  // en butée et le robot tombe. On n'agit QUE sur θ_ref, jamais sur la
  // sortie du PID.
  const float footAvg = Feet::angleAvg();
  {
    const unsigned long ms = millis();
    if (ms - s_recenterLast >= kRecenterPeriodMs) {
      // dt borné : un hoquet de boucle ne doit pas charger le décalage
      // d'un bloc (ceinture, en plus de la remise à zéro à l'armement).
      const float dtRec = constrain((ms - s_recenterLast) * 1e-3f, 0.0f, 1.0f);
      s_recenterLast = ms;
      if (!recenterStep(footAvg, dtRec)) {
        // Pieds au-delà de kFootPanicDeg malgré le recentrage : la
        // butée est imminente, la chute avec. On coupe avant.
        s_fallen = true;
        s_uprightSince = 0;
        halt();
        publishFeet();
        return;
      }
    }
  }

  // ── PID ──────────────────────────────────────────────────────────
  // Pour avancer, le robot doit d'abord se pencher vers l'avant :
  // on décale la consigne d'angle, le PID fait le reste.
  const float setpoint =
      kSetpointDeg + s_fwdSmooth * kTiltPerCmd + s_recenterTrim;
  float error = setpoint - pitch;
  if (fabsf(error) < kErrDeadbandDeg) error = 0.0f;   // mort-zone d'erreur

  float out = s_pid.update(error, rate, dt);
  out = constrain(out, -kOutMax, kOutMax);
  // Soft clamp de butée : la commande s'éteint avant le bout de l'arc.
  out = limitTowardStop(out, footAvg, pitch);

  // ── Différentiel de rotation ─────────────────────────────────────
  const float turn = s_turnSmooth * kTurnPerCmd;
  const float left  = constrain(out + turn, -kOutMax, kOutMax);
  const float right = constrain(out - turn, -kOutMax, kOutMax);

  // Domaine PID (-90..+90) → vitesse de pied en °/s.
  Feet::driveFootSpeed((int)lroundf(left  * kOutToFootDegS),
                       (int)lroundf(right * kOutToFootDegS));
  publishFeet();
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
    s_recenterLast = millis();
    s_recenterTrim = 0.0f;
    s_footOutSince = 0;
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
