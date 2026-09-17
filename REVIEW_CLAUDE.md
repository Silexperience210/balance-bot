# Confrontation — revue adversaire du firmware BalanceBot (Claude, 17/09/2026)

Cible : état du dépôt après le commit `2433f4e` (revue Kimi K3 + corrections Hermes).
Périmètre : `balance-bot/` (14 fichiers, lus intégralement) + `sim/balancebot_sim.py`.
Méthode : lecture ligne à ligne, **ré-exécution du simulateur** (version courante ET
version d'avant `2433f4e`, extraite par `git show`, exécutée depuis stdin — aucun fichier du
dépôt modifié), analyse linéaire du modèle (pôles), dérivation de Lagrange pour la physique,
lecture du `sdkconfig` du core ESP32 3.3.11 pour la question NVS.

Sévérités : **bloquant** / **important** / mineur / cosmétique.

Bilan chiffré : **6 désaccords** avec `REVIEW_KIMI.md` (dont 2 affirmations « vérifié sain »
fausses et 1 « conséquence mesurée » non reproductible), **17 trouvailles nouvelles**
(§4, M1-M19 hors M12/M13 qui prolongent des points de Kimi), dont **8 classées importantes**
— 4 sur la loi de commande / la sécurité du firmware (M1, M3, M6, M8), 2 sur la stratégie
de réglage (M10, M11), 2 sur le simulateur (M2, M4). Verdict en §6 ; **application des
corrections** (état par point, compilation, sim AVANT/APRÈS) en §7.

---

## 1. Les 5 corrections de `REVIEW_KIMI.md`

### #1 — `ui.cpp:511` `FaceFrame s_lastFrame` supprimée
- Verdict : **d'accord**. `grep -rn s_lastFrame balance-bot/` → aucune occurrence restante ;
  la variable n'était lue nulle part. Sans risque (agrégat trivialement constructible, pas
  d'effet de bord à la construction).

### #2 — `balance.cpp:61-63` commentaire « validées en simulation » réécrit
- Verdict : **d'accord sur le fond, désaccord sur l'exécution** (cosmétique). Le nouveau texte
  est désormais **dupliqué** : les lignes 45-49 disaient déjà exactement la même chose (« Gains
  de DÉPART, NON validés par une simulation rejouable (voir FIRMWARE_REVIEW.md §1bis) »). Le
  correctif a remplacé une phrase fausse par une paraphrase de 3 lignes d'un paragraphe situé
  12 lignes plus haut. Il fallait supprimer la ligne, pas la réécrire.
- Plus grave, le même bloc de commentaires contient une **procédure de réglage inapplicable**
  (lignes 40-43) que ni Kimi ni Hermes n'ont relevée — voir §4 M8.

### #3 — `feet.cpp:4,13` `FIT_NOTES.md §9` → `NOTES_v3.md`
- Verdict : **d'accord, mais correction incomplète** (cosmétique). `chassis/NOTES_v3.md`
  existe bien. Restent deux renvois au fichier purgé hors firmware :
  `TEST_PROTOCOL.md:12` (« palonnier calé (FIT_NOTES §9) » — c'est la check-list que
  l'utilisateur suivra au premier test) et `README.md:19` (« châssis v2 : … FIT_NOTES »).

### #4 — `feet.h:5` « v2 » → « v3.1 »
- Verdict : **d'accord, mais correction incomplète** (cosmétique). Le même « v2 » subsiste
  dans **`balance.cpp:15`** (« MÉCANIQUE v2 : plus de roues ») et **`interfaces.h:61`**
  (« servos de POSITION (mécanique v2 — plus de roues) »). Un `grep -n "v2\b"` suffisait.

### #5 — `sim/balancebot_sim.py:135` fenêtre `±0.02` → `DT/2` (« tape ×7 »)
- Verdict sur le code : **d'accord**. Vérifié : avec `DT = 5 ms`, `abs(k·DT − 3) < 0.02`
  est vrai pour k ∈ {597…603} = **7 pas** (calcul exact reproduit), donc `dtheta += push_v`
  était appliqué 7 fois. Ce n'était pas un « étalement volontaire » : un étalement
  volontaire s'écrirait `push_v · dt/0.04` (indépendant du pas) ; ici l'impulsion totale
  dépendait de `dt_sim`, paramètre que `run()` acceptait à l'origine (`b8aa15f`) — c'est la
  signature d'un bug, pas d'un choix. Le libellé « tape 0,4 rad/s » désigne bien une
  impulsion de vitesse unique. Physiquement, 7 × 1,2 = 8,4 rad/s aurait été un coup de
  0,67 m/s au CoM — hors de propos pour un robot dont la base parcourt ±25 mm.
- Fragilité mineure du correctif : `< DT/2` ne déclenche **rien** si `push_t` tombe à un
  demi-pas (ex. 3,0025 s : les deux voisins sont à exactement DT/2, `<` est faux). Un
  drapeau « appliqué une fois dès que `t ≥ push_t` » serait robuste. Sans effet sur les
  scénarios actuels (push_t = 3 est un multiple de DT ; `600·DT == 3.0` exactement).
- **Désaccord sur la « conséquence mesurée »** (important pour la crédibilité de la revue) :
  `REVIEW_KIMI.md` affirme « les scénarios « tape » passent de `chute θ` à `panic φ`
  (θfin +46° → +27°) ». **C'est faux, et non reproductible** : la version d'avant
  correctif (`git show 2433f4e^:sim/balancebot_sim.py | python3 -`) et la version
  courante produisent une sortie **strictement identique** (0/6, mêmes θfin/φfin au dixième).
  Cause : **les six scénarios échouent entre t = 0,35 s et t = 0,55 s**, or la tape est
  appliquée à t = 3 s. **Aucune tape n'a jamais été appliquée** dans le simulateur corrigé —
  ni avant ni après `2433f4e`. Les trois scénarios « tape » sont, dans les faits, trois
  répétitions de « θ0 = 3°, bruit » qui tombent à 0,41 s. Le correctif est juste mais
  **sans effet**, et la vérification annoncée n'a pas eu lieu (ou a été faite sur un autre
  état du dépôt). Preuve : temps d'échec par scénario, version courante :

  ```
  θ0=2° propre     panic φ  t_échec=0.41s
  θ0=2° bruit      panic φ  t_échec=0.41s
  θ0=5° bruit      chute θ  t_échec=0.35s
  tape 0.4 rad/s   panic φ  t_échec=0.41s   (push à t=3 → jamais atteint)
  tape 0.8 rad/s   panic φ  t_échec=0.41s
  tape 1.2 rad/s   panic φ  t_échec=0.41s
  ```

---

## 2. Les 5 suggestions non implémentées

### #6 — `feet.cpp:177` `driveFootSpeed(int, int)` : quantification entière
- Verdict : **d'accord que c'est négligeable — je descendrais à cosmétique**. 1 °/s de pas
  à 200 Hz = 0,005°/cycle, soit 0,055 µs d'impulsion : l'arrondi `lroundf(us)` de
  `footToUs()` (1 µs ≈ 0,09°) absorbe ~18 cycles avant que la consigne servo ne bouge. La
  quantification entière est un ordre de grandeur sous la résolution du servo. Seule
  incohérence réelle : `updateFootVel(out·k)` (`balance.cpp:587`) filtre la valeur
  **non** quantifiée alors que `feet.cpp` intègre la valeur quantifiée — écart < 0,5 °/s,
  sans conséquence. Passer en `float` reste propre, mais ce n'est pas un bug.

### #7 — `balance.cpp:237-247` throttling NVS qui **saute** l'écriture
- Verdict : **d'accord, et je remonte la raison** (mineur → important-si-on-règle-en-équilibre).
  Le constat de perte de la dernière valeur est exact (`now − s_lastSaveMs < 1500 → return`
  sans drapeau dirty ; la page web envoie un POST par relâcher de slider, deux relâchers en
  < 1,5 s perdent le second). Ce qui a été manqué : **l'écriture NVS se fait depuis la tâche
  web (cœur 0) et stalle le cœur 1**. Vérifié dans
  `~/.arduino15/packages/esp32/tools/esp32s3-libs/3.3.11/sdkconfig` :
  `CONFIG_SPI_FLASH_AUTO_SUSPEND is not set` → toute écriture/effacement flash désactive le
  cache et **suspend l'autre cœur** (celui de `Balance::loop()`). `Preferences::putFloat` →
  `nvs_set_blob` + `nvs_commit` (5 fois par sauvegarde) : ~1-3 ms de stall par POST, et
  10-40 ms (effacement de page, découpé par `CONFIG_SPI_FLASH_YIELD_DURING_ERASE=y` en
  tranches de 10 ms) tous les ~50 POST. Ce n'est pas catastrophique, mais c'est un argument
  supplémentaire — et décisif — pour la solution que Kimi proposait : **drapeau dirty +
  écriture au désarmement uniquement** (jamais pendant `g_state.balancing`).

### #8 — `Tuner::toggle()` cœur 1 / `serverTask` cœur 0
- Verdict : **d'accord (mineur)**. `s_up` est un `bool` non-`volatile` lu dans une boucle
  qui appelle des fonctions opaques (`handleClient`, `vTaskDelay`) : le compilateur le relit,
  la course est bénigne. À ajouter : `stopRadio()` coupe la radio pendant qu'un
  `handleClient()` peut être en cours sur l'autre cœur (socket fermé sous lui — lwIP le
  tolère) ; et surtout `.ino:133` fait un **`Serial.printf` depuis `loop()` (cœur 1)** sur
  l'appui long, alors que `STALL_ANALYSIS.md §6` a établi qu'une écriture USB-CDC bloque
  quand l'hôte ne draine pas le port. Appui long BOOT en plein équilibre = risque de
  gel de la boucle. Mineur (geste volontaire), mais incohérent avec la règle du projet.

### #9 — `sim:70` `tau_f = 0.025` vs commentaire « 0,25 s »
- Verdict : **d'accord sur la sévérité (important), désaccord sur le diagnostic**. Kimi
  présente une « divergence 10× à trancher ». Il n'y a rien à trancher : un filtre
  complémentaire n'a **aucun retard** sur le signal vrai (les voies gyro et accel se somment
  à 1 ; 0,25 s est la fréquence de croisement des capteurs, pas un lag). Modéliser 0,25 s de
  retard rendrait tout équilibre impossible. Les vrais retards de la chaîne sont : DLPF
  MPU6050 à 42/44 Hz (~5 ms), échantillonnage (2,5 ms moyen), et surtout la **trame PWM
  50 Hz du servo (0-20 ms, non modélisée)**. 25 ms est donc une valeur défendable comme
  retard *total* de boucle, mais rangé au mauvais endroit (appliqué au pitch ET au gyro comme
  « retard IMU »). Ce qui rend le point **important** : c'est ce paramètre non justifié qui
  fait basculer le verdict du sim sur les gains embarqués. Analyse linéaire du modèle du
  sim (servo 1er ordre 50 ms + filtre) pour Kp25/Ki500/Kd0,5 : pôle dominant **+1,32**
  (instable) avec 25 ms, **−0,15** (stable, marginal) sans. Le « 0/6 » des gains embarqués
  est, en partie, un artefact de ce 25 ms. Correction : mettre le commentaire en accord
  (« retard total de boucle ≈ DLPF + ZOH servo ») et documenter que le verdict en dépend.

### #10 — `interfaces.h` : `Tuner::toggle()` « non déclaré », commentaire `loop()` périmé
- Verdict : **désaccord sur la première moitié**. `Tuner::toggle()` **est déclaré** dans
  `tuner.h:20`, que le `.ino` inclut (`balance-bot.ino:13`) — sinon ça ne compilerait pas.
  Le constat exact est : « `toggle()`/`isUp()`/`lastRequestMs()` vivent dans l'en-tête
  privé `tuner.h` et non dans le contrat gelé `interfaces.h` ». Cosmétique.
  D'accord sur le commentaire `interfaces.h:86` (« sert au plus une requête ») périmé ;
  ajouter `interfaces.h:61` (« mécanique v2 », cf. #4).

---

## 3. Les affirmations « vérifié sain »

### « Cascade de recentrage : signe correct, cohérent sim↔firmware (BQ-BX) » — **FAUX**
- **`balance.cpp:305`** : `−kRecenterKv · (s_recenterVel − s_footVelFilt)`.
- **`sim/balancebot_sim.py:95-96`** : `+self.kv · (self.recenter_vel − self.foot_vel_filt)`.
- Mêmes conventions de part et d'autre (setpoint dans les unités du pitch, `err = ref −
  pitch`, vitesse de pied = −PID, `foot_vel_filt` = vitesse de pied filtrée, `recenter_vel`
  = Kpφ·(0−φ) rampé) : les deux boucles internes sont de **signes opposés**. Historique
  (`git show 6aabd3c`) : la faute n°12 du 09/09 a inversé le signe dans le firmware, et le
  même commit a écrit la cascade du sim… avec l'ancien signe. `FIRMWARE_REVIEW.md` (faute 13
  « cascade portée à l'identique ») et `REVIEW_KIMI.md` (« cohérent ») sont donc faux tous
  les deux sur ce point, et la **RÈGLE D'OR du projet est violée** depuis 8 jours.
- Quel signe est juste ? Non tranché, et la preuve invoquée par la faute 12 est caduque :
  · l'argument physique standard d'une cascade vitesse sur pendule inversé est **(+)** : pour
    accélérer la base vers l'arrière il faut pencher vers l'arrière ;
  · l'argument de la faute 12 (« pied lâché à +20° → +37° en 0,3 s ») décrit le régime
    **transitoire** (à non-minimum de phase : pour créer un penché arrière, le PID commence
    par envoyer le pied en avant) — et il ne domine que parce que Kv·RefMax sature
    (Kv = 3, ±6° → P = 25×6 = 150 → sortie à ±90 °/s dès 2 °/s d'erreur de vitesse) ;
  · dans le sim corrigé, **les deux signes donnent 0/6** et échouent en < 0,5 s (voir M4) :
    la simulation qui a décidé du signe ne tient pas le PID seul, elle ne pouvait rien
    prouver sur la cascade.
- Recommandation : premiers essais réels avec **`kv = 0` via le banc web** (la contribution
  θ_ref devient nulle, la garde `kFootPanicDeg` reste active) ; re-décider le signe et
  Kv ≪ 1 avec un sim qui tient d'abord le PID seul.

### « Physique du sim : θ̈ = (g/h·sinθ − R/h·φ̈·cosθ)/(1 + R/h·cosθ) exacte (BY) » — **FAUX**
- C'est l'approximation « chariot-pendule » (pivot d'accélération imposée a = R(θ̈+φ̈)),
  qui **oublie le couple de réaction du servo sur le corps** (le servo est vissé sur le
  corps : le couple qu'il applique à l'arc s'applique en retour au corps — exactement le
  terme moteur des équations du Segway) et le terme centrifuge. Lagrangien pour une masse
  ponctuelle m à h au-dessus de l'axe, arc de rayon R centré sur l'axe roulant sans glisser
  (x = R(θ+φ), V = mg(R + h cosθ)) :

  ```
  θ̈ · (R² + 2Rh cosθ + h²) = g h sinθ − φ̈ · R (R + h cosθ) + R h sinθ · θ̇²
  ```

  Aux petits angles : autorité de commande **identique** (−φ̈·R/(R+h) dans les deux
  modèles), mais terme de gravité **g·h/(R+h)² = 62,0 s⁻²** (exact) contre
  **g/(R+h) = 87,2 s⁻²** (sim) : pôle instable 7,87 rad/s contre 9,34 rad/s. Le sim est
  **~19 % plus pessimiste** que sa propre hypothèse « masse ponctuelle ». Vérifié
  numériquement : ça ne change pas le 0/6 des gains embarqués (mineur, conservateur), mais
  le mot « exacte » (docstring l. 6, `FIRMWARE_REVIEW.md` faute 13, `REVIEW_KIMI.md` BY)
  doit disparaître.

### « `demoStep` non appelé quand `s_rateLow`/`s_imuLost` (AK) » — vrai, mais…
- Vrai (`balance.cpp:414-418`, `475-480` retournent avant). Ce qui a été manqué : la
  branche **`!s_imuOk`** (`balance.cpp:447-448`) appelle `halt()` **puis** `demoStep()`, et
  `halt()` → `Feet::stop()` → **`s_lastMicros = micros()`** (`feet.cpp:210`) ; le
  `driveFootSpeed()` qui suit quelques µs plus tard voit `dt ≈ 20 µs` → borné à
  `kDtMinS = 0,5 ms` (`feet.cpp:183`) au lieu des 5 ms réels → **la démo sans IMU roule 10×
  trop lentement** (2 °/s au lieu de 20 °/s). C'est précisément le « mode démo UI
  seulement » annoncé par le `.ino` pour valider la mécanique. Mineur, mais c'est un bug
  fonctionnel, pas une nuance. Fix : ne pas appeler `halt()` à chaque itération dans cette
  branche (un `halt()` sur front suffit), ou ne pas réarmer `s_lastMicros` dans `stop()`.

### « `isFallen` vs `obstacle` distincts (AL) » — vrai. Rien à redire.

### « IMU muet → retour `false` géré (AW) » — vrai pour un NACK, **faux négatif** pour un
capteur figé
- `imu.cpp:185` ne détecte que l'échec de transaction. Un MPU6050 qui **ACK mais renvoie
  des données figées** (capteur en reset/veille après un creux d'alimentation, trame de
  zéros : `norm = 0` → `trustAccel = false` → gyro seul avec `rate = −biais/65,5`) fait
  asservir le robot sur un angle mort **sans jamais déclencher `s_imuLost`**. Test de
  vivacité à coût nul : N trames brutes consécutives strictement identiques (les 7 int16)
  ⇒ traiter comme trame perdue. Mineur/important selon la qualité du câblage volant.

### « Anti-windup identique sim/firmware (BS) » — vrai, mais il ne protège pas de ce qui
fait tomber le robot (cliquet de la mort-zone, M3) ni du plafond `kIntegralMax` (M10).

### « Butée unique `FOOT_HARD_DEG` » — vrai (`config.h:70`, `feet.cpp:66`, `balance.cpp:109`).

### « Le 0/6 vient du fait que le pied consomme ses ±45° puis panique » — description
correcte du symptôme, **diagnostic incomplet** : voir M3/M4/M10/M11 — ce n'est pas « les
gains », c'est la structure (mort-zone, plafond intégral, autorité 90 °/s, saturation de
la cascade).

---

## 4. CE QUI A ÉTÉ MANQUÉ (trouvailles nouvelles, par sévérité)

### M1 — Signes opposés de la boucle interne de la cascade (sim ≠ firmware) — **important**
Détaillé en §3. `balance.cpp:305` (−Kv) vs `sim:95-96` (+Kv). Violation de la règle d'or,
signe non tranché, preuve du 09/09 caduque. Action : `kv = 0` au banc pour les premiers
essais ; aligner le sim sur le firmware (ou l'inverse) **explicitement**, avec un
commentaire croisé des deux côtés.

### M2 — Le soft clamp du simulateur est orienté à l'envers — **important (sim / règle d'or)**
`sim:110` : `if out * self.phi_cmd > 0:` où `out` est la sortie PID **non inversée** ; la
vitesse de pied réelle est `u = −out` (`sim:127`). Le pied s'éloigne de la butée quand
`u·φ > 0` ⇔ `out·φ < 0`. Le sim atténue donc… **le retour vers le centre**, et laisse la
poussée vers la butée à pleine autorité. Le firmware est juste (`balance.cpp:579-582` :
inversion **avant** `limitTowardStop`, `out·footAvg ≤ 0 → libre`). L'auteur du sim avait vu
le piège pour l'estimateur (commentaire l. 114-115, `cmd_vel = −out`) mais pas pour le clamp.
`FIRMWARE_REVIEW.md §2` (« même formule que la sim ») compare la formule, pas le signe de la
condition. Effet sur le 0/6 : nul (le clamp n'agit que dans les 10° avant la butée, zone où
la panique à 35° arrive avant) — mais c'est exactement le genre d'écart que la règle d'or
interdit, et il fausserait toute étude du comportement près des butées. Fix : tester
`(−out) * phi_cmd > 0`.

### M3 — Mort-zone d'erreur 0,25° + intégrateur = cliquet → chute garantie en ~1,5 s — **important (firmware)**
`balance.cpp:86` (`kErrDeadbandDeg = 0.25f`) appliquée l. 565 **avant** P et I ; même
chose `sim:47,100`. Mécanisme (trace reproduite ci-dessous, Kp = 100 / Ki = 500 / Kd = 0,5,
θ0 = 0,25°, cascade OFF, clamp orienté comme le firmware) : le robot vit sur le **bord** de
la mort-zone ; chaque sortie au-dessus de +0,25° donne un coup de P qui le ramène juste
dedans, où P et I sont gelés ; l'erreur n'est donc **jamais de l'autre signe**, l'intégrale
n'a rien pour se décharger et **cliquette jusqu'à sa borne** (−25 = 25 °/s de dérive
permanente des pieds) → butée en ~1,3 s → chute. Ce jeu est **linéairement stable** (pôle
dominant −2,87 avec les deux retards) : la chute est due à la seule mort-zone.

```
   t     θ°    φcmd°    I     out        deadband=0.25 → chute@1.36 s (I∈[−25,0], monotone)
 0.10  +0.21   +1.5   −6.6  −31.1       deadband=0    → OK 6 s, φfin +2,4° (I∈[−8.6,0])
 0.30  +0.28   +4.5  −13.8  −43.9
 0.50  +0.33  +10.4  −24.8  −58.1       Idem Kp50/Ki350/Kd1 : chute@1.18 s → OK
 0.70  +0.41  +19.5  −25.0  −65.1       Idem avec bruit IMU + physique exacte : chute@1.79 s → OK
 1.00  +1.01  +39.8  −25.0  −90.0
 1.20  +9.34  +44.2  −25.0  −90.0
```

Sur le robot réel, le bruit IMU et la mort-zone propre du SG90 (~1° ≈ 0,57 mm) brouilleront
le cycle limite, mais le mécanisme (I n'intègre que hors bande et ne se décharge jamais dans
la bande) est structurel. Conséquence pratique : **une campagne de réglage avec cette
mort-zone verra les pieds partir en butée en 1-2 s quels que soient les gains**, et on
accusera les gains. Fix (3 caractères) : `kErrDeadbandDeg = 0.0f` — la justification
« tremblement dû au bruit IMU » ne tient pas (bruit du pitch fusionné ~0,03-0,1° rms, et
le servo ne répond pas sous ~1° de toute façon) ; si une bande est voulue, l'appliquer au
seul terme P, jamais à l'entrée de l'intégrateur. Porter au sim (`DEADBAND = 0`).

### M4 — Le « 0/6, aucun jeu de gains ne tient » est un artefact de structure, pas un fait sur les gains — **important (projet)**
Faits établis par ré-exécution :
1. **Tous** les scénarios échouent en 0,35-0,55 s, **avant la tape** (cf. §1 #5) : les trois
   scénarios « tape » n'ont jamais été joués.
2. **118 des 560** combinaisons (Kp, Ki, Kd, k_out ∈ {1, 3}) du balayage sont
   **linéairement stables** dans le propre modèle du sim (servo 50 ms + filtre 25 ms), et
   pourtant le sim non-linéaire n'en fait tenir **aucune**, même à θ0 = 0,25°. Un modèle
   linéairement stable qui tombe à 0,25° n'est pas « mal réglé » : une non-linéarité le tue.
3. Les non-linéarités en cause, isolées une à une : (a) la mort-zone (M3) — à elle seule
   suffisante ; (b) `kIntegralMax = 25` (M10) ; (c) `kOutToFootDegS = 1` → 90 °/s ≈ 51 mm/s
   de base, non balayé (M11) ; (d) le retard de 25 ms (§2 #9). Avec (a) = 0, (d) = 5 ms,
   Imax = 90 et k_out = 3, les gains embarqués tiennent les scénarios θ0 = 2° (φfin ±10°)
   et deux des trois tapes sont enfin **atteintes** (échec juste après, à 3,2-3,4 s ; la
   troisième tombe à 2,8 s sur son seul θ0 = 3° bruité) : dans ce modèle, 0,4-1,2 rad/s
   sont trop violentes pour ±25 mm de course — limite du robot, pas des gains.
4. La cascade, avec l'un ou l'autre signe et dans **toutes** les configurations testées,
   **aggrave** le résultat (panique à 0,2-0,4 s) : Kv = 3 avec ±6° de θ_ref × Kp ≥ 25 sature
   la sortie au premier écart de vitesse. En l'état c'est un passif, pas une aide.

Conclusion à substituer à « gains à re-régler en réel » : *le simulateur, tel qu'il est,
ne peut valider aucun jeu de gains, et ses échecs sont dominés par quatre choix structurels
(dont deux sont dans le firmware : mort-zone, plafond intégral) et par l'autorité 90 °/s.*
Chercher des gains avec lui avant de corriger ces points est du temps perdu.

### M5 — Physique du sim non « exacte » (couple de réaction servo) — mineur (conservateur)
Détaillé en §3. Retirer « exacte » ; optionnel : adopter l'équation de Lagrange ci-dessus
(3 lignes) — le sim devient ~19 % moins pessimiste sur la gravité, sans changer l'autorité.

### M6 — « Refus d'armer sur batterie faible » désarme aussi **en plein équilibre**, sur un seul échantillon ADC — **important (sécurité)**
`balance.cpp:424-427` s'exécute à **chaque** itération (pas seulement sur le front montant) :
dès que `g_state.batteryLow` passe à vrai, `cmdEnabled` est effacé → front descendant →
`halt()` → le robot debout **tombe**. Or `batteryLow` vient d'**une seule** conversion
`analogReadMilliVolts` par seconde (`battery.cpp:36`, `.ino:140-144`), sans moyenne ni
hystérésis, comparée à 3,5 V. Une LiPo 1S à mi-charge (~3,7 V à vide) sous un appel de 4
SG90 (pointes de 1-2 A, résistance interne + câblage volant) plonge transitoirement sous
3,5 V : **un échantillon malchanceux suffit à faire tomber un robot qui tenait**. L'intention
documentée (A4 : « la demande d'armement est annulée ») est une garde d'**armement** ;
l'implémentation est une coupure permanente. Fix : n'annuler que sur le front montant
(`want && !s_enabled`), et exiger N lectures consécutives basses (ou hystérésis 3,5/3,6 V)
pour déclarer `batteryLow`. Sur USB seul (`batteryV = −1`) le problème est inerte, ce qui
explique qu'il n'ait pas été vu au banc.

### M7 — Démo sans IMU 10× trop lente — mineur
Détaillé en §3 (AK). `balance.cpp:447-448` + `feet.cpp:210,183`.

### M8 — Procédure de réglage (`balance.cpp:40-43`) inapplicable et contradictoire — **important (pilote la campagne de réglage)**
« robot tenu à la main, **Ki = Kd = 0**, monter Kp jusqu'à oscillation ; puis Kd pour
amortir ; puis Ki pour la dérive lente ». C'est la recette d'un PID en **position**. Ici la
sortie est une **vitesse** de pied, donc l'accélération de la base (la seule chose qui
redresse le pendule) est la *dérivée* de la sortie : Ki·θ + Kp·θ̇ + Kd·θ̈. Autrement dit
**Ki est la raideur, Kp l'amortissement, Kd une inertie** — et le commentaire lui-même le
dit dix lignes plus bas (l. 51-56 : « Il faut Ki > g/R ≈ 301… en dessous, le robot tombe
quelle que soit la valeur de Kp »). L'étape 1 (Ki = 0) ne peut **jamais** produire une
oscillation observable, et l'étape 2 (« monter Kd pour amortir ») fait l'inverse de ce
qu'elle annonce. Analyse linéaire du modèle du sim (retards 50 + 25 ms) : Kp = 25 → instable
(+1,32) ; Kp = 50-100 → amortissement franc (pôle dominant −2,3 à −2,9). Réécrire : (1) Ki ≈ 400-500 d'emblée
(> 302), Kp ≈ 50, Kd ≈ 0,5 ; (2) monter **Kp** pour amortir ; (3) Kd en dernier, petit.

### M9 — IMU figée mais ACK non détectée — mineur/important
Détaillé en §3 (AW). `imu.cpp:181-203`.

### M10 — `kIntegralMax = 25` (28 % de `kOutMax`) plafonne le seul terme qui redresse — important (réglage)
`balance.cpp:81`. Dans cette architecture, I est le terme de raideur (cf. M8) ; le borner
à 25 °/s de sortie, c'est plafonner l'accélération cumulée de la base à une fraction de
l'autorité. Mesuré (deadband 0, τ_f 5 ms, k_out 3, cascade OFF, gains embarqués) : Imax = 25
→ 0/6 (chute à 1,8 s) ; Imax = 90 → 2/6 (θ0 = 2° tenus, φfin ±10°). Le commentaire justifie
la borne par le rebond au redressement — l'intégration conditionnelle (l. 194-199) s'en
charge déjà. Fix : `kIntegralMax = kOutMax`.

### M11 — `kOutToFootDegS = 1.0` : 90 °/s, < 25 % d'un SG90, `constexpr`, jamais balayé — important (stratégie de réglage)
`balance.cpp:99`. Le commentaire (l. 97-98) le désigne comme « le PREMIER bouton à monter »
— mais il n'est ni au banc web ni dans le balayage du sim (`--sweep` ne varie que Kp/Ki/Kd,
avec `OUT_TO_FOOT_DEGS = 1`). Le sim ne fait tenir un scénario θ0 = 2° **que** pour
k_out = 3. 51 mm/s de base pour rattraper 2° de penché, c'est peu : un pendule de 8 cm a
une constante de temps de ~0,1 s. Fix : exposer `kOutToFootDegS` au banc (borné 1-3,
persisté), ou le fixer à 2-3 avant la campagne ; l'ajouter au `--sweep`.

### M12 — NVS depuis le cœur 0 stalle le cœur 1 — mineur (vérifié sdkconfig)
Détaillé en §2 #7. Renforce « écrire au désarmement ».

### M13 — Restes de la revue précédente — cosmétique
`balance.cpp:15` et `interfaces.h:61` (« v2 ») ; `interfaces.h:86` (commentaire `loop()`) ;
`TEST_PROTOCOL.md:12`, `README.md:19` (`FIT_NOTES`) ; `balance.cpp:61-63` (paraphrase des
l. 45-49). Un `grep` aurait tout attrapé d'un coup.

### M14 — `Serial.printf` dans `loop()` cœur 1 (`.ino:133`) — mineur
Détaillé en §2 #8. Contraire à la règle établie par `STALL_ANALYSIS.md §6`.

### M15 — Page web : slider Kd borné à 10 (`tuner.cpp:125`) alors que `kKdMax = 20` ; `send()` (l. 142) reposte les 5 sliders — cosmétique/mineur
Un Kd > 10 posé par `curl` est affiché tronqué à 10 par le navigateur puis **réécrit à 10**
au premier geste sur n'importe quel autre slider. Aligner `max="20"`.

### M16 — Réarmement sans recentrage : panique probable si les pieds ont été laissés > ~25° — mineur (documenté, à connaître)
Après un STOP les pieds restent où ils sont (voulu, `halt()`). Au réarmement, aucun
`recenterNow()` (seul le chemin « chute + 700 ms droit » le fait) : avec `footAvg` ≈ 30°,
le premier transitoire franchit `kFootPanicDeg = 35°` → `s_fallen = true` → « CHUTE »
robot debout. Contournement existant : ramener les pieds aux flèches en MANUEL (la démo
autorise le retour vers 0 au-delà de ±15°). À documenter dans `TEST_PROTOCOL.md`, ou
recentrer sur front montant quand |pitch| < 10° et |rate| faible (robot tenu).

### M17 — Ce que le sim ne modélise toujours pas, et qui dominera le réel — mineur (documentation)
Trame PWM 50 Hz (0-20 ms de latence, échantillonneur-bloqueur), **mort-zone du SG90
(~5-10 µs ≈ 0,5-1° ≈ 0,3-0,6 mm de base)**, pas de borne d'accélération (φ̈ impulsionnel
au premier pas : +800 °/s² dans les traces). La mort-zone servo produira un cycle limite
de quelques degrés que le sim ne peut pas prédire. À ajouter à la docstring (l. 26-27).

### M18 — `Imu::calibrate()` : retour ignoré, 400 « échantillons » = 60 vrais — mineur
`balance.cpp:384` ignore le `false` (bus instable → biais gyro à 0, non signalé).
`imu.cpp:171` lit à ~1,4 kHz un capteur configuré à 200 Hz (`kSmplrtDiv = 4`) : 400
lectures ≈ 60 échantillons distincts lus 7× chacun — moyenne correcte mais bruit du biais
√7 fois plus grand qu'annoncé. Lire à 200 Hz pendant 2 s (400 vrais points), et logguer
l'échec.

### M19 — Reprise automatique après `s_imuLost` / `s_rateLow` — à discuter (mineur)
`balance.cpp:414-418`, `472-480` : l'asservissement reprend seul dès que le capteur/la
cadence revient, sur une estimation d'angle qui n'a pas intégré le gyro pendant la coupure
(reconvergence ~0,25 s par l'accel) et un état du robot inconnu. Documenté comme voulu
(« reprise automatique ») ; sur un robot tenu à la main c'est acceptable, sur un robot
libre ce n'est pas plus sûr que d'exiger un réarmement. Je le signale sans le contester.

---

## 5. Désaccords (synthèse)

| # | Ce que `REVIEW_KIMI.md` / Hermes affirme | Mon verdict | Preuve |
|---|---|---|---|
| D1 | #5 « conséquence mesurée : tape passe de chute θ à panic φ, θfin +46° → +27° » | **Faux, non reproductible** : sortie identique avant/après ; aucun scénario n'atteint t = 3 s | §1 #5 (ré-exécution des deux versions) |
| D2 | « Cascade : signe correct, cohérent sim↔firmware » | **Faux** : `−Kv` (`balance.cpp:305`) vs `+Kv` (`sim:96`) depuis `6aabd3c` | §3, M1 |
| D3 | « Physique θ̈ exacte » | **Faux** : approximation chariot-pendule, couple de réaction servo omis (pôle 9,34 vs 7,87 rad/s) | §3, M5 |
| D4 | #10 « `Tuner::toggle()` non déclaré » | **Faux** : déclaré `tuner.h:20`, inclus par le `.ino` | §2 #10 |
| D5 | #9 « divergence 10× à trancher » (0,25 s vs 0,025) | Rien à trancher : 0,25 s serait physiquement absurde ; le vrai enjeu est que le verdict du sim dépend de ce 25 ms non justifié | §2 #9 |
| D6 | « Le 0/6 ⇒ gains à re-régler » (conclusion reprise de `FIRMWARE_REVIEW §1bis`) | Diagnostic incomplet : mort-zone (cliquet), `kIntegralMax`, autorité 90 °/s, saturation cascade ; des jeux linéairement stables tombent à 0,25° | M3, M4, M10, M11 |
| — | #3/#4 corrections « appliquées » | Incomplètes (`balance.cpp:15`, `interfaces.h:61`, `TEST_PROTOCOL.md:12`, `README.md:19`) | §1 #3-#4 |
| — | « Soft clamp : même formule que la sim » (`FIRMWARE_REVIEW §2`, repris par le silence de Kimi) | Même formule, **condition inversée** dans le sim | M2 |

Points où je suis **d'accord** avec la revue initiale : #1, le fond de #2, le code de #5,
#6 (voire moins grave), #7 (voire plus grave), #8, AL, la butée unique, l'anti-windup
identique, le compte « 0/6 » lui-même (reproduit à l'identique, y compris pour mes
variantes de physique).

---

## 6. Verdict final

**À corriger avant le prochain flash** — si, comme tout le dépôt l'indique, ce flash est
celui de la campagne de réglage réel. Aucune des trouvailles ne rend le firmware dangereux à
flasher pour vérifier la mécanique, le signe de l'IMU et le neutre des pieds (les gardes
chute / IMU muette / cadence / servos non attachés / panique sont saines) ; mais deux
défauts feront échouer ou mal interpréter la campagne de réglage, et coûtent quelques lignes :

1. **`balance.cpp:86` `kErrDeadbandDeg = 0.0f`** (M3) — sinon les pieds partent en butée en
   1-2 s quels que soient les gains, et on accusera les gains. Porter `DEADBAND = 0` au sim.
2. **`balance.cpp:424-427`** : garde batterie sur le **front montant seulement** + hystérésis
   / N échantillons (M6) — sinon un creux de tension d'un seul échantillon fait tomber un
   robot qui tenait (inerte sur USB, actif sur batterie).
3. **`kv = 0` au banc web** avant toute autre chose (M1) — aucune modification de code ; la
   cascade telle que réglée est un passif avec l'un ou l'autre signe, et son signe est
   non tranché.
4. Fortement recommandé dans le même flash : `kIntegralMax = kOutMax` (M10) et
   `kOutToFootDegS` exposé au banc ou monté à 2-3 (M11) ; réécrire la procédure de réglage
   (M8) ; `halt()` sur front seulement dans la branche sans IMU (M7).

Et **avant toute nouvelle recherche de gains avec le simulateur** (sinon ses verdicts sont
sans valeur) : condition du soft clamp (M2), signe de la cascade aligné (M1), `DEADBAND`,
justification du retard de 25 ms (§2 #9), retrait du mot « exacte » et, idéalement,
équation de Lagrange (M5), `OUT_TO_FOOT_DEGS` dans le balayage (M11), et vérifier qu'un
scénario **atteint** sa tape avant de conclure quoi que ce soit sur les tapes.

Sur la méthode de la revue précédente : la « vérification ligne par ligne » a validé une
conséquence mesurée qui ne se produit pas (D1) et deux « vérifié sain » démontrablement faux
(D2, D3). Le simulateur est le seul instrument de validation du projet : la règle d'or
(mêmes boucles que `balance.cpp`) est aujourd'hui violée sur deux signes, et personne ne
l'a fait tourner assez loin pour voir qu'aucune tape n'était jamais appliquée.

---

## 7. Application des corrections (17/09/2026 — arbre de travail, commit à venir)

Périmètre appliqué : `balance-bot/` (balance.cpp, imu.cpp/h, battery.cpp/h, tuner.cpp,
ui.cpp — commentaires seuls —, interfaces.h, .ino), `sim/balancebot_sim.py`,
`TEST_PROTOCOL.md`, `README.md`. Rien n'a été flashé ni commité ; gains kKp/kKi/kKd
(25/500/0,5) et structure de la loi de commande inchangés.

| # | Correction | État | Où / comment |
|---|---|---|---|
| M1 | Signe de la boucle interne de la cascade sim ≠ firmware | **appliquée (commit à venir)** | Sim aligné sur le firmware : `-self.kv · (v_cible − φ̇)` (`sim:139`). Commentaire croisé des deux côtés (`balance.cpp` `recenterSetpoint()`, `sim` boucle interne) : « signe NON tranché — à décider en réel, commencer Kv = 0 au banc web ». Le signe n'a pas été tranché ; l'ancien commentaire « vérifié en simulation » est remplacé par le constat de caducité. |
| M2 | Soft clamp du sim orienté à l'envers | **appliquée** | `if (-out) * self.phi_cmd > 0:` (`sim:163`), avec le raisonnement du signe en commentaire. |
| M3 | Mort-zone d'erreur 0,25° + intégrateur = cliquet | **appliquée** | `kErrDeadbandDeg = 0.0f` (`balance.cpp`) et `DEADBAND = 0.0` (sim). Justification réécrite (bande sur P seul si jamais nécessaire). Vérifié dans le sim corrigé : Kp100/Ki500/Kd0,5, θ0 = 0,25°, cascade OFF → bande 0,25° : chute à 1,75 s avec I en butée ; bande 0 : tenu 6 s, φfin +1,6°. Idem Kp50/Ki350/Kd1 (1,52 s → OK) et Kp50/Ki500/Kd0,5 (1,59 s → OK). |
| M5 | Physique « exacte » (couple de réaction servo omis) | **appliquée** | Équation de Lagrange dans `run()` : `θ̈·(R² + 2Rh·cosθ + h²) = g·h·sinθ − φ̈·R·(R + h·cosθ) + R·h·sinθ·θ̇²`. Docstring réécrite (dérivation, petits angles 62,0 s⁻² vs 87,2, pôle 7,87 vs 9,34 rad/s) ; le mot « EXACT » a disparu. |
| M6 | Garde batterie = coupure en plein équilibre sur 1 échantillon | **appliquée** | `balance.cpp` : garde sur le **front montant** seulement (`want && !s_enabled && g_state.batteryLow`) — l'armement reste refusé, un robot debout n'est plus coupé. `battery.cpp` : `batteryLow` exige **3 lectures valides consécutives** < 3,5 V et retombe seulement au-dessus de **3,6 V** (hystérésis, `BAT_LOW_CLEAR_V = BAT_LOW_V + 0,1`, constantes locales — `config.h` non touché). Commentaires `interfaces.h`, `battery.h`, `ui.cpp` mis en accord (l'UI affiche toujours « BAT. FAIBLE », désormais aussi comme invitation à poser un robot debout). |
| M7 | Démo sans IMU 10× trop lente | **appliquée** | `halt()` sur front seulement dans la branche `!s_imuOk` (drapeau statique `s_noImuHalted` ; `s_imuOk` est figé au boot, le front est la première itération). `Feet::stop()` inchangé. |
| M8 | Procédure de réglage inapplicable (recette d'un PID de position) | **appliquée** | Commentaire `balance.cpp:40-53` réécrit pour une sortie en VITESSE : Ki = raideur (≈ 400-500 d'emblée, > g/R ≈ 302), Kp ≈ 50 = amortissement (monter Kp pour amortir), Kd = inertie, petit et en dernier. Le 301 → 302 de la condition de stabilité (9,81/0,0325 = 301,8) harmonisé. |
| M9 | IMU figée mais ACK non détectée | **appliquée** | `imu.cpp` : `readLive()` compare la trame brute (7 int16) à la précédente ; au-delà de `kFrozenMax = 4` trames strictement identiques consécutives, `update()` renvoie `false` → alimente `s_imuFailStreak`/`kImuFailMax` de `balance.cpp` (coupure à 24 trames ≈ 120 ms). Seuil > 1 parce que la cadence millis() du .ino peut relire le même échantillon (lecture < 5 ms après la précédente). Réinitialisé dans `begin()`. |
| M10 | `kIntegralMax = 25` plafonne le terme de raideur | **appliquée** | `kIntegralMax = kOutMax` (bloc anti-windup déplacé après `kOutMax`), `INTEGRAL_MAX = OUT_MAX` dans le sim. Le rebond au redressement reste géré par l'intégration conditionnelle. Effet mesuré (gains embarqués, k_out 3, Kv 0) : panic à 1,13 s (Imax 25) → 1,65 s (Imax 90). |
| M11 | `kOutToFootDegS` constexpr, jamais balayé | **appliquée** | Firmware : `float kOutToFootDegS` borné `kOutToFootMin..Max` = 1..3, API `Balance::setOutScale()/getOutScale()` (ajout non intrusif dans `interfaces.h`), clé NVS « kout » (écriture dans `saveGains()`, relecture bornée dans `begin()`), slider « Autorité kOut » 1-3 pas 0,1 sur la page web + champ `kout` dans `/api/state` et `/api/gains` (tampon 512 o : +11 o, marge conservée). Sim : paramètre `k_out` de `Sim` appliqué à la commande physique (`u = −ctrl()·k_out`) ET à l'estimateur φ̇ ; `--sweep` balaie k_out ∈ {1, 2, 3} ; 4ᵉ argument positionnel `k_out` en CLI. |
| M13 | Restes cosmétiques | **appliquée** | « v2 » → « v3.1 » (`balance.cpp:15`, `interfaces.h:61`) ; commentaire `Tuner::loop()` (`interfaces.h:86`) ; `FIT_NOTES §9` → `chassis/NOTES_v3.md, § Montage` (`TEST_PROTOCOL.md:12`) ; `README.md:19` → « châssis v3.1 : gen_bitcoin_bot.py + STL (v3/) + NOTES_v3.md » (gen_chassis.py n'existe pas non plus) ; paraphrase `balance.cpp:61-63` supprimée, §45-49 conservé. |
| M14 | `Serial.printf` dans `loop()` cœur 1 sur appui long | **appliquée (élargie)** | `.ino:133` : plus aucun `Serial` — `(void)Tuner::toggle()`. Comme `startRadio()`/`stopRadio()` écrivaient aussi sur Serial depuis ce même chemin, leurs traces sont regroupées dans `announce()`, appelée depuis `begin()` (setup) et, sur `toggle()`, par la tâche serveur (cœur 0) via un drapeau `volatile s_announce`. La trace « BANC WEB : OUVERT/FERMÉ » est conservée, hors du chemin chaud. |
| M15 | Slider Kd borné à 10 vs `kKdMax = 20` | **appliquée** | `max="20"` (`tuner.cpp`). |
| M16 | Réarmement sans recentrage → panique si pieds > ~25° | **appliquée (doc seule)** | Paragraphe ajouté à `TEST_PROTOCOL.md` §5 : symptôme (« CHUTE » robot debout), cause (aucun `recenterNow()` à l'armement), consigne (MANUEL, ramener les pieds vers 0 aux flèches, `P:` ≈ 0). Comportement inchangé. |
| M17 | Ce que le sim ne modélise pas | **appliquée** | Docstring du sim : trame PWM 50 Hz (0-20 ms, échantillonneur-bloqueur), mort-zone SG90 (~5-10 µs ≈ 0,5-1°), pas de borne d'accélération, friction/3D/masse des pieds, retard forfaitaire 25 ms. Le commentaire faux de `tau_f` (« filtre complémentaire 0,25 s », §2 #9) est remplacé par « retard total de boucle, non justifié finement, le verdict en dépend » — valeur inchangée. |
| M18 | `Imu::calibrate()` : retour ignoré, 400 lectures = 60 échantillons | **appliquée** | `balance.cpp` : `if (!Imu::calibrate()) Serial.println(…)` (setup, hors chemin chaud), IMU conservée. `imu.cpp` : `delay(5)` entre lectures (≈ 200 Hz → 400 échantillons distincts en ~2,2 s), lectures via `readLive()` (les trames figées ne comptent pas). Commentaire `imu.h` : « ~300 ms » → « ~2 s ». |
| M19 | Reprise automatique après imuLost/rateLow | **appliquée (commentaire seul, rien changé)** | Bloc de commentaire à la déclaration de `s_imuLost`/`s_rateLow` : choix documenté, limite robot libre vs tenu, relais par le verrou de chute. |

Non retenu / hors liste (signalé, pas modifié) :
- **§2 #7 / M12 — throttling NVS qui saute l'écriture** : non demandé, non modifié. Conséquence
  à connaître : dans `handleGains()`, `setGains` → `setRecenterGains` → `setOutScale`
  appellent chacun `saveGains()` ; seul le premier écrit (fenêtre 1,5 s), donc Kpφ/Kv et
  désormais kOut ne sont persistés qu'au POST **suivant** (valeurs déjà en RAM). Fix
  recommandé inchangé : drapeau dirty + écriture au désarmement.
- **§2 #9 — valeur de `tau_f`** : commentaire corrigé (M17), valeur 25 ms conservée (pas dans
  la liste ; le verdict du sim en dépend, c'est écrit dans la docstring).
- `README.md:35` (« Gains validés par simulation ») et `TEST_PROTOCOL.md:3-4` (« gains
  sim-validés ») restent **faux** au vu de §1 #5 / M4 — hors de la liste « renvois périmés »,
  non touchés. À corriger par l'orchestrateur avec le prochain flash.
- `TEST_PROTOCOL.md` §4 et le tableau « Réglages rapides » gardent la logique « position »
  (buzz → ↓Kp ↑Kd) contredite par M8 ; non listés, non touchés.

### Compilation (sans upload)

`arduino-cli compile --fqbn esp32:esp32:esp32s3:USBMode=hwcdc,FlashSize=16M,PSRAM=opi`
+ les defines de `build.sh` (170×320, ST7789) : **0 erreur**, 1 046 902 o de flash (79 %),
50 916 o de RAM (15 %). Recompilation complète séparée (`--build-path /tmp`, `-Wall -Wextra`
effectifs) : **aucun avertissement dans les fichiers modifiés** ; seuls subsistent 3
`-Wformat-truncation` préexistants dans `ui.cpp:1057/1091/1150` (non touchés).

### Simulateur — AVANT / APRÈS (gains embarqués Kp25/Ki500/Kd0,5, `random.seed(42)`)

| Variante | AVANT (`2c64860`) | APRÈS (M1 M2 M3 M5 M10 M11) |
|---|---|---|
| défaut (cascade ON, Kv 3, k_out 1) | **0/6** — panic φ @0,41 s ×5, chute θ @0,35 s | **0/6** — chute θ @0,39-0,49 s ×6 |
| `--no-cascade` | **0/6** — chute θ @0,35-0,54 s | **0/6** — chute θ @0,43-0,90 s |
| k_out 3, Kv 0 (cascade neutralisée) | n/a (k_out non réglable) | **0/6** — panic φ @1,65 s (θ0 = 2°), 0,93 s (tapes) |
| `--sweep` (280 jeux × k_out {1,2,3}, 6/6 exigé) | 0 jeu (280 jeux, k_out 1 seul) | **0 jeu** (cascade Kv 3 : 280 × 3 à 0/6 ; `--no-cascade` : 0 jeu à 6/6) |

Tapes (poussée à t = 3 s) : avec les gains embarqués **aucune tape n'est atteinte**, avant
comme après (chute avant 0,5 s ; 1,65 s au mieux). Elles ne le sont que dans le balayage
étendu, **k_out = 3 et cascade neutralisée** (Kv = 0 ou `--no-cascade`) : meilleur jeu
2/6 avec les **3 tapes atteintes**, par ex. Kp25/Ki350/Kd1 → θ0 = 2° tenus 6 s (φfin +10°/−5°),
tapes → panic φ **0,1-0,2 s après la poussée** (3,10-3,20 s) : 0,4 rad/s consomme déjà les
±25 mm de course, ce que le protocole annonçait déjà comme limite physique. Histogramme
du balayage (Kv 0) : k_out 1 → 280 jeux à 0/6 ; k_out 2 → 13 jeux à 2/6 ; k_out 3 → 26 jeux
à 2/6. Avec la cascade à Kv = 3, **tout** panique φ en 0,2-0,4 s quel que soit k_out
(saturation Kv·RefMax, cf. M4-4) — la recommandation « Kv = 0 au banc » tient.

Lecture : les corrections n'améliorent pas le compte 6/6 des gains embarqués (le retard
forfaitaire de 25 ms les rend linéairement instables, §2 #9) ; elles changent ce que le
sim mesure : (i) les tapes deviennent atteignables (k_out 3), (ii) le cliquet de la
mort-zone est éliminé sur les jeux stables (M3, vérifié ci-dessus), (iii) le plafond
intégral n'écrête plus la raideur (M10 : 1,13 s → 1,65 s avant panic), (iv) le sim et le
firmware ont enfin les mêmes signes (M1, M2) et une physique de 19 % moins pessimiste
(M5). Le prochain pas côté sim n'est pas une recherche de gains mais la justification de
`tau_f` et la modélisation de la trame 50 Hz (M17).
