#pragma once
#include <stdint.h>  // uint8_t etc. — certains .cpp incluent ce header avant Arduino.h
// ═══════════════════════════════════════════════════════════════════
// BalanceBot — interfaces inter-modules (CONTRAT — ne pas modifier)
// Chaque module implémente ses .cpp contre CES headers. Hermes assemble
// le .ino principal. Les signatures ci-dessous sont gelées.
// ═══════════════════════════════════════════════════════════════════

// ── État partagé du robot (mis à jour par chaque module) ────────────
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
  bool  batteryLow = false;  // vrai si lecture valide ET sous BAT_LOW_V
  // commandes UI (module B) — consommées par la boucle d'équilibre
  int   cmdForward = 0;      // -100..+100 (vitesse avant/arrière)
  int   cmdTurn    = 0;      // -100..+100 (rotation)
  bool  cmdEnabled = false;  // mode auto (équilibre) activé par l'UI
  // tête + ultrason (module C)
  int   headPanDeg = 90;     // position courante pan
  int   headTiltDeg= 60;     // position courante tilt
  float obstacleCm = -1.0f;  // distance mesurée (-1 = hors portée)
  bool  obstacleWarn = false;// vrai si obstacle < US_STOP_CM
  // horloge de rendu UI (ms) — pour ne rafraîchir que si changement
  unsigned long uiTick = 0;
};

extern BotState g_state;     // instance globale unique, définie dans le .ino

// ── Module A : équilibre (imu.h / balance.h / feet.h) ──────────────
// Implémente : IMU MPU6050 sur I2C, filtre, PID 200 Hz, pieds en arc
// sur servos de POSITION (mécanique v2 — plus de roues).
namespace Balance {
  bool  begin();                 // init IMU + servos ; false si IMU absent
  void  loop();                  // 1 itération 200 Hz (appelée par le .ino)
  void  setEnabled(bool on);     // active/coupe l'asservissement
  bool  isEnabled();             // ARMÉ (commande) — ≠ g_state.balancing (debout)
  bool  isFallen();              // verrou de chute actif (attend le redressement)
  bool  imuOk();                 // true si MPU6050 répond
  // Réglage à chaud (module D — banc web). Ajout non intrusif : la boucle
  // d'équilibre lit simplement des variables au lieu de constantes.
  void  setGains(float kp, float ki, float kd);  // bornés 0-100 / 0-2000 / 0-20
  void  getGains(float& kp, float& ki, float& kd);
  // Cascade de recentrage des pieds (position φ → vitesse → θ_ref).
  void  setRecenterGains(float kpPhi, float kv);  // bornés 0-5 / 0-20
  void  getRecenterGains(float& kpPhi, float& kv);
  float pitchRateDps();          // dernière vitesse gyro (°/s) — télémétrie
}

// ── Module D : banc de réglage web (tuner.h) ───────────────────────
// Point d'accès WiFi + serveur HTTP pour régler le PID sans reflasher.
// Entièrement inerte tant qu'aucun client ne sollicite le serveur.
namespace Tuner {
  bool  begin();                 // ouvre l'AP « BalanceBot-Tune » ; false si échec
  void  loop();                  // sert au plus une requête (no-op si !begin())
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
  bool  isLow();                 // dernière lecture valide sous le seuil bas
}
