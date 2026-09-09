# BalanceBot — Backlog d'amélioration (marathon jusqu'au 07/09 23h59)

Source : avis Claude Opus (analyse complète firmware + châssis).
Statuts : ⬜ à faire · 🔄 en cours · ✅ fait · ⏸ bloqué (hardware/attente)

## LOT 1 — Bugs critiques firmware ✅ (fait 07/09 ~03:00, commit e238f97)
- [x] 🔴 STOP inopérant après chute (isFallen exposé, toggle sur isEnabled réel)
- [x] Latch de commande (retour neutre si !dirHeld)
- [x] head.cpp moyenne glissante US ×5 (usAvg, amorçage, timeouts non injectés)
- [x] Pan/tilt en float, 30°/s réels, retour centre borné en vitesse
- [x] CHUTE (isFallen) vs OBST. (obstacleWarn) distincts à l'écran
- [x] Signe du pitch explicite sous 1°
- [x] Head::begin() réel (servo.attached() → « TÊTE+US : ÉCHEC »)
- [x] Batterie : −1 hors plage (= USB seul), isLow() seuil 3.5V, batteryLow
- [x] setStatusLine/g_statusLine supprimés partout
- [x] Hygiène : firmware/ + calibration/ supprimés, code mort Wheels retiré

## LOT 2 — Actionneur en position ✅ (feet.cpp, commit faa1994 — 07/09 ~03:30)
- [x] feet.cpp : pilotage ANGLE DE PIED (servos SG90 std, µs 500-2500, float,
      butée dure ±45°, trims kTrimDegL/R, dt réel borné)
- [x] shapeOutput supprimé ; soft clamp dynamique (90−|θ|−9°, taper 10°)
- [x] Recentrage 2 Hz (adouci Lot 2b : trim ±0.4°, 0.10°/s) ; panic > 35°
- [x] footLDeg/footRDeg dans BotState + « PIED P:+0 deg » à l'écran
- [x] wheels.cpp/h supprimés

## LOT 2b — Gains PID ~~validés~~ par SIMULATION ⚠️ INVALIDÉ (revue 09/09)
- [x] Simulateur 1D rejouable (sim/balancebot_sim.py) : prouve Ki > g/R ≈ 300
      requis — le Ki=20 hérité du design « roues » ne pouvait PAS tenir debout
- [x] Gains appliqués : Kp 8→25, Ki 20→500, Kd 0.35→0.5
- [x] Recentrage adouci pour le 1er test (trim ±1→±0.4°, rate 0.3→0.1°/s)
- [x] Fragilité du trim d'angle documentée (balancebot penché = accélère)
- [x] TEST_PROTOCOL.md : protocole complet du premier essai debout
- [ ] ⚠️ **REVUE 09/09 : la « validation » ne tient pas.** Le simulateur ne
      modélisait ni la cascade, ni le roulement exact, et son autorité était
      57× trop forte (cf. commit 19535f7). Modèle corrigé + cascade portée :
      **0/6 scénarios** pour Kp25/Ki500/Kd0.5, et **aucun** jeu du balayage
      (Kp 0,5-100 / Ki 350-2000 / Kd 0,2-20) ne tient. À re-régler au banc web
      sur le robot réel — voir FIRMWARE_REVIEW.md §1bis.
- [ ] Cascade de recentrage : **signe de la boucle interne était inversé**
      (poussait le pied vers la butée) — corrigé, gains à régler en réel.

## ⏭ Prochaines étapes (dépendent du TEST RÉEL)
- [ ] Lot 3 : alim séparée servos (BEC/power bank 5V + GND commun) — Silex
- [ ] Test réel : signe câblage, neutre, équilibre tenu → lâcher
- [ ] Réglage fin gains sur le robot (tableau dans TEST_PROTOCOL.md)
- [ ] Lot 4 : FreeRTOS (équilibre cœur 0) — APRÈS stabilisation réelle
- [x] Lot 5 : banc de réglage web (commit 7d59c75) — AP BalanceBot-Tune,
      page sliders + télémétrie, TESTÉ RUNTIME par Hermes (HTTP 200, state
      JSON OK, POST gains kp 25→30→25 OK, hz 198 avec tuner actif)
- [ ] Lot 6 : ToF VL53L1X (achat ~5 €)
- [ ] Lot 7 : LQR + Kalman

## LOT 3 — Alimentation servos (hardware, à faire par Silex en parallèle)
- [ ] Rail 5-6V séparé (2S+BEC ou boost 5V/3A), masse commune, 470-1000 µF près
      des servos. Cause n°1 des brownouts (déjà observé au test servo).

## LOT 4 — Temps réel (FreeRTOS)
- [ ] Équilibre sur cœur 0 (xTaskCreatePinnedToCore, vTaskDelayUntil, 100 Hz
      aligné SG90), UI/tête/batterie sur cœur 1.
- [ ] pulseIn → capture par interruption (fronts sur ECHO + micros()) ou ToF.
- [ ] Accès g_state : volatile / double-buffer sur les champs partagés.
- [ ] 200 Hz → 100 Hz (les SG90 ne prennent une consigne que toutes les 20 ms).

## LOT 5 — Réglage & adhérence
- [ ] Télémétrie en direct (série 921600 ou WiFi) + gains PID modifiables à chaud.
- [ ] Bande de roulement : TPU/silicone/gaine thermo sur la jante 3,2 mm du
      foot_arc (le PLA lisse glisse).

## LOT 6 — Capteur ToF (achat ~5 €)
- [ ] Remplacer HC-SR04 par VL53L1X (I2C, 50 Hz, supprime pulseIn + diviseur
      + 25 g en haut du mât). Simplifie sensor_mount. Balayage polaire possible.

## LOT 7 — Contrôleur d'état
- [ ] LQR (4 états, position base = R·φ connue exactement) + Kalman 2 états
      (angle + biais gyro) à la place du filtre complémentaire.

## Châssis / divers
- [ ] Prévoir lumière N20+encodeurs dans body_a/body_b (migration future sans
      reconception).
- [ ] README racine du projet + CI qui rejoue gen_chassis.py + verify_chassis.py.
- [ ] Ajouter photos des pièces imprimées au repo.

## Notes marathon
- Fenêtres budget Claude découvertes : ~16h30-17h35, 21h30-22h30+ (durées ~1h,
  le reset est annoncé en fin de session : « resets H:MM »).
- Règle : brief par lot → lancement au créneau → vérification Hermes (compile,
  verify, tests) → flash + validation utilisateur quand pertinent → commit.
