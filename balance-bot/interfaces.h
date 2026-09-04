#pragma once
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
  float batteryV  = 0.0f;    // tension batterie
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

// ── Module A : équilibre (imu.h / balance.h / wheels.h) ────────────
// Implémente : IMU MPU6050 sur I2C, filtre, PID 200 Hz, roues servo.
namespace Balance {
  bool  begin();                 // init IMU + servos ; false si IMU absent
  void  loop();                  // 1 itération 200 Hz (appelée par le .ino)
  void  setEnabled(bool on);     // active/coupe l'asservissement
  bool  isEnabled();
  bool  imuOk();                 // true si MPU6050 répond
}

// ── Module B : UI tactile (ui.h) ───────────────────────────────────
// Implémente : écran TFT_eSPI + TouchLib, boutons, télémétrie.
namespace Ui {
  bool  begin();                 // init écran + touch
  void  loop();                  // lecture tactile + rendu (appelée souvent)
  void  setStatusLine(const char* text);  // ligne d'état libre (ex: mode)
}

// ── Module C : tête + ultrason (head.h / ultrasonic.h) ─────────────
// Implémente : 2 servos pan/tilt + HC-SR04, balayage obstacles.
namespace Head {
  bool  begin();
  void  loop();                  // asservit pan/tilt + lit l'ultrason
  void  scan();                  // déclenche un balayage 180° (mode auto)
}

// ── Utilitaire batterie (battery.h — lu par UI + boucle) ───────────
namespace Battery {
  void  begin();
  float readVolts();             // via PIN_BAT_VOLT (ADC atténué)
}
