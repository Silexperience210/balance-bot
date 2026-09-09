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

// millis() de la dernière requête HTTP servie (0 si aucune). Conservé pour
// la télémétrie / l'UI ; le serveur ne dépend plus de son appelant.
unsigned long lastRequestMs();

// Ouvre/ferme la radio du banc web (appui long BOOT). Renvoie le nouvel
// état : true = AP ouvert. isUp() le lit sans rien changer.
bool toggle();
bool isUp();

} // namespace Tuner
