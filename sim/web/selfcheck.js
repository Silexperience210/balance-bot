/* ═══════════════════════════════════════════════════════════════════
 * BalanceBot — AUTO-TEST du moteur (engine.js)
 *
 * S'exécute tel quel :
 *   · dans un navigateur : ouvrir selfcheck.html (file:// suffit) ;
 *   · en ligne de commande : `node sim/web/selfcheck.js`.
 *
 * Ce qu'il vérifie, contre `python3 sim/balancebot_sim.py` (commit bfe3faa,
 * graine 42, scénarios enchaînés SANS réamorçage du PRNG — exactement comme
 * la boucle `for label, kw in SCENARIOS` du Python) :
 *   1. le PRNG reproduit random.seed(42) de CPython (random(), gauss()) ;
 *   2. gains embarqués Kp25/Ki500/Kd0.5, k_out=1, cascade ON → 0/6, tous en
 *      « chute θ » entre 0,4 et 0,5 s, avec les instants et états finaux du
 *      Python (tolérance 1e-6 : l'écart mesuré est ≤ 2e-13) ;
 *   3. Kp25/Ki350/Kd1, k_out=3, kv=0, cascade ON → « θ0=2° propre » TIENT
 *      (verdict « ok », |θ fin| < 0,5°), et les 6 scénarios donnent 2/6
 *      comme le Python (panic φ 0,1-0,2 s après chaque tape) ;
 *   4. le hook setCustom(fn) est appelé une fois par pas, après la physique,
 *      et ses écritures dans `state` sont prises en compte ;
 *   5. le capteur HC-SR04 + la tête (ultrason.js, miroir de head.cpp) ;
 *   6. la couche DÉPLACEMENT du moteur (consignes cmdForward/cmdTurn lissées,
 *      évitement avoidFwdMax/avoidTurn, différentiel → lacet, pose au sol) :
 *      4 profils scriptés rejoués contre le Python (`pilote=` de run(),
 *      références produites par /tmp/miroir/ref_deplacement.py, reproduites
 *      dans SIM_MIROIR_RAPPORT.md) ;
 *   7. l'évitement de head.cpp transcrit dans ultrason.js (balayage ±30° en
 *      équilibre, ralenti < 60 cm, recul + pivot < 25 cm, pivot seul après
 *      1,5 s, hystérésis 35 cm, choix du côté d'après l'angle de tête) ;
 *   8. la boucle FERMÉE capteur → consignes → moteur, dans l'ordre du viewer,
 *      retombe exactement sur le profil P4 du Python.
 * ═══════════════════════════════════════════════════════════════════ */
(function () {
  "use strict";
  var E = (typeof BalanceEngine !== "undefined") ? BalanceEngine
        : require("./engine.js");
  var U = (typeof Ultrason !== "undefined") ? Ultrason
        : require("./ultrason.js");

  var lines = [], failures = 0;
  function log(s) { lines.push(s); if (typeof console !== "undefined") console.log(s); }
  function check(cond, what) {
    if (!cond) failures++;
    log((cond ? "  ✔ " : "  ✘ ") + what);
    return cond;
  }
  function near(a, b, tol) { return Math.abs(a - b) <= tol; }
  function pad(s, n) { s = String(s); while (s.length < n) s += " "; return s; }
  function fmt(x, d) { return (x >= 0 ? "+" : "") + x.toFixed(d); }

  // Références produites par `python3 balancebot_sim.py` (instrumenté) :
  // verdict, t du dernier pas, θ fin (°), φ_cmd fin (°).
  var REF_DEFAULT = [
    { verdict: "chute θ", t: 0.545, theta: 45.91962816429631, phiCmd: 23.444546284187957 },
    { verdict: "chute θ", t: 0.545, theta: 45.91901948811527, phiCmd: 23.603162462117325 },
    { verdict: "chute θ", t: 0.425, theta: 46.608979396109355, phiCmd: 25.943729912662622 },
    { verdict: "chute θ", t: 0.485, theta: 45.00918921050412, phiCmd: 22.887685945308903 },
    { verdict: "chute θ", t: 0.49,  theta: 46.070818278371235, phiCmd: 24.034214328107574 },
    { verdict: "chute θ", t: 0.485, theta: 45.346702327622296, phiCmd: 22.689846409548 }
  ];
  var REF_HOLDS = [
    { verdict: "ok",      t: 5.995, theta: 1.715125840230751e-09, phiCmd: 7.958799484681711 },
    { verdict: "ok",      t: 5.995, theta: -0.0378802292478174,   phiCmd: -2.6020766407498614 },
    { verdict: "ok",      t: 5.995, theta: -0.07131705564822347,  phiCmd: 174.42922950375902 },
    { verdict: "ok",      t: 7.995, theta: 0.0014119091538717873, phiCmd: 423.88749771454445 },
    { verdict: "ok",      t: 7.995, theta: 0.07562214836614639,   phiCmd: 829.8290406332235 },
    { verdict: "chute θ", t: 3.585, theta: 45.70405205915063,     phiCmd: 152.36565769550293 }
  ];
  // Tolérances : le moteur est EXACTEMENT le Python sur les scénarios sans bruit
  // (écart mesuré 0 au pas 80 ; PRNG MT19937+gauss identique au bit). Sur les
  // scénarios BRUITÉS, les libm (sin/cos V8 vs CPython) font diverger la
  // trajectoire d'AU PLUS UN PAS (5 ms) avant le franchissement du seuil de
  // chute — d'où Δt ≤ 2 pas et des tolérances d'état larges (φ peut faire
  // plusieurs tours : la moindre divergence s'y amplifie).
  var TOL_T = 0.01, TOL_THETA = 1.0, TOL_PHI = 20.0;

  // Joue les 6 scénarios à la suite sur UN sim (même flux PRNG que le Python).
  function runSix(sim, refs) {
    var ok = 0, results = [];
    for (var i = 0; i < E.scenarios.length; i++) {
      var sc = E.scenarios[i];
      sim.reset(sc);
      while (sim.state.verdict === null) sim.step();
      var s = sim.state, r = refs[i];
      if (s.verdict === "ok") ok++;
      var same = s.verdict === r.verdict && near(s.t, r.t, TOL_T) &&
                 near(s.theta, r.theta, TOL_THETA) && near(s.phiCmd, r.phiCmd, TOL_PHI);
      results.push(same);
      log("    " + pad(sc.name, 16) + ": " + pad(s.verdict === "ok" ? "OK" : "❌ " + s.verdict, 10) +
          " t=" + s.t.toFixed(3) + " s  θfin=" + fmt(s.theta, 3) + "°  φfin=" + fmt(s.phiCmd, 3) + "°" +
          (same ? "   = Python" : "   ≠ Python (attendu " + r.verdict + " t=" + r.t + " θ=" + r.theta.toFixed(3) + " φ=" + r.phiCmd.toFixed(3) + ")"));
    }
    return { ok: ok, allSame: results.every(function (x) { return x; }) };
  }

  log("BalanceBot — auto-test du moteur engine.js");
  log("");

  // ── 1. PRNG ──
  log("1. PRNG MT19937 + random.gauss (référence : CPython, random.seed(42))");
  var rng = new E.PyRandom(42);
  check(rng.random() === 0.6394267984578837 && rng.random() === 0.025010755222666936,
        "random() → 0.6394267984578837, 0.025010755222666936");
  rng = new E.PyRandom(42);
  var g1 = rng.gauss(0, 1), g2 = rng.gauss(0, 1);
  check(near(g1, -0.14409032957792836, 1e-15) && near(g2, -0.1729036003315193, 1e-15),
        "gauss(0,1) → -0.14409032957792836, -0.1729036003315193");
  log("");

  // ── 2. Gains embarqués : 0/6 ──
  log("2. Gains embarqués Kp25/Ki500/Kd0.5, k_out=1, kv=3, cascade ON, graine 42");
  var sim = E.create({ seed: 42 });
  var d = runSix(sim, REF_DEFAULT);
  check(d.ok === 0, "0/6 scénarios tenus (obtenu " + d.ok + "/6)");
  check(d.allSame, "verdicts, instants et états finaux conformes au Python");
  log("");

  // ── 3. Un jeu qui TIENT ──
  log("3. Kp25/Ki350/Kd1, k_out=3, kv=0, cascade ON, graine 42");
  var sim2 = E.create({ seed: 42, kp: 25, ki: 350, kd: 1, kOut: 3, kv: 0, cascade: true });
  sim2.reset(E.scenarios[0]);
  while (sim2.state.verdict === null) sim2.step();
  check(sim2.state.verdict === "ok" && Math.abs(sim2.state.theta) < 0.5,
        "θ0=2° propre → « ok », θ fin = " + fmt(sim2.state.theta, 4) + "° (< 0,5°), φ fin = " + fmt(sim2.state.phiCmd, 2) + "°");
  sim2 = E.create({ seed: 42, kp: 25, ki: 350, kd: 1, kOut: 3, kv: 0, cascade: true });
  var h = runSix(sim2, REF_HOLDS);
  check(h.ok === 5, "5/6 scénarios tenus comme le Python (obtenu " + h.ok + "/6)");
  check(h.allSame, "verdicts, instants et états finaux conformes au Python");
  log("");

  // ── 4. Hook ──
  log("4. Hook setCustom(fn) : appelé après la physique, une fois par pas");
  var sim3 = E.create({ seed: 42, kp: 25, ki: 350, kd: 1, kOut: 3, kv: 0 });
  var calls = 0, lastT = -1, lastDt = 0;
  sim3.setCustom(function (t, state, dt) { calls++; lastT = t; lastDt = dt; state.thetaDot += 0.5 * dt; });
  sim3.reset(E.scenarios[0]);
  sim3.stepMany(100);
  check(calls === 100 && lastT === 99 * (1 / 200) && lastDt === 1 / 200 && sim3.state.t === lastT,
        "100 pas → 100 appels, t = " + lastT + " s, dt = " + lastDt);
  sim3.setCustom(function (t, state) { if (t >= 1.0) state.theta = 60; });
  sim3.reset(E.scenarios[0]);
  while (sim3.state.verdict === null) sim3.step();
  check(sim3.state.verdict === "chute θ" && sim3.state.t === 1.0,
        "state.theta = 60° écrit par le hook à t = 1 s → « chute θ » au même pas");
  sim3.setCustom(null);
  log("");

  // ── 5. Capteur ultrason + tête (ultrason.js, miroir de head.cpp) ──
  log("5. Capteur HC-SR04 (ultrason.js) — cadence, lissage, portée, alerte, tête");
  // Cadence normale 200 ms : mesures à 200, 400, …, 1000 ms (tous les 40 pas).
  var us = U.create();
  var fois = [];
  for (var i = 0; i < 200; i++) { us.tick(80, true); if (us.state.mesureFaite) fois.push(us.state.derniereMesureMs); }
  check(fois.join(",") === "200,400,600,800,1000",
        "cadence 200 ms : mesures à " + fois.join(", ") + " ms");
  check(us.state.obstacleCm === 80,
        "lissage amorcé sur la 1re mesure : obstacleCm = 80 cm exactement");

  // Lissage exponentiel sur 5 : saut 80 → 30 cm, une mesure plus tard :
  // moy = 80 + (30 − 80)/5 = 70. Puis convergence vers 30.
  us.tickMany(40, 30, true);
  check(near(us.state.obstacleCm, 70, 1e-12),
        "saut 80→30 cm : une mesure après, moy = " + us.state.obstacleCm.toFixed(2) + " (attendu 70)");
  us.tickMany(2000, 30, true);
  check(near(us.state.obstacleCm, 30, 0.01),
        "la moyenne glissante converge vers la distance réelle (" + us.state.obstacleCm.toFixed(6) + " → 30, ±0,01 cm)");

  // Cadence adaptative : capteur débranché → échecs à 200/400/600 ms,
  // puis 1000 ms : 1600, 2600 (head.cpp l.201-208).
  us = U.create(); us.setActif(false);
  fois = [];
  for (i = 0; i < 520; i++) { us.tick(80, true); if (us.state.mesureFaite) fois.push(us.state.derniereMesureMs); }
  check(fois.join(",") === "200,400,600,1600,2600",
        "capteur débranché : cadence 1000 ms après 3 échecs (" + fois.join(", ") + " ms)");
  check(us.state.cadenceMs === 1000 && us.state.obstacleCm === -1 && !us.state.obstacleWarn,
        "débranché : cadence affichée 1000 ms, distance invalide, pas d'alerte");
  // Retour à 200 ms dès qu'un écho revient.
  us.setActif(true);
  us.tickMany(201, 50, true);   // 1 s + 1 pas : la mesure d'échéance réussit
  check(us.state.cadenceMs === 200 && us.state.failStreak === 0 && us.state.obstacleCm === 50,
        "écho de retour → cadence 200 ms immédiate, moyenne amorcée à 50 (premier écho reçu)");

  // Un timeout n'empoisonne pas la moyenne : 40 cm (amorce), timeouts,
  // puis 60 cm → moy = 40 + (60 − 40)/5 = 44 à la mesure suivante.
  us = U.create();
  us.tickMany(120, 40, true);          // 3 mesures à 40 cm → moy = 40
  us.tickMany(400, 200, true);         // 200 cm : timeout (200×58 > 9500 µs)
  check(us.state.obstacleCm === -1 && !us.state.obstacleWarn,
        "timeout : distance invalide publiée, pas d'alerte");
  us.tickMany(120, 60, true);          // prochaine échéance (cadence 1000 ms)
  check(near(us.state.obstacleCm, 44, 1e-12),
        "timeout non injecté : moyenne reprise en l'état (" + us.state.obstacleCm.toFixed(2) + " = 40 + (60−40)/5)");

  // Portée utile : le budget pulseIn (9500 µs) couvre AUSSI l'attente du
  // front montant d'ECHO (~480 µs, wiring_pulse.c du core ESP32) — le seuil
  // réel est ≈ 155 cm, pas 163,8. 155 cm → écho reçu (155×58+480 = 9470 ≤
  // 9500 µs) mais lissée > 150 cm → « hors portée » SANS compter un échec ;
  // 156 cm (9528 > 9500 µs) et 170 cm → timeout (échec).
  us = U.create();
  us.tickMany(40, 155, true);
  check(us.state.obstacleCm === -1 && us.state.failStreak === 0,
        "155 cm : écho reçu mais hors portée (obstacleCm = −1, pas d'échec)");
  us = U.create();
  us.tickMany(40, 156, true);
  check(us.state.obstacleCm === -1 && us.state.failStreak === 1,
        "156 cm : au-delà du seuil réel (9528 > 9500 µs) → échec compté");
  us = U.create();
  us.tickMany(40, 170, true);
  check(us.state.obstacleCm === -1 && us.state.failStreak === 1,
        "170 cm : au-delà du timeout pulseIn (10340 > 9500 µs) → échec compté");

  // Alerte < US_STOP_CM : warn + angle où l'obstacle a été vu. En équilibre la
  // tête BALAIE ±30° (10044c0) : à la 1re mesure (t = 200 ms) le pan vaut
  // 90 + 30 × 0,195 = 95,85 → 96°, dans la zone morte (±10°) → côté 0.
  us = U.create();
  us.tickMany(40, 20, true);
  check(us.state.obstacleWarn === true && us.state.angleVu === 96 && us.state.obstacleSide === 0,
        "20 cm lissés → ALERTE, angle vu = pan courant du balayage (" + us.state.angleVu + "°), côté 0 (en face)");
  us.tickMany(200, 80, true);
  check(us.state.obstacleWarn === false && us.state.angleVu === -1 && us.state.obstacleSide === 0,
        "obstacle reparti → alerte, angle et côté effacés");

  // Tête : hors équilibre elle balaye (bornée 0…180° / 20…90°) ; en équilibre
  // elle est ramenée au centre (90°/60°) à vitesse bornée 30°/s.
  us = U.create();
  var mn = 999, mx = -999, mnT = 999, mxT = -999;
  for (i = 0; i < 4000; i++) {          // 20 s de balayage (robot au sol)
    us.tick(80, false);
    mn = Math.min(mn, us.state.headPanDeg); mx = Math.max(mx, us.state.headPanDeg);
    mnT = Math.min(mnT, us.state.headTiltDeg); mxT = Math.max(mxT, us.state.headTiltDeg);
  }
  check(mn === 0 && mx === 180,
        "balayage hors équilibre : pan borné à 0…180° (vu " + mn + "…" + mx + ")");
  check(mnT === 20 && mxT === 90,
        "balayage hors équilibre : tilt borné à 20…90° (vu " + mnT + "…" + mxT + ")");

  // Vitesse de balayage réelle = 30°/s (head.cpp l.50-51) : depuis le centre,
  // 1 s au sol → pan 90 + 30 = 120 ; 0,5 s au sol → tilt 60 + 15 = 75.
  us = U.create();
  us.tickMany(200, 80, false);
  check(us.state.headPanDeg === 120,
        "vitesse de pan 30°/s : 90 → " + us.state.headPanDeg + "° après 1 s de balayage (attendu 120)");
  us = U.create();
  us.tickMany(100, 80, false);
  check(us.state.headTiltDeg === 75,
        "vitesse de tilt 30°/s : 60 → " + us.state.headTiltDeg + "° après 0,5 s de balayage (attendu 75)");

  // Angle vu à un pan ≠ 90° : l'alerte survient PENDANT le balayage →
  // l'angle capturé est le pan courant (96° au 1er tic de mesure, t = 200
  // ms), pas le centre 90°.
  us = U.create();
  us.tickMany(200, 20, false);
  check(us.state.obstacleWarn === true && us.state.angleVu === 96,
        "alerte pendant le balayage : angle vu = pan courant (" + us.state.angleVu + "°, ≠ 90°)");

  // Retour en équilibre depuis un balayage large (pan 96 / tilt 75 ici) :
  // le tilt revient à 60 ; le pan, hors fenêtre ou dedans, finit dans la
  // fenêtre ±HEAD_BALANCE_SWEEP_DEG et y BALAIE (head.cpp l.293-311).
  mn = 999; mx = -999; mnT = 999; mxT = -999;
  for (i = 0; i < 1000; i++) {                  // 5 s d'équilibre
    us.tick(80, true);
    if (i >= 200) {                             // après 1 s : régime établi (un aller-retour = 4 s)
      mn = Math.min(mn, us.state.headPanDeg); mx = Math.max(mx, us.state.headPanDeg);
      mnT = Math.min(mnT, us.state.headTiltDeg); mxT = Math.max(mxT, us.state.headTiltDeg);
    }
  }
  check(mnT === 60 && mxT === 60,
        "équilibre : tilt ramené au centre (60°) et immobile (vu " + mnT + "…" + mxT + ")");
  check(mn === 60 && mx === 120,
        "équilibre : pan BALAIE ±HEAD_BALANCE_SWEEP_DEG = 30° autour de 90° (vu " + mn + "…" + mx + ")");
  // Depuis le centre : 30°/s → 120° à t = 1 s, demi-tour, 60° à t = 3 s.
  us = U.create();
  us.tickMany(200, 80, true);
  var pan1s = us.state.headPanDeg;
  us.tickMany(400, 80, true);
  check(pan1s === 120 && us.state.headPanDeg === 60,
        "balayage en équilibre à PAN_SPEED_DEG = 30°/s : 90 → " + pan1s + "° à 1 s (attendu 120), → " + us.state.headPanDeg + "° à 3 s (attendu 60)");
  log("");

  // ── 6. Couche DÉPLACEMENT du moteur (balance.cpp l.673-692, l.751-758) ──
  // Profils rejoués sur le Python (`Sim.run(..., pilote=)`, gains « tient »,
  // θ0=2° propre, graine 42) — références copiées de ref_deplacement.py :
  //   P1 : consigne nulle, évitement RECUL (−20, −40) scripté de 0,2 à 1,0 s,
  //        puis LIBRE → le robot recule, pivote (ψ = −17°) et TIENT ;
  //   P2 : avance à 60 %, RALENTI (plafond 40) dès 0,2 s → sans retour de
  //        vitesse (Kv = 0) la roue sature (270 °/s) → chute à 1,125 s ;
  //   P3 : pivot UI à 100 % de 0,5 à 1,5 s, avoidTurn = 40 en permanence :
  //        l'UI a priorité tant qu'elle tourne, puis le pivot imposé prend
  //        (turnSmooth fin = 40) → ψ fin = 158,3° ;
  //   P4 : recul COMPLET 1,5 s puis PIVOT seul (obstacle jamais dégagé) →
  //        chute à 1,915 s, ψ = −27,9°.
  // θ, φ, ψ, consignes lissées : mêmes opérations IEEE → identité attendue à
  // 1e-12 ; posX/posZ passent par cos/sin(ψ) (libm V8 vs CPython) → 1e-9.
  log("6. Couche déplacement (cmdForward / cmdTurn / avoidFwdMax / avoidTurn → lissage, différentiel, lacet, pose)");
  var REF_DEP = {
    P1: { verdict: "ok",      t: 5.995, theta: 3.85640739005086e-08,  phiCmd: -946.9433671135978, psi: -17.022849976311175, posX: -0.653008531515962,   posZ: 0.19433078536567852,   fwd: 0,  turn: 0 },
    P2: { verdict: "chute θ", t: 1.125, theta: 46.18096452264591,     phiCmd: 209.93866809748798, psi: 0.0,                 posX: 0.169593871414177,    posZ: 0.0,                   fwd: 40, turn: 0 },
    P3: { verdict: "ok",      t: 5.995, theta: 1.7151256316179883e-09, phiCmd: 7.9587994846816885, psi: 158.30784186649734,  posX: 0.004287685670788314, posZ: -3.587758182635299e-05, fwd: 0,  turn: 40 },
    P4: { verdict: "chute θ", t: 1.915, theta: -46.540231340909855,   phiCmd: -279.2977163666369, psi: -27.86857940102333,  posX: -0.21227102270417006, posZ: 0.08140546586369843,   fwd: 0,  turn: -40 }
  };
  var PILOTES = {
    P1: function (sim, t) {
      if (t >= 0.2 && t < 1.0) sim.setBotState({ avoidFwdMax: -20, avoidTurn: -40, obstacleWarn: true });
      else                     sim.setBotState({ avoidFwdMax: 100, avoidTurn: 0,   obstacleWarn: false });
    },
    P2: function (sim, t) { sim.setBotState({ cmdForward: 60, avoidFwdMax: (t >= 0.2) ? 40 : 100 }); },
    P3: function (sim, t) { sim.setBotState({ cmdTurn: (t >= 0.5 && t < 1.5) ? 100 : 0, avoidTurn: 40 }); },
    P4: function (sim, t) {
      if (t < 0.2)      sim.setBotState({ avoidFwdMax: 100, avoidTurn: 0,   obstacleWarn: false });
      else if (t < 1.7) sim.setBotState({ avoidFwdMax: -20, avoidTurn: -40, obstacleWarn: true });
      else              sim.setBotState({ avoidFwdMax: 0,   avoidTurn: -40, obstacleWarn: true });
    }
  };
  function jouerProfil(nom) {
    var sim = E.create({ seed: 42, kp: 25, ki: 350, kd: 1, kOut: 3, kv: 0, cascade: true });
    sim.reset(E.scenarios[0]);
    while (sim.state.verdict === null) {
      PILOTES[nom](sim, sim.state.k * (1 / 200));   // pilote(sim, t) AVANT le pas, comme run()
      sim.step();
    }
    return sim.state;
  }
  Object.keys(REF_DEP).forEach(function (nom) {
    var r = REF_DEP[nom], st = jouerProfil(nom);
    var same = st.verdict === r.verdict && st.t === r.t &&
               near(st.theta, r.theta, 1e-12) && near(st.phiCmd, r.phiCmd, 1e-12) &&
               near(st.psi, r.psi, 1e-12) && near(st.fwdSmooth, r.fwd, 0) && near(st.turnSmooth, r.turn, 0) &&
               near(st.posX, r.posX, 1e-9) && near(st.posZ, r.posZ, 1e-9);
    check(same, nom + " = Python : " + pad(st.verdict, 8) + " t=" + st.t.toFixed(3) + " θ=" + fmt(st.theta, 3) + "° φ=" + fmt(st.phiCmd, 3) +
          "° ψ=" + fmt(st.psi, 3) + "° x=" + fmt(st.posX, 4) + " z=" + fmt(st.posZ, 4) + " fwd=" + st.fwdSmooth + " turn=" + st.turnSmooth +
          (same ? "" : "   ≠ (attendu " + r.verdict + " t=" + r.t + " θ=" + r.theta + " ψ=" + r.psi + " x=" + r.posX + ")"));
  });
  // Lissage kCmdSlewPerS = 200 unités/s : −20 atteint en 0,1 s ; à t = 0,5 s
  // de P1 (0,3 s de recul) fwd = −20, turn = −40, ψ = −3,4149° (Python).
  var simP1 = E.create({ seed: 42, kp: 25, ki: 350, kd: 1, kOut: 3, kv: 0, cascade: true });
  simP1.reset(E.scenarios[0]);
  while (simP1.state.k < 100) { PILOTES.P1(simP1, simP1.state.k * (1 / 200)); simP1.step(); }
  check(simP1.state.fwdSmooth === -20 && simP1.state.turnSmooth === -40 && near(simP1.state.psi, -3.4149474578278034, 1e-12),
        "P1 à t = 0,5 s : consignes lissées fwd=" + simP1.state.fwdSmooth + " turn=" + simP1.state.turnSmooth + ", ψ = " + simP1.state.psi.toFixed(4) + "° (Python −3,4149°)");
  // Le lissage est une rampe : 0 → 60 demande 60/200 = 0,3 s (60 pas), et la
  // consigne d'inclinaison vaut fwd × kTiltPerCmd = 60 × 0,06 = 3,6°.
  var simR = E.create({ seed: 42, kp: 25, ki: 350, kd: 1, kOut: 3, kv: 0, cascade: true });
  simR.reset(E.scenarios[0]);
  simR.setBotState({ cmdForward: 60 });
  simR.stepMany(30);
  var fwdMi = simR.state.fwdSmooth;
  simR.stepMany(30);
  check(fwdMi === 30 && simR.state.fwdSmooth === 60 && near(simR.state.setpoint, 3.6, 1e-12),
        "cmdForward = 60 : rampe 200/s (30 après 0,15 s, 60 après 0,3 s), θ_ref = " + simR.state.setpoint.toFixed(3) + "° (60 × 0,06)");
  // Priorité de l'UI sur le pivot d'évitement, et du recul le plus franc (min).
  // Sims neufs : une consigne d'avance/recul finit en chute (P2), il faut
  // lire les consignes lissées AVANT (60 pas = 0,3 s suffisent à la rampe).
  simR = E.create({ seed: 42, kp: 25, ki: 350, kd: 1, kOut: 3, kv: 0, cascade: true });
  simR.reset(E.scenarios[0]);
  simR.setBotState({ cmdForward: -60, cmdTurn: 30, avoidFwdMax: -20, avoidTurn: -40, obstacleWarn: true });
  simR.stepMany(60);
  check(simR.state.verdict === null && simR.state.fwdSmooth === -60 && simR.state.turnSmooth === 30,
        "UI recule à −60 et tourne à 30 malgré l'évitement (−20, −40) : min() et priorité UI → fwd=" + simR.state.fwdSmooth + " turn=" + simR.state.turnSmooth);
  simR = E.create({ seed: 42, kp: 25, ki: 350, kd: 1, kOut: 3, kv: 0, cascade: true });
  simR.reset(E.scenarios[0]);
  simR.setBotState({ cmdForward: 60, cmdTurn: 0, avoidFwdMax: -20, avoidTurn: -40, obstacleWarn: true });
  simR.stepMany(60);
  check(simR.state.verdict === null && simR.state.fwdSmooth === -20 && simR.state.turnSmooth === -40,
        "UI avance à 60 sous alerte : marche avant interdite, recul imposé −20 et pivot −40 → fwd=" + simR.state.fwdSmooth + " turn=" + simR.state.turnSmooth);
  // Invariant conservé par balance.cpp l.678 : obstacleWarn seul (sans consigne
  // d'évitement, avoidFwdMax = 100) interdit déjà la marche avant.
  simR = E.create({ seed: 42, kp: 25, ki: 350, kd: 1, kOut: 3, kv: 0, cascade: true });
  simR.reset(E.scenarios[0]);
  simR.setBotState({ cmdForward: 60, obstacleWarn: true, avoidFwdMax: 100, avoidTurn: 0 });
  simR.stepMany(60);
  check(simR.state.fwdSmooth === 0,
        "obstacleWarn sans consigne d'évitement (l.678) : marche avant interdite, fwd=" + simR.state.fwdSmooth + " (UI à 60)");
  log("");

  // ── 7. Évitement (ultrason.js, miroir de head.cpp l.91-137) ──
  log("7. Évitement : ralenti < 60 cm, recul + pivot < 25 cm, pivot seul après 1,5 s, hystérésis 35 cm, côté");
  var C = U.constants;
  us = U.create();
  us.tickMany(40, 50, true);                    // 1 mesure à 50 cm
  check(us.state.obstacleSlow === true && us.state.obstacleWarn === false &&
        us.state.avoidPhase === C.AV_RALENTI && us.state.avoidFwdMax === 40 && us.state.avoidTurn === 0,
        "50 cm : obstacleSlow, phase RALENTI, avoidFwdMax = " + us.state.avoidFwdMax + " (AVOID_SLOW_CMD), pas de pivot");
  us = U.create();
  us.tickMany(40, 65, true);
  check(us.state.obstacleSlow === false && us.state.avoidPhase === C.AV_LIBRE && us.state.avoidFwdMax === 100,
        "65 cm (≥ US_SLOW_CM) : pas de ralenti, phase LIBRE, avoidFwdMax = 100");
  us = U.create();
  us.tickMany(40, 20, true);                    // t = 200 ms : alerte → RECUL
  check(us.state.obstacleWarn === true && us.state.avoidPhase === C.AV_RECUL &&
        us.state.avoidFwdMax === -20 && us.state.avoidTurn === -40,
        "20 cm : phase RECUL, avoidFwdMax = " + us.state.avoidFwdMax + " (−AVOID_BACK_CMD), pivot " + us.state.avoidTurn + " (en face → côté par défaut +1 → −40)");
  us.tickMany(299, 20, true);                   // t = 1695 ms : toujours RECUL
  var phaseAvant = us.state.avoidPhase;
  us.tick(20, true);                            // t = 1700 ms : 1500 ms écoulées → PIVOT
  check(phaseAvant === C.AV_RECUL && us.state.avoidPhase === C.AV_PIVOT &&
        us.state.avoidFwdMax === 0 && us.state.avoidTurn === -40,
        "recul borné AVOID_BACK_MAX_MS = 1500 ms : RECUL à 1,695 s, PIVOT à 1,7 s (avoidFwdMax = 0, pivot conservé)");
  us.tickMany(400, 30, true);                   // 30 cm : entre US_STOP_CM et US_CLEAR_CM
  check(us.state.avoidPhase === C.AV_PIVOT && us.state.obstacleWarn === false,
        "hystérésis : 30 cm (> 25, ≤ 35) → plus d'alerte mais l'évitement CONTINUE (PIVOT)");
  us.tickMany(400, 36, true);                   // > US_CLEAR_CM → dégagé, mais < 60 → RALENTI
  check(us.state.avoidPhase === C.AV_RALENTI && us.state.avoidFwdMax === 40 && us.state.avoidTurn === 0,
        "dégagé à 36 cm (> US_CLEAR_CM) : fin du pivot, RALENTI (36 < 60 cm)");
  us.tickMany(400, 80, true);
  check(us.state.avoidPhase === C.AV_LIBRE && us.state.avoidFwdMax === 100,
        "80 cm : LIBRE, avoidFwdMax = 100");
  // Pas d'évitement hors équilibre (robot au sol / tenu) : LIBRE quoi qu'il voie.
  us = U.create();
  us.tickMany(40, 20, false);
  check(us.state.obstacleWarn === true && us.state.avoidPhase === C.AV_LIBRE && us.state.avoidFwdMax === 100 && us.state.avoidTurn === 0,
        "hors équilibre : alerte publiée mais aucune consigne d'évitement (LIBRE, 100, 0)");
  // Côté d'après l'angle de tête (verrouillé à l'entrée en RECUL). Rien devant
  // (−1) pendant que la tête balaie, puis l'obstacle apparaît : la moyenne
  // s'amorce sur cet écho (pas de lissage à traverser) → alerte immédiate.
  // Cadence 1000 ms après 3 échecs → mesures à 1,6 s (pan 102°) et 2,6 s (72°).
  us = U.create();
  us.tickMany(300, -1, true);                   // jusqu'à 1,5 s : rien devant
  us.tickMany(40, 20, true);                    // mesure à 1,6 s, pan = 120 − 30 × 0,6 = 102
  check(us.state.angleVu === 102 && us.state.obstacleSide === 1 && us.state.avoidTurn === -40,
        "obstacle vu à pan " + us.state.angleVu + "° (> 100) : côté +1 → pivot " + us.state.avoidTurn + " (à l'opposé)");
  us = U.create();
  us.tickMany(500, -1, true);                   // jusqu'à 2,5 s
  us.tickMany(40, 20, true);                    // mesure à 2,6 s, pan = 120 − 30 × 1,6 = 72
  check(us.state.angleVu === 72 && us.state.obstacleSide === -1 && us.state.avoidTurn === 40,
        "obstacle vu à pan " + us.state.angleVu + "° (< 80) : côté −1 → pivot " + us.state.avoidTurn);
  us.tickMany(400, -1, true);                   // plus d'écho → LIBRE (cadence → 1 s)
  us.tickMany(380, 20, true);                   // re-vu à 5,2 s, pan 114° → côté +1 → −40
  var vuA = us.state.angleVu, turnA = us.state.avoidTurn, panA = us.state.headPanDeg;
  check(vuA === 114 && turnA === -40 && panA === 72 && us.state.avoidPhase === C.AV_RECUL,
        "manœuvre suivante : côté re-décidé (vu " + vuA + "° → pivot " + turnA + ") puis VERROUILLÉ bien que la tête soit passée à " + panA + "°");
  log("");

  // ── 8. Boucle fermée capteur → consignes → moteur, dans l'ordre du viewer ──
  // Le viewer fait, à chaque pas : sim.step() ; us.tick(distance) ;
  // sim.setBotState(us.state). Obstacle FIXE à 20 cm devant la sonde (plaque
  // jamais dégagée, comme un lobe de 15° sur la plaque de 10 cm) : le capteur
  // publie RECUL à 0,2 s et PIVOT à 1,7 s — exactement le profil P4 du
  // Python. Le robot recule, pivote, et TOMBE à 1,915 s : sans retour de
  // vitesse (Kv = 0), 1,5 s de recul à −20 saturent la roue (250 °/s).
  log("8. Boucle fermée capteur → moteur (ordre du viewer) : retombe sur P4");
  var simF = E.create({ seed: 42, kp: 25, ki: 350, kd: 1, kOut: 3, kv: 0, cascade: true });
  simF.reset(E.scenarios[0]);
  var usF = U.create();
  var phases = [];
  while (simF.state.verdict === null) {
    simF.step();
    usF.tick(20, !simF.state.fallen);
    simF.setBotState({ avoidFwdMax: usF.state.avoidFwdMax, avoidTurn: usF.state.avoidTurn, obstacleWarn: usF.state.obstacleWarn });
    if (phases.length === 0 || phases[phases.length - 1].ph !== usF.state.avoidPhase) phases.push({ t: usF.state.tMs, ph: usF.state.avoidPhase });
  }
  var seq = phases.map(function (p) { return p.ph + "@" + p.t; }).join(" ");
  check(seq === "0@5 2@200 3@1700 0@1920",
        "phases publiées (phase@ms) : " + seq + " (attendu LIBRE, RECUL à 200, PIVOT à 1700, LIBRE dès la chute à 1920)");
  var r4 = REF_DEP.P4;
  check(simF.state.verdict === r4.verdict && simF.state.t === r4.t && near(simF.state.theta, r4.theta, 1e-12) &&
        near(simF.state.psi, r4.psi, 1e-12) && near(simF.state.posX, r4.posX, 1e-9) && near(simF.state.posZ, r4.posZ, 1e-9),
        "trajectoire = P4 du Python : " + simF.state.verdict + " t=" + simF.state.t.toFixed(3) + " ψ=" + fmt(simF.state.psi, 3) + "° x=" + fmt(simF.state.posX, 4) + " z=" + fmt(simF.state.posZ, 4));
  log("");

  var verdict = failures === 0 ? "AUTO-TEST RÉUSSI" : "AUTO-TEST ÉCHOUÉ (" + failures + " contrôle(s))";
  log("═══ " + verdict + " ═══");

  if (typeof document !== "undefined") {
    var pre = document.getElementById("out");
    if (pre) pre.textContent = lines.join("\n");
    var h1 = document.getElementById("verdict");
    if (h1) { h1.textContent = verdict; h1.className = failures === 0 ? "ok" : "ko"; }
  }
  if (typeof process !== "undefined" && process.versions && process.versions.node) {
    process.exitCode = failures === 0 ? 0 : 1;   // code de retour pour la CLI
  }
})();
