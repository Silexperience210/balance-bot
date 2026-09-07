// ═══════════════════════════════════════════════════════════════════
// BalanceBot — sketch principal (assemblage)
// T-Display-S3-Touch (ESP32-S3) · 4× SG90 (2 rotatifs roues, 2 pan/tilt)
// · MPU6050 (I2C) · HC-SR04 · châssis imprimé
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

  // ── Boucle d'équilibre : 200 Hz ─────────────────────────────────
  // Toujours active même à l'arrêt : Balance::loop() mesure l'IMU en
  // continu (le PITCH affiché vit même sans équilibre) et ne pilote les
  // roues que si l'équilibre est activé.
  static unsigned long tBalance = 0;
  if (nowMs - tBalance >= (1000UL / BALANCE_LOOP_HZ)) {
    tBalance = nowMs;
    Balance::loop();
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
  }

  // ── Banc de réglage web : au plus 20 Hz (cadencé dans Tuner::loop) ──
  // Priorité absolue à l'équilibre : quand le robot tient debout, on ne
  // sert le web que si le dernier échange date de plus de 100 ms — assez
  // pour laisser passer la télémétrie (le navigateur interroge toutes
  // les 150 ms) sans jamais enchaîner deux requêtes en pleine correction.
  if (!g_state.balancing || nowMs - Tuner::lastRequestMs() > 100) {
    Tuner::loop();
  }

  // Batterie : lecture 1×/seconde (état global pour l'UI)
  static unsigned long tBat = 0;
  if (nowMs - tBat >= 1000) {
    tBat = nowMs;
    g_state.batteryV = Battery::readVolts();   // -1 = USB seul, pas de batterie
    g_state.batteryLow = Battery::isLow();
    // Fenêtre de debug écoulée : on repart de zéro pour la seconde suivante
    g_state.dbgUiMs = 0;
    g_state.dbgHeadMs = 0;
  }
}
