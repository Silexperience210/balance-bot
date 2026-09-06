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

> **v2 (châssis actuel).** Trois évolutions par rapport à la v1 :
> 1. le **corps est en deux moitiés** `body_a` (avant) / `body_b` (arrière),
>    assemblées par goujons + 4 vis M3 — voir §8 ;
> 2. les roues sont remplacées par des **pieds en arc** `foot_arc`, entraînés
>    par des **SG90 standard 180°** (plus aucune rotation continue) — voir §9 ;
> 3. le berceau du HC-SR04 laisse le **champ des transducteurs entièrement
>    libre** — voir §10.
> Deux cotes de la v1 ont bougé, toutes deux imposées par l'impression :
> `MAST_Y0` passe de −18 à **−20** (dos plan continu, plateau de `body_b`) et
> `CAV_TAPER_Z0` de 38 à **40** (pente de cavité portée de 40.9° à 46.1°).
> L'empreinte au sol, la voie, la garde au sol, l'épaulement porte-carte et
> l'assise de tête sont **inchangés**.

### 1.2 Servo SG90 (×4 : 2 pieds 180°, 2 tête)

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
| Goujon `body_b` / alésage `body_a` | Ø5.8 | **Ø6.00** | +0.20 |
| Tenon de socle / mortaise | 9.0 × 2.9 | **9.30 × 3.20** | +0.30 |
| Tenon de mât / rainure | 1.2 × 1.0 | **1.50 × 1.30** | +0.30 |
| Bras du palonnier SG90 / empreinte | 5.0 | **5.15** | +0.15 |
| Bossage servo Ø11.8 / logement du pied | 11.8 | **Ø12.40** | +0.60 |
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

**Règle v2 : les deux moitiés du corps s'impriment À PLAT, couchées, cavités
ouvertes vers le haut.** L'axe de construction n'est plus Z mais **Y**.

| Pièce | Qté | Orientation | Notes |
|---|---|---|---|
| `body_a` (avant) | 1 | **Couchée sur le PLAN DE JOINT** : poser la face `Y = −0.4` sur le plateau, c'est-à-dire coucher la pièce vers l'arrière. Dans le slicer : rotation de **+90° autour de X**. Empreinte 66 × 128 mm, **hauteur 11.4 mm**. | La face de joint est plane sur toute la pièce : contact plateau maximal, pas de brim nécessaire. Tout se construit vers l'avant du robot : berceau de carte, joues, lèvre, pince, plots de joint — que des voiles verticaux. Aucune cavité fermée. |
| `body_b` (arrière) | 1 | **Couchée sur son DOS PLAN** `Y = −20` : rotation de **−90° autour de X**. Empreinte 66 × 128 mm, **hauteur 27.4 mm** (goujons compris). | Le dos est un plan unique de z = 20 à z = 148 (c'est pour cela que `MAST_Y0` a été aligné sur `BODY_Y0`). Mât, caisson, logette MPU, lumières de servo : toutes les cavités débouchent au sommet, sur le plan de joint. Les goujons Ø5.8 s'impriment en piliers verticaux. |
| `foot_arc` | 2 | **Tel qu'exporté**, axe vertical, face EXTERNE en bas | L'empreinte du palonnier et le dégagement de vis s'ouvrent vers le haut. Les 2 pieds sont **strictement identiques**, pas de miroir. |
| `head_pan` | 1 | **Telle qu'exportée**, à plat, face z = 0 sur le plateau | — |
| `head_tilt` | 1 | **Telle qu'exportée**, debout sur la base | Le moyeu porte sur le bossage Ø11.8, donc **aucun lamage** et donc aucun plafond. |
| `sensor_mount` | 1 | **Telle qu'exportée**, debout sur le rail bas, dos vertical | Biseau à 45° sous le rail haut. Le moyeu Ø16 est un cylindre horizontal : sa moitié basse est un surplomb auto-portant classique, léger affaissement cosmétique possible sur les 2 premières couches du cylindre. |

Les deux servos de pied ont la **même implantation** : le gauche est le droit
tourné de 180° autour de Y (rotation propre). Un seul corps, on inverse
simplement un moteur dans le firmware.

**Les trois seuls surplombs qui subsistent** (aucun ne demande de support) :

1. `body_a`, plaques porte-servo : au-dessus de la lumière du servo, la plaque
   se referme en **pont de 12.2 mm** sur 2.4 mm de large, entre deux appuis
   déjà imprimés. Pontage courant.
2. `body_a`, raccord socle → mât : la face avant de la cavité est un surplomb
   à **46.1°** de l'horizontale, ancré sur le plateau à z = 50. C'est
   exactement la raison du passage de `CAV_TAPER_Z0` de 38 à 40.
3. `body_a`, lèvre basse et nervure de pince du berceau de carte :
   micro-porte-à-faux de **1.0 mm** et **0.4 mm** en bord de tablette.

`body_a` comporte en outre trois rainures d'assemblage débouchant dans la face
plateau (2 rainures de tenon de mât, 1.5 mm ; 2 mortaises de socle,
traversantes) : les rainures de mât se pontent sur 1.5 mm, sans conséquence.

---

## 5. Visserie nécessaire

| Qté | Vis | Emploi | Trou côté pièce |
|---|---|---|---|
| 8 | **M2 × 8 autotaraudeuse** (ou les vis fournies avec les SG90) | Pattes des 4 servos : 2 pieds (à cheval sur `body_a`/`body_b`), 1 pan (dans `head_pan`), 1 tilt (dans `head_tilt`) | avant-trou Ø1.70 |
| 4 | **M3 × 12 autotaraudeuse** | `head_pan` → `body_b` (plancher de 8.4 mm) | Ø3.40 passant / Ø2.60 avant-trou |
| 4 | **M3 × 30 autotaraudeuse** | **Assemblage `body_b` → `body_a`** : posées par l'arrière, tête sur la face plane Y = −20 | Ø3.40 passant (body_b) / Ø2.60 avant-trou (body_a) |
| 2 | **M2 × 6** | MPU6050 → piédestal du corps (une vis dans chaque moitié) | avant-trou Ø1.70 |
| 2 | **M2 × 6** | Carte T-Display S3 → plots du berceau (trous RÉELS de la carte, entraxe 20.01) | avant-trou Ø1.70 |
| 2 | **M2 × 8** | Blocage radial de `head_tilt` sur l'axe du servo pan | avant-trou Ø1.70 |
| 2 | **M2 × 8** | Blocage de `sensor_mount` sur l'axe du servo tilt | avant-trou Ø1.70 |
| 2 | **M2 × 8** | Vis centrales des 2 palonniers SG90 sur leurs axes (fournies avec les servos) | — |
| 4 | **M2 × 8 autotaraudeuse ou M2 + écrou** | Fixation de chaque `foot_arc` sur son palonnier (2 par pied) | trous **oblongs Ø2.2 × 5.0** |

**Total : 20 vis M2 + 8 vis M3.** Aucune vis pour le HC-SR04 (glissière +
4 lèvres latérales). Aucune vis pour les goujons : ils sont **venus de
fonderie sur `body_b`**, il n'y a donc pas de goujon en pièce détachée à
imprimer ni à acheter.

---

## 6. Ordre d'assemblage

**L'ordre a changé en v2 : le corps se ferme à l'étape 6, tout ce qui est à
cheval sur le plan de joint doit être posé avant ou juste après.**

1. **Imprimer** les 6 fichiers : `body_a`, `body_b`, `foot_arc` **×2**,
   `head_pan`, `head_tilt`, `sensor_mount`. Ébavurer les alésages Ø5.2 et
   Ø6.0 ; présenter les 4 goujons de `body_b` dans les alésages de `body_a`
   **à vide**, sans rien d'autre en place, et corriger au besoin (goujon
   Ø5.8 dans Ø6.0 : entrée à la main, sans marteau).
2. **Préparer les servos** : 4 SG90 **standard 180°**, aucune conversion en
   rotation continue. **Mettre les 4 servos au neutre (90°)** avant toute
   liaison mécanique — c'est irréversible ensuite sans démontage.
3. **Servos de pied** : les poser dans les demi-lumières de `body_a`, corps
   vers l'intérieur, axe vers l'extérieur. Les pattes portent sur la face
   extérieure des plaques. **Ne pas visser encore** : la lumière n'est
   complète qu'une fois `body_b` en place. Le câble sort par la lumière et se
   range dans le socle.
4. **Faisceaux** : faire cheminer dès maintenant, dans le mât ouvert de
   `body_b`, les fils des 2 servos de pied, du MPU6050 et de la tête. Le mât
   est une goulotte ouverte tant que les deux moitiés ne sont pas jointes —
   c'est le moment le plus confortable pour câbler.
5. **Présenter `body_b` sur `body_a`** : les 4 goujons (2 tenons
   rectangulaires au socle, 2 goujons Ø5.8 au caisson) et les 2 tenons
   latéraux du mât guident l'accostage. Les deux pièces doivent venir en
   contact franc sur tout le plan de joint, sans jour.
6. **Fermer le corps** : 4 vis **M3 × 30** posées **par l'arrière**, tête sur
   la face plane Y = −20 (2 au socle à x = ±5, z = 21.2 ; 2 au caisson à
   x = ±24, z = 112.9). Serrer en croix, sans forcer (autotaraudage dans le
   PLA de `body_a`).
7. **Visser les 2 servos de pied** : 2 × M2 chacun, les pattes portant sur la
   face extérieure des plaques, maintenant reconstituées.
8. **MPU6050** : sa logette est **à cheval sur le joint**, il se pose donc
   APRÈS fermeture, par l'avant du socle (qui reste ouvert). Encastrement de
   1.5 mm, 2 × M2 (une vis dans chaque moitié).
9. **Pieds en arc** : visser d'abord le palonnier fourni sur l'axe du servo
   (vis M2 centrale), **servo au neutre, arc dirigé vers le BAS** ; puis
   présenter le `foot_arc` sur le palonnier (empreinte en croix côté servo) et
   le fixer par 2 vis M2 dans les trous oblongs. Vérifier que le point de
   contact tombe **exactement sous l'axe** avant de serrer.
10. **Servo pan** dans `head_pan`, engagé **par le dessous** ; les pattes
   portent sur la face supérieure de la collerette. 2 × M2.
11. **`head_pan` sur le corps** : 4 × M3 (Ø3.4 passant dans `head_pan`,
    Ø2.6 taraudé dans le plancher de `body_b`). Le corps du servo pan plonge
    dans le caisson par la lumière prévue ; y faire passer son câble.
12. **`head_tilt` sur l'axe du servo pan** : le moyeu s'assoit **sur le
    bossage Ø11.8** (pas de lamage, c'est la portée). 3.0 mm d'axe utile
    restent dégagés : y serrer les 2 vis radiales M2.
13. **Servo tilt** dans le bras GAUCHE de `head_tilt`, corps vers −X, axe vers
    +X. 2 × M2.
14. **HC-SR04** dans `sensor_mount` : glisser le PCB par l'avant dans la
    glissière, **broches vers le bas**. Le dos, le rail bas et les 4 lèvres
    **latérales** le retiennent ; le champ des capsules reste libre.
15. **`sensor_mount` sur `head_tilt`** : alésage gauche sur l'axe du servo
    tilt, logement droit sur le tourillon Ø4. 2 × M2 de blocage.
16. **Carte T-Display S3** : le berceau appartient **entièrement à `body_a`**,
    la carte peut donc être posée ou retirée **à tout moment, corps fermé**.
    L'introduire **par +X** en la faisant glisser entre la tablette basse et
    le rail haut ; elle se clipse sur la nervure. Verrouiller avec les 2 M2.
    L'USB-C sort par l'échancrure de la joue gauche.
17. **Câblage final** : souder / brancher les fils sur les pads GPIO au dos de
    la carte (servos 1/2/3/10, I2C 17/18, ultrason 11/12), les faire plonger
    par les **deux fenêtres de câblage** de la paroi de caisson, puis
    descendre par le caisson et le mât jusqu'au socle. Un **passe-fil arrière**
    (24 × 10 mm, z 108..118) permet, si besoin, de sortir un faisceau par
    l'arrière du caisson.
18. **Calibration** (`calibration/calibration.ino`) avant de téléverser le
    firmware d'équilibre.

---

## 7. Points de vigilance

1. **L'entraxe des trous du palonnier SG90 n'est pas normalisé** (4.5 à 6.0 mm
   du centre selon la marque). Les 2 trous du `foot_arc` sont donc des
   **oblongs de 5.0 mm de long** (rayon 3.7 à 6.3), qui couvrent toute la
   plage. Si le palonnier fourni a ses trous encore plus loin du centre,
   augmenter `HORN_SCREW_R` — l'empreinte en croix, elle, va jusqu'à r = 10.
2. **Le pied en arc ne transmet aucun couple par l'axe cannelé**, uniquement
   par les 2 vis M2 dans le palonnier. Serrer modérément mais sûrement : c'est
   le seul lien mécanique. Le contact étant au rayon 32.5, l'effort au sol
   travaille en levier sur ces deux vis.
3. **Le corps ne peut être fermé qu'une fois les servos de pied posés** : la
   lumière de chaque servo est à cheval sur le plan de joint. De même la
   logette du MPU6050 — mais elle, elle reste accessible corps fermé, par
   l'avant du socle.
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

---

## 8. Le corps en deux moitiés — choix du plan de joint

### 8.1 Pourquoi ce plan et pas un autre

Le corps v1 était une pièce unique de 128 mm de haut renfermant une cavité
**close** (socle → mât → évasement → caisson). Elle était certes dessinée
« sans support », mais elle ne se contrôle pas et ne se câble pas.

Quatre plans de joint ont été examinés. Le critère retenu est le plus
exigeant : **chaque moitié doit se poser À PLAT sur une grande face plane, et
toutes ses cavités doivent s'ouvrir vers le haut.** Une moitié n'est plate que
si elle repose sur sa peau EXTERNE (ou sur le joint), le côté creux tourné
vers le haut.

| Plan envisagé | Verdict |
|---|---|
| Gauche / droite (X = 0) | ✗ La peau externe latérale est en escalier (socle ±25, mât ±20, caisson ±33). Aucune des deux moitiés ne se pose à plat. |
| Haut / bas (Z = 94) | ~ Supprime bien le volume clos, mais les deux moitiés s'impriment toujours DEBOUT (74 et 54 mm) : rien de gagné sur la planéité, et le mât est coupé en travers de l'effort de flexion — le pire endroit. |
| Avant / arrière à Y = −8 (milieu du mât) | ✗ La moitié avant devrait se poser sur sa peau avant, elle aussi en escalier (socle Y = 10, mât Y = 2, berceau Y = 11) : 9 mm de porte-à-faux sur toute la hauteur. |
| **Avant / arrière à Y = −0.4** (retenu) | ✓ Voir ci-dessous. |

**Le plan retenu, `Y_JOINT = MAST_Y1 − WALL = −0.4`, est la FACE INTERNE de la
paroi avant du mât et du caisson.** C'est le seul plan qui coupe le corps là
où celui-ci présente déjà une grande surface plane continue :

- `body_a` (avant) se pose **sur le plan de joint lui-même**. Toute sa matière
  est au-dessus : paroi avant du mât et du caisson (une plaque de 66 × 106 mm
  posée à plat sur le plateau), plaques porte-servo, plancher, piédestal MPU,
  berceau de carte entier. Hauteur totale **11.4 mm**, empreinte 66 × 128.
  Aucun volume clos, rien à ponter au-delà de 12.2 mm.
- `body_b` (arrière) se pose **sur son dos**, devenu un plan unique
  `Y = −20` de z = 20 à z = 148 — c'est pour cela, et pour cela seulement, que
  `MAST_Y0` a été aligné sur `BODY_Y0`. Le mât creux, le caisson, la logette
  MPU, les lumières de servo et la lumière du servo pan débouchent tous au
  sommet, sur le plan de joint. Hauteur **27.4 mm**, empreinte 66 × 128.

Bénéfice secondaire, décisif à l'usage : **le mât est une goulotte ouverte
tant que les deux moitiés ne sont pas jointes.** Tout le câblage se fait à
plat, à découvert.

### 8.2 Les liaisons du joint

| Repère | Position (x, z) | Mâle sur `body_b` | Femelle sur `body_a` |
|---|---|---|---|
| Tenon de socle ×2 | ±17.5, 23.2 | 9.0 × 2.9, saillie 6.8, venu de fonderie | mortaise **traversante** 9.3 × 3.2 |
| Goujon de caisson ×2 | ±24.0, 108.5 | Ø5.8, saillie 6.8 + bout tronconique Ø4.2 | alésage **traversant** Ø6.0 |
| Tenon de mât ×2 | ±18.8, z 52..92 | languette 1.2 × 1.0 | rainure 1.5 × 1.3 |
| Vis M3 ×4 | ±5.0 / 21.2 et ±24.0 / 112.9 | Ø3.4 passant, tête sur le dos plan | Ø2.6 autotaraudé, 8.5 mm |

**Pourquoi un tenon rectangulaire au socle et un goujon rond au caisson.** Au
socle, la seule zone libre au droit du joint est *sous* les servos : il n'y
reste que **6.4 mm** de hauteur (z 20.0 à 26.4, le corps du servo commence à
26.4). Un goujon Ø6 y laisserait 0.2 mm de matière au-dessus et au-dessous.
Un tenon de 2.9 mm de haut sur 9 mm de large y tient largement, et bloque en
prime la rotation. Au caisson au contraire, `body_a` offre 8.2 mm de matière
pleine (paroi de caisson + gousset du berceau de carte) : le goujon Ø5.8
classique y trouve toute sa place.

Toutes les femelles de `body_a` sont **traversantes** : rien à ponter en fond
d'alésage. Les 4 vis M3 se posent **par l'arrière**, tête directement sur la
face plane Y = −20 (qui est la face plateau de `body_b`, donc parfaitement
plane) ; leur trajet traverse de la matière pleine de bout en bout — plancher
du socle pour les deux basses, plot de joint + tablette du berceau de carte
pour les deux hautes.

### 8.3 L'espace de câblage derrière les pins GPIO

- **6.2 mm** de dégagement franc entre le dos du PCB (Y = 8.2) et la paroi de
  caisson (Y = 2), sur toute la longueur de la carte hormis les deux appuis
  arrière (x ≤ −24.4 et x ≥ +26.8, seuls endroits où le dos de la carte est nu).
- **Deux fenêtres de câblage** percées dans cette paroi, x −24..−7 et
  x +17..+26, z 116..137 : les fils quittent le dos de la carte et plongent
  dans le caisson, profond de **17.2 mm**. Elles évitent les deux appuis
  arrière, les deux plots de vis M2 de la carte, et le volume du servo pan
  (qui occupe x −5..+16 au-dessus de z 125.5).
- Le caisson communique avec le mât par la cavité d'évasement, et le mât avec
  le socle : **un seul chemin continu** de la carte aux servos de pied.
- **Passe-fil arrière** de 24 × 10 mm (x ±12, z 108..118) dans le dos du
  caisson, pour sortir un faisceau vers l'extérieur si besoin.
- La carte reste amovible **corps fermé** : son berceau appartient en entier
  à `body_a`, et elle s'introduit toujours par +X.

---

## 9. Le pied en arc (`foot_arc`)

Les SG90 restent **standard, 180°** : plus aucune conversion en rotation
continue. Le robot n'a plus de roues mais deux patins circulaires qui roulent
sur le sol dans la limite du débattement du servo.

| Cote | Valeur | Justification |
|---|---|---|
| Rayon extérieur | **32.5** | = `WHEEL_R`. Géométrie externe du corps, garde au sol et hauteur d'axe (`AXLE_Z = 32.5`) **inchangées**. |
| Largeur | **9.0** | = `WHEEL_W`, même position en X (`WHEEL_X0 = 31.9`), même voie 72.8 mm. |
| Ouverture angulaire | **200°** | Le débattement utile du servo est ±90° ; l'arc les couvre avec **10° de marge** de chaque côté. |
| Bande de roulement | **3.2 mm, pleine et lisse** | Aucun évidement ne débouche sur la surface de contact. |
| Structure interne | moyeu Ø18 + **5 nervures** de 3.2 mm (dont une à chaque extrémité de l'arc) + **arc intermédiaire** r 19.0..22.2 | Les nervures d'extrémité ferment les deux flancs, l'arc intermédiaire empêche la couronne de s'ovaliser. |

**Orientation angulaire et angle de repos.** Dans le repère de la pièce, l'arc
est centré sur −Y local et couvre **170° à 370°**. Au montage, servo **au
neutre (90°)**, le pied est calé sur le palonnier avec le milieu de l'arc
dirigé **vers le bas** : le point de contact tombe alors **exactement sous
l'axe**, robot vertical, à la même hauteur qu'avec les roues. À ±90° de servo,
le contact se déplace de ±90° le long de l'arc et reste à 10° du bord.

**Fixation.** L'axe cannelé 25 dents n'est **pas** repris directement : on
visse le palonnier fourni sur l'axe (vis M2 centrale), puis le pied sur le
palonnier. L'empreinte du palonnier est donc **du côté SERVO** (face interne
du pied) — et non côté externe comme envisagé au départ : l'axe ne dépasse que
de 4.2 mm dans l'épaisseur du pied, un logement côté externe serait hors
d'atteinte du palonnier. Elle se compose de :

- une **croix à 4 branches** de 5.15 mm de large et 20 mm d'envergure,
  profonde de 3.4 mm, qui reçoit le palonnier en étoile ;
- un **Ø12.4** central qui dégage à la fois le moyeu du palonnier et le
  bossage Ø11.8 du servo ;
- un **Ø8 × 2.2** supplémentaire pour la tête de la vis centrale ;
- **2 trous oblongs Ø2.2 × 5.0** (rayon 3.7 à 6.3), traversants jusqu'à la
  face externe : les vis M2 se posent **par l'extérieur** du pied.

**Impression** : tel qu'exporté, axe vertical, **face externe en bas**.
L'empreinte et le dégagement de vis s'ouvrent vers le haut, les oblongs sont
des perçages verticaux depuis le plateau. Aucun support. Les 2 pieds sont
identiques, pas de miroir.

La pièce `wheel` reste dans `gen_chassis.py` (`piece_roue`) à titre de
référence de cotes, mais elle n'est **plus exportée**.

---

## 10. Le champ des transducteurs du HC-SR04

Le rail haut de la v1 (`sm_haut`) était une barre pleine courant sur toute la
largeur du berceau, juste au-dessus des deux capsules et devant elles. Il est
désormais **limité aux deux bords latéraux**, |x| ≥ 16 mm :

- la zone x = −16..+16, c'est-à-dire **tout l'espace entre les deux capsules**
  (entraxe 26, Ø16 : elles occupent x = −21..+21) est vide **sur toute la
  profondeur vers +Y**, de la face avant du PCB jusqu'à l'infini ;
- le biseau anti-support à 45° a été scindé de la même façon ;
- un volume de garde explicite (`sm_champ`) est soustrait en fin de
  construction : il garantit qu'aucun ajout ultérieur ne reviendra dans cette
  zone ;
- le PCB n'est donc plus retenu que par **le dos, le rail bas et les deux
  bords latéraux** (joues + 4 lèvres à |x| ≥ 18) — ce qui suffit, la glissière
  restant fermée sur trois côtés.

Six sondes de `verify_chassis.py` verrouillent le résultat : vide devant les
capsules (0.3, 20.0, 0.3), vide entre elles (0.3, 12.0, 11.5), rail haut
supprimé au centre (0.3, 4.0, 11.5), bord latéral conservé (20.0, 3.0, 11.5),
lèvres de retenue conservées (20.0, 5.8, ±9.4).
