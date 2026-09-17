// ═══════════════════════════════════════════════════════════════════
// BalanceBot — sketch principal (assemblage)
// T-Display-S3-Touch (ESP32-S3) · 2 pieds en arc + 2 pan/tilt (SG90)
// · MPU6050 (I2C) · HC-SR04 · châssis imprimé ₿
//
// Ce fichier est écrit par Hermes (orchestrateur). Les agents coding
// implémentent UNIQUEMENT les .cpp de leur module contre interfaces.h.
// ═══════════════════════════════════════════════════════════════════
#include <Arduino.h>

#include "config.h"
#include "interfaces.h"
#include "tuner.h"

// État global unique — défini ICI, déclaré extern dans interfaces.h
BotState g_state;

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\n═══ BalanceBot boot ═══");

  // Power ON les périphériques (GPIO15 HIGH = obligatoire sur T-Display S3)
  pinMode(PIN_POWER_ON, OUTPUT);
  digitalWrite(PIN_POWER_ON, HIGH);

  // Bouton BOOT : appui long = ouvre/ferme le banc de réglage web.
  pinMode(PIN_BUTTON_1, INPUT_PULLUP);

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

  // ── Boucle d'équilibre : 200 Hz ─────────────────────────────────
  // Toujours active même à l'arrêt : Balance::loop() mesure l'IMU en
  // continu (le PITCH affiché vit même sans équilibre) et ne pilote les
  // pieds que si l'équilibre est activé.
  static unsigned long tBalance = 0;
  if (nowMs - tBalance >= (1000UL / BALANCE_LOOP_HZ)) {
    tBalance = nowMs;
    unsigned long t0 = micros();
    Balance::loop();
    unsigned long dt = (micros() - t0) / 1000UL;
    if (dt > g_state.dbgBalMs) g_state.dbgBalMs = (uint8_t)min(dt, 255UL);
    if (dt > g_state.dbgBalMaxMs) g_state.dbgBalMaxMs = (uint16_t)min(dt, 65535UL);
    s_lastPhase = 0;
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

  // ── Tête + ultrason : 50 Hz (l'ultrason est auto-cadencé à 10 Hz
  // en interne ; 50 Hz de mouvement pan/tilt est fluide pour des SG90) ──
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
  // Le serveur HTTP vit sur sa propre tâche (cœur 0) : plus rien à
  // cadencer ici, la boucle d'équilibre ne peut plus être gelée par un
  // client TCP lent. Appui long (~1,5 s) sur BOOT = ouvrir/fermer l'AP.
  static unsigned long bootDownMs = 0;
  static bool bootDone = false;
  static bool bootPrev = false;
  const bool bootNow = (digitalRead(PIN_BUTTON_1) == LOW);
  if (bootNow && !bootPrev) {
    bootDownMs = nowMs;
    bootDone = false;
  } else if (bootNow && !bootDone && (nowMs - bootDownMs >= 1500)) {
    bootDone = true;
    // Aucun Serial ici (cœur 1, chemin chaud — STALL_ANALYSIS.md §6,
    // REVIEW_CLAUDE M14) : la trace « OUVERT / FERMÉ » est écrite par la
    // tâche du tuner (cœur 0).
    (void)Tuner::toggle();
    s_lastPhase = 3;
  }
  bootPrev = bootNow;

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
