# Feuille de route — B-bot

Objectif : faire du B-bot un robot **qui tient, qui voit, qui réagit, et qui accueille** —
sans jamais perdre la loi du projet :

> **Le simulateur et le firmware doivent dire la même chose.**

Statuts : ✅ fait · 🔄 en cours · ⏳ à faire · 🔧 demande le robot ou l'imprimante sous la main.

---

## 1. Fondations

| # | Chantier | État | Détail |
|---|---|---|---|
| 1.1 | **CI « règle d'or »** | ✅ | `scripts/verifier-regle-or.py` compare firmware et simulateurs. `scripts/verifier-cotes.py` compare `cotes.py`, les notes, `WHEEL_RADIUS_MM` et le rayon dynamique figé à 41,5 mm. Le workflow lance aussi `chaine_roue.py` et `verif_ultime.py` sur les STL, l'auto-test du simulateur, le bundle, et la compilation. |
| 1.2 | **Deux cœurs** | ✅ 🔧 | Dans le code : `BALANCE_SPLIT_CORES 1`, équilibre sur le cœur 0, écran/tête/tuner sur le cœur 1, repli mono-cœur par `-D`. Pas d'essai chronométré sur le robot dans cette passe. |
| 1.3 | **Arrêt sûr** | ✅ 🔧 | Chute : PWM détaché. Perte IMU (> 100 ms), cadence sous 120 Hz, ou boucle figée : en mode roue, **même coupure**, reprise seulement si le robot est tenu droit (< 10° pendant 700 ms). En mode arc, la reprise automatique de la revue M19 est conservée (le servo tient l'angle). Arrêt d'urgence : appui long sur BOOT, verrouillé jusqu'au RESET. Rien de tout ça n'a été rejoué sur le matériel ici. |
| 1.4 | **Mode d'actionneur** | ✅ 🔧 | `FEET_MODE_CONTINUOUS` vaut **1** (servos 360°). Le CI exige que les deux simulateurs disent `roue`. Les signes `kDirL = −1`, `kDirR = +1` sont l'invariant du montage en miroir, pas un essai au sol. |
| 1.5 | **Chaîne servo-roue** | ✅ 🔧 | Moyeu qui entre, capot dégagé, quatre vis d'oreille (plot pour l'oreille basse de la panse), roue allégée. Recentrage appliqué : deux STL, milieu des faces sur le glyphe, entraxe inchangé (150,13 mm). Mesures dans `chassis/NOTES_v3.md`. Montage dans `docs/MONTAGE.md`. |

## 2. Simulateur

| # | Chantier | État | Détail |
|---|---|---|---|
| 2.1 | **Capteurs HC-SR04** | ✅ | Modélisés en 3D **et** simulés, miroir de `head.cpp` (cadence adaptative 200 ms/1 s, lissage sur 5, portée 150 cm, alerte 25 cm, tête). Contre-vérifié par un agent indépendant. |
| 2.2 | **Corrections de la contre-vérification** | 🔄 | Le défaut bloquant : les animations faussaient la mesure du capteur (jusqu'à 1,34 cm). Plus : un seul module au lieu de deux (fidélité à la photo), aide du panneau, seuil réel 155/164 cm, trous de l'auto-test. |
| 2.3 | **Animations du corps** | ✅ | 5 animations cosmétiques, sans jamais toucher la physique. |
| 2.4 | **Guide utilisateur** | ✅ | `docs/GUIDE-SIMULATEUR.md`, avec 6 exemples d'effets et leurs effets **mesurés**. |
| 2.5 | **Presets d'effets** | ✅ | Les 6 effets du guide sont des boutons du viewer (`sim/web/ui.js`). |
| 2.6 | **Comparaison A/B** | ✅ | Deux instances du moteur, même scénario, même graine (`ui.js`). |
| 2.7 | **Recherche automatique des gains** | ⏳ | Le simulateur explore des centaines de jeux sur les 6 scénarios et sort les meilleurs — puis validation sur le robot. |
| 2.8 | **Rejeu d'un enregistrement réel** | ⏳ 🔧 | Enregistrer l'état du robot à 200 Hz pendant un essai, puis **rejouer ce log dans le simulateur** : la règle d'or devient mesurable. Le simulateur rejoue déjà le Python à la décimale ; il reste à ingérer un log du firmware. |
| 2.9 | **Bruit du capteur réel** | ⏳ 🔧 | Mesurer le bruit de l'IMU du robot et l'injecter dans le simulateur, pour que les verdicts « tient/chute » soient ceux du vrai robot. |
| 2.10 | **Batterie simulée** | ⏳ | Chute de tension sous charge et comportement « batterie faible ». |

## 3. Comportements du robot

| # | Chantier | État | Détail |
|---|---|---|---|
| 3.1 | **Évitement d'obstacle** | ✅ 🔧 | Firmware (`10044c0`) : ralenti < 60 cm, recul doux + pivot du côté libre < 25 cm, pivot seul après 1,5 s, hystérésis 35 cm, tête qui balaie ±30° en équilibre — par les consignes seulement, **jamais** en coupant l'équilibre. Miroir dans les deux simulateurs (couche déplacement + évitement, auto-test §6-8, bouton « Démo évitement »). Le simulateur prévient : sans boucle de vitesse, recul et avance sont des accélérations constantes → chute à la saturation des roues ; à confirmer sur le robot. |
| 3.2 | **« Suis-moi »** | ⏳ | Un correcteur simple sur la distance : garder ~50 cm. |
| 3.3 | **Pilotage au téléphone** | ✅ 🔧 | Page du point d'accès : joystick, retour au neutre si le doigt se lève ou si le navigateur se tait (`tuner.cpp`). Pas rejoué sur un téléphone dans cette passe. |
| 3.4 | **Animations portées sur le robot** | ⏳ 🔧 | Les 5 animations du simulateur, exécutées par les servos réels + le visage. |

## 4. Le robot d'accueil

| # | Chantier | État | Détail |
|---|---|---|---|
| 4.1 | **Voix** | ⏳ 🔧 | Micro I²S + ampli : le B-bot devient la tête d'un assistant local. Les briques existent déjà sur l'établi. |
| 4.2 | **Pourboires Lightning** | 🔄 | QR statique sur l'écran (`TIP_LN_ADDRESS` dans `config.h`, appui court sur KEY). La facture LNbits dynamique et le « merci » ne sont pas codés. |
| 4.3 | **Comportement d'accueil** | ⏳ 🔧 | Il repère une approche (ultrason), se retourne, affiche un visage, propose quelque chose. C'est la somme de 3.1, 3.4 et 4.1. |
| 4.4 | **Tête articulée (châssis v3.2)** | ⏳ 🔧 | Le firmware pilote un pan/tilt (`SERVO_HEAD_PAN` / `TILT`) que le châssis imprimé n'a pas : le HC-SR04 est collé dans la baie haute. Le simulateur calcule le côté de l'évitement avec l'angle de pan, mais le faisceau de distance reste fixé au corps, comme la pièce imprimée. |

## 5. Matériel

| # | Chantier | État | Détail |
|---|---|---|---|
| 5.1 | **IMU moderne** | ⏳ 🔧 | Le MPU6050 est ancien (dérive, bruit). Un ICM-42688 ou BMI270 coûte quelques euros et améliore le signal à la source. |
| 5.2 | **Arrêt d'urgence du rail servos** | 🔄 🔧 | L'appui long sur BOOT coupe le **PWM** (broches à 0). Il ne coupe pas le 5 V des servos : un servo en court-circuit ou un neutre qui rampe malgré le détachement demande un interrupteur sur le rail. Voir `POWER_GUIDE.md`. La masse « 400 g » de l'ancienne note est périmée : les STL donnent ~332 g de plastique calculés, plus l'électronique. |
| 5.3 | **Encodeurs de roue** | ✖️ | **Écarté volontairement** : autant apprendre la mesure de vitesse sur un autre robot, avec du matériel qui la mérite. |

## 6. Le projet

| # | Chantier | État | Détail |
|---|---|---|---|
| 6.1 | **Dépôt public + vitrine** | ✅ | `github.com/Silexperience210/balance-bot` : photo du prototype, aperçu animé, simulateur en ligne (GitHub Pages), 12 tags. |
| 6.2 | **Licence** | ⏳ | Le dépôt public n'en a aucune : sans licence, personne ne peut légalement réutiliser le travail. |
| 6.3 | **Traçabilité des essais** | ⏳ | Journal des flashs et des jeux de gains validés (une entrée par essai réel). |

---

## Ordre conseillé

1. **1.1 + 2.2** (terminer et publier ce qui est commencé) — la CI protège tout ce qui suit.
2. **Essai au sol de 1.2, 1.3, 1.4, 1.5** : le code est là (deux cœurs, coupure PWM, mode continu, chaîne mécanique). Il reste le neutre des servos, le sens d'une roue, le palonnier réel.
3. **3.1 + 3.3** sur le robot (le téléphone et l'évitement sont codés, pas validés en vrai).
4. **2.8 + 2.9** dès qu'un essai réel est enregistré : le simulateur devient *vrai*.
5. **4.2**, la suite : le QR statique est dans le firmware. Il reste la facture dynamique et le remerciement.
6. Le reste (4.1, 4.3, 4.4, 5.1, 5.2) demande le matériel et l'imprimante.

## Ce qui demande le robot ou l'imprimante

Tout ce qui est marqué 🔧 : l'essai de mise au point réel (le robot n'a jamais été flashé avec
les corrections de la revue croisée), le log de rejeu, le bruit mesuré de l'IMU, l'arrêt
d'urgence, la tête articulée, l'IMU moderne et le volet vocal.
