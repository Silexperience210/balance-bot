# BalanceBot — Backlog d'amélioration (marathon jusqu'au 07/09 23h59)

Source : avis Claude Opus (analyse complète firmware + châssis).
Statuts : ⬜ à faire · 🔄 en cours · ✅ fait · ⏸ bloqué (hardware/attente)

## LOT 1 — Bugs critiques firmware (demi-journée, tout localisé)
- [ ] 🔴 STOP inopérant après chute : le toggle UI pilote `g_state.balancing`
      (remis à false par halt()) au lieu de `cmdEnabled`/`s_enabled` → le robot
      se ré-engage seul 700 ms après redressement. Ajouter Balance::isFallen().
- [ ] Latch de commande : retour au neutre seulement si !g_touchedRaw → le doigt
      qui glisse hors du bouton laisse cmdForward=100. Évaluer la zone tenue
      même doigt posé.
- [ ] head.cpp:124 moyenne glissante US : `usSum += d - usSum/N` → point fixe 5·d
      (distance ×5, obstacleWarn à 5 cm réels). Correctif : `usSum += (d-usSum)/N`.
- [ ] head.cpp:186 headPanDeg en int + incrément 0.99 → pan jamais bougé.
      Passer la position en float (ou incrément ≥ 1°).
- [ ] ui.cpp:316-326 : obstacleWarn affiché « CHUTE » au lieu de l'état réel ;
      exporter s_fallen et afficher « CHUTE » seulement pour la vraie chute.
- [ ] ui.cpp:286 : signe du pitch perdu sous 1° (−0.5° → « 0.5 »). Corriger le
      formatage.
- [ ] head.cpp:81 : Head::begin() retourne toujours true (« TÊTE+US : ÉCHEC »
      mort). Détecter un vrai échec. Head::scan() no-op.
- [ ] battery.cpp:30 : 0.0V hors plage indistinguable d'une panne ; aucune
      action batterie basse.
- [ ] setStatusLine vs ligne debug y=54 : se recouvrent (setStatusLine inutilisé,
      le supprimer ou le fusionner).
- [ ] Hygiène : doublons firmware/config.h+interfaces.h figés (supprimer),
      calibration 240×320 obsolète (mettre à jour ou retirer), code mort à
      marquer (Wheels::drive, lastLeftUs).

## LOT 2 — Actionneur en position (feet.cpp) — le cœur
- [ ] Remplacer wheels.cpp (vitesse servo continu) par un pilotage en ANGLE DE
      PIED φ (servos standards), sortie PID = vitesse de pied intégrée,
      saturation |φ| ≤ 90−|θ|−marge.
- [ ] Supprimer shapeOutput (saut 0→8 = impulsion 4,5 mm nuisible).
- [ ] Boucle externe lente : recentrage de φ vers 0 via le setpoint de tangage.
- [ ] Publier φ dans BotState + l'afficher à l'écran.
- [ ] Réglage PID sur le robot (Kp/Ki/Kd adaptés au mode position).

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
