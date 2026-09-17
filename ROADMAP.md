# Feuille de route — B-bot

Objectif : faire du B-bot un robot **qui tient, qui voit, qui réagit, et qui accueille** —
sans jamais perdre la loi du projet :

> **Le simulateur et le firmware doivent dire la même chose.**

Statuts : ✅ fait · 🔄 en cours · ⏳ à faire · 🔧 demande le robot ou l'imprimante sous la main.

---

## 1. Fondations

| # | Chantier | État | Détail |
|---|---|---|---|
| 1.1 | **CI « règle d'or »** | ✅ | `scripts/verifier-regle-or.py` compare les constantes du firmware (`config.h`, `head.cpp`) à celles des deux simulateurs, et `BALANCE_LOOP_HZ` à leur pas de temps. `.github/workflows/verifier.yml` le lance, plus l'auto-test du simulateur, la vérification que le bundle mono-fichier est à jour, l'absence de ressource externe, et la compilation du firmware. |
| 1.2 | **Deux cœurs** | 🔄 | La mesure ultrason bloque jusqu'à 9,5 ms pour un pas d'équilibre de 5 ms : la boucle saute un à deux pas à chaque mesure. Équilibre sur le cœur 0 (priorité haute), écran/tête/tuner sur le cœur 1, avec une compilation de repli mono-cœur. |
| 1.3 | **Arrêt sûr** | 🔄 | Roues coupées à la chute, surveillance de blocage de la boucle, et arrêt d'urgence matériel (bouton BOOT en appui long). |
| 1.4 | **Mode d'actionneur correct** | 🔄 | `FEET_MODE_CONTINUOUS` vaut 0 (servos 180°) alors que le robot a des **servos 360° continus** : c'est la divergence que le CI attrape désormais. |

## 2. Simulateur

| # | Chantier | État | Détail |
|---|---|---|---|
| 2.1 | **Capteurs HC-SR04** | ✅ | Modélisés en 3D **et** simulés, miroir de `head.cpp` (cadence adaptative 200 ms/1 s, lissage sur 5, portée 150 cm, alerte 25 cm, tête). Contre-vérifié par un agent indépendant. |
| 2.2 | **Corrections de la contre-vérification** | 🔄 | Le défaut bloquant : les animations faussaient la mesure du capteur (jusqu'à 1,34 cm). Plus : un seul module au lieu de deux (fidélité à la photo), aide du panneau, seuil réel 155/164 cm, trous de l'auto-test. |
| 2.3 | **Animations du corps** | ✅ | 5 animations cosmétiques, sans jamais toucher la physique. |
| 2.4 | **Guide utilisateur** | ✅ | `docs/GUIDE-SIMULATEUR.md`, avec 6 exemples d'effets et leurs effets **mesurés**. |
| 2.5 | **Presets d'effets** | ⏳ | Les 6 effets du guide en boutons, au lieu d'être recopiés en JavaScript. |
| 2.6 | **Comparaison A/B** | ⏳ | Deux jeux de gains côte à côte, même scénario, même graine. |
| 2.7 | **Recherche automatique des gains** | ⏳ | Le simulateur explore des centaines de jeux sur les 6 scénarios et sort les meilleurs — puis validation sur le robot. |
| 2.8 | **Rejeu d'un enregistrement réel** | ⏳ 🔧 | Enregistrer l'état du robot à 200 Hz pendant un essai, puis **rejouer ce log dans le simulateur** : la règle d'or devient mesurable. Le simulateur rejoue déjà le Python à la décimale ; il reste à ingérer un log du firmware. |
| 2.9 | **Bruit du capteur réel** | ⏳ 🔧 | Mesurer le bruit de l'IMU du robot et l'injecter dans le simulateur, pour que les verdicts « tient/chute » soient ceux du vrai robot. |
| 2.10 | **Batterie simulée** | ⏳ | Chute de tension sous charge et comportement « batterie faible ». |

## 3. Comportements du robot

| # | Chantier | État | Détail |
|---|---|---|---|
| 3.1 | **Évitement d'obstacle** | 🔄 | Le firmware calcule déjà l'angle où l'obstacle a été vu et ne s'en sert jamais. Réaction par la consigne de dérive, **jamais** en coupant l'équilibre. Miroir dans le simulateur ensuite. |
| 3.2 | **« Suis-moi »** | ⏳ | Un correcteur simple sur la distance : garder ~50 cm. |
| 3.3 | **Pilotage au téléphone** | ⏳ | Une page de conduite tactile dans le point d'accès `BalanceBot-Tune` qui existe déjà. |
| 3.4 | **Animations portées sur le robot** | ⏳ 🔧 | Les 5 animations du simulateur, exécutées par les servos réels + le visage. |

## 4. Le robot d'accueil

| # | Chantier | État | Détail |
|---|---|---|---|
| 4.1 | **Voix** | ⏳ 🔧 | Micro I²S + ampli : le B-bot devient la tête d'un assistant local. Les briques existent déjà sur l'établi. |
| 4.2 | **Pourboires Lightning** | ⏳ | Le corps **est** un ₿ : facture LNbits affichée en QR sur l'écran, et un merci quand les sats tombent. Le LNbits et la boutique sont déjà en place. |
| 4.3 | **Comportement d'accueil** | ⏳ 🔧 | Il repère une approche (ultrason), se retourne, affiche un visage, propose quelque chose. C'est la somme de 3.1, 3.4 et 4.1. |
| 4.4 | **Tête articulée (châssis v3.2)** | ⏳ 🔧 | Le firmware pilote un pan/tilt que le châssis n'a pas : une tête porteuse (écran + capteurs) rendrait le balayage et les animations réellement visibles. C'est aussi la seule limite que le simulateur déclare. |

## 5. Matériel

| # | Chantier | État | Détail |
|---|---|---|---|
| 5.1 | **IMU moderne** | ⏳ 🔧 | Le MPU6050 est ancien (dérive, bruit). Un ICM-42688 ou BMI270 coûte quelques euros et améliore le signal à la source. |
| 5.2 | **Arrêt d'urgence** | 🔄 | Bouton matériel qui coupe le rail des servos. Un robot qui tient debout finira par tomber : 400 g de PETG sur une table, ça casse. |
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
2. **1.2 + 1.3 + 1.4** (les deux cœurs, l'arrêt sûr, le mode correct) : c'est ce qui rend les essais réels fiables.
3. **3.1 + 3.3** (évitement + pilotage téléphone) : le robot devient vivant et manœuvrable.
4. **2.8 + 2.9** dès qu'un essai réel est enregistré : le simulateur devient *vrai*.
5. **4.2** (pourboires Lightning) : le plus fort rapport effet/effort de tout le volet « accueil ».
6. Le reste (4.1, 4.3, 4.4, 5.1, 5.2) demande le matériel et l'imprimante.

## Ce qui demande le robot ou l'imprimante

Tout ce qui est marqué 🔧 : l'essai de mise au point réel (le robot n'a jamais été flashé avec
les corrections de la revue croisée), le log de rejeu, le bruit mesuré de l'IMU, l'arrêt
d'urgence, la tête articulée, l'IMU moderne et le volet vocal.
