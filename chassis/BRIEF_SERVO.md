# Brief — Baies de servo du châssis BalanceBot v3 (à corriger)

## Contexte
Le châssis est **généré paramétriquement** par `chassis/gen_bitcoin_bot.py`
(script Blender). Ne modifie QUE ce fichier et les STL régénérés.

Les 2 servos de roue sont des **SG90** : corps 22,8 × 12,2 × 22,5, **arbre de
sortie à 5,9 mm du fond** du corps, bossage de sortie Ø11,8 × 1,5, **oreilles de
fixation 32,2 de long**, sortie de câble sur un flanc, et de petits **taquets de
moulage** en saillie.

Constantes du générateur (déjà dans le fichier) :
`SV_L=22.8`, `SV_W=12.2`, `SV_H=22.5`, `SV_SHAFT_OFF=5.9`, `SV_BOSS_D=11.8`,
`SV_BOSS_H=1.5`, `SV_PILOT_D`, `HUB_BORE_D=SV_SHAFT_D+0.4`, `WALL=2.4`,
`AXLE_Z=42.0`, `GW=118`.

Implantation prévue par le code (repère NON miroir) :
- servo couché, **axe selon X**, sortant par les parois latérales à `z = AXLE_Z` ;
- corps entre `z = AXLE_Z - SV_SHAFT_OFF` et `z + SV_L` (soit 36,1 → 58,9) ;
- cavité ouverte depuis `x = WALL` (côté spine) et depuis
  `x = x_wall_R - WALL` (côté paroi courbe), corps s'étendant vers l'intérieur ;
- l'arbre + le bossage traversent la paroi par un trou Ø12,8 (`axR`/`axL`) et
  entrent dans le **moyeu Ø24 de la roue** ; le moyeu tourne dans le
  **tube-palier Ø24,5** extérieur ;
- les oreilles se vissent (M2 × 8, avant-trous Ø1,7) sur les **cloisons
  verticales (bulk) — cloisons à x = 12…23 et 68…79** (repère non miroir).

## Problème constaté sur la pièce réellement imprimée
1. **Le servo ne rentre pas.** Il possède un **taquet** (saillie de moulage) et
   ses oreilles de fixation ; la cavité est au plus juste → il faut **~1 mm de
   jeu en plus** sur les faces concernées.
2. **Côté opposé, un PLOT DE FIXATION tombe en plein milieu de l'emplacement du
   servo** et le bloque. (Vérifier aussi la cloison `bulk` : une cloison de 11 mm
   d'épaisseur tombe dans l'emprise du corps du servo.)

## Travail demandé

### 1. Trouver un VRAI modèle de SG90
Télécharge un modèle **STL ou STEP d'un SG90 réel** (GrabCAD, Printables,
Thingiverse, ou un dépôt de modèles CAO fiable). Vérifie sa provenance et que
ses cotes correspondent : corps 22,8 × 12,2 × 22,5, oreilles 32,2 × 12,2,
bossage Ø~11,8, arbre Ø4,8, **taquets et sortie de câble présents**. Si aucun
modèle correct n'existe, reconstruis un solide fidèle à partir d'un **datasheet
officiel** (TowerPro SG90 : drawing coté) et dis-le explicitement dans le
rapport.

### 2. Vérifier l'emplacement par la géométrie (pas à l'œil)
Dans Blender (headless) : importe les coques `b_front`/`b_back` régénérées et le
modèle de servo, place le servo **exactement** comme le prévoit le générateur,
puis mesure l'**intersection booléenne** servo × coques. Elle doit être **0 mm³**.
Liste chaque zone de collision avec ses cotes (x, y, z) et l'épaisseur à
enlever. Vérifie aussi qu'il reste **~1 mm de jeu** partout et qu'un **doigt de
montage** peut atteindre les oreilles.

### 3. Corriger `build_body()`
- élargir la cavité d'**au moins 1 mm** là où le taquet/les oreilles coincent ;
- **supprimer ou déplacer** le plot de fixation qui tombe dans l'emprise du servo
  (s'il sert à visser autre chose, déplace-le hors de l'emprise, ne le supprime
  pas à l'aveugle) ;
- dégager la sortie du câble et l'accès aux vis d'oreilles ;
- **NE PAS** toucher à l'enveloppe extérieure, à `AXLE_Z`, aux trous Ø12,8, aux
  tubes-paliers Ø24,5, ni à la poche de la carte / la fenêtre de la dalle.

### 4. Régénérer et prouver
- régénère les STL (comme `chassis/run_v3_design.sh` le fait) ;
- `python3 chassis/verif_ultime.py` doit rester **25/25** (watertight, 0 arête
  libre, 0 non-manifold, cotes de l'enveloppe inchangées) ;
- intersection servo/coques = **0 mm³** (re-mesure après correction) ;
- pas de nouveau surplomb critique pour l'impression.

### 5. Rapport final (court, chiffré)
Avant/après : cotes de la cavité modifiée, zone du plot déplacé, volume
d'intersection (avant → après), source et cotes du modèle de servo utilisé,
résultat de `verif_ultime.py`. Signale tout ce que tu n'as pas pu vérifier.
