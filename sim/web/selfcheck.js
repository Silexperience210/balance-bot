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
 *      et ses écritures dans `state` sont prises en compte.
 * ═══════════════════════════════════════════════════════════════════ */
(function () {
  "use strict";
  var E = (typeof BalanceEngine !== "undefined") ? BalanceEngine
        : require("./engine.js");

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
