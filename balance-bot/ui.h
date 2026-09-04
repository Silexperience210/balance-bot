#pragma once
// ═══════════════════════════════════════════════════════════════════
// BalanceBot — UI tactile (module B)
// Implémente : écran TFT_eSPI + TouchLib, boutons, télémétrie
// ═══════════════════════════════════════════════════════════════════

#include "interfaces.h"

namespace Ui {
  // Initialisation écran + touch. Retourne true si OK.
  bool  begin();

  // Boucle principale : lecture tactile + rendu (appelée souvent)
  void  loop();

  // Affiche une ligne d'état libre dans le footer
  void  setStatusLine(const char* text);
}
