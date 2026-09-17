/* ═══════════════════════════════════════════════════════════════════
 * BalanceBot — simulateur web : CAPTEUR ULTRASON + TÊTE (ultrason.js)
 *
 * Transcription COMPORTEMENTALE de balance-bot/head.cpp (mesure HC-SR04,
 * cadence adaptative, lissage, balayage pan/tilt). RÈGLE D'OR : mêmes
 * constantes que balance-bot/config.h, même ORDRE d'opérations que
 * head.cpp — les lignes du firmware sont citées en commentaire.
 *
 * Ce module ne contient AUCUNE physique d'équilibre : il ne lit que le
 * temps simulé (pas de 5 ms, 200 Hz = BALANCE_LOOP_HZ de config.h) et la
 * distance RÉELLE capteur→obstacle fournie par le viewer. Il ne réagit
 * pas physiquement à l'obstacle : comme le firmware, il publie seulement
 * obstacleCm / obstacleWarn / angleVu (head.cpp l.162-170).
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
 *   capteur.reset()               comme Head::begin() (head.cpp l.45-98)
 *   capteur.state                 vue lecture seule (mise à jour à chaque tick)
 * ═══════════════════════════════════════════════════════════════════ */
(function (root) {
  "use strict";

  // ── Constantes de balance-bot/config.h ─────────────────────────────
  var US_MAX_CM = 150;            // config.h l.75 : portée utile du HC-SR04
  var US_STOP_CM = 25;            // config.h l.76 : distance d'alerte
  var HEAD_PAN_MIN = 0;           // config.h l.71
  var HEAD_PAN_MAX = 180;         // config.h l.72
  var HEAD_TILT_MIN = 20;         // config.h l.73
  var HEAD_TILT_MAX = 90;         // config.h l.74
  var DT_MS = 5;                  // 200 Hz = BALANCE_LOOP_HZ (config.h l.65)

  // ── Constantes de balance-bot/head.cpp ─────────────────────────────
  var US_SMOOTH_COUNT = 5;                            // l.27
  var PAN_SPEED_DEG = 30.0, TILT_SPEED_DEG = 30.0;    // l.38-39 (°/s)
  var PAN_CENTRE = 90.0, TILT_CENTRE = 60.0;          // l.59-62, l.194-195
  // Timeout pulseIn : portée utile × 58 µs/cm + marge (l.134).
  var ECHO_TIMEOUT_US = US_MAX_CM * 58 + 800;         // = 9500 µs
  // Cadence adaptative : 200 ms, 1000 ms après 3 échecs consécutifs (l.108).
  var INTERVAL_NORMALE_MS = 200, INTERVAL_ECHEC_MS = 1000;

  function create() {
    // ── Horloge simulée : ENTIÈRE en ms (5 ms par tick), comme millis() ──
    var tMs = 0;

    // ── État de la mesure (head.cpp) ──
    var lastUsMeasureMs = 0;      // l.106 : 0 → 1re mesure à t = 200 ms
    var usFailStreak = 0;         // l.107
    var usAvg = 0.0;              // l.26 : la moyenne EST la distance lissée
    var usSampleCount = 0;        // l.28 : 0 = moyenne pas encore amorcée
    var actif = true;             // false = capteur absent / ECHO débranché

    // ── État du balayage de tête (head.cpp l.33-37) : FLOAT, comme le
    //    firmware (un int tronquerait l'incrément fractionnaire à 0). ──
    var panPos = PAN_CENTRE, tiltPos = TILT_CENTRE;
    var panDir = 1, tiltDir = 1;                    // l.36-37
    var headPanDeg = 90, headTiltDeg = 60;          // l.91-92 (arrondi publié)

    var obstacleSeenAngle = -1;                     // l.42
    var equilibreCourant = true;                    // g_state.balancing

    // ── Vue publique (réécrite à chaque tick ; les champs reflètent
    //    g_state.obstacleCm / obstacleWarn de head.cpp) ──
    var state = {
      tMs: 0,                    // horloge simulée (ms entières)
      obstacleCm: -1,            // g_state.obstacleCm (l.147/162/174)
      obstacleWarn: false,       // g_state.obstacleWarn (l.148/163)
      angleVu: -1,               // obstacleSeenAngle (l.42/149/166-169)
      failStreak: 0,             // échecs consécutifs (l.107)
      cadenceMs: INTERVAL_NORMALE_MS,  // intervalle courant (l.108)
      nbMesures: 0,              // mesures tentées depuis le reset
      derniereMesureMs: 0,       // horodatage de la dernière tentative
      mesureFaite: false,        // true le tick où une mesure a eu lieu
      actif: true,
      headPanDeg: 90,            // g_state.headPanDeg (l.208)
      headTiltDeg: 60            // g_state.headTiltDeg (l.209)
    };

    function constrain(v, lo, hi) { return v < lo ? lo : (v > hi ? hi : v); }

    // ── measureUltrasonic() (head.cpp l.122-178) ─────────────────────
    // distReelCm : distance RÉELLE capteur→obstacle calculée par le viewer
    // (−1 = rien devant). Retourne true si un écho a été reçu.
    function measureUltrasonic(distReelCm) {
      // pulseIn(ECHO, HIGH, ECHO_TIMEOUT_US) : l'écho revient si la durée
      // aller-retour (dist × 58 µs/cm) tient dans le timeout (l.134-135).
      // Capteur débranché : ECHO ne monte jamais → timeout systématique.
      var dureeOk = actif && distReelCm >= 0 &&
                    distReelCm * 58.0 <= ECHO_TIMEOUT_US;

      // l.137-140 : distance = durée / 58 ; timeout → −1.
      var distanceCm = dureeOk ? distReelCm : -1.0;

      // l.146-151 : le timeout N'EST PAS injecté dans la moyenne — elle
      // est gardée en l'état pour le prochain écho.
      if (distanceCm < 0.0) {
        state.obstacleCm = -1.0;
        state.obstacleWarn = false;
        obstacleSeenAngle = -1;
        return false;
      }

      // l.155-157 : moyenne glissante exponentielle sur 5 échantillons,
      // amorcée sur la première mesure.
      if (usSampleCount === 0) usAvg = distanceCm;
      else                     usAvg += (distanceCm - usAvg) / US_SMOOTH_COUNT;
      if (usSampleCount < US_SMOOTH_COUNT) usSampleCount++;

      var smoothedDistance = usAvg;                 // l.159

      // l.162-163 : publication de l'état.
      state.obstacleCm = smoothedDistance;
      state.obstacleWarn = (smoothedDistance < US_STOP_CM);

      // l.166-170 : angle où l'obstacle a été vu.
      if (state.obstacleWarn) {
        if (obstacleSeenAngle < 0) obstacleSeenAngle = headPanDeg;
      } else {
        obstacleSeenAngle = -1;
      }

      // l.173-175 : clamp à la portée utile (écho reçu mais trop loin :
      // ce n'est PAS un échec, la cadence reste à 200 ms).
      if (smoothedDistance > US_MAX_CM) {
        state.obstacleCm = -1.0;                    // hors portée
      }
      return true;
    }

    // ── handleHeadMovement() (head.cpp l.181-217, sans l'écriture servo) ──
    function handleHeadMovement(dt) {
      if (dt <= 0.0) return;                        // l.187
      if (dt > 0.1) dt = 0.1;                       // l.188

      if (equilibreCourant) {
        // l.190-195 : équilibre → tête ramenée au centre, vitesse bornée.
        var panStep = PAN_SPEED_DEG * dt;
        var tiltStep = TILT_SPEED_DEG * dt;
        panPos += constrain(PAN_CENTRE - panPos, -panStep, panStep);
        tiltPos += constrain(TILT_CENTRE - tiltPos, -tiltStep, tiltStep);
      } else {
        // l.196-205 : robot au sol → balayage continu pan puis tilt.
        panPos += PAN_SPEED_DEG * panDir * dt;
        if (panPos <= HEAD_PAN_MIN)      { panPos = HEAD_PAN_MIN; panDir = 1; }
        else if (panPos >= HEAD_PAN_MAX) { panPos = HEAD_PAN_MAX; panDir = -1; }

        tiltPos += TILT_SPEED_DEG * tiltDir * dt;
        if (tiltPos <= HEAD_TILT_MIN)      { tiltPos = HEAD_TILT_MIN; tiltDir = 1; }
        else if (tiltPos >= HEAD_TILT_MAX) { tiltPos = HEAD_TILT_MAX; tiltDir = -1; }
      }

      // l.208-209 : publication de l'arrondi.
      headPanDeg = Math.round(panPos);
      headTiltDeg = Math.round(tiltPos);
    }

    // ── UN pas de 5 ms : ordre de Head::loop() (l.101-117) : la mesure
    //    d'abord, le balayage ensuite. ──
    function tick(distReelCm, enEquilibre) {
      tMs += DT_MS;
      equilibreCourant = !!enEquilibre;
      state.mesureFaite = false;

      // l.106-113 : cadence ADAPTATIVE. 200 ms tant que l'écho revient ;
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

      handleHeadMovement(DT_MS / 1000.0);

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

    // ── reset() : Head::begin() (l.84-95) — lissage et balayage remis à
    //    zéro, horloge repartie (le viewer le couple au reset du moteur). ──
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
      state.tMs = 0;
      state.obstacleCm = -1.0;
      state.obstacleWarn = false;
      state.angleVu = -1;
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
      US_SMOOTH_COUNT: US_SMOOTH_COUNT,
      ECHO_TIMEOUT_US: ECHO_TIMEOUT_US,
      INTERVAL_NORMALE_MS: INTERVAL_NORMALE_MS,
      INTERVAL_ECHEC_MS: INTERVAL_ECHEC_MS,
      HEAD_PAN_MIN: HEAD_PAN_MIN, HEAD_PAN_MAX: HEAD_PAN_MAX,
      HEAD_TILT_MIN: HEAD_TILT_MIN, HEAD_TILT_MAX: HEAD_TILT_MAX,
      PAN_SPEED_DEG: PAN_SPEED_DEG, TILT_SPEED_DEG: TILT_SPEED_DEG,
      DT_MS: DT_MS
    })
  });

  root.Ultrason = Ultrason;
  // Node (auto-test en ligne de commande) — inerte dans un navigateur.
  if (typeof module !== "undefined" && module.exports) module.exports = Ultrason;
})(typeof window !== "undefined" ? window : globalThis);
