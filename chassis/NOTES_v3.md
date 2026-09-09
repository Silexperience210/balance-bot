# ₿ BalanceBot v3 — NOTES DE CONCEPTION (châssis symbole Bitcoin)

## Pièces (dans chassis/v3/) — cotes MESURÉES (09/09/2026)
| Fichier | Rôle | Dimensions (bbox mm) | Masse PETG (100 %) |
|---|---|---|---|
| b_front.stl | Coque avant (face ₿, écran, yeux) | 132,1 × 23,0 × 201,0 | 134 g |
| b_back.stl | Coque arrière (élec., goujons) | 132,1 × 29,0 × 201,0 | 116 g |
| coin_wheel.stl ×2 | Roues-pièces ₿ Ø80 × 10 + moyeu Ø24×13 | Ø80 × 21 | 54 g |
| coin_tire.stl ×2 | Bandes TPU (TPU 95A) | Ø83 × 7 | 5,6 g TPU |

Total ≈ 378 g (367 g PETG + 11 g TPU). Corps : glyphe ₿ 118 × 165 (GW × GH) + barres → 201 de haut,
profondeur 46 (23 + 23) + goujons 6. Voie des roues (plans médians) : ≈ 108 mm.
**Coques CREUSES** (pas de peau au joint) : la cavité s'ouvre sur le plan de joint y=0, le hardware
se monte par l'ouverture avant vissage (4 goujons + 4 vis M3).

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
- b_front / b_back : face externe sur le plateau (creux vers le haut). Le creux COUNTER de la face ₿
  n'est PAS imprimé en l'air (la face externe EST le plateau) ; les 2 panse-creux (5 831 mm² à 1,6 mm)
  se pontent. Goujons/plots vers le haut. Hauteur d'impression 23 (front) / 29 (back) → ça rentre large.
- coin_wheel : face externe (₿ gravé) sur le plateau → la gravure sort en relief (creux du moule) ;
  moyeu vers le haut. PETG.
- coin_tire : à plat (anneau). TPU 95A.
- **Plaques de slicing** : `export/v31/plate1_b_front.stl` (201 × 132 au sol), `plate2_b_back.stl`,
  `plateR_wheel1/2.stl`, `plateT_tire1/2.stl`. **À RÉGÉNÉRER après tout changement** :
  `python3 chassis/make_plates.py` (transformations vérifiées : 100 % des sommets alignés).
  Les plaques de 14h44 du 08/09 étaient périmées (version FERMÉE + alésage de palier bouché).
- Le CLI headless refuse les coques > ~195 mm (dimension 201) → **slicer en GUI Bambu Studio**.

## Réglages de slicing recommandés (P1S, PETG 0,4 mm)
| Réglage | Coques (front/back) | Roue | Pneu |
|---|---|---|---|
| Hauteur de couche | **0,28** (−30 % de temps) | 0,20 (gravure ₿) | 0,24 |
| Parois | 6 (épaisseur 2,4 mm = la pièce) | 4 | 3 |
| Remplissage | n/a (parois pleines) | 20 % gyroid | 15 % gyroid |
| Support | **aucun** (ponts internes) | aucun | aucun |
| Adhérence | bordure (brim) 5 mm, lit 70-80 °C | brim 5 mm | brim 5 mm |
| Ponts | débit 0,9 · 25 mm/s · ventilo 100 % | idem | — |
| Divers | 1re couche 0,24 · « éviter de traverser les parois » | — | vitesse TPU 25 mm/s |

Surplombs réels mesurés (hors faces posées sur le plateau) : 6,7 k mm² (front, dont 5,8 k = fond des
creux ₿ à 1,6 mm), 1,05 k mm² (back), 0,59 k mm² (roue), 0 (pneu) → aucun support nécessaire.

## Révision du 09/09/2026 (revue impression + corrections)
1. **Alésages de palier bouchés** : le fond de l'alésage tombait pile sur le bout du tube → voile
   d'épaisseur nulle / bouchon plein dans le tube GAUCHE (moyeu impossible à enfoncer). Les alésages
   dépassent maintenant le bout des tubes de 2 mm (bearR → x_in_R+2,5 ; bearL → −14,0).
2. **Purge automatique des voiles** : `purger_dechets()` supprime toute composante à épaisseur nulle
   (connectivité par arêtes) après `nettoyer()` — plus de plaques fantômes (le back passe de 3 composantes
   à 1, watertight, profondeur réelle 29 au lieu de 34,9 gonflée par un voile flottant).
3. **Plaques de slicing régénérées** (`chassis/make_plates.py`) depuis les STL courants.
4. **Avant-trous M3** : présents en vides internes Ø2,6 × 16 mm dans les 4 plots (autotaraudage).
5. **Non-manifold** : les compteurs bruts des STL (39/102/1927/585) sont des sommets non soudés —
   après `merge_vertices` les coques sont watertight (back) ou fermées hors ouverture de joint (front).


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
