/* ═══════════════════════════════════════════════════════════════════
 * BalanceBot — simulateur web : MOTEUR (engine.js)
 *
 * Physique + loi de commande, transcription LIGNE À LIGNE de
 * sim/balancebot_sim.py (commit bfe3faa), qui copie lui-même
 * balance-bot/balance.cpp. RÈGLE D'OR : mêmes boucles, mêmes constantes,
 * mêmes SIGNES, même ORDRE des opérations flottantes — pour une même graine,
 * les trajectoires θ(t)/φ(t) sont celles du Python à l'arrondi près (sin/cos
 * de V8 vs libm ; MT19937 et random.gauss sont reproduits EXACTEMENT, le
 * bruit est donc le même que `random.seed(42)` côté Python).
 *
 * Plain JS, zéro dépendance, zéro build : définit UN global
 * `window.BalanceEngine` (voir /tmp/balancebot-web-spec.md, §API).
 *
 *   BalanceEngine.create(options) → sim
 *   BalanceEngine.defaults        → gains et réglages par défaut
 *   BalanceEngine.scenarios       → les 6 scénarios de balancebot_sim.py
 *   BalanceEngine.constants       → constantes physiques (dessin du viewer)
 *
 *   sim.reset(scenario)   sim.step()   sim.stepMany(n)   sim.state
 *   sim.setCustom(fn)     sim.setNoise(v)   sim.setGains({...})
 *   sim.setBotState({cmdForward, cmdTurn, avoidFwdMax, avoidTurn, obstacleWarn})
 *                         → les ENTRÉES de déplacement (ce que g_state porte
 *                           dans le firmware : flèches de l'UI + évitement de
 *                           head.cpp / ultrason.js)
 *
 * Ce qui N'EST PAS ici (et qui dominera le réel) : trame PWM 50 Hz du SG90,
 * mort-zone du servo, borne d'accélération, friction, 3D — voir la docstring
 * de balancebot_sim.py. Le hook `setCustom` est la seule porte d'injection
 * d'effets : la physique et la loi de commande ne se modifient pas depuis
 * l'éditeur du viewer.
 * ═══════════════════════════════════════════════════════════════════ */
(function (root) {
  "use strict";

  // ── Paramètres physiques (balancebot_sim.py l.72-74) ─────────────
  var G = 9.81, R = 0.0415, H = 0.080;      // gravité, rayon de ROULAGE (pneu Ø83 → 41,5 mm), hauteur CoM (m)
  var TAU_SERVO = 0.05, VMAX_SERVO = 250.0; // servo : 1er ordre (s), vitesse max (°/s)
  var DT = 1.0 / 200;                       // pas de contrôle = 200 Hz (comme le code)

  // ── Constantes du contrôleur (copiées de balance.cpp via le sim) ──
  var OUT_MAX = 90.0;
  var INTEGRAL_MAX = OUT_MAX;               // kIntegralMax = kOutMax (M10)
  var DEADBAND = 0.0;                       // kErrDeadbandDeg = 0 (M3)
  var FOOT_HARD = 45.0, FOOT_MARGIN = 9.0, FOOT_TAPER = 10.0, FALL_ANGLE = 45.0;
  var RECENTER_PERIOD = 0.100;              // 10 Hz
  var RECENTER_VEL_MAX = 20.0, RECENTER_REF_MAX = 6.0, RECENTER_SLEW = 3.0;
  var FOOT_VEL_TAU = 0.08, FOOT_PANIC = 35.0;
  // ── Consignes de DÉPLACEMENT (balance.cpp l.178-183, l.673-692, l.751-758 ;
  //    balancebot_sim.py l.92-108) ──
  // Avancer = incliner la consigne d'angle (kTiltPerCmd) ; tourner =
  // différentiel de vitesse entre les deux roues (kTurnPerCmd). Les deux
  // consignes UI (cmdForward / cmdTurn, −100..100) sont LISSÉES à
  // kCmdSlewPerS. L'évitement d'obstacle (head.cpp → avoidFwdMax /
  // avoidTurn, transcrit dans ultrason.js) n'entre QUE par ici, AVANT le
  // lissage : un plafond sur la marche avant (négatif = recul imposé) et un
  // pivot imposé si l'UI ne tourne pas. Jamais sur le PID ni sur les roues.
  var SETPOINT_DEG = 0.0;                   // kSetpointDeg
  var TILT_PER_CMD = 0.06;                  // kTiltPerCmd  : ° de consigne par unité de cmdForward
  var TURN_PER_CMD = 0.30;                  // kTurnPerCmd  : unités de sortie par unité de cmdTurn
  var CMD_SLEW_PER_S = 200.0;               // kCmdSlewPerS : lissage des consignes (unités/s)
  // Voie des roues (m), plans médians des pneus : faces externes à 146,87 mm
  // (exporter_parts_web.py TRACK), pneu centré 4 mm en dedans → 138,87 mm.
  // Sert UNIQUEMENT à la cinématique du lacet — le firmware n'a ni cap ni
  // odométrie (head.cpp l.10-15) : le lacet est une grandeur du SIMULATEUR
  // (pour voir le pivot), pas une grandeur du robot.
  var TRACK = 0.13887;
  // ── MÉCANIQUE ──────────────────────────────────────────────────────
  // Le robot RÉEL = ROUES Ø80 + pneus Ø83 sur servos **360° continus**
  // (FS90R) : la roue tourne LIBREMENT → NI butée ±45°, NI soft clamp de
  // butée, NI panic. Ces garde-fous modélisaient l'ARC (ancienne mécanique,
  // R = 32,5 mm) ; ils restent disponibles pour comparaison. Miroir exact de
  // sim/balancebot_sim.py (MODE) — les deux se changent ENSEMBLE.
  var MODE = "roue";                        // "roue" = le robot réel | "arc"
  // Retard TOTAL de boucle forfaitaire (ctrl() du Python : tau_f = 0.025) :
  // appliqué au pitch ET au gyro. Le verdict du sim en dépend (§2 #9).
  var TAU_F = 0.025;

  // ═════════════════════════════════════════════════════════════════
  // PRNG : Mersenne Twister MT19937 + random.gauss, à l'identique de
  // CPython (Modules/_randommodule.c, Lib/random.py). Graine entière ≥ 0
  // → init_by_array([graine]) exactement comme random.seed(42). Les
  // scénarios bruités sont donc rejouables ET identiques au Python.
  // ═════════════════════════════════════════════════════════════════
  var MT_N = 624, MT_M = 397;
  var MATRIX_A = 0x9908b0df, UPPER_MASK = 0x80000000, LOWER_MASK = 0x7fffffff;

  function PyRandom(seed) {
    this.mt = new Uint32Array(MT_N);
    this.index = MT_N;
    this.gaussNext = null;                  // cache du 2e tirage (random.gauss)
    this.seed(seed);
  }

  // init_genrand(s)
  PyRandom.prototype._initGenrand = function (s) {
    var mt = this.mt;
    mt[0] = s >>> 0;
    for (var i = 1; i < MT_N; i++) {
      // 1812433253 * (mt[i-1] ^ (mt[i-1] >> 30)) + i   (mod 2^32)
      mt[i] = (Math.imul(1812433253, (mt[i - 1] ^ (mt[i - 1] >>> 30)) >>> 0) + i) >>> 0;
    }
    this.index = MT_N;
  };

  // init_by_array(key) — c'est ce que fait random.seed(int) côté CPython :
  // la graine (valeur absolue) est découpée en mots de 32 bits, poids
  // faible d'abord.
  PyRandom.prototype.seed = function (seed) {
    var n = Math.abs(Math.trunc(Number(seed) || 0));
    var key = [];
    if (n === 0) key.push(0);
    while (n > 0) { key.push(n % 4294967296); n = Math.floor(n / 4294967296); }
    var mt = this.mt, i = 1, j = 0, k;
    this._initGenrand(19650218);
    for (k = Math.max(MT_N, key.length); k > 0; k--) {
      mt[i] = ((mt[i] ^ (Math.imul((mt[i - 1] ^ (mt[i - 1] >>> 30)) >>> 0, 1664525) >>> 0))
               + key[j] + j) >>> 0;
      i++; j++;
      if (i >= MT_N) { mt[0] = mt[MT_N - 1]; i = 1; }
      if (j >= key.length) j = 0;
    }
    for (k = MT_N - 1; k > 0; k--) {
      mt[i] = ((mt[i] ^ (Math.imul((mt[i - 1] ^ (mt[i - 1] >>> 30)) >>> 0, 1566083941) >>> 0))
               - i) >>> 0;
      i++;
      if (i >= MT_N) { mt[0] = mt[MT_N - 1]; i = 1; }
    }
    mt[0] = 0x80000000;                     // bit de poids fort à 1
    this.index = MT_N;
    this.gaussNext = null;                  // random.seed() vide aussi ce cache
  };

  // genrand_uint32()
  PyRandom.prototype.uint32 = function () {
    var mt = this.mt, y, kk;
    if (this.index >= MT_N) {
      for (kk = 0; kk < MT_N - MT_M; kk++) {
        y = (mt[kk] & UPPER_MASK) | (mt[kk + 1] & LOWER_MASK);
        mt[kk] = mt[kk + MT_M] ^ (y >>> 1) ^ ((y & 1) ? MATRIX_A : 0);
      }
      for (; kk < MT_N - 1; kk++) {
        y = (mt[kk] & UPPER_MASK) | (mt[kk + 1] & LOWER_MASK);
        mt[kk] = mt[kk + (MT_M - MT_N)] ^ (y >>> 1) ^ ((y & 1) ? MATRIX_A : 0);
      }
      y = (mt[MT_N - 1] & UPPER_MASK) | (mt[0] & LOWER_MASK);
      mt[MT_N - 1] = mt[MT_M - 1] ^ (y >>> 1) ^ ((y & 1) ? MATRIX_A : 0);
      this.index = 0;
    }
    y = mt[this.index++];
    y ^= (y >>> 11);
    y ^= (y << 7) & 0x9d2c5680;
    y ^= (y << 15) & 0xefc60000;
    y ^= (y >>> 18);
    return y >>> 0;
  };

  // random() = genrand_res53() : 53 bits de mantisse, exact en float64.
  PyRandom.prototype.random = function () {
    var a = this.uint32() >>> 5, b = this.uint32() >>> 6;
    return (a * 67108864.0 + b) * (1.0 / 9007199254740992.0);
  };

  // random.gauss(mu, sigma) — méthode de Box-Muller de Lib/random.py, avec
  // le cache `gauss_next` : un tirage sur deux ne consomme pas le PRNG.
  PyRandom.prototype.gauss = function (mu, sigma) {
    var z = this.gaussNext;
    this.gaussNext = null;
    if (z === null) {
      var x2pi = this.random() * (2 * Math.PI);
      var g2rad = Math.sqrt(-2.0 * Math.log(1.0 - this.random()));
      z = Math.cos(x2pi) * g2rad;
      this.gaussNext = Math.sin(x2pi) * g2rad;
    }
    return mu + z * sigma;
  };

  // ═════════════════════════════════════════════════════════════════
  // Utilitaires
  // ═════════════════════════════════════════════════════════════════
  function isNum(v) { return typeof v === "number" && isFinite(v); }
  function pick(v, dflt) { return isNum(v) ? v : dflt; }
  // balance.cpp slew() (l.282-287) : rampe bornée vers la cible.
  function slew(current, target, maxStep) {
    var delta = target - current;
    if (delta >  maxStep) return current + maxStep;
    if (delta < -maxStep) return current - maxStep;
    return target;
  }

  // ═════════════════════════════════════════════════════════════════
  // Valeurs par défaut, scénarios, constantes exposées
  // ═════════════════════════════════════════════════════════════════
  var defaults = Object.freeze({
    kp: 25, ki: 500, kd: 0.5,               // gains PID embarqués (balance.cpp)
    kpPhi: 0.8, kv: 3.0,                    // cascade de recentrage
    kOut: 1.0,                              // kOutToFootDegS (autorité)
    cascade: true,
    noise: 0,
    tauF: TAU_F,
    dt: DT
  });

  // Les 6 scénarios de balancebot_sim.py (SCENARIOS), mêmes libellés.
  var scenarios = Object.freeze([
    Object.freeze({ name: "θ0=2° propre",   theta0Deg: 2, tmax: 6, noise: 0, push: null }),
    Object.freeze({ name: "θ0=2° bruit",    theta0Deg: 2, tmax: 6, noise: 1, push: null }),
    Object.freeze({ name: "θ0=5° bruit",    theta0Deg: 5, tmax: 6, noise: 1, push: null }),
    Object.freeze({ name: "tape 0.4 rad/s", theta0Deg: 3, tmax: 8, noise: 1, push: Object.freeze({ t: 3, v: 0.4 }) }),
    Object.freeze({ name: "tape 0.8 rad/s", theta0Deg: 3, tmax: 8, noise: 1, push: Object.freeze({ t: 3, v: 0.8 }) }),
    Object.freeze({ name: "tape 1.2 rad/s", theta0Deg: 3, tmax: 8, noise: 1, push: Object.freeze({ t: 3, v: 1.2 }) })
  ]);

  // Constantes utiles au viewer (dessin de l'arc, butées, seuils). Lecture
  // seule : elles ne se règlent pas, elles décrivent le robot.
  var constants = Object.freeze({
    G: G, R: R, H: H, DT: DT,
    TAU_SERVO: TAU_SERVO, VMAX_SERVO: VMAX_SERVO,
    OUT_MAX: OUT_MAX, INTEGRAL_MAX: INTEGRAL_MAX, DEADBAND: DEADBAND,
    FOOT_HARD: FOOT_HARD, FOOT_MARGIN: FOOT_MARGIN, FOOT_TAPER: FOOT_TAPER,
    FALL_ANGLE: FALL_ANGLE, FOOT_PANIC: FOOT_PANIC,
    RECENTER_PERIOD: RECENTER_PERIOD, RECENTER_VEL_MAX: RECENTER_VEL_MAX,
    RECENTER_REF_MAX: RECENTER_REF_MAX, RECENTER_SLEW: RECENTER_SLEW,
    FOOT_VEL_TAU: FOOT_VEL_TAU,
    SETPOINT_DEG: SETPOINT_DEG, TILT_PER_CMD: TILT_PER_CMD,
    TURN_PER_CMD: TURN_PER_CMD, CMD_SLEW_PER_S: CMD_SLEW_PER_S, TRACK: TRACK
  });

  // ═════════════════════════════════════════════════════════════════
  // create(options) → sim
  //
  // options (toutes facultatives) : kp, ki, kd, kpPhi, kv, kOut, cascade,
  //   noise, tauF, seed (graine entière, 42 par défaut = celle du Python),
  //   scenario (chargé par le reset initial ; sinon « θ0=2° propre »).
  //
  // Graine : elle est posée UNE fois à la création (comme random.seed(42)
  // avant la boucle des 6 scénarios en Python) ; reset() NE réamorce PAS le
  // PRNG, sauf si le scénario passé porte un champ `seed`. Enchaîner les 6
  // scénarios avec reset() reproduit donc exactement `python3
  // balancebot_sim.py`.
  // ═════════════════════════════════════════════════════════════════
  function create(options) {
    options = options || {};

    // ── Gains (Sim.__init__) ──
    var kp = pick(options.kp, defaults.kp);
    var ki = pick(options.ki, defaults.ki);
    var kd = pick(options.kd, defaults.kd);
    var cascade = (options.cascade === undefined) ? defaults.cascade : !!options.cascade;
    var kpPhi = pick(options.kpPhi, defaults.kpPhi);
    var kv = pick(options.kv, defaults.kv);
    var kOut = pick(options.kOut, defaults.kOut);   // kOutToFootDegS : °/s de pied par unité de sortie
    var tauF = pick(options.tauF, defaults.tauF);
    var rng = new PyRandom(pick(options.seed, 42));

    // ── État interne, EN RADIANS pour θ/θ̇ (comme le Python), ° pour φ ──
    var theta = 0, dtheta = 0, phi = 0, phiCmd = 0;
    var integ = 0, prevDphi = 0, tNow = 0;
    var pitchF = 0, rateF = 0;
    var recenterVel = 0, footVelFilt = 0;
    var recenterLast = 0;
    var panicked = false;
    // ENTRÉES de déplacement (ce que g_state porte dans le firmware) — posées
    // de l'extérieur (setBotState), conservées par reset() comme les gains.
    var cmdForward = 0, cmdTurn = 0;        // g_state.cmdForward / cmdTurn (−100..100)
    var avoidFwdMax = 100, avoidTurn = 0;   // g_state.avoidFwdMax / avoidTurn (head.cpp)
    var obstacleWarn = false;               // g_state.obstacleWarn (< US_STOP_CM)
    // couche déplacement : consignes lissées, voie différentielle, pose au sol
    var fwdSmooth = 0, turnSmooth = 0;      // s_fwdSmooth / s_turnSmooth
    var phiDiff = 0, phiDiffCmd = 0;        // (φ_G − φ_D)/2 : réel / commandé (°)
    var psi = 0;                            // lacet (rad, + = vers la droite)
    var posX = 0, posZ = 0;                 // axe des roues au sol (m)

    // ── Scénario courant et déroulé (run()) ──
    var theta0Deg = 2, tmax = 6, noise = pick(options.noise, defaults.noise);
    var pushT = 0, pushV = 0;               // push_t, push_v = push or (0, 0)
    var nSteps = 0, k = 0;
    var fallen = false, verdict = null, done = false;

    // ── Télémétrie du dernier pas (lecture seule) ──
    var lastOut = 0;                        // sortie PID après soft clamp (retour de ctrl())
    var lastDphi = 0;                       // vitesse réelle du servo (°/s)
    var lastSetpoint = 0;                   // θ_ref (cascade interne), °
    var lastU = 0;                          // vitesse de pied commandée −out·k_out (°/s)

    var custom = null;                      // hook utilisateur fn(t, state, dt)

    // ── `state` : vue EN DEGRÉS sur l'état vivant, avec accesseurs ──
    // Le viewer ne fait que lire ; le hook peut écrire (theta, thetaDot,
    // phi, phiCmd, integ, pitchFilt, rateFilt, …) et l'écriture est
    // répercutée dans les variables internes du moteur.
    var state = {};
    function prop(name, get, set) {
      Object.defineProperty(state, name, {
        enumerable: true,
        get: get,
        set: set || function () {}          // lecture seule : écriture ignorée (pas de TypeError en mode strict)
      });
    }
    prop("t",        function () { return tNow; });
    prop("theta",    function () { return theta * 180 / Math.PI; },
                     function (v) { if (isNum(v)) theta = v * Math.PI / 180; });
    prop("thetaDot", function () { return dtheta * 180 / Math.PI; },
                     function (v) { if (isNum(v)) dtheta = v * Math.PI / 180; });
    prop("phi",      function () { return phi; },
                     function (v) { if (isNum(v)) phi = v; });
    // φ̇ : vitesse réelle du servo au dernier pas ; l'écrire modifie le
    // « prev_dphi » qui sert au φ̈ du pas suivant.
    prop("phiDot",   function () { return lastDphi; },
                     function (v) { if (isNum(v)) { lastDphi = v; prevDphi = v; } });
    prop("phiCmd",   function () { return phiCmd; },
                     function (v) { if (isNum(v)) phiCmd = v; });
    prop("pidOut",   function () { return lastOut; });
    prop("integ",    function () { return integ; },
                     function (v) { if (isNum(v)) integ = v; });
    prop("pitchFilt", function () { return pitchF; },
                      function (v) { if (isNum(v)) pitchF = v; });
    prop("rateFilt", function () { return rateF; },
                     function (v) { if (isNum(v)) rateF = v; });
    prop("fallen",   function () { return fallen; });
    prop("panicked", function () { return panicked; });
    prop("verdict",  function () { return verdict; });
    // Extras (hors contrat, lecture seule sauf mention) : utiles aux courbes.
    prop("setpoint",    function () { return lastSetpoint; });   // θ_ref cascade (°)
    prop("footVelCmd",  function () { return lastU; });          // −out·k_out (°/s)
    prop("recenterVel", function () { return recenterVel; },
                        function (v) { if (isNum(v)) recenterVel = v; });
    prop("footVelFilt", function () { return footVelFilt; },
                        function (v) { if (isNum(v)) footVelFilt = v; });
    // Couche déplacement (lecture seule) : consignes lissées, lacet, pose.
    prop("cmdForward",  function () { return cmdForward; });
    prop("cmdTurn",     function () { return cmdTurn; });
    prop("avoidFwdMax", function () { return avoidFwdMax; });
    prop("avoidTurn",   function () { return avoidTurn; });
    prop("fwdSmooth",   function () { return fwdSmooth; });    // s_fwdSmooth (unités UI)
    prop("turnSmooth",  function () { return turnSmooth; });   // s_turnSmooth
    prop("phiDiff",     function () { return phiDiff; });      // (φ_G − φ_D)/2 (°)
    prop("psi",         function () { return psi * 180 / Math.PI; });   // lacet (°)
    prop("posX",        function () { return posX; });         // m
    prop("posZ",        function () { return posZ; });         // m
    prop("noise",    function () { return noise; });
    prop("tmax",     function () { return tmax; });
    prop("k",        function () { return k; });                 // pas déjà calculés
    prop("done",     function () { return done; });

    // ── reset(scenario) : Sim.reset() + prologue de run() ──
    // Champs absents → valeur précédente conservée (reset() seul = rejeu).
    function reset(sc) {
      sc = sc || {};
      theta0Deg = pick(sc.theta0Deg, theta0Deg);
      tmax = pick(sc.tmax, tmax);
      noise = pick(sc.noise, noise);
      if (sc.push !== undefined) {
        var p = sc.push;
        pushT = (p && isNum(p.t)) ? p.t : 0;
        pushV = (p && isNum(p.v)) ? p.v : 0;
      }
      if (isNum(sc.seed)) rng.seed(sc.seed);

      // Sim.reset()
      theta = dtheta = phi = phiCmd = 0.0;
      integ = prevDphi = tNow = 0.0;
      pitchF = rateF = 0.0;
      recenterVel = footVelFilt = 0.0;
      recenterLast = 0.0;
      panicked = false;
      fwdSmooth = turnSmooth = 0.0;
      phiDiff = phiDiffCmd = 0.0;
      psi = 0.0;
      posX = posZ = 0.0;
      // run() : θ initial, nombre de pas
      theta = theta0Deg * Math.PI / 180;
      nSteps = Math.trunc(tmax / DT);
      k = 0;
      fallen = false; verdict = null; done = (nSteps <= 0);
      if (done) verdict = "ok";
      lastOut = lastDphi = lastSetpoint = lastU = 0.0;
    }

    // ── ctrl(noise, t) : PID + cascade, à l'identique de balance.cpp ──
    function ctrl(t) {
      // Filtre 1er ordre (retard forfaitaire tau_f) sur pitch ET gyro, bruit
      // gaussien ajouté. Les deux tirages ont lieu même à noise = 0 : le flux
      // du PRNG reste aligné sur le Python.
      var pt = theta * 180 / Math.PI, rt = dtheta * 180 / Math.PI;
      pitchF += ((pt + rng.gauss(0, noise * 0.15)) - pitchF) * (DT / tauF);
      rateF  += ((rt + rng.gauss(0, noise * 1.5))  - rateF)  * (DT / tauF);

      // ── Consignes UI + évitement (balance.cpp l.673-692), AVANT le lissage ──
      var cmdFwd = Math.max(-100, Math.min(100, cmdForward));
      var cmdTrn = Math.max(-100, Math.min(100, cmdTurn));
      if (obstacleWarn && cmdFwd > 0) cmdFwd = 0;            // l.678 : plus de marche avant
      if (cmdFwd > avoidFwdMax) cmdFwd = avoidFwdMax;         // l.687 : plafond / recul imposé (min)
      if (cmdTrn === 0 && avoidTurn !== 0) {                  // l.688 : pivot si l'UI ne tourne pas
        cmdTrn = Math.max(-100, Math.min(100, avoidTurn));
      }
      var maxStep = CMD_SLEW_PER_S * DT;                      // l.690-692 (dt = DT ici)
      fwdSmooth  = slew(fwdSmooth,  cmdFwd, maxStep);
      turnSmooth = slew(turnSmooth, cmdTrn, maxStep);

      // boucle EXTERNE de la cascade (10 Hz), sur φ = phi_cmd (ce que lit feet.cpp)
      if (cascade) {
        if (t - recenterLast >= RECENTER_PERIOD) {
          var dtRec = Math.min(Math.max(t - recenterLast, 0.0), 1.0);
          recenterLast = t;
          if (MODE === "arc" && Math.abs(phiCmd) > FOOT_PANIC) {
            panicked = true;
          } else {
            var target = Math.max(-RECENTER_VEL_MAX, Math.min(RECENTER_VEL_MAX, kpPhi * (0.0 - phiCmd)));
            var slewStep = RECENTER_SLEW * dtRec;
            if (target > recenterVel + slewStep) {
              recenterVel += slewStep;
            } else if (target < recenterVel - slewStep) {
              recenterVel -= slewStep;
            } else {
              recenterVel = target;
            }
          }
        }
      }

      // boucle INTERNE (200 Hz) : contribution à θ_ref. SIGNE (−), aligné sur
      // balance.cpp recenterSetpoint() : −kRecenterKv·(v_cible − φ̇). Non
      // tranché en réel (REVIEW_CLAUDE.md M1) — ne se change qu'avec le
      // firmware ET le Python, jamais ici seul.
      var ref = 0.0;
      if (cascade) {
        ref = Math.max(-RECENTER_REF_MAX, Math.min(RECENTER_REF_MAX,
                                                   -kv * (recenterVel - footVelFilt)));
      }

      // balance.cpp l.724-725 : kSetpointDeg + s_fwdSmooth·kTiltPerCmd + recenterSetpoint()
      var setpoint = SETPOINT_DEG + fwdSmooth * TILT_PER_CMD + ref;
      lastSetpoint = setpoint;
      var err = setpoint - pitchF;
      if (Math.abs(err) < DEADBAND) err = 0.0;
      var p = kp * err;
      var d = -kd * rateF;
      var cand = Math.max(-INTEGRAL_MAX, Math.min(INTEGRAL_MAX, integ + ki * err * DT));
      var raw = p + cand + d;
      if (Math.abs(raw) < OUT_MAX || raw * err < 0) {
        integ = cand;                       // intégration conditionnelle (anti-windup)
      }
      var out = Math.max(-OUT_MAX, Math.min(OUT_MAX, p + integ + d));
      // soft clamp de butée (feet.cpp fournit φ intégré = phi_cmd).
      // SIGNE (REVIEW_CLAUDE.md M2) : `out` est la sortie PID NON inversée ;
      // la vitesse de pied réelle est u = −out. Le pied pousse vers la butée
      // quand u·φ > 0 ⇔ (−out)·φ > 0.
      if (MODE === "arc" && (-out) * phiCmd > 0) {
        var lim = Math.min(FOOT_HARD, 90.0 - Math.abs(pitchF) - FOOT_MARGIN);
        out *= Math.max(0.0, Math.min(1.0, (lim - Math.abs(phiCmd)) / FOOT_TAPER));
      }
      // estimateur φ̇ : 1er ordre sur la commande APRÈS clamp, AVANT différentiel.
      // Même signe : la commande réellement envoyée à feet.cpp est −out·k_out.
      var alpha = DT / (FOOT_VEL_TAU + DT);
      var cmdVel = -out * kOut;
      footVelFilt += alpha * (cmdVel - footVelFilt);
      return out;
    }

    // ── step() : UN pas de DT — corps de la boucle de run() ──
    // Ordre : ctrl → φ_cmd → servo → Lagrange → tape → θ̇, θ → hook → verdict.
    function step() {
      if (done) return;
      var t = k * DT;                       // horodatage du pas, comme run() (t = k·DT)

      // câblage stabilisant (comme le firmware) : `outFw` est la sortie PID
      // INVERSÉE de balance.cpp (l.741).
      var out = ctrl(t);
      lastOut = out;
      var outFw = -out;
      // Différentiel de rotation (balance.cpp l.751-758) : roue G = out +
      // turn, roue D = out − turn, chacune bornée, puis °/s de pied via
      // k_out (Feet::driveFootSpeed(left · kOutToFootDegS, right · …)).
      // La MOYENNE des deux roues pilote θ (le pendule ne voit que l'axe) ;
      // la DIFFÉRENCE ne fait que pivoter le robot (lacet).
      // À cmdTurn = 0 : left = right = outFw, u = outFw·kOut exactement.
      var turn = turnSmooth * TURN_PER_CMD;
      var left  = Math.max(-OUT_MAX, Math.min(OUT_MAX, outFw + turn));
      var right = Math.max(-OUT_MAX, Math.min(OUT_MAX, outFw - turn));
      var u = (left + right) / 2 * kOut;
      var uDiff = (left - right) / 2 * kOut;
      lastU = u;
      // roue (servo 360°) : pas de butée, la roue tourne sans fin ;
      // arc : butée dure ±FOOT_HARD (ancienne mécanique).
      if (MODE === "arc") {
        phiCmd = Math.max(-FOOT_HARD, Math.min(FOOT_HARD, phiCmd + u * DT));
      } else {
        phiCmd += u * DT;
      }
      var dphi = Math.max(-VMAX_SERVO, Math.min(VMAX_SERVO, (phiCmd - phi) / TAU_SERVO));
      var dphidd = (dphi - prevDphi) / DT * (Math.PI / 180.0);   // rad/s²
      prevDphi = dphi;
      lastDphi = dphi;
      phi += dphi * DT;
      // Voie différentielle : même servo du 1er ordre que la moyenne (la loi
      // est linéaire, la décomposition somme/différence est exacte hors
      // saturation VMAX_SERVO). Lacet ψ = (φ_G − φ_D)·R/TRACK.
      phiDiffCmd += uDiff * DT;
      var dphiDiff = Math.max(-VMAX_SERVO, Math.min(VMAX_SERVO, (phiDiffCmd - phiDiff) / TAU_SERVO));
      phiDiff += dphiDiff * DT;
      psi = 2.0 * phiDiff * (Math.PI / 180.0) * R / TRACK;
      // Lagrange : θ̈·(R² + 2Rh cosθ + h²) = g·h·sinθ − φ̈·R·(R + h·cosθ) + R·h·sinθ·θ̇²
      var cosT = Math.cos(theta), sinT = Math.sin(theta);
      var inertia = R * R + 2.0 * R * H * cosT + H * H;
      var thdd = (G * H * sinT - dphidd * R * (R + H * cosT)
                  + R * H * sinT * dtheta * dtheta) / inertia;
      if (pushT && Math.abs(t - pushT) < DT / 2) {
        dtheta += pushV;                    // tape : impulsion de vitesse, UNE fois
      }
      dtheta += thdd * DT;
      theta += dtheta * DT;
      // Pose au sol : roulement sans glissement le long du cap, l'axe avance
      // de R·(Δθ + Δφ) (x_axe = R·(θ + φ) à ψ = 0).
      var ds = R * (dtheta * DT + dphi * DT * (Math.PI / 180.0));
      posX += ds * Math.cos(psi);
      posZ += ds * Math.sin(psi);
      tNow = t;
      k++;

      // Hook « effets secondaires » : APRÈS la physique, AVANT le verdict.
      if (custom) custom(t, state, DT);

      // Verdicts, dans l'ordre du Python : chute θ, puis panique φ, puis fin.
      if (Math.abs(theta * 180 / Math.PI) > FALL_ANGLE) {
        fallen = true; verdict = "chute θ"; done = true;
        return;
      }
      if (panicked) {
        verdict = "panic φ"; done = true;
        return;
      }
      if (k >= nSteps) {
        verdict = "ok"; done = true;
      }
    }

    function stepMany(n) {
      n = Math.trunc(Number(n) || 0);
      while (n-- > 0 && !done) step();
    }

    function setCustom(fn) {
      custom = (typeof fn === "function") ? fn : null;
    }

    function setNoise(v) {
      if (isNum(v)) noise = v;
    }

    // Entrées de déplacement (g_state du firmware) : flèches de l'UI
    // (cmdForward / cmdTurn) et évitement publié par head.cpp / ultrason.js
    // (avoidFwdMax / avoidTurn / obstacleWarn). Seuls les champs fournis
    // sont pris ; les entiers sont tronqués comme les `int` du firmware.
    function setBotState(b) {
      b = b || {};
      if (isNum(b.cmdForward))  cmdForward  = Math.trunc(b.cmdForward);
      if (isNum(b.cmdTurn))     cmdTurn     = Math.trunc(b.cmdTurn);
      if (isNum(b.avoidFwdMax)) avoidFwdMax = Math.trunc(b.avoidFwdMax);
      if (isNum(b.avoidTurn))   avoidTurn   = Math.trunc(b.avoidTurn);
      if (b.obstacleWarn !== undefined) obstacleWarn = !!b.obstacleWarn;
    }

    // Réglage à chaud : seuls les champs fournis (et finis) sont pris ; pas
    // de bornes (le sim sert à CHERCHER des gains, contrairement au firmware
    // qui borne les siens).
    function setGains(g) {
      g = g || {};
      if (isNum(g.kp)) kp = g.kp;
      if (isNum(g.ki)) ki = g.ki;
      if (isNum(g.kd)) kd = g.kd;
      if (isNum(g.kpPhi)) kpPhi = g.kpPhi;
      if (isNum(g.kv)) kv = g.kv;
      if (isNum(g.kOut)) kOut = g.kOut;
      if (g.cascade !== undefined) cascade = !!g.cascade;
    }

    // Reset initial : scénario demandé, sinon « θ0=2° propre » avec le bruit
    // des options.
    reset(options.scenario || { theta0Deg: 2, tmax: 6, noise: noise, push: null });

    return {
      reset: reset,
      step: step,
      stepMany: stepMany,
      state: state,
      setCustom: setCustom,
      setNoise: setNoise,
      setGains: setGains,
      setBotState: setBotState
    };
  }

  var BalanceEngine = Object.freeze({
    create: create,
    defaults: defaults,
    scenarios: scenarios,
    constants: constants,
    // Exposé pour l'auto-test (comparaison avec random.seed(42) de CPython).
    PyRandom: PyRandom
  });

  root.BalanceEngine = BalanceEngine;
  // Node (auto-test en ligne de commande : `node selfcheck.js`) — inerte dans
  // un navigateur, ce n'est PAS un module ES.
  if (typeof module !== "undefined" && module.exports) module.exports = BalanceEngine;
})(typeof window !== "undefined" ? window : globalThis);

/* ═══════════════════════════════════════════════════════════════════
 * AUTO-TEST : ouvrir sim/web/selfcheck.html (navigateur, file://) ou lancer
 * `node sim/web/selfcheck.js`. Attendu (identique à `python3 balancebot_sim.py`) :
 *   · gains par défaut Kp25/Ki500/Kd0.5, k_out=1, cascade ON, graine 42 :
 *     0/6, « chute θ » en 0,4-0,5 s (t = 0,495 / 0,495 / 0,385 / 0,445 / 0,445 / 0,445) ;
 *   · Kp25/Ki350/Kd1, k_out=3, kv=0, cascade ON, θ0=2° propre : « ok » (θ fini ≈ 0°).
 * ═══════════════════════════════════════════════════════════════════ */
