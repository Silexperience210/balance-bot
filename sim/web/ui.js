/* BalanceBot — viewer 3D (visualisation Three.js + éditeur).
   Ne contient AUCUNE physique : tout le calcul passe par window.BalanceEngine
   (contrat commun /tmp/balancebot-web-spec.md). Plain JS, zéro build, zéro fetch.

   CONVENTION DE REPÈRE 3D (rendu)
   -------------------------------
   Les pièces (parts.js, généré par chassis/assets/exporter_parts_web.py) sont
   les VRAIS STL du châssis, convertis du repère design Blender (Z-up :
   X = voie gauche→droite, Y = arrière→avant, Z = haut, sol z = 0) vers le
   repère Three.js Y-up par permutation cyclique (déterminant +1) :
       x_three = y_design  (avance / roulement)
       y_three = z_design  (verticale)
       z_three = x_design  (axe transverse = axe des ROUES = axe de tangage)
   Origine robot : point central de l'axe des roues — le groupe `robot` est
   posé à y = R (hauteur de l'axe) et tout pivote autour de l'axe Z local.
   - Le pitch θ est une rotation autour de l'axe Z.
   - Signe : θ > 0 → le corps penche vers +X et l'ensemble roule vers +X.
     En Three.js (rotation anti-horaire autour de +Z), cela donne :
       corps  .rotation.z = −θ(rad)
       roues  .rotation.z = −(θ + φ)(rad)   (spin des roues, φ = angle servo)
   - Roulement sans glissement (cohérent avec le Lagrange du contrat) :
       x_centre = R · (θ + φ)   (R = 41,5 mm = rayon de roulement WHEEL_R)
     à lacet nul ; avec le lacet ψ (couche déplacement du moteur : différentiel
     des roues sur la voie), la pose au sol est intégrée par le moteur
     (state.posX / posZ, m) et le robot tourne de −ψ autour de +Y (ψ > 0 =
     vers la droite, +Z). Les deux roues tournent de φ ± φ_diff.
   - θ, φ, φ_diff, ψ, posX, posZ viennent STRICTEMENT de sim.state. */
(function () {
  "use strict";

  var DEG = Math.PI / 180;

  // ---- Vérifie la présence du moteur (peut ne pas encore exister) ----
  if (!window.BalanceEngine || typeof window.BalanceEngine.create !== "function") {
    document.getElementById("msg-moteur").style.display = "block";
    return;
  }
  // ---- Vérifie la présence de Three.js (libs locales lib/) ----
  if (!window.THREE || !THREE.OrbitControls) {
    var msg = document.getElementById("msg-moteur");
    msg.textContent = "⚠ lib/three.min.js ou lib/OrbitControls.js introuvable.";
    msg.style.display = "block";
    return;
  }
  // ---- Vérifie la présence du module capteur ultrason (miroir de head.cpp) ----
  if (!window.Ultrason || typeof window.Ultrason.create !== "function") {
    var msgUs = document.getElementById("msg-moteur");
    msgUs.textContent = "⚠ ultrason.js introuvable ou invalide : window.Ultrason n'est pas défini.";
    msgUs.style.display = "block";
    return;
  }
  var BE = window.BalanceEngine;
  var US = window.Ultrason;

  // Constante géométrique du rendu (pas de physique ici) : rayon de roulement
  // WHEEL_R = 41,5 mm (gen_bitcoin_bot.py) — l'axe des roues est à 41,5 mm du sol.
  var R = 0.0415;

  // ---- État du viewer ----
  var sim = BE.create(BE.defaults);
  var us = US.create();          // capteur HC-SR04 + tête pan/tilt (head.cpp)
  var scenarioCourant = BE.scenarios[0];
  var enMarche = false;
  var accumulateur = 0;        // temps simulé à consommer (s)
  var vitesseLecture = 1;      // 0,5× / 1× / 2×
  var pasComptes = 0;          // pour la vitesse affichée (pas/s)
  var vitessePas = 0;          // moyenne lissée
  var dernierT = null;

  // ======================================================================
  // Réglages (sliders) — valeurs par défaut lues depuis BalanceEngine.defaults
  // ======================================================================
  var REGLAGES = [
    { cle: "kp",      nom: "Kp",      min: 0, max: 60,   pas: 0.5 },
    { cle: "ki",      nom: "Ki",      min: 0, max: 1000, pas: 5 },
    { cle: "kd",      nom: "Kd",      min: 0, max: 5,    pas: 0.05 },
    { cle: "kpPhi",   nom: "Kpφ",     min: 0, max: 3,    pas: 0.05 },
    { cle: "kv",      nom: "Kv",      min: 0, max: 10,   pas: 0.1 },
    { cle: "kOut",    nom: "k_out",   min: 0, max: 5,    pas: 0.1 },
    { cle: "noise",   nom: "Bruit",   min: 0, max: 1,    pas: 0.01 }
  ];
  var champs = {};   // cle -> {input, val}

  function litGains() {
    return {
      kp: +champs.kp.input.value,
      ki: +champs.ki.input.value,
      kd: +champs.kd.input.value,
      kpPhi: +champs.kpPhi.input.value,
      kv: +champs.kv.input.value,
      kOut: +champs.kOut.input.value,
      cascade: document.getElementById("rg-cascade").checked
    };
  }

  function pousseReglages() {
    sim.setGains(litGains());
    sim.setNoise(+champs.noise.input.value);
  }

  // ── JEUX DE GAINS ────────────────────────────────────────────────────
  // `embarques` = ce qui est FLASHÉ dans le firmware : il TOMBE (0/6 scénarios
  // mesurés) — c'est le constat de FIRMWARE_REVIEW.md §1bis, la raison même de
  // la campagne de réglage. `tient` = meilleur jeu trouvé au banc (5/6), la
  // cascade étant neutralisée (Kv = 0 : à Kv = 3 elle sature et fait tomber).
  var JEUX = {
    tient: {
      nom: "jeu qui TIENT (5/6 · Kv=0)",
      gains: { kp: 25, ki: 350, kd: 1, kpPhi: 0.8, kv: 0, kOut: 3 }
    },
    embarques: {
      nom: "gains EMBARQUÉS (il tombe)",
      gains: { kp: 25, ki: 500, kd: 0.5, kpPhi: 0.8, kv: 3, kOut: 1 }
    }
  };
  var jeuCourant = "tient";        // on ouvre sur un robot qui TIENT

  function appliqueJeu(nom) {
    var j = JEUX[nom];
    if (!j) return;
    jeuCourant = nom;
    Object.keys(j.gains).forEach(function (k) {
      if (!champs[k]) return;
      champs[k].input.value = j.gains[k];
      champs[k].val.textContent = (+j.gains[k]).toFixed(2);
    });
    pousseReglages();
  }

  function construitReglages() {
    var conteneur = document.getElementById("reglages");
    // Sélecteur de jeu de gains (au-dessus des sliders)
    var ligJ = document.createElement("div");
    ligJ.className = "reglage";
    ligJ.innerHTML = "<label>Jeu de gains</label><select id='sel-jeu'>" +
      Object.keys(JEUX).map(function (k) {
        return "<option value='" + k + "'>" + JEUX[k].nom + "</option>";
      }).join("") + "</select>";
    conteneur.appendChild(ligJ);

    REGLAGES.forEach(function (r) {
      var def = JEUX[jeuCourant].gains[r.cle];
      if (def === undefined) def = BE.defaults[r.cle];
      var ligne = document.createElement("div");
      ligne.className = "reglage";
      ligne.innerHTML =
        "<label>" + r.nom + "</label>" +
        "<input type='range' min='" + r.min + "' max='" + r.max + "' step='" + r.pas + "'>" +
        "<span class='val'></span>";
      var input = ligne.querySelector("input");
      var val = ligne.querySelector(".val");
      input.value = def;
      val.textContent = (+def).toFixed(2);
      input.addEventListener("input", function () {
        val.textContent = (+input.value).toFixed(2);
        pousseReglages();
      });
      conteneur.appendChild(ligne);
      champs[r.cle] = { input: input, val: val };
    });
    // Cascade : case à cocher
    var ligC = document.createElement("div");
    ligC.className = "reglage";
    ligC.innerHTML = "<label>Cascade</label><input type='checkbox' id='rg-cascade'>";
    var cb = ligC.querySelector("input");
    cb.checked = !!BE.defaults.cascade;
    cb.addEventListener("change", pousseReglages);
    conteneur.appendChild(ligC);

    var selJeu = document.getElementById("sel-jeu");
    selJeu.value = jeuCourant;
    selJeu.addEventListener("change", function () { appliqueJeu(this.value); });
  }

  // ======================================================================
  // Scénarios (boutons depuis BalanceEngine.scenarios)
  // ======================================================================
  function construitScenarios() {
    var conteneur = document.getElementById("scenarios");
    BE.scenarios.forEach(function (sc, i) {
      var b = document.createElement("button");
      b.textContent = sc.name;
      if (i === 0) b.classList.add("actif");
      b.addEventListener("click", function () {
        scenarioCourant = sc;
        conteneur.querySelectorAll("button").forEach(function (x) { x.classList.remove("actif"); });
        b.classList.add("actif");
        // Le scénario impose son propre niveau de bruit : on reflète dans le slider
        champs.noise.input.value = sc.noise;
        champs.noise.val.textContent = (+sc.noise).toFixed(2);
        sim.reset(sc);
        us.reset();              // le capteur repart comme le robot
        pousseEvitement();       // … et l'évitement repart LIBRE
        // Le slider vient d'être aligné sur sc.noise : pousseReglages() propage tout.
        pousseReglages();
        accumulateur = 0;
        enMarche = true;
        majBoutons();
      });
      conteneur.appendChild(b);
    });
  }

  // ======================================================================
  // RUN / PAUSE / RESET + vitesse de lecture
  // ======================================================================
  function majBoutons() {
    document.getElementById("btn-run").classList.toggle("actif", enMarche);
    document.getElementById("btn-pause").classList.toggle("actif", !enMarche);
  }
  document.getElementById("btn-run").addEventListener("click", function () {
    enMarche = true; majBoutons();
  });
  document.getElementById("btn-pause").addEventListener("click", function () {
    enMarche = false; majBoutons();
  });
  document.getElementById("btn-reset").addEventListener("click", function () {
    sim.reset(scenarioCourant);
    us.reset();                    // Head::begin() : lissage + balayage à zéro
    pousseEvitement();             // évitement LIBRE
    accumulateur = 0;
    enMarche = false;
    majBoutons();
  });

  document.getElementById("vitesses").querySelectorAll("button").forEach(function (b) {
    b.addEventListener("click", function () {
      vitesseLecture = parseFloat(b.getAttribute("data-v"));
      document.getElementById("vitesses").querySelectorAll("button").forEach(function (x) {
        x.classList.toggle("actif", x === b);
      });
    });
  });

  // ======================================================================
  // Éditeur « effets secondaires »
  // ======================================================================
  var CODE_DEFAUT =
"// Effets secondaires — appelé UNE fois par pas (200 Hz), APRÈS la physique.\n" +
"// t     : temps simulé (s)\n" +
"// state : état du robot, EN DEGRÉS (theta, thetaDot, phi, pidOut, pitchFilt, ...)\n" +
"// dt    : pas de temps (s)\n" +
"// Décommente un exemple ou écris le tien. La physique du cœur n'est PAS ici.\n" +
"function customEffects(t, state, dt) {\n" +
"  // Exemple 1 — vent constant (pousse régulièrement le corps) :\n" +
"  // state.thetaDot += 10 * dt;        // thetaDot est en °/s\n" +
"\n" +
"  // Exemple 2 — friction (amortit l'oscillation du corps) :\n" +
"  // state.thetaDot *= (1 - 0.5 * dt);\n" +
"\n" +
"  // Exemple 3 — décalage de mesure (le capteur filtré dérive de +0,3°) :\n" +
"  // state.pitchFilt += 0.3;\n" +
"\n" +
"  // Exemple 4 — coup ponctuel à t = 2 s (tape sur le robot) :\n" +
"  // if (t >= 2 && t < 2 + dt) state.thetaDot += 25;   // °/s\n" +
"}\n";

  var editeur = document.getElementById("editeur");
  var zoneErreur = document.getElementById("erreur-editeur");
  editeur.value = CODE_DEFAUT;

  document.getElementById("btn-appliquer").addEventListener("click", function () {
    try {
      // Le code doit définir `function customEffects(t, state, dt)` ; on la récupère.
      var fn = new Function(editeur.value + "\n;return customEffects;")();
      if (typeof fn !== "function") {
        throw new Error("Le code doit définir une fonction customEffects(t, state, dt).");
      }
      sim.setCustom(fn);
      zoneErreur.textContent = "";
    } catch (e) {
      // Erreur de syntaxe ou d'exécution à la compilation : on affiche, on ne plante pas.
      zoneErreur.textContent = "Erreur : " + e.message;
    }
  });
  document.getElementById("btn-reinit-code").addEventListener("click", function () {
    editeur.value = CODE_DEFAUT;
    zoneErreur.textContent = "";
    sim.setCustom(null);   // remet le modèle nominal (aucun effet)
  });

  // ======================================================================
  // Panneau « Capteur ultrason » : curseur d'obstacle + case « débranché »
  // ======================================================================
  var rgDistance = document.getElementById("rg-distance");
  var vDistance = document.getElementById("v-distance");
  rgDistance.addEventListener("input", function () {
    distanceObstacleM = (+rgDistance.value) / 100;
    vDistance.textContent = rgDistance.value + " cm";
    placeObstacle();
  });

  var rgCapteur = document.getElementById("rg-capteur");
  var vCapteur = document.getElementById("v-capteur");
  rgCapteur.addEventListener("change", function () {
    us.setActif(rgCapteur.checked);
    vCapteur.textContent = rgCapteur.checked ? "ECHO câblé" : "débranché";
  });

  // ======================================================================
  // Panneau « Déplacement » : les flèches de l'UI du robot (g_state.cmdForward
  // / cmdTurn, ±100). Poussées au moteur par setBotState, comme l'UI écrit
  // g_state ; l'évitement (ultrason.js) y est poussé à chaque pas (boucle).
  // ======================================================================
  var rgAvancer = document.getElementById("rg-avancer");
  var rgTourner = document.getElementById("rg-tourner");
  var vAvancer = document.getElementById("v-avancer");
  var vTourner = document.getElementById("v-tourner");
  function pousseDeplacement() {
    vAvancer.textContent = rgAvancer.value;
    vTourner.textContent = rgTourner.value;
    sim.setBotState({ cmdForward: +rgAvancer.value, cmdTurn: +rgTourner.value });
  }
  rgAvancer.addEventListener("input", pousseDeplacement);
  rgTourner.addEventListener("input", pousseDeplacement);
  document.getElementById("btn-dep-stop").addEventListener("click", function () {
    rgAvancer.value = 0; rgTourner.value = 0;
    pousseDeplacement();
  });
  // Démo : consignes nulles, plaque à 25 cm (la sonde la voit à ~20 cm), RESET
  // puis RUN → recul + pivot dès la première mesure (t = 0,2 s).
  document.getElementById("btn-dep-demo").addEventListener("click", function () {
    rgAvancer.value = 0; rgTourner.value = 0;
    pousseDeplacement();
    rgDistance.value = 25;
    rgDistance.dispatchEvent(new Event("input"));
    sim.reset(scenarioCourant);
    us.reset();
    pousseEvitement();
    accumulateur = 0;
    enMarche = true;
    majBoutons();
  });

  // Recopie de ce que head.cpp publie dans g_state vers ce que balance.cpp
  // lit : avoidFwdMax / avoidTurn / obstacleWarn.
  function pousseEvitement() {
    var u = us.state;
    sim.setBotState({ avoidFwdMax: u.avoidFwdMax, avoidTurn: u.avoidTurn, obstacleWarn: u.obstacleWarn });
  }

  // ======================================================================
  // Scène 3D (Three.js). Échelle : 1 unité = 1 m. Voir repère en tête de fichier.
  // ======================================================================
  var conteneur3d = document.getElementById("vue3d");

  var renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setClearColor(0x14161a);
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.outputEncoding = THREE.sRGBEncoding;
  conteneur3d.appendChild(renderer.domElement);

  var scene = new THREE.Scene();
  scene.fog = new THREE.Fog(0x14161a, 0.9, 2.2);   // fondu discret vers le fond

  var camera = new THREE.PerspectiveCamera(42, 1, 0.01, 10);
  camera.position.set(0.34, 0.20, 0.38);           // trois-quarts devant

  var controles = new THREE.OrbitControls(camera, renderer.domElement);
  controles.target.set(0, 0.10, 0);                // mi-hauteur du corps ₿ (201 mm, axe à 41,5 mm)
  controles.enableDamping = true;
  controles.dampingFactor = 0.08;
  controles.minDistance = 0.10;
  controles.maxDistance = 2.0;
  controles.maxPolarAngle = Math.PI * 0.495;       // ne pas passer sous le sol

  // ---- Éclairage : une directionnelle clé (ombres) + ambiance + appoint ----
  var lumiereCle = new THREE.DirectionalLight(0xffffff, 1.05);
  lumiereCle.position.set(0.5, 0.8, 0.35);
  lumiereCle.castShadow = true;
  lumiereCle.shadow.mapSize.set(1024, 1024);
  lumiereCle.shadow.camera.left = -0.4;
  lumiereCle.shadow.camera.right = 0.4;
  lumiereCle.shadow.camera.top = 0.4;
  lumiereCle.shadow.camera.bottom = -0.4;
  lumiereCle.shadow.camera.far = 3;
  scene.add(lumiereCle);
  scene.add(new THREE.AmbientLight(0x9aa4b0, 0.5));
  var appoint = new THREE.DirectionalLight(0xbfd0ff, 0.25);   // rim froid, sans ombre
  appoint.position.set(-0.5, 0.3, -0.4);
  scene.add(appoint);

  // ---- Sol : disque mat sombre + grille discrète ----
  var sol = new THREE.Mesh(
    new THREE.CircleGeometry(0.7, 48),
    new THREE.MeshStandardMaterial({ color: 0x1b1e24, metalness: 0.05, roughness: 0.95 })
  );
  sol.rotation.x = -Math.PI / 2;
  sol.receiveShadow = true;
  scene.add(sol);

  var grille = new THREE.GridHelper(1.2, 24, 0x3a414c, 0x232830);
  grille.position.y = 0.0005;
  grille.material.transparent = true;
  grille.material.opacity = 0.55;
  scene.add(grille);

  // ---- Matériaux : fidèles à chassis/assets/vue_eclatee.py ----
  // Coques : ORANGE du PRODUIT — la fonction d'assemblage RÉELLE de
  // gen_bitcoin_bot.py utilise `orange` (0.97, 0.58, 0.10). La vue éclatée
  // (vue_eclatee.py) peignait les coques en PETG doré : c'est un matériau de
  // vue éclatée, pas celui du produit.
  var matCoque = new THREE.MeshStandardMaterial({
    color: 0xff9d2e, metalness: 0.30, roughness: 0.36
  });
  // Roues : `dark` (0.10, 0.10, 0.11) dans l'assemblage réel — noir métallisé.
  var matRoue = new THREE.MeshStandardMaterial({
    color: 0x1a1a1c, metalness: 0.55, roughness: 0.42
  });
  // MAT_TPU (0.20, 0.20, 0.22) : bande de roulement TPU sombre
  var matTPU = new THREE.MeshStandardMaterial({
    color: 0x292929, metalness: 0.0, roughness: 0.9
  });

  // ---- Pièces réelles du châssis : parts.js (base64, généré par
  //      chassis/assets/exporter_parts_web.py — voir son en-tête pour le repère) ----
  var PIECES = window.BALANCEBOT_PARTS ? window.BALANCEBOT_PARTS.pieces : null;
  if (!PIECES) {
    var msgPieces = document.getElementById("msg-moteur");
    msgPieces.textContent = "⚠ parts.js introuvable ou invalide : régénère-le avec" +
      " chassis/assets/exporter_parts_web.py.";
    msgPieces.style.display = "block";
    return;
  }

  function decodeB64(b64) {
    var bin = atob(b64), n = bin.length, oct = new Uint8Array(n);
    for (var i = 0; i < n; i++) oct[i] = bin.charCodeAt(i);
    return oct.buffer;
  }

  function meshPiece(id, mat) {
    var p = PIECES[id];
    var geo = new THREE.BufferGeometry();
    geo.setAttribute("position",
      new THREE.BufferAttribute(new Float32Array(decodeB64(p.positions)), 3));
    geo.setIndex(new THREE.BufferAttribute(new Uint32Array(decodeB64(p.indices)), 1));
    geo.computeVertexNormals();
    var m = new THREE.Mesh(geo, mat);
    m.castShadow = true;
    m.receiveShadow = true;
    return m;
  }

  // ---- Hiérarchie : robot (roulement) > corps (θ) / roues (θ+φ) ----
  // L'axe de tangage = axe des roues = axe Z passant par l'origine de `robot`.
  var groupeCorps = new THREE.Group();   // pivote de θ (les 2 coques ₿)
  groupeCorps.add(meshPiece("b_front", matCoque));
  groupeCorps.add(meshPiece("b_back", matCoque));
  // Une roue par groupe : elles tournent de θ+φ±φ_diff (différentiel de
  // rotation → lacet), la gauche (−Z) = « out + turn » du firmware.
  var groupeRoueG = new THREE.Group();
  groupeRoueG.add(meshPiece("roue_G", matRoue));
  groupeRoueG.add(meshPiece("pneu_G", matTPU));
  var groupeRoueD = new THREE.Group();
  groupeRoueD.add(meshPiece("roue_D", matRoue));
  groupeRoueD.add(meshPiece("pneu_D", matTPU));

  var robot = new THREE.Group();
  robot.add(groupeCorps);
  robot.add(groupeRoueG);
  robot.add(groupeRoueD);
  robot.position.y = R;                  // axe des roues à hauteur R du sol
  scene.add(robot);

  // ======================================================================
  // Capteur HC-SR04 (les « yeux » du robot réel, voir docs/photos/
  // robot-reel.jpg) : pièce ACHETÉE, pas de STL → modélisation Three.js.
  // Module réel ≈ 45 × 20 × 15 mm, deux transducteurs cylindriques Ø16 mm.
  // UN SEUL module sur le robot réel (config.h:61-62 : un TRIG, un ECHO) :
  // sur la photo il est centré dans le lobe haut du ₿, au-dessus de
  // l'écran, et ce sont ses deux transducteurs qui font les « yeux ».
  // Solidaire de groupeCorps : il tangue avec θ comme le corps.
  // ======================================================================
  var matPCB = new THREE.MeshStandardMaterial({
    color: 0x14508c, metalness: 0.2, roughness: 0.6     // sérigraphie bleue HC-SR04
  });
  var matTransd = new THREE.MeshStandardMaterial({
    color: 0xc9ccd2, metalness: 0.85, roughness: 0.35   // aluminium des transducteurs
  });
  var matGrilleUS = new THREE.MeshStandardMaterial({
    color: 0x7f848c, metalness: 0.6, roughness: 0.55    // grille avant du transducteur
  });

  function moduleHCSR04() {
    var g = new THREE.Group();
    // PCB : 45 mm (Z) × 20 mm (Y) × 2 mm (X), face avant vers +X
    var pcb = new THREE.Mesh(new THREE.BoxGeometry(0.002, 0.020, 0.045), matPCB);
    pcb.position.x = 0.001;
    g.add(pcb);
    // Deux transducteurs Ø16 × 12 mm, axes vers +X, centrés à ±11 mm en Z
    [-0.011, 0.011].forEach(function (dz) {
      var corps = new THREE.Mesh(
        new THREE.CylinderGeometry(0.008, 0.008, 0.012, 24), matTransd);
      corps.rotation.z = -Math.PI / 2;                   // axe Y → axe X
      corps.position.set(0.008, 0, dz);
      var grille = new THREE.Mesh(
        new THREE.CircleGeometry(0.0068, 24), matGrilleUS);
      grille.rotation.y = Math.PI / 2;                   // face vers +X
      grille.position.set(0.0141, 0, dz);
      corps.castShadow = true;
      g.add(corps); g.add(grille);
    });
    pcb.castShadow = true;
    return g;
  }

  // Position sur la face avant (repère viewer, m) : la coque avant s'étend
  // jusqu'à x = 23 mm (parts.js, b_front) ; lobe haut du ₿, au-dessus de
  // l'écran (y = +30,5 mm), centré en Z — les yeux de la photo réelle.
  var US_X = 0.023, US_Y = 0.098;
  var moduleUS = moduleHCSR04();
  moduleUS.position.set(US_X, US_Y, 0);
  groupeCorps.add(moduleUS);

  // Origine de la MESURE : la face avant des transducteurs (grille à
  // x_local = 14,1 mm + 1 mm de garde). Ce ne sont PAS des objets de la
  // scène : la distance est calculée analytiquement depuis la pose
  // physique (voir distanceReelleCm), jamais depuis le maillage animé.
  var SONDE_X = US_X + 0.015, SONDE_Y = US_Y;

  // Faisceau ultrason : cône apex au capteur, allongé vers l'obstacle.
  // Rayon constant 12,2 mm (seul scale.x varie) : le demi-angle apparent
  // dépend donc de la longueur (≈ 5,4° à 13 cm, ≈ 0,5° à 150 cm) — c'est
  // un pointeur visuel, PAS le lobe réel (~15°) du HC-SR04. Couleur selon
  // l'état. Visuellement solidaire du corps (enfant de groupeCorps) : il
  // suit les animations, mais sa LONGUEUR vient de la distance physique.
  var geoFaisceau = new THREE.ConeGeometry(0.0122, 1, 24, 1, true);
  geoFaisceau.translate(0, -0.5, 0);          // apex à l'origine, base à y = −1
  geoFaisceau.rotateZ(Math.PI / 2);           // base vers +X
  var matFaisceau = new THREE.MeshBasicMaterial({
    color: 0x5bbf6a, transparent: true, opacity: 0.16,
    depthWrite: false, side: THREE.DoubleSide
  });
  var faisceau = new THREE.Mesh(geoFaisceau, matFaisceau);
  faisceau.position.set(SONDE_X, SONDE_Y, 0);
  groupeCorps.add(faisceau);

  // ---- Obstacle déplaçable : plaque verticale devant le robot. Le curseur
  //      fixe sa position au RESET du robot (x = 0 = axe des roues) ; la
  //      distance MESURÉE est recalculée depuis la sonde (pose physique). ----
  var OBSTACLE_EP = 0.01;                     // épaisseur 10 mm
  var OBSTACLE_LARG = 0.10;                   // largeur 100 mm (axe Z)
  var obstacle = new THREE.Mesh(
    new THREE.BoxGeometry(OBSTACLE_EP, 0.14, OBSTACLE_LARG),
    new THREE.MeshStandardMaterial({ color: 0x8a919c, metalness: 0.1, roughness: 0.8 })
  );
  obstacle.castShadow = true;
  obstacle.receiveShadow = true;
  scene.add(obstacle);

  var distanceObstacleM = 0.80;               // position du curseur (m)
  function placeObstacle() {
    obstacle.position.set(distanceObstacleM, 0.07, 0);
  }
  placeObstacle();

  // Distance RÉELLE capteur → face avant de l'obstacle, dans le plan du sol
  // (l'obstacle est vertical : l'écho revient de sa face, quelle que soit la
  // hauteur). −1 = obstacle derrière le capteur (pas d'écho).
  // Calculée ANALYTIQUEMENT depuis la pose PHYSIQUE (sim.state), jamais
  // depuis le maillage : les offsets d'animation (pitch/lacet/saut) sont
  // ajoutés à groupeCorps APRÈS la pose physique dans majScene() — ils sont
  // cosmétiques et ne doivent pas toucher la mesure, exactement comme sur
  // le robot réel où le HC-SR04 ne connaît que θ et le roulement.
  // Pose monde de la sonde (repère de l'en-tête) : l'avancée dans le plan du
  // corps f = SONDE_X·cos θ + SONDE_Y·sin θ, tournée du lacet ψ autour de
  // l'axe des roues (posX, posZ) intégré par le moteur :
  //   x = posX + f·cos ψ,   z = posZ + f·sin ψ.
  // GÉOMÉTRIE DU CAPTEUR ≠ GÉOMÉTRIE DU DÉCOR : la plaque fait 10 cm de large
  // et le HC-SR04 n'est pas un rayon mais un LOBE (« measuring angle 15° »
  // du datasheet → demi-angle LOBE_DEMI_ANGLE_DEG). On cherche le point de
  // la face avant (segment z ∈ ±5 cm) le plus proche de la sonde À
  // L'INTÉRIEUR du lobe : c'est le premier écho. Rien dans le lobe → −1.
  // À ψ = 0 (pas de pivot) on retrouve exactement dx = x_face − x_sonde.
  // Ni la hauteur (mesure horizontale) ni le tangage de la sonde ne
  // comptent : l'écho revient de la face verticale, comme avant.
  // Le pan de la tête NE tourne PAS le faisceau : sur le châssis v3 le
  // capteur est fixé au corps (ROADMAP 4.4 : la tête pan/tilt n'existe pas).
  var LOBE_DEMI_ANGLE_DEG = 15;
  function distanceReelleCm() {
    var st = sim.state;
    var th = st.theta * DEG, psi = st.psi * DEG;
    var f = SONDE_X * Math.cos(th) + SONDE_Y * Math.sin(th);
    var cPsi = Math.cos(psi), sPsi = Math.sin(psi);
    var xSonde = st.posX + f * cPsi, zSonde = st.posZ + f * sPsi;
    var dx = (obstacle.position.x - OBSTACLE_EP / 2) - xSonde;
    if (dx <= 0 || cPsi <= 0) return -1;        // plaque derrière la sonde, ou dos tourné
    // Bords du lobe sur la face (x = x_face) : z = z_sonde + dx·tan(ψ ± α).
    // Un bord qui regarde vers l'arrière (cos ≤ 0) ne borne plus de ce côté.
    var a = LOBE_DEMI_ANGLE_DEG * DEG, zLo = -Infinity, zHi = Infinity;
    if (Math.cos(psi - a) > 0) zLo = zSonde + dx * Math.tan(psi - a);
    if (Math.cos(psi + a) > 0) zHi = zSonde + dx * Math.tan(psi + a);
    zLo = Math.max(zLo, -OBSTACLE_LARG / 2);
    zHi = Math.min(zHi,  OBSTACLE_LARG / 2);
    if (zLo > zHi) return -1;                   // la plaque est hors du lobe
    var zStar = Math.min(Math.max(zSonde, zLo), zHi);   // point de la face le plus proche
    return Math.hypot(dx, zStar - zSonde) * 100;        // m → cm
  }

  // ======================================================================
  // Écran ST7789 (56 × 26 mm) : visage piloté par l'état simulé.
  // Portage de balance-bot/ui.cpp (mode AUTO) : constantes « flashées » et
  // table faceStyle() reprises telles quelles, dans le repère du firmware
  // (320 × 170 px, y vers le bas — même convention que le canvas 2D).
  // Simplifications : pas de ₿ en pupille, pas de clin d'œil (FX_CLIN), le
  // « content » est un simple arc ∩ au lieu d'amande + arc couleur fond.
  // ======================================================================
  var FACE_CY = 84, FACE_CX_L = 100, FACE_CX_R = 219;   // EYE_GAP = 118
  var LID_TOP = 0.28, EXP_TOP = 1.0, EXP_BOT = 0.62, IRIS_R = 0.52;

  // faceStyle() : w, h, ang (°), slit (iris en fente), gazeMax (px), red.
  var FACE_STYLES = {
    calme:    { w: 104, h: 68, ang: 6,  slit: false, gazeMax: 18, red: false },
    penche:   { w: 104, h: 57, ang: 13, slit: false, gazeMax: 16, red: false },
    mefiant:  { w: 104, h: 44, ang: 15, slit: true,  gazeMax: 6,  red: false },
    enerve:   { w: 104, h: 27, ang: 26, slit: true,  gazeMax: 6,  red: true  },
    surprise: { w: 100, h: 76, ang: 3,  slit: false, gazeMax: 10, red: false },
    content:  { w: 95,  h: 55, ang: 4,  slit: false, gazeMax: 18, red: false },
    chute:    { w: 104, h: 68, ang: 6,  slit: false, gazeMax: 18, red: false }
  };

  // Canvas hors écran au ratio de la dalle (56:26), dessiné dans le repère
  // firmware 320 × 170 via une transformée d'échelle.
  var faceCanvas = document.createElement("canvas");
  faceCanvas.width = 224;
  faceCanvas.height = 104;
  var faceCtx = faceCanvas.getContext("2d");
  var faceTex = new THREE.CanvasTexture(faceCanvas);
  faceTex.encoding = THREE.sRGBEncoding;

  var ecran = new THREE.Mesh(
    new THREE.PlaneGeometry(0.056, 0.026),
    new THREE.MeshBasicMaterial({ map: faceTex })   // dalle auto-lumineuse (non éclairée)
  );
  // Centre de la fenêtre écran (repère design → repère viewer, voir en-tête) :
  // (X=59,5 ; y=18,0 ; Z=72,0) mm design → (18,0 ; 72,0−41,5 ; 59,5−64,565) mm.
  ecran.position.set(0.018, 0.0305, -0.005065);
  ecran.rotation.y = Math.PI / 2;        // la dalle regarde vers l'avant (+x)
  groupeCorps.add(ecran);                // solidaire du corps : tangue avec θ

  // Points de l'amande (faceEyePoints) : paupière haute franche, ventre
  // bombé, miroir via `inn` (+1 œil gauche, −1 œil droit).
  function amande(cx, w, h, ang, inn) {
    var N = 18, pts = [];
    var ht = h * LID_TOP, hb = h * (1 - LID_TOP);
    var ca = Math.cos(ang * DEG), sa = Math.sin(ang * DEG);
    var i, t, x, y;
    for (i = 0; i <= N; i++) {           // paupière haute
      t = -1 + 2 * i / N;
      x = t * w / 2;
      y = -ht * Math.pow(Math.max(0, 1 - t * t), EXP_TOP);
      pts.push([cx + inn * (x * ca - y * sa), FACE_CY + (x * sa + y * ca)]);
    }
    for (i = 0; i <= N; i++) {           // paupière basse
      t = 1 - 2 * i / N;
      x = t * w / 2;
      y = hb * Math.pow(Math.max(0, 1 - t * t), EXP_BOT);
      pts.push([cx + inn * (x * ca - y * sa), FACE_CY + (x * sa + y * ca)]);
    }
    return pts;
  }

  function dessineOeil(cx, inn, st, f) {
    var ctx = faceCtx;
    var col = f.red ? "#ff603c" : "#ff9d2e";
    if (f.expr === "content" && !f.blink) {
      // « ^^ » : arc bombé vers le haut (le firmware superpose un arc couleur
      // fond sur l'amande — même lecture, ici un seul tracé).
      ctx.strokeStyle = col;
      ctx.lineWidth = 10;
      ctx.lineCap = "round";
      ctx.beginPath();
      ctx.arc(cx, FACE_CY, st.w * 0.34, 200 * DEG, 340 * DEG);
      ctx.stroke();
      return;
    }
    var pts = amande(cx, st.w, st.h, st.ang, inn);
    ctx.fillStyle = col;
    ctx.beginPath();
    ctx.moveTo(pts[0][0], pts[0][1]);
    for (var i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
    ctx.closePath();
    ctx.fill();
    if (f.blink) return;                 // œil fermé : rien de plus
    if (f.expr === "chute") {            // croix blanches par-dessus l'amande
      ctx.strokeStyle = "#e8e8e8";
      ctx.lineWidth = 4;
      ctx.lineCap = "round";
      ctx.beginPath();
      ctx.moveTo(cx - 17, FACE_CY - 17); ctx.lineTo(cx + 17, FACE_CY + 17);
      ctx.moveTo(cx + 17, FACE_CY - 17); ctx.lineTo(cx - 17, FACE_CY + 17);
      ctx.stroke();
      return;
    }
    // Iris sombre (disque, ou fente si slit) + reflet — faceDrawEye().
    var hb = st.h * (1 - LID_TOP);
    var r = hb * IRIS_R;
    var ix = cx + Math.max(-st.gazeMax, Math.min(st.gazeMax, f.gaze));
    var iy = FACE_CY + hb * 0.30;
    ctx.fillStyle = "#0d0f12";
    if (st.slit) {
      var ww = Math.max(2, r / 4);
      ctx.fillRect(ix - ww, iy - r, 2 * ww + 1, 2 * r + 1);
    } else {
      ctx.beginPath();
      ctx.arc(ix, iy, r, 0, 2 * Math.PI);
      ctx.fill();
    }
    ctx.fillStyle = "#e8e8e8";           // reflet (côté intérieur, en haut)
    ctx.beginPath();
    ctx.arc(ix - inn * r * 0.4, iy - r * 0.4, Math.max(1.5, r * 0.22), 0, 2 * Math.PI);
    ctx.fill();
  }

  function dessineVisage(f) {
    faceCtx.setTransform(1, 0, 0, 1, 0, 0);
    faceCtx.fillStyle = "#0d0f12";
    faceCtx.fillRect(0, 0, faceCanvas.width, faceCanvas.height);
    faceCtx.setTransform(faceCanvas.width / 320, 0, 0, faceCanvas.height / 170, 0, 0);
    var st = FACE_STYLES[f.expr];
    if (f.blink) st = { w: st.w, h: 8, ang: st.ang, slit: false, gazeMax: st.gazeMax, red: st.red };
    dessineOeil(FACE_CX_L, +1, st, f);
    dessineOeil(FACE_CX_R, -1, st, f);
  }

  // faceCompute() adaptée aux grandeurs du simulateur (pitchFilt / rateFilt
  // en °, °/s), avec hystérésis kExprHoldMs = 400 ms et clignements
  // (90 ms toutes les 3–6 s, même recette pseudo-aléatoire que le firmware).
  var visage = {
    expr: "calme", exprDepuis: 0,
    prochainBlink: 3, blinkJusqua: -1,
    forcee: null,                        // expression forcée par le sélecteur
    exprAnim: null,                      // expression forcée par une ANIMATION
    gazeAnim: null,                      // regard forcé par une ANIMATION (px)
    dessin: null                         // dernière trame dessinée
  };

  function trameVisage(s) {
    var t = s.t;
    if (t < visage.exprDepuis) {         // reset : le temps a reculé
      visage.exprDepuis = t;
      visage.prochainBlink = t + 3;
      visage.blinkJusqua = -1;
    }
    if (t >= visage.prochainBlink) {
      visage.blinkJusqua = t + 0.09;
      visage.prochainBlink = t + 3 + (t % 3);
    }
    var blink = t < visage.blinkJusqua;

    var ap = Math.abs(s.pitchFilt), ar = Math.abs(s.rateFilt);
    var expr;
    if (visage.forcee) {
      expr = visage.forcee;
    } else if (s.fallen || s.verdict === "chute θ") {
      expr = "chute";
    } else if (s.verdict === "panic φ") {
      expr = "enerve";
    } else if (ar > 60) {
      expr = "surprise";
    } else if (ap > 8 || ar > 40) {
      expr = "enerve";
    } else if (ap < (visage.expr === "content" ? 2.5 : 1.5) &&
               ar < (visage.expr === "content" ? 12 : 6)) {
      expr = "content";
    } else if (ap > 3) {
      expr = "penche";
    } else {
      expr = "calme";
    }
    // Maintien minimal de 0,4 s — sauf la détresse, immédiate.
    if (!visage.forcee && expr !== visage.expr &&
        expr !== "chute" && expr !== "enerve" && expr !== "surprise" &&
        t - visage.exprDepuis < 0.4) {
      expr = visage.expr;
    }
    // Couche ANIMATION : cosmétique, prime sur l'expression automatique
    // (mais pas sur le sélecteur manuel, qui reste prioritaire).
    if (!visage.forcee && visage.exprAnim) expr = visage.exprAnim;
    if (expr !== visage.expr) { visage.expr = expr; visage.exprDepuis = t; }

    // Le regard suit le tangage, quantifié par pas de 2 px (gazeQ) — sauf si
    // une animation le force (regard gauche-droite).
    var gaze = Math.max(-18, Math.min(18, s.pitchFilt * 1.6));
    if (visage.gazeAnim !== null) gaze = Math.max(-18, Math.min(18, visage.gazeAnim));
    gaze = Math.trunc(gaze / 2) * 2;

    return { expr: expr, red: FACE_STYLES[expr].red, blink: blink, gaze: gaze };
  }

  // Redessine UNIQUEMENT quand la trame change (pas à chaque frame).
  function majVisage() {
    var f = trameVisage(sim.state);
    var d = visage.dessin;
    if (!d || d.expr !== f.expr || d.red !== f.red ||
        d.blink !== f.blink || d.gaze !== f.gaze) {
      dessineVisage(f);
      faceTex.needsUpdate = true;
      visage.dessin = f;
    }
  }

  // Sélecteur manuel : force une expression, « auto » rend la main à l'état.
  var selVisage = document.getElementById("sel-visage");
  selVisage.addEventListener("change", function () {
    visage.forcee = selVisage.value === "auto" ? null : selVisage.value;
    visage.dessin = null;                // redessin immédiat
  });

  // ======================================================================
  // ANIMATIONS du corps — couche strictement COSMÉTIQUE.
  // Ces offsets sont ajoutés au MAILLAGE après la pose physique : jamais
  // dans sim.state, jamais dans la commande. « Aucune » = offsets nuls →
  // image strictement identique à l'original. L'horloge est le temps RÉEL
  // (rAF) : l'animation joue même en pause, sans toucher à la physique.
  // ======================================================================
  var animCourante = "aucune";
  var animT0 = 0;                        // déclenchement (ms, horloge rAF)
  var maintenantMs = 0;                  // dernier timestamp rAF connu

  function offsetsAnim() {
    var z = { pitch: 0, lacet: 0, saut: 0, expr: null, gaze: null };
    if (animCourante === "aucune") return z;
    var t = (maintenantMs - animT0) / 1000;
    if (t < 0) return z;
    switch (animCourante) {
      case "hochement":                  // oui-oui : ±4° de tangage, en boucle
        z.pitch = -4 * DEG * Math.sin(2 * Math.PI * 1.6 * t);
        z.expr = "content";
        break;
      case "regard":                     // balayage de lacet ±16° + regard
        z.lacet = 16 * DEG * Math.sin(2 * Math.PI * 0.5 * t);
        z.gaze = 18 * Math.sin(2 * Math.PI * 0.5 * t);
        z.expr = "calme";
        break;
      case "sursaut": {                  // one-shot 0,7 s : bond + recul
        var p = t / 0.7;
        if (p < 1) {
          z.saut = 0.022 * Math.sin(Math.PI * p);
          z.pitch = 5 * DEG * Math.sin(Math.PI * p);
          z.expr = "surprise";
        }
        break;
      }
      case "danse":                      // lacet + rebond + tangage, en boucle
        z.lacet = 20 * DEG * Math.sin(2 * Math.PI * 1.1 * t);
        z.pitch = -3 * DEG * Math.sin(2 * Math.PI * 2.2 * t);
        z.saut = 0.008 * Math.abs(Math.sin(2 * Math.PI * 2.2 * t));
        z.expr = "content";
        break;
    }
    return z;
  }

  var selAnim = document.getElementById("sel-anim");
  selAnim.addEventListener("change", function () {
    animCourante = selAnim.value;
    animT0 = maintenantMs;               // relance proprement depuis t = 0
  });
  document.getElementById("btn-anim-rejouer").addEventListener("click", function () {
    animT0 = maintenantMs;               // rejoue l'animation courante
  });

  // Met à jour les poses depuis l'état du moteur (degrés → radians).
  function majScene() {
    var s = sim.state;
    var th = s.theta * DEG;
    var ph = s.phi * DEG;
    var pd = s.phiDiff * DEG;
    var an = offsetsAnim();
    groupeCorps.rotation.z = -th + an.pitch;   // θ physique + offset cosmétique
    groupeCorps.rotation.y = an.lacet;         // lacet cosmétique uniquement
    groupeRoueG.rotation.z = -(th + ph + pd);  // spin des roues (roulement + servo φ ± différentiel)
    groupeRoueD.rotation.z = -(th + ph - pd);
    robot.position.x = s.posX;                 // pose au sol intégrée par le moteur
    robot.position.z = s.posZ;                 //   (= R·(θ+φ) sur x tant que ψ = 0)
    robot.rotation.y = -s.psi * DEG;           // lacet PHYSIQUE (différentiel des roues)
    robot.position.y = R + an.saut;            // rebond cosmétique uniquement
    visage.exprAnim = an.expr;
    visage.gazeAnim = an.gaze;
    // Chute : lueur rouge discrète du corps
    matCoque.emissive.setHex(s.fallen ? 0x4a1208 : 0x000000);

    // Faisceau ultrason : longueur = distance réelle (bornée à la portée),
    // couleur = état publié par le capteur (vert / rouge / gris discret).
    var u = us.state;
    var dCm = distanceReelleCm();
    faisceau.visible = u.actif;
    var longueur = (dCm >= 0 ? Math.min(dCm, US.constants.US_MAX_CM) : US.constants.US_MAX_CM) / 100;
    faisceau.scale.x = Math.max(0.02, longueur);
    if (u.obstacleWarn) {
      matFaisceau.color.setHex(0xe0533d);      // ALERTE < 25 cm
      matFaisceau.opacity = 0.35;
    } else if (u.obstacleCm >= 0) {
      matFaisceau.color.setHex(0x5bbf6a);      // obstacle dans la portée
      matFaisceau.opacity = 0.18;
    } else {
      matFaisceau.color.setHex(0x8a919c);      // rien / hors portée
      matFaisceau.opacity = 0.08;
    }
  }

  // Redimensionnement du renderer selon le conteneur (vérifié à chaque frame)
  function ajusteTaille() {
    var w = conteneur3d.clientWidth, h = conteneur3d.clientHeight;
    var c = renderer.domElement;
    if (c.width !== Math.floor(w * renderer.getPixelRatio()) || c.height !== Math.floor(h * renderer.getPixelRatio())) {
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    }
  }

  // ======================================================================
  // Télémétrie
  // ======================================================================
  var el = {
    theta: document.getElementById("t-theta"),
    phi: document.getElementById("t-phi"),
    pid: document.getElementById("t-pid"),
    integ: document.getElementById("t-integ"),
    verdict: document.getElementById("verdict"),
    temps: document.getElementById("t-temps"),
    vitesse: document.getElementById("t-vitesse"),
    overlay: document.getElementById("overlay-verdict")
  };

  function majTelemetrie() {
    var s = sim.state;
    el.theta.textContent = s.theta.toFixed(2) + " °";
    el.phi.textContent = s.phi.toFixed(2) + " °";
    el.pid.textContent = s.pidOut.toFixed(2);
    el.integ.textContent = s.integ.toFixed(2);
    el.temps.textContent = s.t.toFixed(2) + " s";
    el.vitesse.textContent = "×" + vitesseLecture + " · " + Math.round(vitessePas) + " pas/s";
    var v = s.verdict;
    el.overlay.style.display = "none";
    if (v === "ok") {
      el.verdict.textContent = "ok — tient !"; el.verdict.className = "ok";
      el.overlay.textContent = "ÉQUILIBRE OK"; el.overlay.className = "ok";
      el.overlay.style.display = "block";
    } else if (v === "chute θ") {
      el.verdict.textContent = "chute θ"; el.verdict.className = "chute";
      el.overlay.textContent = "CHUTE θ"; el.overlay.className = "chute";
      el.overlay.style.display = "block";
    } else if (v === "panic φ") {
      el.verdict.textContent = "panic φ"; el.verdict.className = "panique";
      el.overlay.textContent = "PANIC φ"; el.overlay.className = "panique";
      el.overlay.style.display = "block";
    } else {
      el.verdict.textContent = "en cours…"; el.verdict.className = "encours";
    }
  }

  // ---- Télémétrie du capteur ultrason (état publié par ultrason.js) ----
  var elUs = {
    distance: document.getElementById("us-distance"),
    etat: document.getElementById("us-etat"),
    cadence: document.getElementById("us-cadence"),
    echecs: document.getElementById("us-echecs"),
    tete: document.getElementById("us-tete"),
    angle: document.getElementById("us-angle"),
    phase: document.getElementById("us-phase"),
    avoid: document.getElementById("us-avoid"),
    effective: document.getElementById("dep-effective"),
    lacet: document.getElementById("dep-lacet"),
    pos: document.getElementById("dep-pos")
  };
  var PHASES = [
    { txt: "LIBRE",                          cls: "rien" },
    { txt: "RALENTI (< 60 cm)",              cls: "ralenti" },
    { txt: "RECUL + PIVOT (< 25 cm)",        cls: "alerte" },
    { txt: "PIVOT seul (recul épuisé)",      cls: "alerte" }
  ];

  function majTelemetrieUS() {
    var u = us.state, s = sim.state;
    elUs.distance.textContent = u.obstacleCm >= 0 ? u.obstacleCm.toFixed(1) + " cm" : "—";
    if (!u.actif) {
      elUs.etat.textContent = "absent (ECHO débranché)";
      elUs.etat.className = "rien";
    } else if (u.obstacleWarn) {
      elUs.etat.textContent = "ALERTE < 25 cm";
      elUs.etat.className = "alerte";
    } else if (u.obstacleSlow) {
      elUs.etat.textContent = "ralenti < 60 cm";
      elUs.etat.className = "ralenti";
    } else if (u.obstacleCm >= 0) {
      elUs.etat.textContent = "obstacle";
      elUs.etat.className = "obstacle";
    } else {
      elUs.etat.textContent = "rien";
      elUs.etat.className = "rien";
    }
    elUs.cadence.textContent = u.cadenceMs + " ms";
    elUs.echecs.textContent = String(u.failStreak);
    elUs.tete.textContent = u.headPanDeg + "° / " + u.headTiltDeg + "°";
    elUs.angle.textContent = u.angleVu >= 0
      ? u.angleVu + "° / " + (u.obstacleSide > 0 ? "+1 (pan > 100)" : u.obstacleSide < 0 ? "−1 (pan < 80)" : "0 (en face)")
      : "—";
    var ph = PHASES[u.avoidPhase] || PHASES[0];
    elUs.phase.textContent = ph.txt;
    elUs.phase.className = ph.cls;
    elUs.avoid.textContent = "avance ≤ " + u.avoidFwdMax + (u.avoidTurn ? " · pivot " + (u.avoidTurn > 0 ? "+" : "") + u.avoidTurn : "");
    elUs.effective.textContent = "avance " + s.fwdSmooth.toFixed(0) + " · tourne " + s.turnSmooth.toFixed(0) +
                                 " (θ_ref " + s.setpoint.toFixed(2) + "°)";
    elUs.lacet.textContent = s.psi.toFixed(1) + " °";
    elUs.pos.textContent = "x " + (s.posX * 100).toFixed(1) + " · z " + (s.posZ * 100).toFixed(1) + " cm";
  }

  // ======================================================================
  // Boucle principale (requestAnimationFrame, temps réel × vitesse de lecture)
  // ======================================================================
  function boucle(maintenant) {
    if (dernierT === null) dernierT = maintenant;
    var dtReel = Math.min(0.1, (maintenant - dernierT) / 1000);
    dernierT = maintenant;
    maintenantMs = maintenant;           // horloge des animations cosmétiques

    if (enMarche && !sim.state.verdict) {
      accumulateur += dtReel * vitesseLecture;
      var n = Math.floor(accumulateur / BE.defaults.dt);
      if (n > 0) {
        if (n > 2000) n = 2000;                  // garde-fou anti-spirale
        accumulateur -= n * BE.defaults.dt;
        // La distance est figée le temps du lot : le capteur échantillonne
        // au plus tous les 40 pas (200 ms), l'approximation est invisible.
        var dCm = distanceReelleCm();
        // Pas par pas, dans l'ordre du firmware : la boucle d'équilibre
        // avance (cœur 0), la tête mesure/balaie/décide (cœur 1) sur la
        // même horloge de 5 ms, et ce qu'elle publie (avoidFwdMax,
        // avoidTurn, obstacleWarn) est lu par le pas SUIVANT — c'est le
        // couplage vérifié par selfcheck.js §8.
        for (var i = 0; i < n && !sim.state.verdict; i++) {
          sim.step();
          us.tick(dCm, !sim.state.fallen);
          pousseEvitement();
        }
        pasComptes += n;
      }
    } else {
      accumulateur = 0;
    }

    // vitesse (pas/s), lissée
    if (dtReel > 0) {
      var inst = pasComptes / dtReel;
      vitessePas += (inst - vitessePas) * 0.2;
    }
    pasComptes = 0;

    if (sim.state.verdict) { enMarche = false; majBoutons(); }

    ajusteTaille();
    majScene();
    majVisage();
    majTelemetrie();
    majTelemetrieUS();
    controles.update();
    renderer.render(scene, camera);
    requestAnimationFrame(boucle);
  }

  // ---- Initialisation ----
  construitReglages();
  construitScenarios();
  sim.reset(scenarioCourant);
  pousseReglages();
  majBoutons();
  requestAnimationFrame(boucle);
})();
