#pragma once
// ═══════════════════════════════════════════════════════════════════
// BalanceBot — UI tactile (module B)
// Implémente : écran TFT_eSPI + TouchLib, boutons, télémétrie
// ═══════════════════════════════════════════════════════════════════

#include "interfaces.h"

namespace Ui {
  // Initialisation écran + touch. Retourne true si OK.
  bool  begin();

  // Diagnostic du repère tactile (TOUCH_REVIEW.md §4). Dernier point
  // VALIDE, rémanent après relâchement : brut (sortie TouchLib, donc déjà
  // transposé par son setRotation(1)) et transformé (repère écran
  // 320×170). seq = numéro du tap, incrémenté à chaque front montant.
  struct TouchDebug {
    bool     down;                 // doigt posé à l'instant de la lecture
    int16_t  rawX, rawY;           // brut TouchLib
    int16_t  x, y;                 // après transformation (0..319 / 0..169)
    uint32_t seq;                  // compteur de taps
    bool     mirrorX, mirrorY;     // drapeaux actifs dans le binaire courant
  };
  TouchDebug touchDebug();
  void  setTouchSkip(bool skip);     // diagnostic : coupe la lecture I²C du touch
  void  setIntGate(bool on);         // diagnostic : ne lire que si INT est actif

  // Boucle principale : lecture tactile + rendu (appelée souvent)
  void  loop();

  // Aperçu du visage SANS armer (banc web) : expr = index d'état
  // 0..7 (calme, penché, méfiant, énervé, surprise, content, clin, chute),
  // ms = durée d'affichage, sweep = fait balayer le regard (test de charge).
  // Permet de valider les expressions à l'écran sans lancer l'asservissement.
  void  previewFace(uint8_t expr, unsigned long ms, bool sweep = false);

  // Écran POURBOIRE (ROADMAP 4.2 étape 1) : affiche le QR statique de
  // l'adresse Lightning (config.h, TIP_LN_ADDRESS) pendant TIP_QR_HOLD_MS,
  // puis retour automatique à l'écran courant. Un tap ferme plus tôt.
  // Appelé par le .ino sur appui COURT de KEY — sûr à tout moment : c'est
  // du dessin, jamais une commande (l'équilibre n'y touche pas).
  void  showTip();
}
