# ₿ BalanceBot v3 — notes de conception

Source des cotes : `chassis/cotes.py`. Ce fichier décrit l'état des STL
`chassis/v3/` régénérés avec le générateur. Les chiffres de volume viennent
d'un lancer de `chassis/review/chaine_roue.py` sur ces STL (trimesh, sommets
soudés). Ce ne sont pas des pesées.

Les révisions des 09/09 et 10/09, en bas de page, sont un historique. Là où
elles contredisent cette page (vis M2 × 8, gorge « 8,4 », trou d'axe Ø12,8,
roue pleine, capot non dégagé), c'est cette page qui fait foi.

## Pièces (`chassis/v3/`)

| Fichier | Rôle | Boîte (mm) | Volume | Masse calculée |
|---|---|---|---|---|
| `b_front.stl` | Coque avant | 132,13 × 23,02 × 201 | 105,09 cm³ | 133,5 g PETG |
| `b_back.stl` | Coque arrière | 132,13 × 29 × 201 | 91,73 cm³ | 116,5 g PETG |
| `coin_wheel.stl` ×2 | Roue ₿, 6 bras | Ø80 × 22,34 | 28,19 cm³ | 35,8 g PETG |
| `coin_tire.stl` ×2 | Bande TPU | Ø83 × 7 | 4,42 cm³ | 5,3 g TPU |

Densités utilisées pour la masse : PETG 1,27 g/cm³, TPU 1,20 g/cm³. Total
calculé ≈ 332 g (321 g PETG + 11 g TPU), plus la visserie, les servos et
l'électronique, qui ne sont pas dans les STL. L'enveloppe des coques
(132,13 × 23,02 × 201 et 132,13 × 29 × 201) n'a pas bougé.

Inertie de la roue autour de son axe, calculée sur le maillage :
Izz ≈ 2,42×10⁻⁵ kg·m². Le simulateur dynamique ignore la masse des roues
(`sim/balancebot_sim.py` ne la met pas dans le Lagrangien). Alléger la roue
rapproche le robot réel de ce modèle. On n'a pas changé les équations.

## Chaîne servo → palonnier → moyeu → roue

Repère `u` : 0 sur la face de sortie du servo, croissant vers la roue.
Contrôlé sur les STL à ±0,2 mm par `chaine_roue.py`.

| Cote | Valeur | D'où elle sort |
|---|---|---|
| Axe, z | 42,0 mm | rayon monté : fond de gorge 39,5 + épaisseur pneu 2,5 |
| Épaulement du palier | u = 1,30 | dans la paroi de 2,4 mm |
| Bout du moyeu | u = 1,70 | jeu axial 0,40 mm avant l'épaulement |
| Longueur du moyeu | 14,33 mm | il entre : l'alésage utile fait 13,73 mm, le moyeu n'en engage que 13,33 |
| Bouche du tube | u = 15,03 | débord réel, `TUBE_OVER` compris |
| Face interne du disque | +1,0 mm | `WHEEL_GAP`, au-delà de la bouche |
| Trou d'axe | Ø12,4 + fente | bossage Ø11,8 + 0,6 ; rectangle du capot |
| Empreinte en croix | profondeur 4,80 | bras 20 × 5,2, jeu 0,35 / face, plus 0,40 axial |
| Cavité du capot | Ø18,4 × 2,60 | le capot ne tourne pas avec la roue |
| Alésage d'arbre | Ø5,4 × 5,50, borgne | la face ₿ n'est pas percée |

Les deux tubes ont la même longueur (12,13 mm au-delà de la peau). Une seule
roue s'imprime. Le milieu des axes, avant miroir, est à 53,4 mm ; le centre
du glyphe est à 59 mm. Écart −5,6 mm vers le spine. Recentrer demanderait
deux moyeux différents ou de toucher l'enveloppe : ce n'est pas fait.
L'ancien commentaire « −11 mm » décrivait mal `TUBE` (12,1 mm). Après miroir,
les faces externes des roues sont à x = −10,50 et 139,63 mm (entraxe 150,1 mm,
milieu 64,56 mm).

### Ce qui est mesuré, et ce qui ne l'est pas

Mesuré sur des maillages du dépôt (pas sur un servo en main) :

- le capot oblong, sur `chassis/assets/servo/Servo-SG90.stl` (bibliothèque
  FreeCAD, LGPL) : 4,0 mm de haut, largeur 11,8 mm, débord 2,9 mm vers le
  bout long. `servo_fit.py --hump` : intersection 0 mm³ avec les coques ;
- le bossage datasheet Ø11,8 × 1,5 et l'arbre qui pointe à 6,0 mm de la face
  sont les cotes déjà codées, pas un relevé au pied à coulisse ;
- `servo_fit.py` sans capot : intersection 0 mm³ aussi ;
- la peau de la panse à la hauteur de l'oreille basse (z = 33,6) est à
  x = 97,3 avant miroir, la face d'oreille à x = 100,4. L'oreille est hors
  de la peau. Trois vis sur quatre. La semelle compense, elle ne remplace
  pas la vis.

À contrôler en main, SG90 ou FS90R selon ce qui est monté. Ne pas prendre
les chiffres suivants pour une mesure :

- palonnier en croix : l'empreinte vise 20 × 5,2 × 1,8 mm, jeu 0,35 mm par
  face. Si le palonnier livré est plus long, plus large ou plus épais, il
  ne rentre pas. Le relever avant d'imprimer un lot ;
- si le capot réel fait 4 mm et que l'arbre ne dépasse que de 6,0 mm
  (datasheet), l'engagement des cannelures dans le palonnier posé sur le
  capot n'est que de 1,7 mm. Le STL de référence a un arbre plus long
  (~7 mm au-dessus de la face). À vérifier : un engagement trop court ne
  tient pas le couple ;
- si le capot réel n'est que le bossage de 1,5 mm, le palonnier s'assoit
  plus bas (dos à u = 1,80). L'empreinte fait 4,80 mm de profondeur depuis
  le bout du moyeu (u = 1,70 → fond à u = 6,50) : le palonnier flotte
  axialement jusqu'à la vis centrale. C'est voulu, ce n'est pas un serrage ;
- la semelle est 0,7 mm sous le corps nominal. Les 0,5 mm de « bavure »
  (`SG_TAB` dans `review/sg90_model.py`) ne sont pas mesurés : c'est une
  enveloppe pour que le test d'intersection passe. Un servo vissé sur ses
  oreilles ne doit pas porter sur la semelle ; elle arrête une chute ;
- trou d'axe Ø12,4 imprimé à l'horizontale (coque couchée) : ce n'est pas
  un alésage. S'il sort trop petit, on l'alèse. Le centrage du servo, ce
  sont les vis d'oreille et la semelle ;
- interférence du pneu : 1,0 mm au diamètre (Ø intérieur 78 sur un fond de
  gorge Ø79). On ne l'a pas desserrée : le Ø extérieur 83 du STL en dépend.
  Un TPU trop dur s'enfile à la main, quitte à tiédir la bande.

Ordre de montage de la roue : visser le palonnier sur le servo (la vis
centrale le plaque), puis enfiler la roue. Pas de vis traversant la face ₿.

## Vis

- Oreilles de servo : vis livrées avec le SG90 (≈ Ø1,9 × 6,5) ou M2 × 6.
  Pas M2 × 8 : elles débouchaient sur la peau. Avant-trous Ø1,7 borgnes.
  Côté panse, seule l'oreille haute a de la matière.
- Coques : 4 vis M3 × 30, tête noyée Ø6,4, passage Ø3,4, avant-trou Ø2,5
  (était Ø2,6 ; 2,5 mord mieux dans le PETG, les rayons du test de position
  y = 0,5…16,5 sont inchangés).
- Carte et MPU : avant-trous Ø1,7, vis M2. Le dessus du piédestal MPU est
  à `AXLE_Z − 2` mm : la carte de 2 mm amène le plan du capteur à hauteur
  d'axe. L'ancienne note « z = 36,5 » ne correspond plus au générateur.

## Impression

Plaques : `export/v31/`, régénérées par `python3 chassis/make_plates.py`.
Les relancer après chaque `gen_bitcoin_bot.py`. Détail pratique :
`docs/IMPRESSION.md`.

La dépouille à 45° dans les creux du ₿ n'est pas faite. Ces contre-poinçons
font 1,6 mm de profond sur une largeur de plusieurs centimètres : un
chanfrein de bord ne supprime pas le pont, et les remplir changerait la
face. On garde le pontage (débit 0,9, 25 mm/s, ventilateur à fond) et la
face externe sur le plateau.

## Deux rayons, une voie figée

| Grandeur | Valeur | Où |
|---|---|---|
| Rayon monté, axe du châssis | 42,0 mm | `cotes.AXLE_Z`, viewer (`meta.rayonRoulement`) |
| Rayon dynamique | 41,5 mm | `engine.js`, `balancebot_sim.py`. Figé : `selfcheck.js` |
| Voie du lacet simulé | 0,13887 m | idem, ne pas « corriger » |
| Entraxe des faces externes | 150,1 mm | STL, `cotes.roues_apres_miroir()` |

`kDirL = −1` et `kDirR = +1` dans `feet.cpp` restent : les servos sont en
miroir. On n'a pas inversé un signe sans un essai au sol.

## Historique (ne plus s'en servir pour une cote)

- 09/09 — alésages de palier débouchants, purge des voiles, plaques
  `make_plates.py`. L'avant-trou M3 était alors Ø2,6.
- 10/09 — baies servo : intersection 1779 mm³ ramenée à 0 sur le modèle
  datasheet. Trois vis sur quatre déjà constatées. Le capot oblong
  (269 mm³) était laissé en collision parce que les trous Ø12,8 étaient
  gelés. Ce gel est levé : la fente du capot est dans le générateur, et
  `servo_fit.py --hump` retombe à 0 mm³.
