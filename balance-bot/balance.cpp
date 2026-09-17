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
//                    cascade φ  ──────────┘  (θ_ref)
//
// MÉCANIQUE v3.1 : plus de roues, deux PIEDS EN ARC sur SG90 standard.
// Un servo de position a un DÉBATTEMENT FINI : le PID ne peut plus
// tourner indéfiniment. Deux mécanismes s'ajoutent donc ici :
//   · un soft clamp qui annule la vitesse AVANT la butée ;
//   · une CASCADE DE RECENTRAGE en vitesse (boucle externe 10 Hz sur la
//     position de pied φ → consigne de vitesse ; boucle interne continue
//     → θ_ref). Elle ne court-circuite JAMAIS le PID.
//
// Cadencé à BALANCE_LOOP_HZ (200 Hz) par le .ino ; aucun delay() ici.
// ═══════════════════════════════════════════════════════════════════
#include <Arduino.h>
#include <Preferences.h>

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
// Procédure de réglage (robot tenu à la main) — REVIEW_CLAUDE.md M8.
// La sortie est une VITESSE de pied : l'accélération de la base (la seule
// chose qui redresse le pendule) est la DÉRIVÉE de la sortie, soit
// Ki·θ + Kp·θ̇ + Kd·θ̈. Ici Ki est donc la RAIDEUR, Kp l'AMORTISSEMENT et
// Kd une inertie : la recette habituelle d'un PID de position (Ki = Kd = 0,
// monter Kp jusqu'à l'oscillation) ne s'applique PAS — avec Ki = 0 aucune
// oscillation n'est observable, le robot tombe.
//   1. partir de Ki ≈ 400-500 (> g/R ≈ 302 s⁻², condition ci-dessous),
//      Kp ≈ 50, Kd ≈ 0,5. Le Kp = 25 embarqué est en dessous : l'analyse
//      linéaire du modèle du sim (retards 50 + 25 ms) le donne instable,
//      Kp 50-100 franchement amorti ;
//   2. monter Kp pour AMORTIR (trop bas → balancement lent qui s'amplifie,
//      trop haut → tremblement) ;
//   3. Kd en dernier, petit (≲ 2) : il ne fait que lisser ; trop → buzz aigu.
//
// Gains de DÉPART, NON validés par une simulation rejouable (voir
// FIRMWARE_REVIEW.md §1bis) : le simulateur du dépôt modélisait un autre
// robot (autorité 57× trop forte, roulement incomplet, sans cascade). Avec
// le modèle corrigé, ce jeu de gains ne tient aucun scénario — le réglage
// réel au banc web (BalanceBot-Tune) est l'étape obligatoire suivante.
//
// Condition de stabilité : la commande agit en VITESSE de pied, donc le
// terme intégral est ce qui fournit la position de pied compensant la
// gravité. Il faut Ki > g/R ≈ 9.81 / 0.0325 ≈ 302 s⁻² pour que le point
// de contact rattrape le CoM ; en dessous, le robot tombe quelle que
// soit la valeur de Kp. L'ancien Ki = 20 (hérité du design « roues »,
// jamais testé) est 15× trop faible → chute systématique en sim.
// NON-const : réglables à chaud par le banc web (tuner.cpp) via
// Balance::setGains(). Des float 32 bits sur ESP32 : lecture/écriture
// atomiques (un seul mot machine), pas de tearing possible entre la
// boucle d'équilibre et le serveur web — ni volatile ni mutex requis.
float kKp = 25.0f;   // vitesse par degré d'erreur
float kKi = 500.0f;  // vitesse par (degré · seconde) — cf. Ki > g/R
float kKd = 0.5f;    // vitesse par (degré / seconde) — sur le gyro

// Bornes de réglage à chaud (garde-fous du banc web)
constexpr float kKpMax = 100.0f;
constexpr float kKiMax = 2000.0f;
constexpr float kKdMax = 20.0f;

// Consigne d'équilibre : angle auquel le robot tient réellement debout.
// Décaler de quelques dixièmes si le robot dérive toujours du même côté.
constexpr float kSetpointDeg = 0.0f;

// ── Morts-zones ────────────────────────────────────────────────────
// Erreur : AUCUNE (0) — REVIEW_CLAUDE.md M3. L'ancienne bande de 0,25°
// était appliquée AVANT P et I : le robot vivait sur son bord, chaque
// sortie de bande donnait un coup de P qui le ramenait juste dedans, où P
// et I étaient gelés ; l'erreur ne changeait donc jamais de signe,
// l'intégrale ne se déchargeait jamais et cliquetait jusqu'à sa borne →
// pieds en butée en 1-2 s quels que soient les gains (reproduit en sim,
// jeu linéairement stable). Le bruit du pitch fusionné (~0,03-0,1° rms)
// ne justifie pas de bande : le SG90 ne répond pas sous ~1° de toute
// façon. Si une bande redevenait nécessaire, ne l'appliquer QU'AU terme
// P, jamais à l'entrée de l'intégrateur. (Le test « < 0 » est inerte.)
constexpr float kErrDeadbandDeg = 0.0f;
// Sortie : plus de mort-zone ni de relèvement (shapeOutput) — c'était
// une compensation du frottement sec des SG90 en rotation continue. En
// commande de POSITION, ce saut 0→8 se traduirait par un bond du pied
// de plusieurs dixièmes de degré à chaque cycle : nuisible.
constexpr float kOutMax       = 90.0f;

// ── Anti-windup ────────────────────────────────────────────────────
// Le terme intégral est borné à la PLEINE sortie (REVIEW_CLAUDE.md M10) :
// en commande de vitesse, I est le terme de RAIDEUR (cf. procédure de
// réglage) ; l'ancien plafond de 25 (28 % de kOutMax) bridait
// l'accélération cumulée de la base — mesuré en sim (mort-zone 0, retard
// 5 ms, k_out 3, gains embarqués) : Imax 25 → 0/6, Imax 90 → θ0 = 2° tenus.
// Le rebond au redressement (I chargé pendant la chute), lui, est déjà
// évité par l'intégration CONDITIONNELLE de Pid::update (gel quand la
// sortie sature).
constexpr float kIntegralMax = kOutMax;

// ── Sortie PID → vitesse de pied ───────────────────────────────────
// Le domaine du PID (-90..+90) est lu comme des °/s de pied. À 1.0,
// pleine commande = 90 °/s ; l'arc a un rayon de 32.5 mm, soit
// 0.567 mm de déplacement au sol par degré → 51 mm/s au maximum.
// C'est le PREMIER bouton à monter si le robot est trop lent à se
// rattraper : un SG90 tient ~300 °/s à vide, donc jusqu'à ~3.0.
// NON-const depuis REVIEW_CLAUDE.md M11 : slider « Autorité » du banc web
// (Balance::setOutScale, borné kOutToFootMin..Max, persisté NVS « kout »)
// et balayé par le --sweep du sim — où aucun jeu ne tient le moindre
// scénario sous k_out = 2, et où les tapes ne sont atteintes qu'à k_out = 3.
// Feet:: écrête de son côté à kSpeedMaxDegS (400 °/s) : 3 × 90 = 270 °/s
// reste dans la plage.
float kOutToFootDegS = 1.0f;
constexpr float kOutToFootMin = 1.0f;
constexpr float kOutToFootMax = 3.0f;

// ── Butée des pieds (débattement fini du servo de position) ────────
// Le pied ET le corps consomment le même arc : le point de contact se
// trouve à ≈ (φ + θ) du milieu de l'arc. La limite utile dépend donc
// du tangage courant. L'arc couvre ±100°, le servo ±90° :
//   limite = 90° − |θ| − marge, plafonnée par la butée dure de feet.cpp.
// La marge (9°) couvre le retard du servo et l'incertitude de calage
// du palonnier (4 positions à 90° : jusqu'à quelques degrés d'erreur).
constexpr float kFootMarginDeg = 9.0f;
constexpr float kFootHardDeg   = FOOT_HARD_DEG;   // = butée dure de feet.cpp (config.h)
// Le soft clamp s'ouvre progressivement sur les 10 derniers degrés :
// une coupure franche exciterait le pendule.
constexpr float kFootTaperDeg  = 10.0f;

// ── Recentrage en CASCADE (remplace le trim d'angle) ───────────────
// Le trim précédent (±0.4° sur θ_ref) était trop faible : après une tape
// qui laissait le pied à 36°, le robot restait collé près de la butée et
// tombait à la perturbation suivante. On asservit désormais la POSITION
// du pied par une cascade classique :
//
//   externe (10 Hz)  : v_cible = kRecenterKpPhi · (0 − φ)   borné ±VelMax
//   interne (200 Hz) : θ_ref  += kRecenterKv · (v_cible − φ̇)  borné ±RefMax
//   PID 200 Hz       : maintient θ = θ_ref (inchangé)
//
// φ̇ est estimé SANS ENCODEUR : dériver la position intégrée par feet.cpp
// serait bruité, on filtre à la place la VITESSE COMMANDÉE par un 1er
// ordre τ = kFootVelTau — ce qui approxime la réponse du servo, et c'est
// exactement ce qui a été simulé (sim/cascade_recenter.md).
//
// Au centre et à l'arrêt (φ = 0, φ̇ = 0) la contribution est nulle : le
// PID retrouve son comportement normal. NON-const : réglables à chaud.
constexpr unsigned long kRecenterPeriodMs = 100;   // 10 Hz (boucle externe)
float kRecenterKpPhi = 0.8f;    // °/s de v_cible par ° d'erreur de pied
float kRecenterKv    = 3.0f;    // ° de θ_ref par °/s d'erreur de vitesse
constexpr float kRecenterVelMax = 20.0f;  // borne de v_cible (°/s)
constexpr float kRecenterRefMax = 6.0f;   // borne de la contribution θ_ref (°)
constexpr float kRecenterSlew   = 3.0f;   // rampe de v_cible (°/s²)
constexpr float kFootVelTau     = 0.08f;  // filtre de la vitesse commandée (s)
constexpr float kFootPanicDeg   = 35.0f;  // butée imminente → halt()

// Bornes de réglage à chaud des gains de cascade
constexpr float kRecenterKpPhiMax = 5.0f;
constexpr float kRecenterKvMax    = 20.0f;

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
// Trames IMU consécutives perdues tolérées avant coupure : à 200 Hz,
// 20 trames ≈ 100 ms. En deçà, l'angle précédent tient (micro-coupure
// I2C) ; au-delà, on asservirait sur une mesure figée.
constexpr uint16_t     kImuFailMax = 20;

// ── Surveillance de cadence ─────────────────────────────────────────
// Sous ce seuil, la boucle ne pilote plus correctement les pieds (l'UI,
// le TFT ou le web lui ont volé du temps) : on coupe plutôt que de laisser
// un asservissement faux. La grâce couvre le démarrage (WiFi/TFT).
constexpr float         kMinLoopHz   = 120.0f;
constexpr unsigned long kRateGraceMs = 3000;

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
// REPRISE AUTOMATIQUE après s_imuLost / s_rateLow — choix documenté
// (REVIEW_CLAUDE.md M19), comportement volontairement CONSERVÉ : les deux
// drapeaux se relèvent SEULS dès que la cause disparaît (une trame IMU
// repasse, la cadence revient), sans réarmement par l'utilisateur. Limite :
// pendant la coupure les pieds sont figés (halt) et l'angle n'a plus
// intégré le gyro ; à la reprise l'estimation reconverge sur l'accel en
// ~0,25 s et l'état réel du robot est inconnu. Robot TENU à la main
// (campagne de réglage) : acceptable. Robot LIBRE : pas plus sûr que
// d'exiger un réarmement — il est probablement déjà par terre, et c'est
// alors le verrou de chute (|θ| > kFallAngleDeg) qui prend le relais.
bool  s_imuLost   = false;         // IMU muet : équilibre coupé jusqu'au retour
float s_fwdSmooth = 0.0f;          // consignes UI lissées
float s_turnSmooth= 0.0f;
float s_lastRateDps = 0.0f;        // dernière vitesse gyro (télémétrie web)
unsigned long s_lastMicros   = 0;
unsigned long s_uprightSince = 0;  // début de la fenêtre de redressement
bool          s_rateLow      = false;  // boucle trop lente → arrêt de sécurité

// ── Gains persistants (NVS) ────────────────────────────────────────
// Sans ça, chaque reset repart sur les valeurs de compilation et tout le
// réglage fait au banc web est perdu (le flash n'est pas infini : on
// throttle les écritures).
Preferences   s_prefs;
bool          s_prefsOk     = false;
unsigned long s_lastSaveMs  = 0;
constexpr unsigned long kSaveThrottleMs = 1500;

float         s_recenterVel  = 0.0f;  // v_cible lissée de la boucle externe (°/s)
float         s_footVelFilt  = 0.0f;  // vitesse de pied commandée, filtrée (°/s)
unsigned long s_recenterLast = 0;     // dernier passage de la boucle 10 Hz

inline float slew(float current, float target, float maxStep) {
  const float delta = target - current;
  if (delta >  maxStep) return current + maxStep;
  if (delta < -maxStep) return current - maxStep;
  return target;
}

// Écrit les gains en NVS (throttlé : un glissement de slider = 1 écriture).
void saveGains() {
  if (!s_prefsOk) return;
  const unsigned long now = millis();
  if (now - s_lastSaveMs < kSaveThrottleMs) return;
  s_lastSaveMs = now;
  s_prefs.putFloat("kp",    kKp);
  s_prefs.putFloat("ki",    kKi);
  s_prefs.putFloat("kd",    kKd);
  s_prefs.putFloat("kpPhi", kRecenterKpPhi);
  s_prefs.putFloat("kv",    kRecenterKv);
  s_prefs.putFloat("kout",  kOutToFootDegS);
}

// Coupe tout : pieds freinés SUR PLACE (surtout pas de retour au neutre,
// qui ferait basculer un robot debout), intégrateurs vidés, état à jour.
void halt() {
  Feet::stop();
  s_pid.reset();
  s_fwdSmooth = 0.0f;
  s_turnSmooth = 0.0f;
  s_recenterVel = 0.0f;
  s_footVelFilt = 0.0f;
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

// Boucle EXTERNE de la cascade, appelée à 10 Hz : la position du pied
// donne une consigne de VITESSE de pied, montée en rampe pour éviter les
// à-coups. Renvoie false si les pieds sont si loin que la butée est
// imminente (l'appelant coupe alors tout).
bool recenterStep(float footAvg, float dtRec) {
  if (fabsf(footAvg) > kFootPanicDeg) return false;

  // Pied parti vers l'avant ⇒ il faut le ramener en ARRIÈRE : v_cible
  // est de signe opposé à φ (φ_ref = 0).
  const float target = constrain(kRecenterKpPhi * (0.0f - footAvg),
                                 -kRecenterVelMax, kRecenterVelMax);
  s_recenterVel = slew(s_recenterVel, target, kRecenterSlew * dtRec);
  return true;
}

// Boucle INTERNE de la cascade (appelée à 200 Hz) : l'écart entre la
// vitesse de pied voulue et celle réellement commandée devient un angle.
//
// SIGNE NON TRANCHÉ — à décider en RÉEL (REVIEW_CLAUDE.md M1). Deux
// arguments s'opposent :
//   · (−), retenu ici depuis le 09/09 : un setpoint POSITIF fait pencher
//     le robot vers l'avant, ce qui commande au PID des pieds une rotation
//     vers l'ARRIÈRE (le point d'appui suit le CoM) ; pour RAMENER un pied
//     parti vers l'avant (φ > 0, v_cible négative) il faudrait donc un
//     setpoint positif, de signe opposé à (v_cible − φ̇) ;
//   · (+), cascade de vitesse classique du pendule inversé : pour
//     accélérer la base vers l'arrière il faut d'abord pencher vers
//     l'arrière — le raisonnement (−) décrit le transitoire à non-minimum
//     de phase, qui ne domine que parce que Kv·RefMax sature.
// La « vérification en simulation » du 09/09 (pied lâché à +20° → +37°)
// est CADUQUE : ce sim ne tenait pas le PID seul, les deux signes y
// donnent 0/6. Le sim (sim/balancebot_sim.py, boucle interne) est ALIGNÉ
// sur ce (−) — règle d'or — et porte le même avertissement. Premiers
// essais : Kv = 0 au banc web (contribution nulle, garde kFootPanicDeg
// toujours active), puis trancher le signe en réel avec Kv ≪ 1.
inline float recenterSetpoint() {
  return constrain(-kRecenterKv * (s_recenterVel - s_footVelFilt),
                   -kRecenterRefMax, kRecenterRefMax);
}

// Estimateur de vitesse de pied SANS ENCODEUR : 1er ordre sur la commande
// envoyée à feet.cpp (approxime le retard du servo).
inline void updateFootVel(float cmdDegS, float dt) {
  const float alpha = dt / (kFootVelTau + dt);
  s_footVelFilt += alpha * (cmdDegS - s_footVelFilt);
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
  s_imuLost = false;
  s_lastMicros = micros();
  s_recenterLast = millis();
  s_recenterVel = 0.0f;
  s_footVelFilt = 0.0f;

  // Gains persistants : recharge le réglage fait au banc web avant de
  // toucher aux pieds. Re-bornés (une NVS abîmée ne doit pas armer des
  // gains absurdes).
  s_prefsOk = s_prefs.begin("balancebot", false);
  if (s_prefsOk) {
    kKp = constrain(s_prefs.getFloat("kp", kKp), 0.0f, kKpMax);
    kKi = constrain(s_prefs.getFloat("ki", kKi), 0.0f, kKiMax);
    kKd = constrain(s_prefs.getFloat("kd", kKd), 0.0f, kKdMax);
    kRecenterKpPhi = constrain(s_prefs.getFloat("kpPhi", kRecenterKpPhi), 0.0f, kRecenterKpPhiMax);
    kRecenterKv    = constrain(s_prefs.getFloat("kv",    kRecenterKv),    0.0f, kRecenterKvMax);
    kOutToFootDegS = constrain(s_prefs.getFloat("kout",  kOutToFootDegS), kOutToFootMin, kOutToFootMax);
    Serial.printf("GAINS NVS : Kp=%.1f Ki=%.0f Kd=%.2f | Kpφ=%.1f Kv=%.1f | kOut=%.1f\n",
                  kKp, kKi, kKd, kRecenterKpPhi, kRecenterKv, kOutToFootDegS);
  }

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

  // Calibration du neutre : biais gyro mesuré robot posé, immobile
  // (~2 s bloquantes, 400 vrais échantillons à 200 Hz — REVIEW_CLAUDE.md
  // M18). Un échec (bus instable, trames figées) laisse le biais gyro à 0
  // et l'angle amorcé par Imu::begin() : on le DIT sur le port série
  // (setup(), pas encore le chemin chaud) sans couper l'IMU pour autant.
  if (!Imu::calibrate()) {
    Serial.println("IMU       : calibration ÉCHOUÉE (lectures invalides) — biais gyro laissé à 0");
  }
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
      // Surveillance : passé la grâce de démarrage, une cadence sous le
      // seuil met l'asservissement en sécurité (il revient tout seul).
      if (nowMs > kRateGraceMs) s_rateLow = (g_state.balanceHz < kMinLoopHz);
    }
  }

  // Cadence insuffisante : on ne pilote plus (voir kMinLoopHz).
  if (s_rateLow) {
    halt();
    publishFeet();
    return;
  }

  bool want = isEnabled();
  // Refus d'ARMER sur batterie faible : sous BAT_LOW_V la cellule est à
  // ~10 % et l'appel de courant des servos fait s'effondrer la tension
  // (brownout → reboot en pleine correction). On annule la demande.
  // Sur le FRONT MONTANT seulement (REVIEW_CLAUDE.md M6) : testée à chaque
  // itération, cette garde désarmait aussi un robot DEBOUT (halt() →
  // chute) sur un seul échantillon ADC en creux. batteryLow est désormais
  // hystérétique et débouncé (battery.cpp), et un robot déjà en équilibre
  // n'est plus coupé : l'écran (« BAT. FAIBLE ») et le visage rouge
  // préviennent, c'est à l'utilisateur de le poser ; le prochain armement
  // sera refusé.
  if (want && !s_enabled && g_state.batteryLow) {
    g_state.cmdEnabled = false;
    want = false;
  }
  if (want && !s_enabled) {          // front montant : on repart propre
    s_pid.reset();
    s_lastMicros = micros();
    s_uprightSince = 0;
    // Armement par g_state.cmdEnabled (l'UI et le banc web n'appellent pas
    // setEnabled) : sans ça, s_recenterLast daterait de la dernière
    // désactivation et le premier pas de la boucle externe verrait un dt
    // de plusieurs secondes — soit toute la rampe franchie d'un bloc.
    s_recenterLast = millis();
    s_recenterVel = 0.0f;
    s_footVelFilt = 0.0f;
  } else if (!want && s_enabled) {   // front descendant : arrêt propre
    halt();
  }
  s_enabled = want;

  if (!s_imuOk) {
    // Pas d'IMU : aucun équilibre possible, mais la mécanique reste
    // pilotable en démo par les flèches de l'UI.
    // halt() sur FRONT seulement (REVIEW_CLAUDE.md M7) : appelé à chaque
    // itération, il réarmait Feet::s_lastMicros (via Feet::stop()) quelques
    // µs avant le driveFootSpeed() de demoStep(), qui voyait dt ≈ 20 µs →
    // borné à 0,5 ms au lieu des 5 ms réels : la démo roulait 10× trop
    // lentement. s_imuOk est figé au boot : le seul front est la première
    // itération (un désarmement passe, lui, par le front descendant traité
    // plus haut, qui appelle halt()).
    static bool s_noImuHalted = false;
    if (!s_noImuHalted) {
      s_noImuHalted = true;
      halt();
    }
    demoStep();
    return;
  }

  // Servos de pieds non attachés : φ resterait à 0 alors que les pieds
  // sont morts — le robot « équilibrerait » dans le vide et tomberait.
  if (!Feet::ready()) {
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
  // Une trame perdue (bus I2C secoué) : l'angle précédent tient. Au-delà
  // de kImuFailMax consécutives, on asservirait sur une mesure FIGÉE — on
  // coupe et on attend le retour du capteur (s_imuLost se relève seul dès
  // qu'une trame repasse). Un capteur qui ACK mais renvoie des registres
  // figés compte aussi comme « trame perdue » (imu.cpp, kFrozenMax —
  // REVIEW_CLAUDE.md M9).
  static uint16_t s_imuFailStreak = 0;
  if (Imu::update(dt)) {
    s_imuFailStreak = 0;
    s_imuLost = false;
  } else if (++s_imuFailStreak >= kImuFailMax) {
    s_imuLost = true;
    halt();
    publishFeet();
    return;
  }
  const float pitch = Imu::pitchDeg();
  const float rate  = Imu::pitchRateDps();
  g_state.pitchDeg  = pitch;
  s_lastRateDps     = rate;          // exposé au banc web (télémétrie seule)

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

  // ── Cascade de recentrage — boucle externe (10 Hz) ───────────────
  // Le débattement du servo est fini : sans cette boucle le pied part
  // en butée et le robot tombe. On n'agit QUE sur θ_ref, jamais sur la
  // sortie du PID.
  const float footAvg = Feet::angleAvg();
  {
    const unsigned long ms = millis();
    if (ms - s_recenterLast >= kRecenterPeriodMs) {
      // dt borné : un hoquet de boucle ne doit pas franchir la rampe
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
  // La boucle INTERNE de la cascade s'ajoute ici, à pleine cadence : elle
  // suit s_footVelFilt qui, lui, évolue à 200 Hz.
  const float setpoint =
      kSetpointDeg + s_fwdSmooth * kTiltPerCmd + recenterSetpoint();
  float error = setpoint - pitch;
  if (fabsf(error) < kErrDeadbandDeg) error = 0.0f;   // mort-zone d'erreur

  // SIGNE DE LA CONTRE-RÉACTION — ne pas « simplifier » cette inversion.
  // Le PID ci-dessus est un PID standard sur (consigne − mesure). Un pendule
  // INVERSÉ demande le signe OPPOSÉ : quand le robot penche vers l'avant
  // (pitch > 0 ⇒ error < 0), il faut que les pieds roulent vers l'AVANT
  // (out > 0) pour ramener le point d'appui sous le centre de gravité.
  // Sans cette inversion la boucle est une contre-réaction POSITIVE (le
  // terme en θ̇ comme celui en θ déstabilisent) et le robot pique du nez.
  // C'est exactement ce que fait le simulateur validé, qui intègre −ctrl()
  // (sim/balancebot_sim.py : « u = -self.ctrl(noise) »).
  // Tout ce qui suit (soft clamp, estimateur φ̇, différentiel) attend un
  // « out » homogène à une VITESSE DE PIED : l'inversion doit rester ici,
  // avant ces étages.
  float out = -s_pid.update(error, rate, dt);
  out = constrain(out, -kOutMax, kOutMax);
  // Soft clamp de butée : la commande s'éteint avant le bout de l'arc.
  out = limitTowardStop(out, footAvg, pitch);

  // Estimation de φ̇ pour la boucle interne : on filtre la commande de
  // vitesse MOYENNE, prise APRÈS le clamp (c'est ce que les pieds font
  // vraiment) et AVANT le différentiel (qui s'annule en moyenne).
  updateFootVel(out * kOutToFootDegS, dt);

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

// Passe par le DRAPEAU partagé : la boucle d'équilibre reste la SEULE à
// écrire sur les servos (un appelant venu du banc web, sur une autre
// tâche, ne doit pas toucher aux canaux PWM pendant qu'elle pilote). Le
// reset du PID et la purge des consignes UI se font sur front MONTANT
// dans loop(), l'arrêt sur front DESCENDANT.
void setEnabled(bool on) {
  g_state.cmdEnabled = on;
}

// État ARMÉ = la DEMANDE (contrat interfaces.h), pas l'état appliqué :
// l'UI et le banc web voient leur clic immédiatement, l'application se
// fait au cycle suivant (≤ 5 ms).
bool isEnabled() { return g_state.cmdEnabled; }

// Verrou de chute : vrai tant que le robot n'a pas été redressé et tenu
// vertical kRecoverHoldMs. L'UI s'en sert pour afficher « CHUTE » (et
// pour ne PAS confondre avec un simple obstacle).
bool isFallen() { return s_fallen; }

bool imuOk() { return s_imuOk; }

// Perte d'IMU À CHAUD (trames manquantes au-delà de kImuFailMax) et mise en
// sécurité de cadence (< kMinLoopHz). Distincts de imuOk(), figé au boot :
// sans eux, un robot dont l'IMU décroche ou dont la cadence s'effondre gardait
// un visage impassible (FINAL_REVIEW constat 6).
bool imuLost() { return s_imuLost; }
bool rateLow() { return s_rateLow; }

// ── Réglage à chaud des gains (banc web — tuner.cpp) ───────────────
// Bornées : une valeur aberrante envoyée depuis le téléphone (doigt qui
// dérape, requête tronquée) ne doit pas pouvoir faire diverger le PID.
// NaN → gain laissé inchangé (constrain() ne filtre pas les NaN).
void setGains(float kp, float ki, float kd) {
  if (!isnan(kp)) kKp = constrain(kp, 0.0f, kKpMax);
  if (!isnan(ki)) kKi = constrain(ki, 0.0f, kKiMax);
  if (!isnan(kd)) kKd = constrain(kd, 0.0f, kKdMax);
  saveGains();
}

void getGains(float& kp, float& ki, float& kd) {
  kp = kKp;  ki = kKi;  kd = kKd;
}

// ── Gains de la cascade de recentrage (mêmes règles) ───────────────
void setRecenterGains(float kpPhi, float kv) {
  if (!isnan(kpPhi)) kRecenterKpPhi = constrain(kpPhi, 0.0f, kRecenterKpPhiMax);
  if (!isnan(kv))    kRecenterKv    = constrain(kv,    0.0f, kRecenterKvMax);
  saveGains();
}

void getRecenterGains(float& kpPhi, float& kv) {
  kpPhi = kRecenterKpPhi;  kv = kRecenterKv;
}

// ── Autorité de sortie (°/s de pied par unité de sortie PID) ────────
// Bornée 1-3 (REVIEW_CLAUDE.md M11) : sous 1 le robot n'a plus de quoi se
// rattraper, au-delà de 3 on dépasse ce qu'un SG90 tient à vide.
void setOutScale(float k) {
  if (!isnan(k)) kOutToFootDegS = constrain(k, kOutToFootMin, kOutToFootMax);
  saveGains();
}

float getOutScale() { return kOutToFootDegS; }

float pitchRateDps() { return s_lastRateDps; }

} // namespace Balance
