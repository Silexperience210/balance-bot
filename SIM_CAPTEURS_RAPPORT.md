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
- **Modules HC-SR04 en 3D** : pièces achetées, pas de STL → modélisation
  Three.js : PCB bleu 45 × 20 × 2 mm + deux transducteurs Ø16 × 12 mm avec
  grille avant. Deux modules symétriques (z = ±26 mm) sur la face avant, partie
  haute du ₿ (y = +98 mm au-dessus de l'axe), plaqués sur la coque (x = 23 mm,
  face avant mesurée sur `parts.js`). Ajoutés à `groupeCorps` → ils suivent
  exactement les transformations du corps.
- **Sonde logique** : le firmware n'a qu'UN HC-SR04 (`config.h:61-62`) ; la
  mesure part du milieu des deux modules, à la face avant des transducteurs.
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
- **Un seul capteur logique** (comme le firmware, `config.h:61-62`) alors que
  deux modules sont modélisés visuellement : la mesure part du milieu des deux.
- Le blocage de `pulseIn` (jusqu'à 9,5 ms volés à la boucle d'équilibre) n'est
  **pas** répercuté sur la physique — ce serait modifier le moteur, interdit
  par la mission ; seule la cadence des mesures est reproduite.

## Fichiers modifiés

- `sim/web/ultrason.js` — **nouveau** (capteur HC-SR04 + tête, miroir de `head.cpp`)
- `sim/web/ui.js` — modules 3D, sonde, faisceau, obstacle, animations, télémétrie capteur
- `sim/web/index.html` — panneaux « Capteur ultrason » et « Animations », script `ultrason.js`
- `sim/web/selfcheck.js` — section 5 (16 contrôles ultrason/tête), sections 1–4 inchangées
- `sim/web/selfcheck.html` — chargement d'`ultrason.js`
- `chassis/assets/emballer_simulateur.py` — `ultrason.js` ajouté à l'ordre d'inlining
- `sim/web/simulateur-balancebot.html` — régénéré (bundle mono-fichier)
- `simulateur.html` (racine) — copie du bundle régénéré
