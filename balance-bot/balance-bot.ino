// ═══════════════════════════════════════════════════════════════════
// BalanceBot — sketch principal (assemblage)
// T-Display-S3-Touch (ESP32-S3) · 2 roues sur servos continus + tête
// pan/tilt (SG90) · MPU6050 (I2C) · HC-SR04 · châssis imprimé ₿
//
// RÉPARTITION SUR LES DEUX CŒURS (BALANCE_SPLIT_CORES = 1, config.h) :
//   cœur 0, tâche « balance », priorité BALANCE_TASK_PRIO :
//       capteur d'assiette → correcteur → roues, à BALANCE_LOOP_HZ,
//       cadencée par vTaskDelayUntil (période exacte, sans dérive) ;
//   cœur 1, loop() Arduino : écran (60 Hz), tête + ultrason (50 Hz —
//       le pulseIn() bloquant y vit désormais sans toucher l'équilibre),
//       batterie (1 Hz), boutons, surveillance de la boucle d'équilibre.
//   Le banc web (tuner.cpp) garde sa propre tâche, déplacée sur le cœur 1.
// Avec BALANCE_SPLIT_CORES = 0 : tout dans loop(), comme avant (repli).
// Dans les deux cas Balance::loop() est appelée à la MÊME cadence, avec
// la MÊME loi de commande : seul l'appelant change.
//
// PARTAGE DE DONNÉES : uniquement via g_state (BotState, interfaces.h),
// « un mot machine, un seul écrivain » — voir le commentaire du struct.
// ═══════════════════════════════════════════════════════════════════
#include <Arduino.h>

#include "config.h"
#include "interfaces.h"
#include "tuner.h"
#include "ui.h"          // Ui::showTip() (appui court KEY)

// État global unique — défini ICI, déclaré extern dans interfaces.h
BotState g_state;

// ── Un pas d'équilibre, avec sa mesure de durée ─────────────────────
// Partagé par les deux modes de compilation : la tâche (cœur 0) ou la
// phase de loop() (mono-cœur) appellent exactement ceci.
static inline void balanceStep() {
  const unsigned long t0 = micros();
  Balance::loop();
  const unsigned long dt = (micros() - t0) / 1000UL;
  if (dt > g_state.dbgBalMs)    g_state.dbgBalMs    = (uint8_t)min(dt, 255UL);
  if (dt > g_state.dbgBalMaxMs) g_state.dbgBalMaxMs = (uint16_t)min(dt, 65535UL);
}

#if BALANCE_SPLIT_CORES
// ── Tâche d'équilibre (cœur BALANCE_TASK_CORE) ──────────────────────
// vTaskDelayUntil : réveil à t0 + n·période, sans accumuler de retard.
// FreeRTOS tourne à 1000 Hz (CONFIG_FREERTOS_HZ) → 200 Hz = 5 ticks
// exacts. La tâche cède le cœur entre deux pas : l'IDLE0 tourne (le
// watchdog de tâche surveille l'IDLE du cœur 0), le WiFi (priorité 23)
// aussi. Aucun Serial ici : USB-CDC peut bloquer (STALL_ANALYSIS.md §6).
static TaskHandle_t s_balanceTask = nullptr;

static void balanceTask(void*) {
  TickType_t last = xTaskGetTickCount();
  const TickType_t period = pdMS_TO_TICKS(1000 / BALANCE_LOOP_HZ);
  for (;;) {
    vTaskDelayUntil(&last, period);
    balanceStep();
  }
}
#endif

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\n═══ BalanceBot boot ═══");

  // Power ON les périphériques (GPIO15 HIGH = obligatoire sur T-Display S3)
  pinMode(PIN_POWER_ON, OUTPUT);
  digitalWrite(PIN_POWER_ON, HIGH);

  // Boutons : BOOT (GPIO 0) = ARRÊT D'URGENCE (appui > ESTOP_HOLD_MS),
  // KEY (GPIO 14) = appui LONG : ouvrir/fermer le banc web ; appui COURT :
  // écran pourboire (QR Lightning — ROADMAP 4.2 étape 1).
  pinMode(PIN_ESTOP, INPUT_PULLUP);
  pinMode(PIN_TUNER_TOGGLE, INPUT_PULLUP);

  Battery::begin();

  if (Ui::begin())      Serial.println("UI        : OK");
  else                  Serial.println("UI        : ÉCHEC");

  if (Balance::begin()) Serial.println("ÉQUILIBRE : OK (IMU présent)");
  else                  Serial.println("ÉQUILIBRE : IMU absent — mode démo UI seulement");

  if (Head::begin())    Serial.println("TÊTE+US   : OK");
  else                  Serial.println("TÊTE+US   : ÉCHEC");

  // Banc de réglage web (AP « BalanceBot-Tune » → http://192.168.4.1).
  // Un échec n'empêche pas le boot : Tuner::loop() devient un no-op et
  // le robot se comporte exactement comme sans ce module.
  Tuner::begin();

#if BALANCE_SPLIT_CORES
  // Lancée en DERNIER : tous les begin() (I2C, servos, NVS) sont faits,
  // la tâche ne partage plus rien d'autre que g_state avec ce cœur.
  const BaseType_t ok = xTaskCreatePinnedToCore(
      balanceTask, "balance", BALANCE_TASK_STACK, nullptr,
      BALANCE_TASK_PRIO, &s_balanceTask, BALANCE_TASK_CORE);
  if (ok == pdPASS) Serial.printf("ÉQUILIBRE : tâche sur le cœur %d, priorité %d, %d Hz\n",
                                  BALANCE_TASK_CORE, (int)BALANCE_TASK_PRIO, BALANCE_LOOP_HZ);
  else              Serial.println("ÉQUILIBRE : ÉCHEC de création de la tâche — ROUES INERTES");
#else
  Serial.println("ÉQUILIBRE : mono-cœur (BALANCE_SPLIT_CORES = 0), dans loop()");
#endif

  Serial.println("═══ BalanceBot prêt ═══");
}

void loop() {
  const unsigned long nowMs = millis();
  const unsigned long loopT0 = micros();

  // ── Diagnostic de cadence (enquête 09/09) ───────────────────────
  // L'écart entre deux départs de loop() dit si la boucle a été retardée ;
  // la durée du corps (loopT0) dit si le retard vient de DEDANS. Les deux
  // ensemble séparent « phase lente » de « blocage externe » (WiFi, cache
  // flash, interruptions). s_lastPhase = dernière phase exécutée.
  static uint8_t       s_lastPhase = 5;
  static unsigned long tPrevLoop   = 0;
  static uint8_t       s_prevLoopMs = 0;
  const unsigned long gap = nowMs - tPrevLoop;
  tPrevLoop = nowMs;
  if (gap > g_state.dbgGapMs) {
    g_state.dbgGapMs   = (uint16_t)min(gap, 65535UL);
    g_state.dbgGapPhase = s_lastPhase;
  }
  if (gap > g_state.dbgWorstMs) g_state.dbgWorstMs = (uint16_t)min(gap, 65535UL);
  if (gap > 100) {                     // gros décrochage : on garde sa signature
    g_state.dbgBigGaps++;
    g_state.dbgLastGapMs     = (uint16_t)min(gap, 65535UL);
    g_state.dbgLastGapPhase  = s_lastPhase;
    g_state.dbgLastGapLoopMs = s_prevLoopMs;
  }

#if !BALANCE_SPLIT_CORES
  // ── Boucle d'équilibre : 200 Hz (mono-cœur) ─────────────────────
  // Toujours active même à l'arrêt : Balance::loop() mesure l'IMU en
  // continu (le PITCH affiché vit même sans équilibre) et ne pilote les
  // roues que si l'équilibre est activé.
  static unsigned long tBalance = 0;
  if (nowMs - tBalance >= (1000UL / BALANCE_LOOP_HZ)) {
    tBalance = nowMs;
    balanceStep();
    s_lastPhase = 0;
  }
#else
  // ── Surveillance de la boucle d'équilibre (cœur 0) ──────────────
  // Filet rendu possible par la séparation : si la tâche ne démarre plus
  // de pas pendant BALANCE_STALL_MS, ses roues sont coupées D'ICI.
  (void)Balance::watchdog(nowMs);
#endif

  // ── Arrêt d'urgence matériel : BOOT tenu > ESTOP_HOLD_MS ────────
  // Roues coupées, écran « ARRÊT » (Ui::loop), verrouillé jusqu'au RESET.
  // Vérifié AVANT l'écran et la tête : rien ne doit passer devant.
  {
    static unsigned long estopDownMs = 0;
    static bool estopPrev = false;
    const bool estopNow = (digitalRead(PIN_ESTOP) == LOW);
    if (estopNow && !estopPrev) estopDownMs = nowMs;
    else if (estopNow && !g_state.estop && (nowMs - estopDownMs >= ESTOP_HOLD_MS)) {
      Balance::emergencyStop();
    }
    estopPrev = estopNow;
  }

  // ── UI : 60 Hz (au lieu de « en continu ») ───────────────────────
  // Le touch CST816 partage le bus I2C avec le MPU6050. Le lire à chaque
  // itération de loop() (des milliers de fois/s) monopolise le bus et
  // dégrade la boucle d'équilibre. 60 Hz = latence tactile < 17 ms,
  // largement suffisant, et le bus respire.
  static unsigned long tUi = 0;
  if (nowMs - tUi >= 16) {
    tUi = nowMs;
    unsigned long t0 = micros();
    Ui::loop();
    unsigned long dt = (micros() - t0) / 1000UL;  // ms arrondi bas
    if (dt > g_state.dbgUiMs) g_state.dbgUiMs = (uint8_t)min(dt, 255UL);
    if (dt > g_state.dbgUiMaxMs) g_state.dbgUiMaxMs = (uint16_t)min(dt, 65535UL);
    s_lastPhase = 1;   // FINAL_REVIEW constat 2 : sans ça, un blocage de
                       // Ui::loop() était étiqueté « phase 0 = balance »
  }

  // ── Tête + ultrason : 50 Hz (l'ultrason est auto-cadencé à 200 ms /
  // 1 s en interne ; 50 Hz de mouvement pan/tilt est fluide pour des SG90) ──
  static unsigned long tHead = 0;
  if (nowMs - tHead >= 20) {
    tHead = nowMs;
    unsigned long t0 = micros();
    Head::loop();
    unsigned long dt = (micros() - t0) / 1000UL;
    if (dt > g_state.dbgHeadMs) g_state.dbgHeadMs = (uint8_t)min(dt, 255UL);
    if (dt > g_state.dbgHeadMaxMs) g_state.dbgHeadMaxMs = (uint16_t)min(dt, 65535UL);
    s_lastPhase = 2;
  }

  // ── Banc de réglage web ─────────────────────────────────────────
  // Le serveur HTTP vit sur sa propre tâche (TUNER_TASK_CORE) : plus rien
  // à cadencer ici. Appui long (TUNER_TOGGLE_HOLD_MS) sur KEY (GPIO 14)
  // = ouvrir/fermer l'AP ; appui COURT = écran pourboire (QR Lightning).
  // (BOOT est réservé à l'arrêt d'urgence.)
  static unsigned long keyDownMs = 0;
  static bool keyDone = false;
  static bool keyPrev = false;
  const bool keyNow = (digitalRead(PIN_TUNER_TOGGLE) == LOW);
  if (keyNow && !keyPrev) {
    keyDownMs = nowMs;
    keyDone = false;
  } else if (keyNow && !keyDone && (nowMs - keyDownMs >= TUNER_TOGGLE_HOLD_MS)) {
    keyDone = true;
    // Aucun Serial ici (STALL_ANALYSIS.md §6, REVIEW_CLAUDE M14) : la
    // trace « OUVERT / FERMÉ » est écrite par la tâche du tuner.
    (void)Tuner::toggle();
    s_lastPhase = 3;
  } else if (!keyNow && keyPrev && !keyDone) {
    // Appui COURT sur KEY (relâché avant TUNER_TOGGLE_HOLD_MS) : écran
    // pourboire (QR Lightning statique, TIP_LN_ADDRESS dans config.h).
    // Du dessin uniquement — aucune consigne, l'équilibre n'est pas touché.
    Ui::showTip();
    s_lastPhase = 3;
  }
  keyPrev = keyNow;

  // Batterie : lecture 1×/seconde (état global pour l'UI)
  static unsigned long tBat = 0;
  if (nowMs - tBat >= 1000) {
    tBat = nowMs;
    unsigned long t0 = micros();
    g_state.batteryV = Battery::readVolts();   // -1 = USB seul, pas de batterie
    g_state.batteryLow = Battery::isLow();
    unsigned long dt = (micros() - t0) / 1000UL;
    if (dt > g_state.dbgBatMs) g_state.dbgBatMs = (uint8_t)min(dt, 255UL);
    if (dt > g_state.dbgBatMaxMs) g_state.dbgBatMaxMs = (uint16_t)min(dt, 65535UL);
    s_lastPhase = 4;
    // Fenêtre de debug écoulée : on repart de zéro pour la seconde suivante
    g_state.dbgUiMs = 0;
    g_state.dbgHeadMs = 0;
    g_state.dbgBalMs = 0;
    g_state.dbgBatMs = 0;
    g_state.dbgGapMs = 0;
    g_state.dbgLoopMs = 0;
    if (g_state.balanceHz > 0.0f && g_state.balanceHz < 120.0f) g_state.dbgStalls++;
  }

  // Durée du corps de loop() : si elle reste petite alors que l'écart entre
  // deux départs explose, le retard vient de l'extérieur de loop().
  {
    unsigned long dt = (micros() - loopT0) / 1000UL;
    if (dt > g_state.dbgLoopMs) g_state.dbgLoopMs = (uint8_t)min(dt, 255UL);
    if (dt > g_state.dbgLoopMaxMs) g_state.dbgLoopMaxMs = (uint16_t)min(dt, 65535UL);
    s_prevLoopMs = (uint8_t)min(dt, 255UL);   // durée de CETTE itération, pas
                                              // le max de la seconde (constat 2)
  }
}
