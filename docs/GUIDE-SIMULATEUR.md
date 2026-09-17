# Guide du simulateur

Ce simulateur rejoue **la même physique et le même correcteur que le robot**, mais il
existe surtout pour une chose : **pouvoir régler, casser et comprendre sans risquer le
robot**. La règle du projet est simple, et elle vaut pour tout ce qui suit :

> **Le simulateur et le firmware doivent dire la même chose.** Toute divergence est un bug
> des deux côtés à la fois.

Deux façons de l'ouvrir — aucune installation, aucun serveur :

- **en ligne** : <https://silexperience210.github.io/balance-bot/simulateur.html>
- **en local** : télécharge `simulateur.html` et ouvre-le par double-clic (tout est dans le
  fichier : le moteur, les vraies pièces 3D, le visage).

---

## 1. La vue 3D

| Geste | Effet |
|---|---|
| glisser | tourner autour du robot |
| molette | zoomer |
| clic droit | déplacer la vue |

Le robot, l'obstacle, le faisceau et les capteurs sont des modèles **des vraies pièces**
(`chassis/v3/`). Les coques sont à la couleur du produit.

## 2. Faire tourner la simulation

- **`RUN`** lance ou reprend, **`PAUSE`** arrête sur place, **`RESET`** remet le scénario à
  son état initial.
- **Vitesse de lecture** : `0,5×` · `1×` · `2×`. Mets **0,5× pour regarder une chute** :
  c'est là qu'on voit *pourquoi* le robot tombe, pas seulement qu'il tombe.
- **Scénarios** : `θ0=2° propre` (départ penché de 2°, sans bruit), `θ0=2° bruit`,
  `θ0=5° bruit` (avec le bruit du capteur réel), et trois `tape 0,4 / 0,8 / 1,2 rad/s`
  (une poussée franche, à un instant donné — la façon la plus parlante de tester la
  robustesse).
- La bannière en haut de la scène donne le verdict en direct : **ÉQUILIBRE OK**, chute,
  ou dépassement.

## 3. Les gains

- **Jeu de gains** : deux préréglages.
  - `jeu qui TIENT (5/6 · Kv=0)` — le robot reste debout dans 5 scénarios sur 6. **C'est le
    réglage par défaut.**
  - `gains EMBARQUÉS (il tombe)` — exactement ce qui est flashé dans le robot aujourd'hui,
    qui ne tient pas encore. Utile pour voir l'écart à combler.
- **Les cinq curseurs** : `Kp` (proportionnel — la raideur), `Ki` (intégral — rattrape la
  dérive lente ; c'est lui qui manque quand le robot s'incline doucement), `Kd`
  (dérivé — amortit), `Kpφ` et `Kv` (la cascade interne de vitesse).
- Repère utile : la condition de stabilité demande **Ki > g/R ≈ 300**. Un `Ki` trop faible
  est *l'erreur classique* : le robot paraît tenir puis se couche lentement, sans que rien
  ne l'ait poussé.

## 4. Le visage

`auto — suit l'état simulé` laisse le visage exprimer ce que fait vraiment le robot
(équilibre, chute, batterie faible). Les autres entrées forcent une expression : `calme`,
`penché`, `méfiant`, `énervé`, `surpris`, `content`, `chute`. C'est le même dessin que
l'écran du robot (table `faceStyle()` du firmware).

## 5. Le capteur à ultrasons

Le robot a un **HC-SR04** ; le simulateur le reproduit **au comportement près**, y compris
ses défauts :

- **Obstacle** : un curseur de **5 à 200 cm** place une plaque devant le robot. Le chiffre
  affiché est la position du **centre** de la plaque depuis l'axe des roues ; la distance
  mesurée, elle, part de la **sonde** (≈ 4 cm plus en avant). Une lecture plus petite que le
  curseur est donc **normale**.
- **`ECHO câblé`** : décoche-la pour simuler un capteur **absent ou mal câblé**. C'est
  exactement ce qui arrive sur un vrai montage quand la ligne ECHO n'est pas branchée.
- **Le faisceau** : 🟢 obstacle vu · 🔴 **alerte** (moins de 25 cm) · gris discret : rien
  dans la portée.
- **Télémétrie** : distance lissée, état, **cadence de mesure** (200 ms ; elle passe à
  **1 s après trois échecs consécutifs** — sur le vrai robot la mesure bloque le
  processeur, on l'espace donc quand il n'y a rien à voir), échecs consécutifs, position de
  la tête, et l'angle sous lequel l'obstacle a été vu.

**Ce que le capteur ne fait pas** : le firmware ne réagit pas physiquement à un obstacle —
il publie la distance et l'alerte, c'est tout. Le simulateur fait **pareil** : il ne freine
pas le robot tout seul, ce serait inventer un comportement que le robot n'a pas.

## 6. Les animations

Un sélecteur avec `Aucune`, `Hochement`, `Regard gauche-droite`, `Sursaut` (un coup,
relançable), `Danse`, plus **`Rejouer`**. Ce sont des animations **cosmétiques** : elles
jouent sur l'image, jamais sur la physique. Le robot continue de tenir exactement comme
avant, et `Aucune` redonne l'image strictement identique. C'est volontaire : on veut
pouvoir filmer le robot sans fausser la moindre mesure.

## 7. Donner des fonctions au robot (le moteur d'effets)

C'est la partie puissante. En bas de page, l'éditeur **« EFFETS SECONDAIRES (HOOK
MOTEUR) »** accepte du JavaScript, que tu appliques avec **`Appliquer`**. Ta fonction est
appelée **200 fois par seconde**, **après** la physique de chaque pas :

```javascript
function customEffects(t, state, dt) {
  // t  : temps simulé en secondes
  // dt : pas de temps (0,005 s à 200 Hz)
  // state : l'état du robot, EN DEGRÉS
}
```

### Ce que tu peux modifier et lire

| Écriture (ça agit) | Lecture seule (ça informe) |
|---|---|
| `theta`, `thetaDot` (assiette et sa vitesse) | `t` (temps simulé) |
| `phi`, `phiDot`, `phiCmd` (roue : position, vitesse, consigne) | `pidOut` (sortie du correcteur) |
| `integ` (terme intégral) | `setpoint`, `footVelCmd` (cascade interne) |
| `pitchFilt`, `rateFilt` (mesures **filtrées** — c'est ce que voit le correcteur) | `noise`, `verdict`, `fallen`, `panicked`, `done`, `k`, `tmax` |
| `recenterVel`, `footVelFilt` | |

Écrire dans `pitchFilt` plutôt que dans `theta` simule un **défaut de capteur**, pas une
poussée : le correcteur croit alors à une inclinaison qui n'existe pas — c'est ainsi qu'on
teste une panne de mesure.

### Exemples prêts à coller

Les valeurs indiquées après la flèche sont **mesurées dans le simulateur**, sur le scénario
`θ0=2° propre` avec le jeu de gains qui tient — pas des estimations.

```javascript
// 1. Vent constant : pousse le corps en continu
//    → tient à 10 °/s² ; tombe à 3,1 s à 30, à 1,8 s à 60, à 1,1 s à 120
function customEffects(t, state, dt) { state.thetaDot += 10 * dt; }

// 2. Sol glissant : amortit l'oscillation — il tient mieux, pas moins bien
function customEffects(t, state, dt) { state.thetaDot *= (1 - 0.5 * dt); }

// 3. Capteur qui dérive de +0,5° : le correcteur se bat contre un fantôme
//    → CHUTE en ~1,2 s. C'est l'exemple le plus parlant : une erreur de mesure
//      tue le robot aussi sûrement qu'une poussée.
function customEffects(t, state, dt) { state.pitchFilt += 0.5; }

// 4. Tape à t = 2 s (une impulsion, une seule)
//    → encaisse 25 °/s sans broncher ; tombe à 60 °/s (2,8 s) et 120 °/s (2,3 s)
function customEffects(t, state, dt) {
  if (t >= 2 && t < 2 + dt) state.thetaDot += 25;   // °/s
}

// 5. Sol en pente : le robot est incliné en permanence
//    → tient à 3 °/s ; monte la valeur pour trouver le décrochage
function customEffects(t, state, dt) { state.theta += 3 * dt; }

// 6. Servo paresseux : la roue ne suit la consigne qu'à moitié
//    → CHUTE en ~0,5 s : le robot perd son autorité de correction
function customEffects(t, state, dt) { state.phiDot *= 0.5; }
```

### Les garde-fous

- Le cœur physique **n'est pas modifiable** : le hook est la **seule porte d'injection**.
  Tu ne peux donc pas « tricher » — ni sur le modèle du robot, ni sur le correcteur.
- Une faute de syntaxe s'affiche **sous l'éditeur**, sans planter la page.
- **`Réinitialiser le code`** enlève ton effet et remet le modèle nominal.
- Pour comparer proprement : lance un scénario **sans** effet, note le verdict, applique
  l'effet, relance le **même scénario**. C'est comme ça qu'on découvre qu'un réglage est
  fragile.

## 8. Ce que le simulateur ne fait pas

Autant le dire franchement, pour ne pas se fier à une simulation au-delà de ce qu'elle
vaut :

- **la tête pan/tilt n'est pas visible** : le châssis n'a pas de tête séparée (c'est le
  corps entier), donc l'orientation de la tête est simulée et affichée, mais pas montrée
  en 3D ;
- le simulateur reproduit la **cadence** des mesures, mais pas le **temps processeur volé**
  par la mesure ultrason (sur le robot, la mesure bloque la boucle d'équilibre jusqu'à
  9,5 ms) ;
- la mesure de distance est **horizontale** : un obstacle très bas ou très haut ne serait
  pas distingué ;
- **pas de collision** : le robot peut traverser l'obstacle et rouler au-delà — le firmware
  ne réagit pas à l'obstacle (il publie la distance et l'alerte, c'est tout), le simulateur
  fait pareil. La distance devient simplement négative (−1, « pas d'écho ») une fois la
  plaque dépassée ;
- après une chute, la simulation **s'arrête** (elle ne rejoue pas le robot à terre) ;
- les frottements, le jeu mécanique, la souplesse des servos et l'usure **ne sont pas
  modélisés** : si le robot réel se comporte moins bien que la simulation, cherche d'abord
  de ce côté.

---

*Ce guide décrit le simulateur du dépôt. Si tu changes une constante du firmware
(`balance-bot/config.h`), répercute-la ici **et** dans `sim/web/ultrason.js` : c'est la
règle d'or.*
