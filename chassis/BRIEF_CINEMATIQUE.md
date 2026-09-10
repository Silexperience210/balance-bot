# Brief — Cinématique BalanceBot : tout disparaît pendant l'éclaté

## Symptôme (constaté par l'utilisateur, confirmé par mesure)
Dans `chassis/render/cinematique.mp4`, **au moment de la vue éclatée, plus rien
n'est visible** : le cadre est vide et les pièces ont disparu. Le reste de la
vidéo est bon.

Mesures sur les images rendues (`chassis/render/frames/f_%04d.png`, 1280×720),
comptage des pixels « orange métal » (r>90, r>1.5g, g>1.3b) :

| image | phase | pixels orange | image occupée |
|---|---|---|---|
| 300 | orbite (OK) | 30 339 (x 468..807) | normal |
| 390 | début éclaté | 917 (x 303..363) | ça rétrécit |
| **421** | **pic de l'éclaté** | **333 (x 287..303, y 691..719)** | **1,6 % — cadre vide à 95-98 %** |
| 480 | remontage | 8 599 (x 378..467) | ça revient |

À l'image 420, un modèle de vision ne voit qu'**un petit objet cylindrique noir
(<1 % de l'image)**, décentré en bas à droite. Les coques orange (132 × 201 mm)
devraient pourtant occuper ~13 % du cadre à 1 000 mm avec l'objectif de 62 mm :
elles ne sont plus dans le champ.

## Code concerné (`chassis/assets/cinematique.py`)
- **Caméra** : bloc `CAM_KEYS` (à partir de « caméra : gros plan sur l'écran »).
  L'azimut vient de la rotation Z de l'empty `orbite` ; `placer_camera(0, dist,
  haut, cible)` ne pose que la position LOCALE et la visée.
- **Éclatement** : dict `ECLATE` + la boucle
  `pieces = {... if o.name in ECLATE}` → clés `(1, pos_a)`, `(240, pos_a)`,
  `(420, pos_e)`, `(570, pos_a)`.
- Les pièces éclatées sont parentées au `pivot` (empty sur l'axe des roues) avec
  `matrix_parent_inverse`.

## Suspicions à vérifier (ne pas se contenter de la première)
1. **La ROTATION de la caméra n'est jamais keyframée** — seule `location` l'est.
   La visée reste donc celle de la DERNIÈRE entrée de `CAM_KEYS` (image 780 :
   200 mm, haut 84, cible 76) alors que la caméra se balade de 115 à 1120 mm.
   Calcule l'écart de visée réel et son effet.
2. Interpolation Bézier des positions : vérifier qu'aucune clé n'overshoot (la
   caméra pourrait partir très loin entre deux clés).
3. Les vecteurs d'éclatement sont additionnés à `obj.location` : pour les coques
   importées (STL) `location` vaut (0,0,0) et la géométrie porte les cotes —
   vérifier que le décalage appliqué est bien celui attendu.
4. Vérifier enfin que rien ne masque : ordre le long de l'axe de visée.

## Travail demandé
1. **Diagnostiquer la cause RÉELLE** avec un **script de projection** :
   `bpy_extras.object_utils.world_to_camera_view` + `scene.frame_set(f)` **puis
   `bpy.context.view_layer.update()`** (sans ce refresh les matrices restent
   figées et la mesure est fausse — piège déjà rencontré). ATTENTION : les clés
   de caméra sont dans le bloc « mode cinématique », APRÈS la ligne
   `if MODE == "still":` → un probe qui n'exécute que l'en-tête du script n'aura
   AUCUNE animation de caméra. Construis le probe de façon à évaluer la scène
   animée complète.
   Pour chaque pièce et chaque image clé (300 / 390 / 420 / 480 / 570), imprime
   la position caméra monde, la boîte englobante en pixels et si elle est dans le
   cadre (0..1280 × 0..720).
2. **Corriger** ce qui est faux (viser correctement à chaque image — keyframer la
   visée si nécessaire — et adapter les distances/offsets pour que TOUTES les
   pièces restent dans le cadre avec une taille lisible pendant l'éclaté).
3. **Prouver** : re-rendre SEULEMENT quelques images de contrôle, pas les 780 :
   `blender --background --python chassis/assets/cinematique.py -- cine 390 430`
   (le script accepte déjà une plage `[début fin]`). Puis, sur ces images,
   **recompter les pixels orange** et vérifier que les coques ET les composants
   (carte, dalle, servos, capteurs) sont visibles et bien cadrés. Donne les
   chiffres avant/après.
4. Ne pas toucher : durée (26 s), 30 fps, 780 images, 1280×720, ni le châssis
   (`chassis/gen_bitcoin_bot.py`, les STL, le travail servos déjà commité).

## Rapport attendu
Cause racine (une phrase), ce qui a été changé (chiffres), les mesures de pixels
avant/après sur les images de contrôle, et ce que tu n'as PAS pu vérifier.
