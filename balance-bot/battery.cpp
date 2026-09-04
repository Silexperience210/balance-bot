// ═══════════════════════════════════════════════════════════════════
// BalanceBot — Module batterie (implémentation)
// ═══════════════════════════════════════════════════════════════════

#include "battery.h"

namespace Battery {

// Constantes de calibration (valeurs typiques T-Display-S3) :
// diviseur 100k/100k → facteur 2 ; atténuation ADC 11dB (0-3.3V).
static const float ADC_FACTOR = 2.0f;   // pont diviseur 1/2
static const float ADC_MAX_MV = 3300.0f;
static const int   ADC_BITS   = 12;     // résolution 4096

void begin() {
  // PIN_BAT_VOLT = GPIO4 = ADC1_CH3 — lecture analogique simple
  pinMode(PIN_BAT_VOLT, INPUT);
  // Atténuation 11 dB : pleine échelle 3.3V (les GPIO ESP32-S3 sont 3.3V)
  analogSetPinAttenuation(PIN_BAT_VOLT, ADC_11db);
  // Une lecture de stabilisation
  (void)readVolts();
}

float readVolts() {
  int raw = analogRead(PIN_BAT_VOLT);
  if (raw <= 0) return 0.0f;
  float mv = (raw * ADC_MAX_MV) / (float)((1 << ADC_BITS) - 1);
  float volts = (mv / 1000.0f) * ADC_FACTOR;
  // Plage plausible batterie LiPo 1S : 3.0 - 4.4 V. Hors plage → 0
  if (volts < 3.0f || volts > 4.4f) return 0.0f;
  return volts;
}

}  // namespace Battery
