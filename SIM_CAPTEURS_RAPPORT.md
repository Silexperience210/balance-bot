# SIM_CAPTEURS_RAPPORT — Capteurs à ultrasons + animations du corps

Date : 2026-09-17. Portée : `sim/web/` + l'emballeur. Le firmware
(`balance-bot/`) et le châssis n'ont **pas** été touchés — ils restent la
référence. Le cœur du moteur `engine.js` n'a **pas** été modifié : le hook
`customEffects` reste la seule porte d'injection de la physique.

## Ce qui a été ajouté, fichier par fichier

### `sim/web/ultrason.js` (NOUVEAU)

Module pur JS (zéro dépendance, exporte `window.Ultrason` + `module.exports`
pour Node), transcription comportementale de `balance-bot/head.cpp`. Il est
cadencé sur l'horloge du moteur : le viewer l'appelle une fois par pas de 5 ms
(200 Hz = `BALANCE_LOOP_HZ`, `config.h:65`), donc les mesures tombent tous les
40 pas — tous les 200 pas après 3 échecs. Chaque comportement, ligne à ligne :

| Comportement simulé | Référence firmware |
|---|---|
| Constantes `US_MAX_CM = 150`, `US_STOP_CM = 25` | `config.h:75-76` |
| Bornes tête pan 0…180°, tilt 20…90°, centre 90°/60° | `config.h:71-74`, `head.cpp:59-62` |
| Vitesse tête 30°/s, position float bornée par pas | `head.cpp:38-39`, `head.cpp:191-195` |
| Cadence adaptative : 200 ms, 1000 ms après 3 échecs consécutifs, retour à 200 ms dès qu'un écho revient | `head.cpp:106-113` |
| Timeout `pulseIn` = `150 × 58 + 800 = 9500 µs` : l'écho « revient » si `dist × 58 ≤ 9500` (soit ≈ 163,8 cm) | `head.cpp:134-135` |
| Conversion `distance = durée_µs / 58` (côté sim : la distance réelle est l'entrée, la durée est le critère d'écho) | `head.cpp:139` |
| Timeout **non injecté** dans la moyenne, distance publiée −1, pas d'alerte | `head.cpp:146-151` |
| Lissage exponentiel sur 5 échantillons (`moy += (mesure − moy) / 5`), amorcé sur la 1re mesure | `head.cpp:26-28`, `head.cpp:155-157` |
| Alerte quand la distance lissée < 25 cm, angle où l'obstacle a été vu | `head.cpp:163-170` |
| Lissée > 150 cm → « hors portée » (`obstacleCm = −1`) **sans** compter un échec | `head.cpp:173-175` |
| Équilibre → tête ramenée au centre, immobile ; au sol → balayage continu | `head.cpp:190-205` |
| `reset()` = `Head::begin()` : lissage et balayage remis à zéro | `head.cpp:84-95` |

Le module ne fait que **publier** `obstacleCm` / `obstacleWarn` / `angleVu` :
comme le firmware, il ne déclenche aucune réaction physique du robot.

### `sim/web/ui.js` (modifié)

- **Garde-fou** : bannière d'erreur si `ultrason.js` est absent (même esprit que
  celui d'`engine.js`).
- **Module HC-SR04 en 3D** : pièce achetée, pas de STL → modélisation
  Three.js : PCB bleu 45 × 20 × 2 mm + deux transducteurs Ø16 × 12 mm avec
  grille avant. UN SEUL module, comme le robot réel (`config.h:61-62` :
  un TRIG, un ECHO ; `docs/photos/robot-reel.jpg`) : centré en Z sur la face
  avant, lobe haut du ₿ (y = +98 mm au-dessus de l'axe), plaqué sur la coque
  (x = 23 mm, face avant mesurée sur `parts.js`). Ajouté à `groupeCorps` →
  il suit exactement les transformations du corps.
- **Mesure analytique** : la distance est calculée depuis la pose PHYSIQUE
  (`sim.state` : x = R·(θ+φ) + SONDE_X·cos θ + SONDE_Y·sin θ), jamais depuis
  le maillage — les animations ne peuvent pas la toucher (voir
  « Après contre-vérification »).
- **Obstacle déplaçable** : plaque verticale de 10 × 140 × 100 mm posée au sol,
  placée par le curseur (5–200 cm). La distance mesurée est recalculée chaque
  frame **depuis la sonde** (`getWorldPosition`) jusqu'à la face avant de
  l'obstacle, dans le plan du sol — pas depuis le centre du robot. Quand le
  robot roule vers l'obstacle, la mesure diminue réellement.
- **Faisceau** : cône semi-transparent apex au capteur, longueur = distance
  réelle bornée à la portée ; vert = obstacle détecté, rouge = ALERTE < 25 cm,
  gris discret = rien/hors portée, masqué si le capteur est débranché.
- **Cadencement** : dans la boucle rAF, après `sim.stepMany(n)`, le viewer
  appelle `us.tickMany(n, distanceReelleCm(), !sim.state.fallen)` — le capteur
  partage l'horloge simulée (mesures aux mêmes instants que sur le robot).
  `us.reset()` est couplé au bouton RESET et au changement de scénario.
- **Télémétrie capteur** : distance lissée, état (rien / obstacle /
  ALERTE < 25 cm / absent), cadence courante (200/1000 ms), échecs consécutifs,
  pan/tilt de la tête, angle vu.
- **Animations** (sélecteur « ANIMATIONS » + bouton « Rejouer ») : `Aucune`,
  `Hochement`, `Regard gauche-droite`, `Sursaut`, `Danse`. Couche strictement
  cosmétique : offsets (tangage, lacet, rebond) ajoutés au **maillage** après
  la pose physique dans `majScene()`, plus expression/regard du visage forcés
  (`visage.exprAnim` / `gazeAnim`). `sim.state` et la commande ne sont jamais
  touchés ; `Aucune` = offsets nuls → image strictement identique à avant.
  Horloge = temps réel rAF (l'animation joue même en pause, sans avancer la
  physique) ; `Sursaut` est un one-shot de 0,7 s relançable, les autres
  bouclent ; changer de sélection ou cliquer « Rejouer » repart de t = 0.

### `sim/web/index.html` (modifié)

- Deux panneaux dans la colonne de droite (style existant conservé) :
  « Capteur ultrason (HC-SR04) » (curseur d'obstacle 5–200 cm, case « ECHO
  câblé », mini-grille de télémétrie) et « Animations » (sélecteur + Rejouer).
- Balise `<script src="ultrason.js"></script>` entre `engine.js` et `parts.js`.
- Styles : `#sel-anim` repris du sélecteur de visage, états du capteur
  colorés via les variables du thème (`--vert`, `--rouge`).

### `sim/web/selfcheck.js` (modifié) + `sim/web/selfcheck.html` (modifié)

- Sections 1–4 **inchangées** (mêmes valeurs de référence Python, mêmes
  tolérances) — la physique n'a pas bougé et l'écart reste nul.
- Nouvelle section 5 (16 contrôles) sur `ultrason.js` : cadence 200 ms
  (mesures à 200/400/600/800/1000 ms), amorçage du lissage, saut 80→30 cm
  (moy = 70 exactement), convergence, cadence 1000 ms après 3 échecs
  (200/400/600/1600/2600 ms), retour à 200 ms à l'écho retrouvé, timeout non
  injecté (44 = 40 + (60−40)/5), portée (160 cm = écho hors portée sans échec,
  170 cm = timeout), alerte < 25 cm + angle vu = 90°, balayage borné 0…180°,
  recentrage 90°/60° en équilibre.
- `selfcheck.html` charge `ultrason.js` avant `selfcheck.js`.

### `chassis/assets/emballer_simulateur.py` (modifié)

`ultrason.js` ajouté à `ORDRE`. Régénéré : `sim/web/simulateur-balancebot.html`
(1 424 548 octets, 6 fichiers inlinés, aucun `<script src=` résiduel) puis
copié sur `simulateur.html` à la racine (la racine était une copie exacte du
bundle, vérifié par `cmp` avant régénération). Vérifié en `file://` sous
Chrome headless : la scène rend, l'auto-test passe dans le navigateur.

## Sortie réelle de `node sim/web/selfcheck.js`

```
BalanceBot — auto-test du moteur engine.js

1. PRNG MT19937 + random.gauss (référence : CPython, random.seed(42))
  ✔ random() → 0.6394267984578837, 0.025010755222666936
  ✔ gauss(0,1) → -0.14409032957792836, -0.1729036003315193

2. Gains embarqués Kp25/Ki500/Kd0.5, k_out=1, kv=3, cascade ON, graine 42
    θ0=2° propre    : ❌ chute θ  t=0.545 s  θfin=+45.920°  φfin=+23.445°   = Python
    θ0=2° bruit     : ❌ chute θ  t=0.545 s  θfin=+45.919°  φfin=+23.603°   = Python
    θ0=5° bruit     : ❌ chute θ  t=0.425 s  θfin=+46.609°  φfin=+25.944°   = Python
    tape 0.4 rad/s  : ❌ chute θ  t=0.485 s  θfin=+45.009°  φfin=+22.888°   = Python
    tape 0.8 rad/s  : ❌ chute θ  t=0.490 s  θfin=+46.071°  φfin=+24.034°   = Python
    tape 1.2 rad/s  : ❌ chute θ  t=0.485 s  θfin=+45.347°  φfin=+22.690°   = Python
  ✔ 0/6 scénarios tenus (obtenu 0/6)
  ✔ verdicts, instants et états finaux conformes au Python

3. Kp25/Ki350/Kd1, k_out=3, kv=0, cascade ON, graine 42
  ✔ θ0=2° propre → « ok », θ fin = +0.0000° (< 0,5°), φ fin = +7.96°
    θ0=2° propre    : OK         t=5.995 s  θfin=+0.000°  φfin=+7.959°   = Python
    θ0=2° bruit     : OK         t=5.995 s  θfin=-0.038°  φfin=-2.602°   = Python
    θ0=5° bruit     : OK         t=5.995 s  θfin=-0.071°  φfin=+174.429°   = Python
    tape 0.4 rad/s  : OK         t=7.995 s  θfin=+0.001°  φfin=+423.887°   = Python
    tape 0.8 rad/s  : OK         t=7.995 s  θfin=+0.076°  φfin=+829.829°   = Python
    tape 1.2 rad/s  : ❌ chute θ  t=3.585 s  θfin=+45.704°  φfin=+152.366°   = Python
  ✔ 5/6 scénarios tenus comme le Python (obtenu 5/6)
  ✔ verdicts, instants et états finaux conformes au Python

4. Hook setCustom(fn) : appelé après la physique, une fois par pas
  ✔ 100 pas → 100 appels, t = 0.495 s, dt = 0.005
  ✔ state.theta = 60° écrit par le hook à t = 1 s → « chute θ » au même pas

5. Capteur HC-SR04 (ultrason.js) — cadence, lissage, portée, alerte, tête
  ✔ cadence 200 ms : mesures à 200, 400, 600, 800, 1000 ms
  ✔ lissage amorcé sur la 1re mesure : obstacleCm = 80 cm exactement
  ✔ saut 80→30 cm : une mesure après, moy = 70.00 (attendu 70)
  ✔ la moyenne glissante converge vers la distance réelle (30.000571 → 30, ±0,01 cm)
  ✔ capteur débranché : cadence 1000 ms après 3 échecs (200, 400, 600, 1600, 2600 ms)
  ✔ débranché : cadence affichée 1000 ms, distance invalide, pas d'alerte
  ✔ écho de retour → cadence 200 ms immédiate, moyenne re-amorcée à 50
  ✔ timeout : distance invalide publiée, pas d'alerte
  ✔ timeout non injecté : moyenne reprise en l'état (44.00 = 40 + (60−40)/5)
  ✔ 160 cm : écho reçu mais hors portée (obstacleCm = −1, pas d'échec)
  ✔ 170 cm : au-delà du timeout pulseIn (9860 > 9500 µs) → échec compté
  ✔ 20 cm lissés → ALERTE, angle vu = pan 90° (tête centrée)
  ✔ obstacle reparti → alerte et angle effacés
  ✔ balayage hors équilibre : pan borné à 0…180° (vu 0…180)
  ✔ équilibre : tête ramenée au centre (90°/60°) et immobile

═══ AUTO-TEST RÉUSSI ═══
```

(code de sortie 0 ; même verdict « AUTO-TEST RÉUSSI » sous Chrome headless en
ouvrant `sim/web/selfcheck.html` en `file://`.)

## Ce qui reste imparfait

- **Le balayage de tête n'est pas visible en 3D** : le châssis n'a pas de
  maillage de tête séparé (la « tête » est le corps entier), donc pan/tilt ne
  sont simulés que logiquement — affichés dans la télémétrie et utilisés pour
  l'« angle vu ». Faire pivoter le corps entier serait faux physiquement.
- **Après la chute, le temps simulé s'arrête** (le moteur s'arrête au verdict,
  comportement d'origine inchangé) : le balayage « robot au sol » n'est donc
  observable en pratique que dans l'auto-test, pas dans la scène live.
- **Distance mesurée dans le plan du sol** (distance horizontale sonde → face
  avant de l'obstacle) : on ignore la différence de hauteur, légitime pour un
  obstacle vertical, mais un obstacle très bas ou très haut ne serait pas
  distingué. L'obstacle est unique, vertical, et ne peut pas être déplacé
  latéralement (curseur de distance uniquement, pas de glisser 3D).
- **La distance est figée pendant chaque lot** de pas calculés entre deux
  frames (échantillonnée une fois par frame) : invisible, car le capteur
  n'échantillonne qu'au plus tous les 40 pas (200 ms).
- **Un seul capteur, logique ET visuel** (comme le firmware et le robot
  réel, `config.h:61-62` + photo) : un seul module HC-SR04 modélisé, la
  mesure part de la face avant de ses transducteurs.
- Le blocage de `pulseIn` (jusqu'à 9,5 ms volés à la boucle d'équilibre) n'est
  **pas** répercuté sur la physique — ce serait modifier le moteur, interdit
  par la mission ; seule la cadence des mesures est reproduite.

## Fichiers modifiés

- `sim/web/ultrason.js` — **nouveau** (capteur HC-SR04 + tête, miroir de `head.cpp`)
- `sim/web/ui.js` — module 3D, mesure analytique, faisceau, obstacle, animations, télémétrie capteur
- `sim/web/index.html` — panneaux « Capteur ultrason » et « Animations », script `ultrason.js`
- `sim/web/selfcheck.js` — section 5 (16 contrôles ultrason/tête), sections 1–4 inchangées
- `sim/web/selfcheck.html` — chargement d'`ultrason.js`
- `chassis/assets/emballer_simulateur.py` — `ultrason.js` ajouté à l'ordre d'inlining
- `sim/web/simulateur-balancebot.html` — régénéré (bundle mono-fichier)
- `simulateur.html` (racine) — copie du bundle régénéré

---

## Après contre-vérification (rapport indépendant `/home/silex/REVIEW_SIM_CAPTEURS.md`, HEAD `4796227`)

La contre-vérification a validé l'essentiel et relevé un défaut bloquant
(point C : les animations faussaient la mesure) plus des finitions. Tous les
points sont traités, dans `sim/web/` + `docs/GUIDE-SIMULATEUR.md` uniquement ;
`engine.js` et la physique d'`ultrason.js` n'ont pas bougé (seul le critère
d'écho du point F-b est corrigé, voir ci-dessous).

**1. (BLOQUANT, défaut C) La distance ne dépend plus des animations.**
Avant : la sonde était un `Object3D` enfant de `groupeCorps`, donc
`distanceReelleCm()` (via `getWorldPosition()`) incluait les offsets
d'animation appliqués par `majScene()`. Correction choisie : la distance est
calculée **analytiquement depuis la pose physique** (`sim.state`), sans passer
par la scène :

```
x_sonde = R·(θ+φ) + SONDE_X·cos θ + SONDE_Y·sin θ     (z = 0)
```

C'est la garantie la plus forte : les offsets d'animation n'existant que dans
le maillage, une mesure qui ne lit pas le maillage ne peut pas les voir — par
construction, pas par convention. Le **faisceau reste enfant de
`groupeCorps`** (il suit visuellement le corps, animations comprises : c'est
le choix assumé, il n'est qu'un pointeur), mais sa **longueur** vient de la
distance physique. Vérifié **par la mesure** (banc Node/Playwright dans
`/tmp/bench`, Chrome, même méthode que le rapport — pause, curseur 18 cm,
θ = 2°) :

| | anim « aucune » | hochement | regard | sursaut | danse |
|---|---|---|---|---|---|
| **avant** (HEAD) | 13,215 cm | 12,56–13,90 (Δ 1,34) | 13,22–13,42 (Δ 0,21) | 13,22–14,07 (Δ 0,86) | 12,87–13,88 (Δ 1,01) |
| **après** | 13,215 cm | **13,215 cm fixe (Δ 0,000)** | idem | idem | idem |

En RUN (« θ0=2° propre », curseur 18 cm) : lissée 13,126 cm sans animation ;
après 3 s de « danse » : **13,124 cm** après correction (13,281 cm avant,
fluctuante). La valeur de référence 13,215 cm est strictement identique avant
et après : la formule analytique retombe sur la pose monde mesurée (sonde
x = 42,85 mm).

**2. (BLOQUANT, F-5) Un seul module HC-SR04.** Le robot réel n'a qu'un module
(`config.h:61-62` ; sur la photo ce sont ses deux transducteurs qui font les
« yeux »). La scène 3D n'en modélise plus qu'**un**, centré en Z (z = 0) à la
place des yeux de la photo : face avant x = 23 mm, lobe haut y = +98 mm,
au-dessus de l'écran. Logique inchangée (un seul capteur, comme le firmware).

**3. (E) Panneau « Obstacle » clarifié.** Ajout d'une ligne d'aide dans le
panneau : le curseur place le **centre d'une plaque de 10 mm mesuré depuis
l'axe des roues au RESET** (si le robot roule, la mesure s'en écarte), et en
**PAUSE** la télémétrie est figée (le capteur ne tique qu'en marche) alors que
le faisceau suit le curseur.

**4. (F-b) Seuil d'écho réel ≈ 155 cm — reproduit, pas seulement documenté.**
Dans le core ESP32, le timeout de `pulseIn` court depuis l'appel, attente du
front montant d'ECHO incluse (~450–500 µs après TRIG — à quoi sert la marge
de 800 µs du firmware). `ultrason.js` modélise désormais ce délai
(`ECHO_DELAI_FRONT_US = 480`, milieu de la plage) : l'écho revient si
`dist×58 + 480 ≤ 9500 µs`, soit un seuil à **155,5 cm** comme le vrai robot.
Le selfcheck borne le seuil : 155 cm = écho hors portée sans échec, 156 cm =
échec compté.

**5. (F-f) Trous de l'auto-test comblés** (section 5 : 16 → 20 contrôles) :
vitesse de pan mesurée (90 → 120° en 1 s de balayage), vitesse de tilt
(60 → 75° en 0,5 s), bornes du tilt en balayage (20…90°), `angleVu` testé à
un pan ≠ 90° (alerte pendant le balayage → 96°, pas le centre). Contre-épreuve
par mutation : `PAN_SPEED 30→60` ✘ détecté (2 contrôles), `HEAD_TILT_MIN 20→0`
✘ détecté, `ECHO_DELAI_FRONT_US 480→0` ✘ détecté.

**6. Libellé** : « moyenne re-amorcée à 50 » → « moyenne amorcée à 50 (premier
écho reçu) » — le capteur n'avait jamais reçu d'écho dans ce scénario.

**7. Commentaire du faisceau** : le « demi-angle ~7° » était faux
(`ConeGeometry(0.0122, 1)` = 0,7° à 1 m, et seul `scale.x` varie). Le
commentaire dit désormais la vérité : rayon constant 12,2 mm, demi-angle
apparent dépendant de la longueur — un pointeur visuel, pas le lobe réel
(~15°) du HC-SR04.

**8. Pas de collision** : écrit dans `docs/GUIDE-SIMULATEUR.md` §8 (« Ce que le
simulateur ne fait pas ») — le robot peut traverser l'obstacle, comme le
firmware qui ne réagit pas.

**Validation finale** : bundle régénéré (`emballer_simulateur.py` →
`sim/web/simulateur-balancebot.html`, 1 426 820 octets, 6 fichiers inlinés,
0 `<script src=` résiduel) et copié sur `simulateur.html` à la racine
(`cmp` identique). `node sim/web/selfcheck.js` → exit 0, sections 1–4
inchangées, section 5 (extraits) :

```
  ✔ 155 cm : écho reçu mais hors portée (obstacleCm = −1, pas d'échec)
  ✔ 156 cm : au-delà du seuil réel (9528 > 9500 µs) → échec compté
  ✔ 170 cm : au-delà du timeout pulseIn (10340 > 9500 µs) → échec compté
  ✔ balayage hors équilibre : tilt borné à 20…90° (vu 20…90)
  ✔ vitesse de pan 30°/s : 90 → 120° après 1 s de balayage (attendu 120)
  ✔ vitesse de tilt 30°/s : 60 → 75° après 0,5 s de balayage (attendu 75)
  ✔ alerte pendant le balayage : angle vu = pan courant (96°, ≠ 90°)
═══ AUTO-TEST RÉUSSI ═══
```

(même verdict « AUTO-TEST RÉUSSI » sous Chrome headless en `file://` ; rendu
du bundle vérifié par capture : un seul module à deux transducteurs au-dessus
de l'écran, comme la photo.)

---

**Post-scriptum (miroir du firmware `10044c0`, 18/09/2026)** — ce rapport décrit l'état
au commit `2911095` : les numéros de lignes de `head.cpp` cités ci-dessus sont ceux d'AVANT
`10044c0` (décalés d'environ +100 depuis : `kEchoTimeoutUs` l.134 → 232, cadence l.108 →
203, `handleHeadMovement` l.181-217 → 284-333), et les deux phrases « équilibre → tête
ramenée au centre, immobile » et « comme le firmware, il ne déclenche aucune réaction
physique » ne sont plus vraies : la tête balaie ±30° en équilibre et le firmware évite
l'obstacle (ralenti / recul + pivot / reprise). Le simulateur en est le miroir — voir
`SIM_MIROIR_RAPPORT.md`, `docs/GUIDE-SIMULATEUR.md` §5 bis et `sim/web/selfcheck.js` §6-8.
