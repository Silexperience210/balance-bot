// ═══════════════════════════════════════════════════════════════════
// BalanceBot — Module batterie (battery.h + battery.cpp)
// Lecture de la tension batterie via PIN_BAT_VOLT (ADC1_CH3, GPIO4).
// Note : sur T-Display-S3, la tension batterie n'est lisible QUE quand
// l'USB est débranché (sinon la batterie est en charge et l'ADC lit la
// tension USB). Valeur indicative, pas un fuel gauge.
// ═══════════════════════════════════════════════════════════════════
#pragma once

#include <Arduino.h>
#include "config.h"

namespace Battery {
  void  begin();
  float readVolts();   // tension estimée en volts ; -1 = aucune batterie plausible
  bool  isLow();       // BAT_LOW_SAMPLES lectures VALIDES consécutives sous BAT_LOW_V ;
                       // retombe au-dessus de BAT_LOW_V + 0,1 V (hystérésis) — cf. battery.cpp
}
