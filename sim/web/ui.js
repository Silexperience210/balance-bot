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
   - θ et φ viennent STRICTEMENT de sim.state (degrés → radians ici). */
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
  var BE = window.BalanceEngine;

  // Constante géométrique du rendu (pas de physique ici) : rayon de roulement
  // WHEEL_R = 41,5 mm (gen_bitcoin_bot.py) — l'axe des roues est à 41,5 mm du sol.
  var R = 0.0415;

  // ---- État du viewer ----
  var sim = BE.create(BE.defaults);
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

  function construitReglages() {
    var conteneur = document.getElementById("reglages");
    REGLAGES.forEach(function (r) {
      var def = BE.defaults[r.cle];
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
  var groupePieds = new THREE.Group();   // pivote de θ+φ (roues ₿ + bandes TPU)
  groupePieds.add(meshPiece("roue_D", matRoue));
  groupePieds.add(meshPiece("roue_G", matRoue));
  groupePieds.add(meshPiece("pneu_D", matTPU));
  groupePieds.add(meshPiece("pneu_G", matTPU));

  var robot = new THREE.Group();
  robot.add(groupeCorps);
  robot.add(groupePieds);
  robot.position.y = R;                  // axe des roues à hauteur R du sol
  scene.add(robot);

  // Met à jour les poses depuis l'état du moteur (degrés → radians).
  function majScene() {
    var s = sim.state;
    var th = s.theta * DEG;
    var ph = s.phi * DEG;
    groupeCorps.rotation.z = -th;              // θ > 0 → penche vers +X
    groupePieds.rotation.z = -(th + ph);       // spin des roues (roulement + servo φ)
    robot.position.x = R * (th + ph);          // roulement sans glissement
    // Chute : lueur rouge discrète du corps
    matCoque.emissive.setHex(s.fallen ? 0x4a1208 : 0x000000);
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

  // ======================================================================
  // Boucle principale (requestAnimationFrame, temps réel × vitesse de lecture)
  // ======================================================================
  function boucle(maintenant) {
    if (dernierT === null) dernierT = maintenant;
    var dtReel = Math.min(0.1, (maintenant - dernierT) / 1000);
    dernierT = maintenant;

    if (enMarche && !sim.state.verdict) {
      accumulateur += dtReel * vitesseLecture;
      var n = Math.floor(accumulateur / BE.defaults.dt);
      if (n > 0) {
        if (n > 2000) n = 2000;                  // garde-fou anti-spirale
        accumulateur -= n * BE.defaults.dt;
        sim.stepMany(n);
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
    majTelemetrie();
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
