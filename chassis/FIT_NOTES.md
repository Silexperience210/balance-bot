# BalanceBot — notes d'ajustement, d'assemblage et de visserie

Document de référence pour `gen_chassis.py`. Tout ce qui suit est soit **mesuré**
sur un modèle de référence, soit **dérivé** de ces mesures — rien n'est estimé.

Repère (robot debout) : `X` = axe des roues (droite = +X), `Y` = profondeur
(+Y = avant, l'écran regarde +Y), `Z` = vertical, `Z = 0` au sol.
1 unité Blender = 1 mm.

---

## 1. Mesures réelles utilisées

### 1.1 Carte LilyGO T-Display S3 Touch

Relevées sur les modèles de référence cités dans l'en-tête de `gen_chassis.py` :

- carte nue : `t-display-s3-full.stl` (dossier `dimensions/` du dépôt de référence)
- coque Touch : `T-Display-S3-Touch_V5 v36.step`

| Cote | Valeur mesurée | Constante |
|---|---|---|
| Longueur PCB | **60.78** mm (Y 0.00..60.78) | `PCB_LEN` |
| Largeur PCB | **25.51** mm (X −12.75..12.75) | `PCB_WID` |
| Épaisseur du circuit seul | **1.20** mm (z −1.20..0.00) | `PCB_T` |
| Saillie composants au dos | **5.18** mm (z −6.38..−1.20) | `PCB_BACK` |
| Dalle + nappe tactile en façade | **3.50** mm (z 0.00..+3.50) | `PCB_FRONT` |
| Zone de PCB nu (bout opposé USB) | **8.03** mm (Y 52.75..60.78) | `PCB_BARE_END` |
| Largeur prise USB-C | **8.09** mm (X −4.18..3.91) | `USB_W` |
| Verre | **24.01 × 52.53** mm (X −11.49..12.52, Y 0.22..52.75) | `GLASS_W`, `GLASS_L` |
| Capot composants arrière | Y **6.66..56.53** | `SHROUD_Y0/Y1` |
| Trous de fixation | **Ø1.95**, à (−10.09, 57.66) et (+9.92, 57.66) → **entraxe 20.01** | `PCB_FIX_*` |

**Conséquence de conception, imposée par la mesure :** le verre ne laisse que
**0.23 mm** de retrait sur un grand côté. *Aucune lèvre frontale n'est possible*
ailleurs que sur les 8 mm de PCB nu. Le berceau ne tient donc la carte que par
l'arête basse (lèvre de 1.0 mm de haut — le verre commence 1.26 mm plus haut que
l'arête du PCB, aucun pixel n'est masqué), par les deux appuis arrière posés
uniquement là où le dos est nu, et par une nervure d'encliquetage.

### 1.2 Servo SG90 (×4 : 2 roues en rotation continue, 2 tête)

| Cote | Valeur | Constante |
|---|---|---|
| Corps | **22.8 × 12.2 × 22.5** mm | `SV_L`, `SV_W`, `SV_H` |
| Dessous des pattes / bas du corps | **15.9** mm | `SV_FLANGE_Z` |
| Épaisseur des pattes | **2.5** mm | `SV_FLANGE_T` |
| Longueur hors-tout pattes comprises | **32.2** mm | `SV_TAB_SPAN` |
| Entraxe des trous de pattes | **27.8** mm | `SV_HOLE_PITCH` |
| Axe de sortie / extrémité avant du corps | **5.9** mm (décentré !) | `SV_SHAFT_OFF` |
| Ø axe cannelé | **4.8** mm | `SV_SHAFT_D` |
| Dépassement de l'axe au-dessus de la face de sortie | **4.5** mm | `SV_SHAFT_PROJ` |
| Bossage circulaire autour de l'axe | **Ø11.8 × 1.5** mm | `SV_BOSS_D/H` |

L'axe étant décentré, les deux trous de pattes tombent à **−8.4** et **+19.4**
de l'axe. Les bras de `head_tilt` couvrent toute cette plage : sinon la
deuxième vis n'a plus de matière à mordre.

### 1.3 Périphériques

| Élément | Cotes | Constantes |
|---|---|---|
| MPU6050 (GY-521) | 21.0 × 16.0 × 2.0, 2 trous M2 entraxe 15.0 | `MPU_*` |
| HC-SR04 | 45.0 × 20.0 × 15.0, PCB 1.6, capsules Ø16 entraxe 26 | `SR_*` |

---

## 2. Règles d'impression et jeux

Buse 0.4 mm, PLA. Quatre tolérances seulement, appliquées partout :

| Rôle | Valeur | Constante |
|---|---|---|
| Coulissement / pose sans jeu perceptible | **+0.15** | `SLIDING_FIT` |
| Passage libre, insertion sans effort | **+0.30** | `CLEARANCE_FIT` |
| Emmanchement serré | **+0.05** | `PRESS_FIT` |
| Alésage imprimé (Ø ≤ 10) = Ø réel + | **+0.30** | `HOLE_BONUS` |

Murs : **2.4 mm** courant (6 × 0.4), **2.0 mm** pour les cloisons internes.
Chanfrein anti-support générique : **1.2 mm à 45°**.

### 2.1 Jeux appliqués, ajustement par ajustement

| Liaison | Nominal | Réalisé | Jeu |
|---|---|---|---|
| Corps servo dans sa lumière | 22.8 × 12.2 | **23.10 × 12.50** | +0.30 |
| Berceau enserrant le corps | 22.8 × 12.2 | 22.95 × 12.35 | +0.15 |
| Alésage de moyeu de roue / axe Ø4.8 | 4.8 | **Ø5.20** | +0.40 |
| Lamage de roue / bossage Ø11.8 × 1.5 | 11.8 | **Ø12.40 × 1.70** | +0.60 / +0.20 |
| Alésage `head_tilt` / axe pan Ø4.8 | 4.8 | **Ø5.20** | +0.40 |
| Alésage `sensor_mount` / axe tilt Ø4.8 | 4.8 | **Ø5.20** | +0.40 |
| Logement du tourillon / tige Ø4.0 | 4.0 | **Ø4.30** | +0.30 |
| Logette MPU6050 | 21.0 × 16.0 | 21.30 × 16.30, prof. 1.5 | +0.30 |
| Glissière du PCB HC-SR04 | 1.6 | **1.75** | +0.15 |
| Baie HC-SR04 (L × H) | 45.0 × 20.0 | 45.30 × 20.30 | +0.30 |
| Berceau de carte (largeur, en Z) | 25.51 | **114.09..139.91 = 25.82** | +0.15 par côté |
| Avant-trou M2 autotaraudeur dans le PLA | M2 | **Ø1.70** | — |
| M3 passant / avant-trou M3 | M3 | **Ø3.40 / Ø2.60** | — |

### 2.2 L'encliquetage de la carte (le seul ajustement en interférence)

Nervure de **0.4 mm** sur l'appui arrière, en vis-à-vis de la lèvre basse :
l'entrée du logement se referme à **0.95 mm** pour un PCB de **1.20 mm**, soit
**0.25 mm d'interférence**. La carte se clipse en glissant par +X et tient
seule ; une rampe à 45° sur la nervure évite de râper le PCB à l'insertion.
Les 2 vis M2 ne font que verrouiller. **À valider sur un tirage d'essai** avant
d'y engager une vraie carte (voir §6, point 4).

---

## 3. Implantation générale (dérivée)

| Grandeur | Valeur |
|---|---|
| Axe des roues | **z = 32.5 mm** (= rayon de roue) |
| Voie (entre plans médians de roue) | **72.8 mm** |
| Largeur hors-tout aux roues | **81.8 mm** |
| Garde au sol sous le socle | **20.0 mm** (le socle est à z = 20) |
| Hauteur hors-tout (sol → sommet `sensor_mount`) | **209.65 mm** |
| Axe de tangage (hauteur du capteur) | **197.10 mm** |
| Engagement axe servo / moyeu de roue | **2.50 mm** |
| Engagement axe pan / moyeu `head_tilt` | **3.00 mm** |
| MPU6050 | **6.5 mm sous l'axe des roues**, sur l'axe médian |
| Épaisseur du plancher au droit des vis M3 de tête | **8.4 mm** |

**Le socle ne peut pas toucher le sol, quel que soit l'angle d'inclinaison** :
tout le corps jusqu'à **z = 59.9 mm** reste à l'intérieur du disque de roue
(coin le plus éloigné : 23.58 mm contre un rayon de 32.5 mm). C'est l'arête
arrière du mât qui sort la première du disque, à z ≈ 59.9 — au-delà, en cas de
chute franche, c'est le mât puis la tête qui portent.

---

## 4. Orientations d'impression (aucun support nulle part)

| Pièce | Qté | Orientation | Notes |
|---|---|---|---|
| `body` | 1 | **Telle qu'exportée**, debout sur le socle (Z = axe de construction) | Toutes les parois verticales, tous les plafonds biseautés à 45° : raccord socle→mât en tronc de pyramide, plafond du caisson en bâtière, rail de carte incliné, gousset sous la tablette. 128 mm de haut → brim conseillé. |
| `wheel` | 2 | **Telle qu'exportée**, axe vertical, face EXTERNE en bas | Le lamage Ø12.4 s'ouvre vers le haut : aucun plafond en porte-à-faux. Les 2 roues sont **strictement identiques**, pas de miroir. |
| `head_pan` | 1 | **Telle qu'exportée**, à plat, face z = 0 sur le plateau | — |
| `head_tilt` | 1 | **Telle qu'exportée**, debout sur la base | Le moyeu porte sur le bossage Ø11.8, donc **aucun lamage** et donc aucun plafond. |
| `sensor_mount` | 1 | **Telle qu'exportée**, debout sur le rail bas, dos vertical | Biseau à 45° sous le rail haut. Le moyeu Ø16 est un cylindre horizontal : sa moitié basse est un surplomb auto-portant classique, léger affaissement cosmétique possible sur les 2 premières couches du cylindre. |

Les deux servos de roue ont la **même implantation** : le gauche est le droit
tourné de 180° autour de Y (rotation propre). Un seul corps, on inverse
simplement un moteur dans le firmware.

---

## 5. Visserie nécessaire

| Qté | Vis | Emploi | Trou côté pièce |
|---|---|---|---|
| 8 | **M2 × 8 autotaraudeuse** (ou les vis fournies avec les SG90) | Pattes des 4 servos : 2 roues (dans `body`), 1 pan (dans `head_pan`), 1 tilt (dans `head_tilt`) | avant-trou Ø1.70 |
| 4 | **M3 × 12 autotaraudeuse** | `head_pan` → `body` (plancher de 8.4 mm) | Ø3.40 passant / Ø2.60 avant-trou |
| 2 | **M2 × 6** | MPU6050 → piédestal du `body` | avant-trou Ø1.70 |
| 2 | **M2 × 6** | Carte T-Display S3 → plots du berceau (trous RÉELS de la carte, entraxe 20.01) | avant-trou Ø1.70 |
| 2 | **M2 × 8** | Blocage radial de `head_tilt` sur l'axe du servo pan | avant-trou Ø1.70 |
| 2 | **M2 × 8** | Blocage de `sensor_mount` sur l'axe du servo tilt | avant-trou Ø1.70 |
| 4 | **M2 × 10** | Blocage radial des 2 roues sur les axes (2 par roue, à 90°) | **Ø2.20 — voir §6 point 1** |

**Total : 20 vis M2 + 4 vis M3.** Aucune vis pour le HC-SR04 (glissière + 4
lèvres de retenue) ni pour les roues au-delà des vis radiales.

---

## 6. Ordre d'assemblage

1. **Imprimer** les 5 pièces (`wheel` ×2). Ébavurer les alésages Ø5.2 : passer
   un foret Ø5 à la main, sans perceuse.
2. **Préparer les servos** : convertir 2 SG90 en rotation continue (ou utiliser
   des FS90R) pour les roues. **Mettre les 2 servos de tête au neutre (90°)**
   avant toute liaison mécanique — c'est irréversible ensuite sans démontage.
3. **Servos de roue** : les engager dans les lumières du `body` **par
   l'intérieur** ; les pattes viennent porter sur la face extérieure des
   plaques. 2 × M2 chacun. Le câble sort librement par la lumière (la paroi
   arrière n'est pas percée, pour ne pas affaiblir le socle).
4. **MPU6050** dans la logette du piédestal, encastrement de 1.5 mm, 2 × M2.
   **Faire remonter le câble dans le mât maintenant** : il n'est plus
   accessible une fois la tête posée.
5. **Roues** : emmancher sur les axes (Ø5.2 sur Ø4.8), le lamage vient
   s'asseoir sur le bossage Ø11.8. Serrer les 2 vis radiales de chaque roue.
6. **Servo pan** dans `head_pan`, engagé **par le dessous** ; les pattes
   portent sur la face supérieure de la collerette. 2 × M2.
7. **`head_pan` sur le `body`** : 4 × M3 (Ø3.4 passant dans `head_pan`,
   Ø2.6 taraudé dans le plancher). Le corps du servo pan plonge dans le
   caisson par la lumière prévue ; y faire passer son câble.
8. **`head_tilt` sur l'axe du servo pan** : le moyeu s'assoit **sur le bossage
   Ø11.8** (pas de lamage, c'est la portée). 3.0 mm d'axe utile restent
   dégagés : y serrer les 2 vis radiales M2.
9. **Servo tilt** dans le bras GAUCHE de `head_tilt`, corps vers −X, axe vers
   +X. 2 × M2.
10. **HC-SR04** dans `sensor_mount` : glisser le PCB par l'avant dans la
    glissière, **broches vers le bas**. Les 4 lèvres le retiennent.
11. **`sensor_mount` sur `head_tilt`** : alésage gauche sur l'axe du servo
    tilt, logement droit sur le tourillon Ø4. 2 × M2 de blocage.
12. **Carte T-Display S3** : l'introduire **par +X** en la faisant glisser
    entre la tablette basse et le rail haut ; elle se clipse sur la nervure.
    Verrouiller avec les 2 M2. L'USB-C sort par l'échancrure de la joue gauche.
13. **Câblage**, puis **calibration** (`calibration/calibration.ino`) avant de
    téléverser le firmware d'équilibre.

---

## 7. Points de vigilance

1. **Trous radiaux des roues à Ø2.2 : ce sont des trous de PASSAGE, pas des
   avant-trous.** Partout ailleurs, l'avant-trou M2 autotaraudeur vaut Ø1.70
   (`SV_PILOT_D`) ; la roue utilise `GRUB_D = 2.2`. Une vis M2 n'y mordra pas
   dans le PLA. Trois issues : passer `GRUB_D` à 1.7, poser un écrou M2 en
   contre-face, ou utiliser une vis sans tête M3 dans un insert. **C'est le
   seul point qui empêche un serrage effectif en l'état.**
2. **Engagement axe/moyeu de roue : 2.50 mm seulement.** C'est le maillon
   faible mécanique de la transmission (le script le contrôle et exige ≥ 2.0).
   Les vis radiales ne sont donc pas optionnelles : sans elles, la roue patine
   ou se déchausse.
3. **Cote axiale de `sensor_mount` indéterminée de 0.3 mm.** La face gauche du
   moyeu est à X = −5.20 alors que le bossage Ø11.8 du servo tilt s'arrête à
   X = −4.90 : la pièce viendra en fait porter sur le bossage, soit 0.3 mm plus
   à +X que le modèle. Ce n'est pas gênant (porter sur le bossage est même une
   référence axiale propre, c'est le principe retenu pour `head_tilt`), mais la
   CAO et la réalité diffèrent de 0.3 mm. Pour aligner les deux : centrer
   `sm_moyeu` à X = 0.85 au lieu de 0.70.
4. **L'encliquetage de la carte travaille en interférence de 0.25 mm** sur un
   PCB portant une dalle de verre collée. Imprimer d'abord la seule zone du
   berceau (ou un tronçon) et valider l'effort d'insertion à la main avant
   d'y engager la carte.
5. **Le neutre des servos de tête doit être réglé avant l'étape 8.** Une fois
   `head_tilt` bloqué par ses vis radiales, la course pan/tilt est figée par
   rapport au débattement réel du servo.
6. **Fragilité du sondage de `verify_chassis.py`.** Le contrôle matière/vide
   est un lancer de rayon : si le point tombe exactement sur une arête de
   triangulation, la traversée est comptée deux fois et la parité s'inverse —
   une pièce pleine est lue « vide ». C'est ce qui est arrivé au moyeu de
   `sensor_mount` : avec un nombre de segments **multiple de 12**, le polygone
   place un sommet pile à 30°, soit Y = −2 − 8·sin(30°) = **−6.00**, exactement
   le plan de sonde. Le moyeu est passé à **64 segments** (non multiple de 12 :
   sommets voisins à −5.771 et −6.445). **Règle à retenir : pour tout cylindre
   sondé, éviter un nombre de segments multiple de 12, ou décaler le point de
   sonde d'une valeur non remarquable.**
7. **Nit de documentation** : le commentaire de `BODY_Z0` annonce « 12.5 mm de
   garde au sol ». 12.5 mm est la distance sous l'*axe des roues* ; la garde au
   sol réelle est de **20.0 mm**.
8. **Les modèles de référence sont dans `/tmp`** (`/tmp/t-display-s3-ref`,
   `/tmp/touch-3d`). Ils ne survivront pas à un redémarrage : toutes les cotes
   qu'ils ont servi à établir sont figées en constantes dans `gen_chassis.py`,
   c'est désormais la seule source à jour.
