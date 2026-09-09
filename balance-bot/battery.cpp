// ═══════════════════════════════════════════════════════════════════
// BalanceBot — Module batterie (implémentation)
// ═══════════════════════════════════════════════════════════════════

#include "battery.h"

namespace Battery {

// Constantes de calibration (valeurs typiques T-Display-S3) :
// diviseur 100k/100k → facteur 2 ; atténuation ADC 11dB (0-3.3V).
static const float ADC_FACTOR = 2.0f;   // pont diviseur 1/2

// Plage plausible d'une cellule LiPo 1S : 3.0 V (protection basse) à 4.4 V.
// Hors de cette plage, ce n'est PAS une batterie faible mais une absence de
// batterie (USB seul : l'ADC lit ~0 V, ou la ligne de charge sature) → -1,
// que l'UI affiche « USB » et non « 0.00 V ».
static const float BAT_MIN_V = 3.0f;
static const float BAT_MAX_V = 4.4f;

// Dernière lecture valide sous le seuil bas (BAT_LOW_V, config.h).
static bool s_low = false;

void begin() {
  // PIN_BAT_VOLT = GPIO4 = ADC1_CH3 — lecture analogique simple
  pinMode(PIN_BAT_VOLT, INPUT);
  // Atténuation 11 dB : pleine échelle 3.3V (les GPIO ESP32-S3 sont 3.3V)
  analogSetPinAttenuation(PIN_BAT_VOLT, ADC_11db);
  // Une lecture de stabilisation
  (void)readVolts();
}

float readVolts() {
  // analogReadMilliVolts() applique la courbe de calibration eFuse du S3
  // (linéarité + gain). Un analogRead() brut mis à l'échelle est non
  // linéaire et se trompe de 10-20 % : inutilisable pour un seuil à 3,5 V.
  const uint32_t pinMv = analogReadMilliVolts(PIN_BAT_VOLT);
  const float volts = (pinMv / 1000.0f) * ADC_FACTOR;
  if (pinMv == 0 || volts < BAT_MIN_V || volts > BAT_MAX_V) {
    s_low = false;      // pas de batterie mesurable : ni basse ni haute
    return -1.0f;       // « aucune batterie plausible » (cf. interfaces.h)
  }
  s_low = (volts < BAT_LOW_V);
  return volts;
}

bool isLow() { return s_low; }

}  // namespace Battery
