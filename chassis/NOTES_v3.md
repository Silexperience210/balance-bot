# ₿ BalanceBot v3 — NOTES DE CONCEPTION (châssis symbole Bitcoin)

## Pièces (dans chassis/v3/)
| Fichier | Rôle | Dimensions | Masse PETG |
|---|---|---|---|
| b_front.stl | Coque avant (face ₿, écran, yeux) | 104 × 20 × 195 | ~113 g |
| b_back.stl | Coque arrière (élec., goujons) | 104 × 26 × 195 (goujons +6) | ~89 g |
| coin_wheel.stl ×2 | Roues-pièces ₿ Ø70, ₿ gravé | Ø70 × 10 + moyeu Ø24×13 | ~52 g |
| coin_tire.stl ×2 | Bandes TPU (TPU 95A) | Ø int 68.1 × 8 | ~4 g |

Total ~305 g PETG + 8 g TPU. Corps : glyphe ₿ 90 × 170 (hors barres) + barres 15 → 205 de haut.
Voie des roues (plans médians) : ≈ 108 mm (centres x −17,5 / +96 après miroir) — légère asymétrie
compensée par la masse (corps centré ~45, la batterie côté spine).

## Montage
1. Servos 9 g continus (SG90-FS90R size) TÊTE EN BAS, collés à leur paroi : face de sortie contre la paroi
   latérale intérieure (gauche : spine x=90 ; droite : paroi courbe x≈11), corps dans la cavité, pattes
   vissées (M2 × 8, Ø1.7) sur les cloisons verticales (bulk) — cloisons à x = 12…23 et 68…79.
2. L'axe/bossage du servo traverse la paroi par un trou Ø12.8 (axR/axL) puis entre dans le moyeu Ø24 de la roue.
3. Roue : enfiler le moyeu sur le palonnier (croix) pré-vissé à l'axe ; le moyeu (13 mm) coulisse dans le
   tube-palier du corps (Ø24.5) ; l'empreinte au fond du moyeu (3.6 mm) attrape la croix. Jeu axial ~3 mm
   (lamage HUB_CB_H+3) pour ne pas serrer.
4. Bande TPU : étirer par-dessus la jante (gorge Ø69 × 8.4, bande Ø int 68.1 → interférence 0.9).
5. Joint des coques : goujons Ø5.8 (b_back, x4) → alésages Ø6.0 (b_front, prof 6.8) ; vis M3 × 30
   tête noyée Ø6.4 (b_back) → passage Ø3.4 → avant-trou Ø2.6 dans les plots du front (autotaraudage).
   Plots de vis à 4 endroits : spine z≈71/142, mur courbe bas droite (45°), plafond panse haute (z≈184).
6. Carte T-Display S3 : paysage, dalle dans la fenêtre 40.6 × 22.6 du contre-poinçon bas (lcz≈66.8),
   rails haut/bas + 2 vis M2 aux trous réels (x = lcx − 30.39 + 57.66, z = lcz ± 10) ; USB-C vers le bas
   (lumière sous le corps à z=19-23).
7. MPU6050 : piédestal dont le DESSUS est à z = 36.5 (l'axe de tangage !) ; vis M2 entraxe 15 (Ø1.7).
8. HC-SR04 : poussé dans la baie haute (fenêtre 45×20), transducteurs dans les 2 trous Ø16.6 (entraxe 26) ;
   colle sur les rails.
9. Interrupteur : lumière 13 × 8 côté arrière du spine (z 148-156).

## Orientation d'impression (P1S, plateau 256 × 256)
- b_front / b_back : face externe sur le plateau (creux vers le haut), zéro support (le creux COUNTER de la
  face ₿ n'est pas imprimé en l'air : la face externe EST le plateau). Goujons/plots vers le haut.
- coin_wheel : face externe (₿ gravé) sur le plateau → la gravure sort en relief (creux du moule) ;
  moyeu vers le haut. PETG, couches 0.2.
- coin_tire : à plat (anneau). TPU 95A.
- Attention : le corps est large (104) mais rentre (plateau 256) ; hauteur d'impression ~195 pour les coques
  couchées → NON : couchée, la hauteur = 40 mm de large ? La coque couchée sur sa face externe (plan y=20) :
  dimensions au sol 104 (x) × 195 (z→y) → TROP GRAND pour 256 ? 195 < 256 ✓ ça rentre (104 × 195 au sol).
  Temps estimé b_front ~3h30, b_back ~3h à 0.2 PETG.

## Réglages électriques (rappel POWER_GUIDE)
- Servos sur 5 V séparé (BEC/buck), GND commun ; jamais le 3V3 de la carte.
- Firmware : mode FEET_MODE_CONTINUOUS (déjà prêt, Lot 3a) ; constante kAccelPitchSign à vérifier au test.

## Historique de conception (bref)
- v3.0 glyphe paramétrique (spine/panses/barres) ; coque 2 moitiés à joint y=0 ; contre-poinçons lus par ombres.
- Instabilités booléennes EXACT combattues : alésages des paliers limités AU TUBE (Ø24.5 de 79.2→92.5),
  trous de bossage séparés Ø12.8 dans la paroi, tubes Ø26.5 ancrés 1.4 mm dans la paroi, avant-trous M3
  percés AVANT la coupe (trou continu au joint), coupe finale par booleen sur géométrie assainie.
- Artefacts résiduels : 12 arêtes à >2 faces (front) et 3 arêtes libres (back) à la face de joint, au droit
  des trous M3 — microscopiques, dans la matière du joint, sans effet impression (réparés par le slicer).
