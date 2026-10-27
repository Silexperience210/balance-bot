# Review complète BalanceBot — Kimi K3 + vérification Hermes

Date : 15/09/2026. Périmètre : `balance-bot/` (14 fichiers, ~3 600 lignes avec en-têtes)
+ `sim/balancebot_sim.py`. Méthode : revue intégrale par **Kimi K3** (agent délégué),
puis **vérification ligne par ligne et corrections par Hermes** (l'orchestrateur — le
rapport de l'agent n'est jamais pris tel quel).

> Kimi a timeout (EXIT=124) après avoir fait toute la revue mais avant d'écrire : ses
> constats ont été repris de son journal, **chacun re-vérifié sur le code**, puis
> corrigés par Hermes.

## Baseline (avant correction)
- Compilation : **0 erreur**, 79 % flash, 15 % RAM.
- Simulateur : **0/6 scénarios tenus** avec les gains embarqués Kp25/Ki500/Kd0.5
  (avec et sans cascade) — reproduit, conforme à `FIRMWARE_REVIEW.md §1bis`.

## Corrections appliquées (vérifiées)

| # | Fichier | Constat | Correction |
|---|---|---|---|
| 1 | `ui.cpp:511` | `FaceFrame s_lastFrame;` déclarée et **jamais utilisée** (seule occurrence du firmware). | Supprimée. |
| 2 | `balance.cpp:61` | Commentaire « Les valeurs ci-dessous restent les valeurs **validées en simulation** » — **faux** (elles tiennent 0/6). Contredit les lignes 55-60. | Réécrit : gains de DÉPART, NON validés, renvoi `FIRMWARE_REVIEW.md §1bis`. |
| 3 | `feet.cpp:4,13` | Deux références `chassis/FIT_NOTES.md §9` — fichier **purgé** (la faute 11 de la revue 09/09 disait les avoir réécrites, mais ces deux-là subsistaient). | `NOTES_v3.md`. |
| 4 | `feet.h:5` | « la mécanique **v2** n'a plus de roues » — version périmée. | `v3.1`. |
| 5 | `sim/balancebot_sim.py:135` | **Bug du simulateur** : le « tape » (coup) appliquait `push_v` sur **chaque pas** dans une fenêtre `±0.02 s` (= 7 pas à dt 5 ms) → un « tape 0,4 rad/s » envoyait en réalité **2,8 rad/s**. | Fenêtre réduite à `DT/2` (un seul pas) : coup = `push_v`, conforme au libellé des scénarios. |

Conséquence mesurée du correctif 5 : les scénarios « tape » passent de `chute θ` à
`panic φ` (θfin +46° → +27°), mais **le résultat global reste 0/6** — la conclusion
« gains à re-régler en réel » ne change pas, elle est simplement désormais plus honnête.

## Suggestions retenues (non implémentées — à arbitrer)

| # | Fichier | Suggestion | Sévérité |
|---|---|---|---|
| 6 | `feet.cpp` `driveFootSpeed(int,…)` | Quantifie la vitesse en `int` : la fraction de °/s est perdue à chaque cycle (dérive mineure de l'intégrale). Passer en `float`. | mineur |
| 7 | `tuner.cpp` `saveGains` | Throttling NVS 1,5 s **saute** l'écriture : une rafale de sliders suivie d'un reset perd la dernière valeur. Écrire au désarmement ou suivre un drapeau dirty. | mineur |
| 8 | `tuner.cpp`/`.ino` `Tuner::toggle()` | Appelé sur cœur 1, serveur sur cœur 0 : course bénigne sur `s_up`. | mineur |
| 9 | `sim/balancebot_sim.py` `tau_f=0.025` | Commentaire « 0,25 s » vs valeur `0.025` : divergence 10× sur le lag modélisé de l'angle (fidélité sim↔firmware à trancher). | important |
| 10 | `interfaces.h` | `Tuner::toggle()` non déclaré (utilisé dans le `.ino`) ; commentaire `Tuner::loop()` périmé (« sert au plus une requête » alors que c'est un no-op). | cosmétique |

## Vérifié sain (extraits — le silence ne vaut pas « non vérifié »)
- Cascade de recentrage : signe correct, cohérent sim↔firmware (BQ-BX).
- Physique du sim : `θ̈ = (g/h·sinθ − R/h·φ̈·cosθ)/(1 + R/h·cosθ)` exacte (BY).
- Sécurité : `demoStep` non appelé quand `s_rateLow`/`s_imuLost` (AK) ; `isFallen` vs
  `obstacle` distincts (AL) ; IMU muet → retour `false` géré (AW) ; anti-windup
  identique sim/firmware (BS).
- Butée unique `FOOT_HARD_DEG` (config.h) respectée — pas de littéral recopié.
- Le « 0/6 » vient du fait que **le pied consomme ses ±45° de course puis panique** —
  cohérent avec la limite structurelle documentée (mobilité ±25 mm).

## Verdict compilation après correction
`arduino-cli compile` (FQBN + flags de `build.sh`, **sans upload**) : **0 erreur**,
79 % flash, 15 % RAM.
