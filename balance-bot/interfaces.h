#pragma once
#include <stdint.h>  // uint8_t etc. — certains .cpp incluent ce header avant Arduino.h
// ═══════════════════════════════════════════════════════════════════
// BalanceBot — interfaces inter-modules (CONTRAT — ne pas modifier)
// Chaque module implémente ses .cpp contre CES headers. Hermes assemble
// le .ino principal. Les signatures ci-dessous sont gelées.
// ═══════════════════════════════════════════════════════════════════

// ── État partagé du robot (mis à jour par chaque module) ────────────
//
// ACCÈS CONCURRENT (BALANCE_SPLIT_CORES=1) — méthode retenue : « un mot
// machine, un seul écrivain ». Chaque champ est un scalaire ≤ 32 bits
// naturellement aligné : sur Xtensa LX7 une lecture/écriture d'un tel mot
// est ATOMIQUE (jamais de valeur « à moitié écrite »), ni mutex ni section
// critique nécessaires. Chaque champ n'a qu'UN écrivain (tableau ci-dessous),
// l'autre cœur ne fait que lire ; aucune décision ne dépend de la cohérence
// de DEUX champs lus ensemble (cmdForward/cmdTurn sont lissés, un pas de
// décalage entre eux est invisible). Seule exception : cmdEnabled, écrit par
// l'UI/le banc web (armer) ET par la boucle (refus sur batterie faible) —
// un bool, dernier écrivain gagnant, et c'est le comportement voulu.
// Les drapeaux d'arrêt sûr (balLastStepMs, estop) sont volatile : leur
// lecteur boucle dessus, le compilateur ne doit pas les mettre en registre.
//
//   écrivain = tâche d'équilibre (cœur 0) : balancing, pitchDeg, balanceHz,
//     footLDeg, footRDeg, dbgBalMs, dbgBalMaxMs, balLastStepMs
//     (dbgBalMs est aussi remis à zéro chaque seconde par loop() :
//     diagnostic seul, un maximum perdu est sans conséquence)
//   écrivain = loop() / cœur 1 : tout le reste (UI, tête, batterie, tuner,
//     diagnostic, évitement, estop)
struct BotState {
  // boucle d'équilibre (module A)
  bool  balancing = false;   // vrai quand le robot tient debout
  float pitchDeg  = 0.0f;    // inclinaison mesurée
  float balanceHz = 0.0f;    // fréquence RÉELLE de la boucle d'équilibre
  int   footLDeg  = 0;       // angle du pied gauche (° ; 0 = repos, + = avant)
  int   footRDeg  = 0;       // angle du pied droit  (idem)
  uint8_t dbgUiMs  = 0;      // pire temps d'Ui::loop (ms, dernière seconde)
  uint8_t dbgHeadMs = 0;     // pire temps de Head::loop (ms, dernière seconde)
  // Diagnostic de cadence (enquête 09/09 : chutes de balanceHz) — permet de
  // distinguer « le corps de loop() a duré longtemps » (phase nommée par
  // dbgGapPhase) de « le départ de loop() a été retardé de l'extérieur »
  // (dbgLoopMs reste petit, cause = interruption/WiFi/cache flash).
  uint16_t dbgGapMs   = 0;   // plus grand écart entre 2 départs de loop() (s en cours)
  uint16_t dbgWorstMs = 0;   // plus grand écart depuis le boot
  uint8_t  dbgGapPhase = 5;  // phase exécutée avant l'écart (0 bal,1 ui,2 head,3 boot,4 bat,5 autre)
  uint8_t  dbgLoopMs  = 0;   // pire durée d'un corps de loop() (s en cours)
  uint8_t  dbgBalMs   = 0;   // pire durée de Balance::loop() (s en cours)
  uint8_t  dbgBatMs   = 0;   // pire durée de la lecture batterie (s en cours)
  uint16_t dbgStalls  = 0;   // secondes où balanceHz < 120 (hors 0)
  // Signature du DERNIER gros écart (> 100 ms) : dit si la boucle était
  // lente (corps long) ou seulement privée de CPU (corps court).
  uint16_t dbgBigGaps = 0;   // nombre d'écarts > 100 ms depuis le boot
  uint16_t dbgLastGapMs = 0;
  uint8_t  dbgLastGapPhase = 5;
  uint8_t  dbgLastGapLoopMs = 0;
  // Max CUMULATIFS (jamais remis à zéro) : la remise à zéro par seconde
  // effaçait justement la preuve pendant la seconde de la chute.
  uint16_t dbgBalMaxMs = 0, dbgUiMaxMs = 0, dbgHeadMaxMs = 0, dbgBatMaxMs = 0;
  uint16_t dbgLoopMaxMs = 0;
  uint16_t dbgTouchMaxMs = 0;  // pire g_touch->read() (I2C CST816) — cumulatif
  uint16_t dbgDrawMaxMs  = 0;  // pire bloc de dessin dans Ui::loop() — cumulatif
  float batteryV  = 0.0f;    // tension batterie (-1 = aucune batterie plausible : USB seul)
  bool  batteryLow = false;  // vrai si lecture valide ET sous BAT_LOW_V (hystérésis + N lectures, battery.cpp)
  // commandes UI (module B) — consommées par la boucle d'équilibre
  int   cmdForward = 0;      // -100..+100 (vitesse avant/arrière)
  int   cmdTurn    = 0;      // -100..+100 (rotation)
  bool  cmdEnabled = false;  // mode auto (équilibre) activé par l'UI
  // tête + ultrason (module C)
  int   headPanDeg = 90;     // position courante pan
  int   headTiltDeg= 60;     // position courante tilt
  float obstacleCm = -1.0f;  // distance mesurée (-1 = hors portée)
  bool  obstacleWarn = false;// vrai si obstacle < US_STOP_CM
  bool  obstacleSlow = false;// vrai si US_STOP_CM ≤ obstacle < US_SLOW_CM
  int8_t obstacleSide = 0;   // côté où l'obstacle a été vu : -1 pan<90, +1 pan>90, 0 en face/inconnu
  // Évitement (module C, calculé sur le cœur 1 ; consommé par balance.cpp
  // AVANT le lissage des consignes — jamais sur le PID) :
  int   avoidFwdMax = 100;   // plafond de cmdForward : 100 libre, 40 ralenti, 0 stop, <0 recul imposé
  int   avoidTurn   = 0;     // pivot imposé si l'UI ne tourne pas (-100..100, 0 = aucun)
  uint8_t avoidPhase = 0;    // 0 libre · 1 ralenti · 2 recul+pivot · 3 pivot seul (recul épuisé)
  // Arrêt sûr : date (millis) du dernier DÉPART de pas d'équilibre — écrit par
  // la boucle à chaque pas, lu par la surveillance de loop() (cœur 1).
  volatile uint32_t balLastStepMs = 0;
  volatile bool estop = false;   // arrêt d'urgence verrouillé (RESET pour repartir)
  // horloge de rendu UI (ms) — pour ne rafraîchir que si changement
  unsigned long uiTick = 0;
};

extern BotState g_state;     // instance globale unique, définie dans le .ino

// ── Module A : équilibre (imu.h / balance.h / feet.h) ──────────────
// Implémente : IMU MPU6050 sur I2C, filtre, PID 200 Hz, roues sur servos
// à rotation CONTINUE (FEET_MODE_CONTINUOUS=1, robot réel) ou pieds en
// arc sur servos de position (=0, ancienne mécanique v3.1).
namespace Balance {
  bool  begin();                 // init IMU + servos ; false si IMU absent
  void  loop();                  // 1 itération 200 Hz (appelée par le .ino)
  void  setEnabled(bool on);     // active/coupe l'asservissement
  bool  isEnabled();             // ARMÉ (commande) — ≠ g_state.balancing (debout)
  bool  isFallen();              // verrou de chute actif (attend le redressement)
  bool  imuOk();                 // true si MPU6050 répond
  bool  imuLost();               // IMU muette EN COURS (> kImuFailMax trames)
  bool  rateLow();               // cadence sous kMinLoopHz → arrêt de sécurité
  // Réglage à chaud (module D — banc web). Ajout non intrusif : la boucle
  // d'équilibre lit simplement des variables au lieu de constantes.
  void  setGains(float kp, float ki, float kd);  // bornés 0-100 / 0-2000 / 0-20
  void  getGains(float& kp, float& ki, float& kd);
  // Cascade de recentrage des pieds (position φ → vitesse → θ_ref).
  void  setRecenterGains(float kpPhi, float kv);  // bornés 0-5 / 0-20
  void  getRecenterGains(float& kpPhi, float& kv);
  // Autorité de sortie kOutToFootDegS (°/s de pied par unité de sortie PID),
  // bornée 1-3, persistée NVS — REVIEW_CLAUDE.md M11.
  void  setOutScale(float k);
  float getOutScale();
  float pitchRateDps();          // dernière vitesse gyro (°/s) — télémétrie
  // ── Arrêt sûr ──────────────────────────────────────────────────
  // Surveillance appelée par loop() (cœur 1) à chaque itération : si la
  // boucle d'équilibre n'a pas démarré de pas depuis BALANCE_STALL_MS,
  // coupe les roues (PWM détaché) depuis ce cœur-ci. Renvoie true tant
  // que la coupure est active. La boucle, si elle repart, réarme seule.
  bool  watchdog(unsigned long nowMs);
  bool  stalled();               // coupure « boucle figée » en cours
  // Arrêt d'urgence (bouton PIN_ESTOP) : roues coupées immédiatement,
  // verrouillé jusqu'au RESET — aucune reprise logicielle possible.
  void  emergencyStop();
  bool  emergencyStopped();
  bool  wheelsCut();             // PWM des roues détaché (chute, figée ou estop)
}

// ── Module D : banc de réglage web (tuner.h) ───────────────────────
// Point d'accès WiFi + serveur HTTP pour régler le PID sans reflasher.
// Entièrement inerte tant qu'aucun client ne sollicite le serveur.
namespace Tuner {
  bool  begin();                 // ouvre l'AP « BalanceBot-Tune » ; false si échec
  void  loop();                  // no-op : le serveur vit sur sa propre tâche (TUNER_TASK_CORE) ; conservé pour le contrat
  bool  active();                // true si un client a dialogué récemment
}

// ── Module B : UI tactile (ui.h) ───────────────────────────────────
// Implémente : écran TFT_eSPI + TouchLib, boutons, télémétrie.
namespace Ui {
  bool  begin();                 // init écran + touch
  void  loop();                  // lecture tactile + rendu (appelée souvent)
}

// ── Module C : tête + ultrason (head.h / ultrasonic.h) ─────────────
// Implémente : 2 servos pan/tilt + HC-SR04, balayage obstacles.
namespace Head {
  bool  begin();
  void  loop();                  // asservit pan/tilt + lit l'ultrason
  // scan() supprimé : c'était un no-op appelé toutes les 500 ms. Le
  // balayage est assuré par le mouvement continu de handleHeadMovement().
}

// ── Utilitaire batterie (battery.h — lu par UI + boucle) ───────────
namespace Battery {
  void  begin();
  float readVolts();             // via PIN_BAT_VOLT (ADC atténué) ; -1 si invalide
  bool  isLow();                 // batterie faible (hystérésis 3,5/3,6 V + N lectures consécutives)
}
