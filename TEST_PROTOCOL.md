# BalanceBot — Protocole de test réel (premier essai debout)

Firmware : commit 87758d0 (Lot 1 bugs + Lot 2 feet.cpp + Lot 2b gains
sim-validés Kp25/Ki500/Kd0.5). À faire dans l'ordre, SANS brûler d'étapes.

## Prérequis matériel

- [ ] T-Display S3 Touch flashé (./build.sh) branché en USB
- [ ] **Alimentation séparée 5-6V pour les servos** (Lot 3) : les servos ne
      doivent JAMAIS tirer sur le 3V3/5V de la carte → brownout → reboot.
      Minimum : power bank 5V + GND commun. Même pour un seul servo.
- [ ] 2× SG90 + 2× foot_arc imprimés, palonnier calé (FIT_NOTES §9)
- [ ] MPU6050 monté sur son piédestal (fils fixes, plus de duponts volants)
- [ ] Table lisse, dégagée, ~1 m² — et un matelas/oreiller derrière le robot
      pour les premières chutes (elles arriveront)

## Étapes (chacune validée avant la suivante)

### 1. Boot et neutre (sans équilibre)
Brancher. Écran : « BALANCEBOT », pitch qui VIT, « USB » en batterie,
`P:` affiche l'angle pied (0 au repos).
**Vérifier** : les 2 pieds sont au neutre — milieu de l'arc pile sous l'axe,
robot visuellement droit. Si décalé : caler le palonnier (4 positions à 90°)
puis trims `kTrimDegL/R` dans feet.cpp.

### 2. Mode démo (flèches de l'UI, équilibre OFF)
Toucher AVANT/ARRIÈRE : les pieds roulent doucement ±15° max. GAUCHE/DROITE :
différentiel. **Vérifier** : les 2 pieds bougent en miroir dans le bon sens.
Si un pied part à l'envers : inverser `kDirL` ou `kDirR` (feet.cpp) — ou
tourner le palonnier de 180° (plus simple).

### 3. Signe du câblage (CRITIQUE — à faire robot tenu, couché ou sur son dos)
Poser le robot sur le dos (pieds en l'air, libres). Activer EQUIL. Incliner
le corps vers l'avant de ~10° à la main :
- **Bon signe** : les pieds partent VERS L'AVANT (pour rattraper la chute)
- **Mauvais signe** : les pieds partent en arrière → couper STOP immédiatement,
  inverser le signe (voir note ci-dessous)
Note : « avant » = le sens où le haut du robot penche. Si mauvais signe,
corriger par UN SEUL patch : `kAccelPitchSign` dans imu.cpp (section RÉGLAGE
MÉCANIQUE, ligne ~46) — +1 → −1 (ou l'inverse). C'est le correctif global
(équivalent à inverser kDirL ET kDirR, mais en 1 constante). Ne pas toucher
aux servos si le signe est le même sur les deux pieds.

### 4. Équilibre tenu (robot maintenu)
Tenir le robot droit à la main (pieds au sol), activer EQUIL. Sentir les
pieds qui « vivent » sous les doigts (micro-ajustements). Incliner
doucement de ±5° : le robot doit pousser pour se redresser. Relâcher
progressivement en gardant les mains prêtes à rattraper.
- Oscillation rapide (buzz) → Kd trop faible OU Kp trop fort
- Mou mou / tombe lentement → Kp/Ki trop faibles
- Chute d'un côté constant → neutre décalé (trims) ou signe

### 5. Pose libre (premier lâcher)
Le robot tenu droit, le poser, attendre qu'il soit stable 1-2 s (le pitch
doit être ~0), puis lâcher doucement en retirant les mains vers le bas.
S'il part en avant ou en arrière : il « court » — c'est le récentrage qui
doit le ramener (max 0.4° de trim — si ça ne suffit pas, c'est le sujet du
prochain réglage, PAS un bug).

## Réglages rapides (constantes, balance.cpp)
| Symptôme | Constante |
|---|---|
| Buzz / oscillation rapide | ↓ kKp (25→15), ↑ kKd (0.5→1.0) |
| Tombe mollement | ↑ kKp (25→40), ↑ kKi (500→700) |
| Dérive avant/arrière constante | kTrimDegL/R (feet.cpp) ou neutre palonnier |
| Recentrage trop lent | ↑ kRecenterTrimMax (0.4→0.8), ↑ kRecenterRateDegS |
| Robot complet (tête + mât montés, CoM > 100 mm) | Essayer Kp 40, Ki 600, Kd 1.5 (sim : gains v1 tiennent h ≤ 100 mm) |

## Limites connues (à ne pas prendre pour des bugs)
- Course du pied ±45° → une grosse tape fait « courir » le robot puis
  tomber (physique, pas un défaut de gains)
- Le recentrage est volontairement TRÈS doux pour le premier test
- 200 Hz de boucle, mais le SG90 ne prend une consigne que toutes les 20 ms
- Sans alim séparée, les servos font rebooter la carte (brownout)
