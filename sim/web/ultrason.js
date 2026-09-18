/* ═══════════════════════════════════════════════════════════════════
 * BalanceBot — simulateur web : CAPTEUR ULTRASON + TÊTE + ÉVITEMENT (ultrason.js)
 *
 * Transcription COMPORTEMENTALE de balance-bot/head.cpp (mesure HC-SR04,
 * cadence adaptative, lissage, balayage pan/tilt, machine à états
 * d'évitement). RÈGLE D'OR : mêmes constantes que balance-bot/config.h,
 * même ORDRE d'opérations que head.cpp — les lignes du firmware sont citées
 * en commentaire (head.cpp / config.h : commit 10044c0 ; balance.cpp : 2fafb7c).
 *
 * Ce module ne contient AUCUNE physique d'équilibre : il ne lit que le
 * temps simulé (pas de 5 ms, 200 Hz = BALANCE_LOOP_HZ de config.h) et la
 * distance RÉELLE capteur→obstacle fournie par le viewer. Comme le
 * firmware, il ne touche JAMAIS au PID : il publie obstacleCm /
 * obstacleWarn / obstacleSlow / obstacleSide / angleVu (head.cpp
 * l.244-273) et les CONSIGNES d'évitement avoidFwdMax / avoidTurn /
 * avoidPhase (l.85-137), que le moteur (engine.js, miroir de balance.cpp
 * l.673-692) applique aux consignes de déplacement AVANT leur lissage.
 *
 * Plain JS, zéro dépendance : définit UN global `window.Ultrason`
 * (export Node pour l'auto-test : `node sim/web/selfcheck.js`).
 *
 *   Ultrason.create()            → capteur
 *   Ultrason.constants           → constantes de config.h / head.cpp
 *
 *   capteur.tick(distCm, enEquilibre)        un pas de 5 ms
 *   capteur.tickMany(n, distCm, enEquilibre) n pas d'un coup
 *   capteur.setActif(bool)        false = ECHO débranché (timeouts en série)
 *   capteur.reset()               comme Head::begin() (head.cpp l.140-193)
 *   capteur.state                 vue lecture seule (mise à jour à chaque tick)
 * ═══════════════════════════════════════════════════════════════════ */
(function (root) {
  "use strict";

  // ── Constantes de balance-bot/config.h ─────────────────────────────
  var US_MAX_CM = 150;            // config.h l.103 : portée utile du HC-SR04
  var US_STOP_CM = 25;            // config.h l.104 : ne plus avancer, reculer doucement
  var US_SLOW_CM = 60;            // config.h l.105 : sous cette distance (et ≥ US_STOP_CM) : ralentir
  var US_CLEAR_CM = 35;           // config.h l.163 : hystérésis, fin d'évitement seulement au-delà
  var HEAD_PAN_MIN = 0;           // config.h l.99
  var HEAD_PAN_MAX = 180;         // config.h l.100
  var HEAD_TILT_MIN = 20;         // config.h l.101
  var HEAD_TILT_MAX = 90;         // config.h l.102
  var HEAD_BALANCE_SWEEP_DEG = 30;  // config.h l.168 : balayage ±30° autour du centre EN ÉQUILIBRE (0 = tête fixe)
  var DT_MS = 5;                  // 200 Hz = BALANCE_LOOP_HZ (config.h l.92)
  // Évitement (config.h l.152-163), en unités de consigne UI (−100..100).
  var AVOID_SLOW_CMD = 40;        // l.156 : < US_SLOW_CM → marche avant plafonnée à 40 %
  var AVOID_BACK_CMD = 20;        // l.157 : < US_STOP_CM → recul doux à 20 % (≈ 1,2° de consigne)
  var AVOID_BACK_MAX_MS = 1500;   // l.158 : recul borné dans le temps (capteur masqué)
  var AVOID_TURN_CMD = 40;        // l.159 : pivot vers le côté libre pendant le recul
  var AVOID_TURN_SIGN = +1;       // l.160 : −1 si le robot pivote VERS l'obstacle au premier essai
  var AVOID_SIDE_DEAD_DEG = 10;   // l.161 : |pan − 90| sous ce seuil → obstacle « en face »
  var AVOID_DEFAULT_SIDE = +1;    // l.162 : côté choisi quand l'obstacle est en face

  // ── Constantes de balance-bot/head.cpp ─────────────────────────────
  var US_SMOOTH_COUNT = 5;                            // l.39
  var PAN_SPEED_DEG = 30.0, TILT_SPEED_DEG = 30.0;    // l.50-51 (°/s)
  var PAN_CENTRE = 90.0, TILT_CENTRE = 60.0;          // l.45-46, l.156-157, l.184-187
  // Timeout pulseIn : portée utile × 58 µs/cm + marge (l.232).
  var ECHO_TIMEOUT_US = US_MAX_CM * 58 + 800;         // = 9500 µs
  // Dans le core ESP32 (wiring_pulse.c), le chronomètre de pulseIn part À
  // L'APPEL : l'attente du front montant d'ECHO (~450–500 µs après TRIG sur
  // un HC-SR04, délai interne du module) consomme le budget — c'est
  // justement à quoi sert la marge de 800 µs du firmware. Conséquence : le
  // vrai robot compte un échec au-delà de (9500 − 480)/58 ≈ 155 cm, pas
  // 163,8 cm. On reproduit ce délai (480 µs, milieu de la plage mesurée) ;
  // le négliger laisserait le simulateur « voir » des échos entre ~155 et
  // ~164 cm que le robot réel ne verrait pas.
  var ECHO_DELAI_FRONT_US = 480;
  // Cadence adaptative : 200 ms, 1000 ms après 3 échecs consécutifs (l.203).
  var INTERVAL_NORMALE_MS = 200, INTERVAL_ECHEC_MS = 1000;
  // Phases de l'évitement (head.cpp l.70 : enum AvoidPhase).
  var AV_LIBRE = 0, AV_RALENTI = 1, AV_RECUL = 2, AV_PIVOT = 3;

  function create() {
    // ── Horloge simulée : ENTIÈRE en ms (5 ms par tick), comme millis() ──
    var tMs = 0;

    // ── État de la mesure (head.cpp) ──
    var lastUsMeasureMs = 0;      // l.201 : 0 → 1re mesure à t = 200 ms
    var usFailStreak = 0;         // l.202
    var usAvg = 0.0;              // l.38 : la moyenne EST la distance lissée
    var usSampleCount = 0;        // l.40 : 0 = moyenne pas encore amorcée
    var actif = true;             // false = capteur absent / ECHO débranché

    // ── État du balayage de tête (head.cpp l.45-49) : FLOAT, comme le
    //    firmware (un int tronquerait l'incrément fractionnaire à 0). ──
    var panPos = PAN_CENTRE, tiltPos = TILT_CENTRE;
    var panDir = 1, tiltDir = 1;                    // l.48-49
    var headPanDeg = 90, headTiltDeg = 60;          // l.186-187 (arrondi publié)

    var obstacleSeenAngle = -1;                     // l.55
    var equilibreCourant = true;                    // g_state.balancing

    // ── État de l'évitement (head.cpp l.70-73) ──
    var avoidPhase = AV_LIBRE;                      // l.71
    var avoidSinceMs = 0;                           // l.72 : entrée dans RECUL
    var avoidSide = 0;                              // l.73 : côté verrouillé (−1 / +1)

    // ── Vue publique (réécrite à chaque tick ; les champs reflètent
    //    g_state.obstacle* / avoid* de head.cpp) ──
    var state = {
      tMs: 0,                    // horloge simulée (ms entières)
      obstacleCm: -1,            // g_state.obstacleCm (l.245/262/277)
      obstacleWarn: false,       // g_state.obstacleWarn (l.246/263) : < US_STOP_CM
      obstacleSlow: false,       // g_state.obstacleSlow (l.247/264) : US_STOP_CM ≤ d < US_SLOW_CM
      obstacleSide: 0,           // g_state.obstacleSide (l.248/273) : −1 pan<90, +1 pan>90, 0 en face/inconnu
      angleVu: -1,               // obstacleSeenAngle (l.55/249/268-272)
      avoidFwdMax: 100,          // g_state.avoidFwdMax (l.86) : 100 libre · 40 ralenti · 0 stop · <0 recul imposé
      avoidTurn: 0,              // g_state.avoidTurn (l.87) : pivot imposé si l'UI ne tourne pas
      avoidPhase: AV_LIBRE,      // g_state.avoidPhase (l.88) : 0 libre · 1 ralenti · 2 recul+pivot · 3 pivot seul
      failStreak: 0,             // échecs consécutifs (l.202)
      cadenceMs: INTERVAL_NORMALE_MS,  // intervalle courant (l.203)
      nbMesures: 0,              // mesures tentées depuis le reset
      derniereMesureMs: 0,       // horodatage de la dernière tentative
      mesureFaite: false,        // true le tick où une mesure a eu lieu
      actif: true,
      headPanDeg: 90,            // g_state.headPanDeg (l.324)
      headTiltDeg: 60            // g_state.headTiltDeg (l.325)
    };

    function constrain(v, lo, hi) { return v < lo ? lo : (v > hi ? hi : v); }

    // ── sideFromPan() (head.cpp l.78-83) : côté de l'obstacle d'après
    //    l'angle de tête. Le sens mécanique n'est pas connu du firmware
    //    (AVOID_TURN_SIGN le règle au premier essai réel). ──
    function sideFromPan(panDeg) {
      var d = panDeg - 90;
      if (d >  AVOID_SIDE_DEAD_DEG) return +1;
      if (d < -AVOID_SIDE_DEAD_DEG) return -1;
      return 0;                                     // en face : côté par défaut
    }

    // ── publishAvoid() (head.cpp l.85-89) ──
    function publishAvoid(fwdMax, turn) {
      state.avoidFwdMax = fwdMax;
      state.avoidTurn = turn;
      state.avoidPhase = avoidPhase;
    }

    // ── updateAvoidance() (head.cpp l.91-137) : machine à états, 50 Hz
    //    dans le firmware (avec la tête), à chaque tick de 5 ms ici — elle ne
    //    change d'état qu'aux mesures (200 ms) et sur le compteur de recul
    //    (1,5 s), la granularité est sans effet. ──
    function updateAvoidance() {
      // l.95-99 : uniquement quand le robot tient debout.
      if (!equilibreCourant) {
        avoidPhase = AV_LIBRE;
        publishAvoid(100, 0);
        return;
      }
      var now = tMs;                                // l.100 : millis()
      var d = state.obstacleCm;                     // l.101 : −1 = pas d'écho
      var seen = (d >= 0.0);                        // l.102

      switch (avoidPhase) {                         // l.104-129
        case AV_LIBRE:
        case AV_RALENTI:
          if (state.obstacleWarn) {                 // l.107 : d < US_STOP_CM
            avoidPhase = AV_RECUL;
            avoidSinceMs = now;
            var side = (obstacleSeenAngle >= 0) ? sideFromPan(obstacleSeenAngle) : 0;
            if (side === 0) side = AVOID_DEFAULT_SIDE;
            // l.112-114 : obstacle vu à droite (+1) → pivoter à gauche : −side,
            // au signe mécanique près.
            avoidSide = -side * AVOID_TURN_SIGN;
          } else if (state.obstacleSlow) {          // l.115
            avoidPhase = AV_RALENTI;
          } else {
            avoidPhase = AV_LIBRE;
          }
          break;
        case AV_RECUL:
        case AV_PIVOT:
          if (!seen || d > US_CLEAR_CM) {           // l.123 : passage dégagé (hystérésis)
            avoidPhase = state.obstacleSlow ? AV_RALENTI : AV_LIBRE;
          } else if (avoidPhase === AV_RECUL && now - avoidSinceMs >= AVOID_BACK_MAX_MS) {
            avoidPhase = AV_PIVOT;                  // l.126 : on ne recule pas à l'infini
          }
          break;
      }

      switch (avoidPhase) {                         // l.131-136
        case AV_LIBRE:   publishAvoid(100, 0); break;
        case AV_RALENTI: publishAvoid(AVOID_SLOW_CMD, 0); break;
        case AV_RECUL:   publishAvoid(-AVOID_BACK_CMD, avoidSide * AVOID_TURN_CMD); break;
        case AV_PIVOT:   publishAvoid(0, avoidSide * AVOID_TURN_CMD); break;
      }
    }

    // ── measureUltrasonic() (head.cpp l.220-281) ─────────────────────
    // distReelCm : distance RÉELLE capteur→obstacle calculée par le viewer
    // (−1 = rien devant). Retourne true si un écho a été reçu.
    function measureUltrasonic(distReelCm) {
      // pulseIn(ECHO, HIGH, ECHO_TIMEOUT_US) : le budget du timeout couvre
      // AUSSI l'attente du front montant (ECHO_DELAI_FRONT_US, voir en
      // tête) — l'écho revient si délai + durée aller-retour (dist × 58
      // µs/cm) tient dans le timeout (l.232-233, wiring_pulse.c).
      // Capteur débranché : ECHO ne monte jamais → timeout systématique.
      var dureeOk = actif && distReelCm >= 0 &&
                    distReelCm * 58.0 + ECHO_DELAI_FRONT_US <= ECHO_TIMEOUT_US;

      // l.235-238 : distance = durée / 58 ; timeout → −1.
      var distanceCm = dureeOk ? distReelCm : -1.0;

      // l.244-251 : le timeout N'EST PAS injecté dans la moyenne — elle
      // est gardée en l'état pour le prochain écho.
      if (distanceCm < 0.0) {
        state.obstacleCm = -1.0;
        state.obstacleWarn = false;
        state.obstacleSlow = false;
        state.obstacleSide = 0;
        obstacleSeenAngle = -1;
        return false;
      }

      // l.255-257 : moyenne glissante exponentielle sur 5 échantillons,
      // amorcée sur la première mesure.
      if (usSampleCount === 0) usAvg = distanceCm;
      else                     usAvg += (distanceCm - usAvg) / US_SMOOTH_COUNT;
      if (usSampleCount < US_SMOOTH_COUNT) usSampleCount++;

      var smoothedDistance = usAvg;                 // l.259

      // l.262-264 : publication de l'état.
      state.obstacleCm = smoothedDistance;
      state.obstacleWarn = (smoothedDistance < US_STOP_CM);
      state.obstacleSlow = (smoothedDistance >= US_STOP_CM && smoothedDistance < US_SLOW_CM);

      // l.266-273 : angle où l'obstacle a été vu (premier écho sous
      // US_STOP_CM dans le balayage courant) → côté publié pour l'évitement.
      if (state.obstacleWarn) {
        if (obstacleSeenAngle < 0) obstacleSeenAngle = headPanDeg;
      } else {
        obstacleSeenAngle = -1;
      }
      state.obstacleSide = (obstacleSeenAngle >= 0) ? sideFromPan(obstacleSeenAngle) : 0;

      // l.275-278 : clamp à la portée utile (écho reçu mais trop loin :
      // ce n'est PAS un échec, la cadence reste à 200 ms).
      if (smoothedDistance > US_MAX_CM) {
        state.obstacleCm = -1.0;                    // hors portée
      }
      return true;
    }

    // ── handleHeadMovement() (head.cpp l.284-333, sans l'écriture servo) ──
    function handleHeadMovement(dt) {
      if (dt <= 0.0) return;                        // l.290
      if (dt > 0.1) dt = 0.1;                       // l.291

      if (equilibreCourant) {
        // l.293-311 : équilibre → tilt ramené au centre (vitesse bornée) ;
        // pan en balayage ÉTROIT ±HEAD_BALANCE_SWEEP_DEG autour de 90°
        // (0 = tête fixe, comportement d'avant 10044c0) — c'est ce balayage
        // qui donne un CÔTÉ à l'obstacle pour l'évitement.
        var panStep = PAN_SPEED_DEG * dt;
        var tiltStep = TILT_SPEED_DEG * dt;
        tiltPos += constrain(TILT_CENTRE - tiltPos, -tiltStep, tiltStep);
        var kLo = PAN_CENTRE - HEAD_BALANCE_SWEEP_DEG;
        var kHi = PAN_CENTRE + HEAD_BALANCE_SWEEP_DEG;
        if (HEAD_BALANCE_SWEEP_DEG <= 0 || panPos < kLo - panStep || panPos > kHi + panStep) {
          // l.304-306 : hors de la fenêtre (on vient du balayage large) : retour au centre
          panPos += constrain(PAN_CENTRE - panPos, -panStep, panStep);
        } else {
          panPos += PAN_SPEED_DEG * panDir * dt;    // l.308-310
          if (panPos <= kLo)      { panPos = kLo; panDir = 1; }
          else if (panPos >= kHi) { panPos = kHi; panDir = -1; }
        }
      } else {
        // l.312-321 : robot au sol → balayage continu pan puis tilt.
        panPos += PAN_SPEED_DEG * panDir * dt;
        if (panPos <= HEAD_PAN_MIN)      { panPos = HEAD_PAN_MIN; panDir = 1; }
        else if (panPos >= HEAD_PAN_MAX) { panPos = HEAD_PAN_MAX; panDir = -1; }

        tiltPos += TILT_SPEED_DEG * tiltDir * dt;
        if (tiltPos <= HEAD_TILT_MIN)      { tiltPos = HEAD_TILT_MIN; tiltDir = 1; }
        else if (tiltPos >= HEAD_TILT_MAX) { tiltPos = HEAD_TILT_MAX; tiltDir = -1; }
      }

      // l.324-325 : publication de l'arrondi.
      headPanDeg = Math.round(panPos);
      headTiltDeg = Math.round(tiltPos);
    }

    // ── UN pas de 5 ms : ordre de Head::loop() (l.196-215) : la mesure
    //    d'abord, le balayage ensuite, l'évitement en dernier. ──
    function tick(distReelCm, enEquilibre) {
      tMs += DT_MS;
      equilibreCourant = !!enEquilibre;
      state.mesureFaite = false;

      // l.201-208 : cadence ADAPTATIVE. 200 ms tant que l'écho revient ;
      // 1000 ms après 3 échecs consécutifs ; retour à 200 ms dès qu'un
      // écho revient (failStreak repart à 0).
      var interval = (usFailStreak >= 3) ? INTERVAL_ECHEC_MS : INTERVAL_NORMALE_MS;
      state.cadenceMs = interval;
      if (tMs - lastUsMeasureMs >= interval) {
        lastUsMeasureMs = tMs;
        state.nbMesures++;
        state.derniereMesureMs = tMs;
        state.mesureFaite = true;
        if (measureUltrasonic(distReelCm)) usFailStreak = 0;
        else                               usFailStreak++;
      }

      handleHeadMovement(DT_MS / 1000.0);           // l.211

      updateAvoidance();                            // l.214

      // Recopie de l'état interne dans la vue publique.
      state.tMs = tMs;
      state.failStreak = usFailStreak;
      state.angleVu = obstacleSeenAngle;
      state.headPanDeg = headPanDeg;
      state.headTiltDeg = headTiltDeg;
      state.actif = actif;
    }

    function tickMany(n, distReelCm, enEquilibre) {
      n = Math.trunc(Number(n) || 0);
      while (n-- > 0) tick(distReelCm, enEquilibre);
    }

    function setActif(b) { actif = !!b; }

    // ── reset() : Head::begin() (l.179-191) — lissage et balayage remis à
    //    zéro, horloge repartie (le viewer le couple au reset du moteur) ;
    //    l'évitement repart LIBRE comme au boot. ──
    function reset() {
      tMs = 0;
      lastUsMeasureMs = 0;
      usFailStreak = 0;
      usAvg = 0.0;
      usSampleCount = 0;
      panPos = PAN_CENTRE; tiltPos = TILT_CENTRE;
      panDir = 1; tiltDir = 1;
      headPanDeg = 90; headTiltDeg = 60;
      obstacleSeenAngle = -1;
      avoidPhase = AV_LIBRE; avoidSinceMs = 0; avoidSide = 0;
      state.tMs = 0;
      state.obstacleCm = -1.0;
      state.obstacleWarn = false;
      state.obstacleSlow = false;
      state.obstacleSide = 0;
      state.angleVu = -1;
      state.avoidFwdMax = 100;
      state.avoidTurn = 0;
      state.avoidPhase = AV_LIBRE;
      state.failStreak = 0;
      state.cadenceMs = INTERVAL_NORMALE_MS;
      state.nbMesures = 0;
      state.derniereMesureMs = 0;
      state.mesureFaite = false;
      state.headPanDeg = 90;
      state.headTiltDeg = 60;
    }

    reset();
    return {
      tick: tick,
      tickMany: tickMany,
      setActif: setActif,
      reset: reset,
      state: state
    };
  }

  var Ultrason = Object.freeze({
    create: create,
    constants: Object.freeze({
      US_MAX_CM: US_MAX_CM,
      US_STOP_CM: US_STOP_CM,
      US_SLOW_CM: US_SLOW_CM,
      US_CLEAR_CM: US_CLEAR_CM,
      US_SMOOTH_COUNT: US_SMOOTH_COUNT,
      ECHO_TIMEOUT_US: ECHO_TIMEOUT_US,
      ECHO_DELAI_FRONT_US: ECHO_DELAI_FRONT_US,
      INTERVAL_NORMALE_MS: INTERVAL_NORMALE_MS,
      INTERVAL_ECHEC_MS: INTERVAL_ECHEC_MS,
      HEAD_PAN_MIN: HEAD_PAN_MIN, HEAD_PAN_MAX: HEAD_PAN_MAX,
      HEAD_TILT_MIN: HEAD_TILT_MIN, HEAD_TILT_MAX: HEAD_TILT_MAX,
      HEAD_BALANCE_SWEEP_DEG: HEAD_BALANCE_SWEEP_DEG,
      PAN_SPEED_DEG: PAN_SPEED_DEG, TILT_SPEED_DEG: TILT_SPEED_DEG,
      AVOID_SLOW_CMD: AVOID_SLOW_CMD, AVOID_BACK_CMD: AVOID_BACK_CMD,
      AVOID_BACK_MAX_MS: AVOID_BACK_MAX_MS, AVOID_TURN_CMD: AVOID_TURN_CMD,
      AVOID_TURN_SIGN: AVOID_TURN_SIGN, AVOID_SIDE_DEAD_DEG: AVOID_SIDE_DEAD_DEG,
      AVOID_DEFAULT_SIDE: AVOID_DEFAULT_SIDE,
      AV_LIBRE: AV_LIBRE, AV_RALENTI: AV_RALENTI, AV_RECUL: AV_RECUL, AV_PIVOT: AV_PIVOT,
      DT_MS: DT_MS
    })
  });

  root.Ultrason = Ultrason;
  // Node (auto-test en ligne de commande) — inerte dans un navigateur.
  if (typeof module !== "undefined" && module.exports) module.exports = Ultrason;
})(typeof window !== "undefined" ? window : globalThis);
