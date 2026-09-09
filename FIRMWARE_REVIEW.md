# Review firmware BalanceBot — 09/09/2026

Périmètre : les 14 fichiers du sketch (`balance-bot/`, ~2 300 lignes) — `balance.cpp`,
`feet.cpp`, `imu.cpp`, `head.cpp`, `ui.cpp`, `tuner.cpp`, `battery.cpp`, le `.ino`,
`config.h`, `interfaces.h` et les en-têtes privés. Méthode : lecture intégrale, comparaison
avec le modèle validé en simulation (`sim/balancebot_sim.py`), puis **compile vérifiée**
(`arduino-cli`, FQBN/flags de `build.sh`) après correction — 78 % flash, 15 % RAM, 0 warning.

> La loi de commande n'a qu'UNE modification : le **signe de la cascade de
> recentrage** (faute n°12), démontré faux en simulation — le reste (PID, soft
> clamp, bornes, dt) est inchangé. Aucune re-simulation du PID n'est nécessaire
> pour les autres correctifs (garde-fous et précision de mesure uniquement).

---

## 1. Fautes corrigées (commit « review firmware »)

| # | Fichier | Faute | Correction |
|---|---|---|---|
| 1 | `config.h`, `feet.cpp`, `balance.cpp` | Butée dure des pieds recopiée en littéral `45.0f` dans **deux** fichiers : le soft clamp et la butée réelle peuvent diverger silencieusement (classe de bug déjà vue sur le châssis). | `#define FOOT_HARD_DEG 45.0f` dans `config.h`, source unique lue par les deux. |
| 2 | `balance.cpp` | **IMU muet non détecté** : `Imu::update()` était appelé en ignorant son retour. Bus I2C secoué (duponts volants) → l'angle se fige et le robot asservit sur une mesure morte jusqu'à la chute. | Compteur de trames perdues ; au-delà de 20 consécutives (~100 ms à 200 Hz) → `halt()`. Reprise automatique dès qu'une trame repasse (`s_imuLost`). |
| 3 | `balance.cpp` | **Servos de pieds non attachés** : `Feet::begin()` n'était pas vérifié. Servos absents → φ reste à 0, le robot « équilibre » des pieds morts. | Garde `if (!Feet::ready()) { halt(); return; }` avant toute logique d'asservissement. |
| 4 | `balance.cpp` | **Armement sur consigne héritée** : un doigt resté sur une flèche pendant que l'équilibre était coupé repartait à 100 à l'armement → bond du robot. | `setEnabled(true)` remet `cmdForward`/`cmdTurn` à zéro. |
| 5 | `battery.cpp` | **ADC brut non calibré** : `analogRead()` remis à l'échelle linéairement → 10-20 % d'erreur (le seuil 3,5 V n'a plus de sens). | `analogReadMilliVolts()` (courbe eFuse du S3). |
| 6 | `tuner.cpp` | **POST tronqué = gain à 0** : `arg().toFloat()` renvoie 0 pour `kp=` ou `kp=abc`, et `setGains()` recevait ce 0 → perte du terme P en pleine session de réglage. | Parsing strict `strtof` + vérification de fin de chaîne ; non numérique → `NAN` (gain inchangé). |
| 7 | `imu.cpp` | **Détection capteur incomplète** : le premier ACK sur 0x68 suffisait ; un autre esclave à cette adresse faisait échouer `WHO_AM_I` **sans essayer 0x69**. | Chaque adresse est testée complètement (présence **et** identité) avant d'abandonner. |
| 8 | `head.cpp` | **Ultrason bloquant 12 ms** (2,4 cycles de la boucle 200 Hz) pour une portée utile de 150 cm. | Timeout calculé depuis `US_MAX_CM` (8,7 ms + marge) — moins de temps volé à l'équilibre. |
| 9 | `head.cpp` | **Servos de tête réécrits 50×/s** à position identique → vibration/ronronnement SG90 pour rien. | Écriture uniquement au changement de position. |
| 10 | `ui.cpp` | **Touch en panne = écran mort** : `Ui::begin()` retournait `false` et `Ui::loop()` sortait, plus aucune télémétrie. | L'écran reste actif (télémétrie), les boutons sont inertes, bandeau rouge « TOUCH KO », statut sur le port série. |
| 11 | `.ino`, `config.h`, `feet.cpp`, `ui.cpp` | Commentaires périmés : « 4× SG90 (2 rotatifs roues…) », renvoi à `chassis/FIT_NOTES.md` (purgé), « ancien wheels.cpp », « roues au neutre ». | Réécrits (pieds en arc v3.1, `NOTES_v3.md`). |
| 12 | `balance.cpp` | **Signe de la cascade de recentrage inversé** : pour un pied parti en avant (φ > 0), la contribution au setpoint était négative, donc le PID commandait le pied… **vers l'avant** : le pied filait vers la butée au lieu de revenir (simulation : pied lâché à +20° → +37° en 0,3 s, puis panic). | Contribution inversée (`-kRecenterKv·(v_cible − φ̇)`), dérivation et preuve en commentaire. Les gains de la cascade restent à régler sur le robot (tuner). |
| 13 | `sim/balancebot_sim.py` | **Le simulateur ne modélisait pas le firmware** : ni cascade de recentrage, ni roulement exact (`ẍ = R·φ̈` au lieu de `R·(θ̈+φ̈)`), plus un amortissement artificiel `-0,5·θ̇`, et sa docstring affirmait des gains « validés » que son propre code invalide (0/6 scénarios). | Modèle physique exact, cascade portée à l'identique, docstring remplacée par l'état MESURÉ + mode `--sweep` / `--no-cascade`. |

## 1bis. Le point le plus important : la validation de la loi de commande ne tient plus

Ce n'est pas une ligne de code mais l'état du projet, et c'est ce qui doit guider le premier
test réel :

1. `sim/balancebot_sim.py` **n'a jamais modélisé la cascade de recentrage** (lot 2c) — son
   contrôleur était le PID seul. Le script qui avait « validé » la cascade n'est pas dans le
   dépôt (seul `sim/cascade_recenter.md`, sa docstring, a été committé) : ce résultat n'est
   pas rejouable.
2. Le modèle physique du sim était faux sur deux points (déjà identifiés dans le message du
   commit 19535f7, jamais corrigés dans le fichier) : unité °/rad (facteur 57 sur l'autorité
   de commande) et roulement incomplet `ẍ = R·φ̈` au lieu de `ẍ = R·(θ̈+φ̈)`. S'y ajoutait un
   amortissement artificiel `-0,5·θ̇` (optimiste).
3. Conséquence mesurée avec le simulateur corrigé (09/09) : **les gains embarqués
   Kp25/Ki500/Kd0.5 ne tiennent AUCUN des 6 scénarios** (0/6), avec ou sans cascade, et un
   balayage de 280 jeux (Kp 0,5→100 · Ki 350→2000 · Kd 0,2→20) n'en trouve **aucun** qui
   tienne. Mode d'échec : le pied consomme ses ±45° de course puis le robot tombe.
4. Ce que ça NE veut pas dire : que le robot ne peut pas tenir (le modèle 1D reste une
   idéalisation, sans friction ni borne d'accélération servo). Ce que ça veut dire : **le jeu
   de gains actuel n'est pas justifié par une simulation rejouable**, et le réglage réel via
   le banc web (`BalanceBot-Tune`) n'est pas une option mais une étape obligatoire — ce que le
   commit 19535f7 disait déjà.

Recommandation : après le premier test réel (signe, neutre, tenu à la main), régler
Kp/Ki/Kd au banc web en partant de valeurs volontairement basses, et **ne pas se fier** aux
valeurs « validées » de la docstring d'origine (supprimées).

## 2. Points contrôlés et jugés CORRECTS (pas de changement)

- **Signe de contre-réaction** : `out = -pid.update(...)` avec dérivée sur le gyro — identique
  au simulateur (`u = -self.ctrl()`), et l'inversion est faite **avant** le soft clamp et
  l'estimateur φ̇, comme l'exige la suite de la chaîne.
- **Anti-windup conditionnel**, bornes `kIntegralMax`/`kOutMax`, mort-zone d'erreur : conformes
  au modèle validé (Kp 25 / Ki 500 / Kd 0.5).
- **Soft clamp** `limit = min(45, 90 − |θ| − 9)` et rampe sur 10° : même formule que la sim.
- **Cascade de recentrage** : boucle externe 10 Hz bornée ±20 °/s avec rampe 3 °/s², boucle
  interne ±6° sur θ_ref, estimateur φ̇ 1er ordre 80 ms pris **après** le clamp et **avant** le
  différentiel — structure conforme à `sim/cascade_recenter.md`. **Le SIGNE de la boucle
  interne était faux** (voir faute n°12) : corrigé.
- **dt** bornés (0,5–50 ms) dans `balance.cpp` **et** `feet.cpp`, rollover `micros()` géré par
  arithmétique non signée.
- **Miroir des servos** (`kDirL=-1`, `kDirR=+1`) et neutre 1500 µs / 90° : cohérents avec le
  montage décrit ; `attach()` testé via `attached()` (canal 0 valide).
- **Partage I2C touch + MPU** : UI cadencée à 60 Hz, timeout Wire 2 ms, `setClock(400 kHz)` —
  la stratégie annoncée est bien celle appliquée.
- **Fusion complémentaire** : α = 0,98 à 200 Hz (τ ≈ 0,25 s), recalage accel refusé hors
  [0,8–1,2] g (choc/démarrage) — correct et prudent.
- **Écran 170×320 / rotation 3 + touch rotation 1 / CGRAM_OFFSET** : conforme au `build.sh`.
- **Réglage à chaud** : float 32 bits alignés, lectures/écritures atomiques sur Xtensa — le
  commentaire de `balance.cpp` est exact (pas de `volatile` nécessaire).

## 3. Limites connues, NON corrigées (volontaire)

1. **`pulseIn()` reste bloquant** (≤ 9 ms). Correction propre = driver HC-SR04 non bloquant
   (interruption sur ECHO + `micros()`), ou mesure déportée sur le second cœur. Chantier
   séparé, à faire avec un test réel.
2. **`WebServer::handleClient()` peut bloquer jusqu'à ~5 s** sur un client TCP qui n'envoie
   rien (constantes `HTTP_MAX_*_WAIT` de la lib). Le garde-fou du `.ino` (servir seulement si
   équilibre OFF ou > 100 ms depuis la dernière requête) réduit l'exposition mais ne l'annule
   pas → voir suggestion n°1.
3. **Mode CONTINU sans encodeur** : φ est une intégrale de la consigne, donc une *estimation*
   (documenté). En continu, la butée n'est qu'une convention — c'est structurel, pas un bug.
4. **Gains non persistés** : un reset perd le réglage (voir suggestion n°3).

## 4. Suggestions d'amélioration (classées)

### Sécurité / robustesse (par ordre d'impact)

1. **Déporter le banc web sur une tâche dédiée (cœur 0).** `xTaskCreatePinnedToCore()` qui
   boucle `handleClient()` avec 5-10 ms de pause. La boucle d'équilibre ne peut plus être
   gelée par un client TCP qui traîne. Prévoir une petite discipline de concurrence :
   les gains (`float` alignés) sont atomiques ; pour `setEnabled()` depuis la tâche web,
   passer par un drapeau `volatile bool` consommé par la boucle d'équilibre (évite deux
   writers sur les mêmes canaux LEDC).
2. **Sortir `Balance::loop()` de `loop()`** : tâche FreeRTOS priorité haute (ou `esp_timer`
   périodique) à 200 Hz. Aujourd'hui, l'affichage SPI (TFT), le touch I2C et le web
   s'exécutent dans le même fil : tout dépassement décale directement l'asservissement.
3. **Watchdog de cadence** : si `g_state.balanceHz < 120` pendant > 200 ms → `halt()`. La
   mesure existe déjà (affichée à l'écran) mais n'agit pas.
4. **Refus d'armer sur batterie faible** : `BAT_LOW_V` (3,5 V) = cellule à ~10 % ; l'appel de
   courant des 4 SG90 fait s'effondrer la tension → brownout/reboot en pleine correction.
   Bloquer l'armement (ou avertir) quand `g_state.batteryLow`.
5. **Persister les gains en NVS** (`Preferences`) : chargement au boot, écriture à chaque POST
   `/api/gains`. Évite de tout reperdre à chaque flash/reset.
6. **AP de réglage à la demande** : un appui long sur le bouton BOOT (GPIO0) ouvre/ferme l'AP.
   Moins de radio au repos, moins de surface d'attaque (le réseau est ouvert, documenté comme
   tel) — et possibilité d'ajouter un WPA2 fixe affiché à l'écran.

### Qualité de mesure

7. **Recalibration gyro à chaud** : refaire `Imu::calibrate()` dès que |rate| < 1 °/s et
   |pitch| < 1° pendant ~2 s (robot posé, équilibre OFF). Le biais gyro dérive avec la
   température et n'est mesuré qu'au boot.
8. **Filtre Kalman / Madgwick** au lieu du complémentaire : gain de précision en dynamique,
   utile si vous ajoutez des accélérations franches (marche avec encodeurs).
9. **Anti-vibration mécanique** : mousse/entretoise souple sous le MPU6050 — le DLPF 42 Hz
   ne suffit pas quand les servos claquent.

### Fonctionnel

10. **Évitement d'obstacle réel** : aujourd'hui `obstacleWarn` coupe juste la marche avant.
    Le suivi de l'angle où l'obstacle a été vu existe déjà (`obstacleSeenAngle`) : ajouter un
    cap de contournement + un arrêt moteurs si l'obstacle est sous `US_STOP_CM`.
11. **Mode « recherche de verticale »** après une chute : faire tourner doucement un pied pour
    retrouver un appui connu (le mode continu le permet sans butée).
12. **Télémétrie enregistrée** : buffer circulaire de (θ, φ, gains, Hz) en RAM, dump sur le
    port série ou en JSON via `/api/log`. Indispensable pour régler autrement qu'à l'œil.
13. **OTA (ArduinoOTA)** : reflasher sans câble, une fois le robot monté (le port USB devient
    difficile d'accès avec le châssis ₿).
14. **Bouton d'arrêt physique** : le bouton 2 (GPIO14) est libre — le câbler en coupure
    matérielle de l'alimentation servo (relais/MOSFET) est le seul vrai « kill switch ».

### Dette technique

15. **Tests unitaires du contrôleur** : extraire le PID/clamp dans un header pur C++ sans
    dépendance Arduino, compilable et testable sur PC (le simulateur deviendrait un vrai test
    de non-régression de la loi de commande, plus une copie manuelle).
16. **`interfaces.h` à re-geler** : il décrit encore « mécanique v2 » et un `Battery::begin()`
    sans atténuation. Une passe de mise à jour après stabilisation du contrat.
