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

  Serial.println("═══ BalanceBot prêt ═══");
}

void loop() {
  // Boucle d'équilibre : cadencée à BALANCE_LOOP_HZ (200 Hz)
  static unsigned long lastBalance = 0;
  if (g_state.balancing || Balance::isEnabled()) {
    unsigned long now = millis();
    if (now - lastBalance >= (1000UL / BALANCE_LOOP_HZ)) {
      lastBalance = now;
      Balance::loop();
    }
  }

  // UI : rafraîchie en continu (touch + rendu)
  Ui::loop();

  // Tête + ultrason : balayage/évitement
  Head::loop();

  // Batterie : lecture 1×/seconde (état global pour l'UI)
  static unsigned long lastBatMs = 0;
  if (millis() - lastBatMs >= 1000) {
    lastBatMs = millis();
    g_state.batteryV = Battery::readVolts();
  }
}
