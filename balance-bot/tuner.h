#pragma once
// ═══════════════════════════════════════════════════════════════════
// BalanceBot — module D · banc de réglage web (en-tête privé)
//
// L'API publique (begin/loop/active) est déclarée dans interfaces.h.
// Ce header n'ajoute que ce dont le .ino a besoin pour CADENCER les
// appels : la date de la dernière requête servie.
// ═══════════════════════════════════════════════════════════════════
#include <Arduino.h>
#include "interfaces.h"

namespace Tuner {

// millis() de la dernière requête HTTP servie (0 si aucune). Le .ino
// s'en sert pour ne pas déranger la boucle d'équilibre en pleine
// correction : on ne sert le web que si l'équilibre est OFF, ou si le
// dernier échange date de plus de 100 ms.
unsigned long lastRequestMs();

} // namespace Tuner
