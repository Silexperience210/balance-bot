# Revue du pipeline tactile — BalanceBot (lecture seule)

Date : 2026-09-09 · Portée : `balance-bot/ui.cpp`, `balance-bot/ui.h`, `balance-bot/tuner.cpp`,
`~/Arduino/libraries/TouchLib`, `~/Arduino/libraries/TFT_eSPI/TFT_Drivers/ST7789_Rotation.h`.

**Aucun fichier de code n'a été modifié.** Le firmware a été compilé tel quel (sans upload) avec
les options de `build.sh` : `exit 0`, 1 042 898 o (79 %) de flash, 50 812 o de RAM globale.

---

## 0. Vérification des faits fournis

| # | Fait annoncé | Vérifié ? | Preuve |
|---|---|---|---|
| F1 | ST7789 170×320, paysage via `setRotation(3)` | ✅ | `ui.cpp:598` ; `build.sh` : `-DTFT_WIDTH=170 -DTFT_HEIGHT=320 -DCGRAM_OFFSET` ; `ui.cpp:30-31` `WIDTH 320 / HEIGHT 170` |
| F2 | Init TouchLib + `setRotation(1)` | ✅ | `ui.cpp:601-609` (adresse `CTS820_SLAVE_ADDRESS` = 0x15, `CSTSelfConstants.h:4`) |
| F3 | TouchLib rot 1 = échange x/y, rot 2 et 3 non implémentées | ✅ | `ModulesCSTSelf.tpp:99-104` : `if (rotation == 0) {} else if (rotation == 1) { swap }` — **aucun `else`**, donc 2 et 3 retombent silencieusement sur l'identité |
| F4 | Aucune API de miroir dans TouchLib | ✅ | `grep -rn "irror" ~/Arduino/libraries/TouchLib/src` → 0 résultat ; l'interface publique se limite à `setRotation/getRotation` (`ModulesCSTSelf.tpp:108-110`) |
| F5 | `readTouch()` ne transforme rien | ✅ | `ui.cpp:417-429` : `g_touchX = (int16_t)p.x; g_touchY = (int16_t)p.y;` |
| F6 | Zones tactiles et zone STOP | ✅ | `ui.cpp:100-106` et `ui.cpp:160` (`STOP_X=60, STOP_Y=40, STOP_W=200, STOP_H=92`) |

Un fait annoncé est **faux** et c'est lui qui a masqué le bug : voir constat **C2**.

---

## 1. Analyse géométrique

### 1.1 Repères

* **Repère verre `V`** (ce que voit l'opérateur, paysage) : `(Xe, Ye)`, `Xe ∈ [0,319]` de gauche à
  droite, `Ye ∈ [0,169]` de haut en bas. C'est le repère dans lequel sont exprimées les zones
  (`ui.cpp:100-106`) et dans lequel TFT_eSPI dessine en rotation 3.
* **Repère natif du panneau `P`** : 170 colonnes × 320 lignes (le verre n'expose que 170 des 240
  colonnes de GRAM ; `ST7789_Rotation.h:23-27` applique `colstart = 35` quand `_init_width == 170`).
* **Repère brut du CST816** : `(xr, yr)` tel que sorti des registres
  (`ModulesCSTSelf.tpp:85-86`, 12 bits par axe via `COMBINE_H4L8`).

**Hypothèse H0** — l'affichage est à l'endroit : l'opérateur lit « BALANCEBOT » en haut à gauche
(`ui.cpp:566`) et n'a jamais signalé une image retournée. Donc « repère de dessin TFT rotation 3 »
= repère verre `V`. On cherche uniquement la relation `brut → V`.

### 1.2 Ce que fait TFT_eSPI en rotation 3

`ST7789_Rotation.h:135` : `MADCTL = MV | MY | RGB`, avec `colstart = 0`, `rowstart = 35`
(lignes 124-128). Donc en rotation 3 l'axe écran `x` (0..319) est l'axe **long** du panneau
(320, sans offset) et l'axe écran `y` (0..169) est l'axe **court** (170, décalé de 35 dans la
GRAM de 240). Comparaison utile : la rotation 1 vaut `MX | MV` (`:68`). Rotation 1 et rotation 3
diffèrent donc de `MX|MY`, c'est-à-dire **exactement d'une rotation de 180°** — pas d'un miroir.
C'est le point clé du §1.5.

### 1.3 Ce que fait TouchLib en rotation 1

`ModulesCSTSelf.tpp:100-104` : `(p.x, p.y) = (yr, xr)`. C'est une **transposition**, c'est-à-dire
la réflexion par rapport à la première diagonale (déterminant −1) — et **pas** une rotation de 90°.
Une transposition aligne les axes (elle envoie l'axe 320 sur `p.x` et l'axe 170 sur `p.y`) mais ne
fixe **aucun sens**.

### 1.4 Composition : il ne reste que 4 possibilités

La dalle capacitive est laminée sur le panneau : chaque axe brut est parallèle à un axe du panneau,
au signe près. Sous l'hypothèse **H1** « `xr` = axe court (170), `yr` = axe long (320) » :

```
xr ∈ { Ye , 169 − Ye }        yr ∈ { Xe , 319 − Xe }
```

puis la transposition de TouchLib :

```
p.x = yr ∈ { Xe , 319 − Xe }
p.y = xr ∈ { Ye , 169 − Ye }
```

et `readTouch()` recopie tel quel (`ui.cpp:425-426`). Donc **le firmware est forcément dans un de
ces quatre états, et un seul** :

| État | `g_touchX` | `g_touchY` | Nature |
|---|---|---|---|
| A — identité | `Xe` | `Ye` | rien à faire |
| **B — miroir X** | **`319 − Xe`** | `Ye` | réflexion |
| C — miroir Y | `Xe` | `169 − Ye` | réflexion |
| D — 180° | `319 − Xe` | `169 − Ye` | rotation |

### 1.5 Pourquoi ni `tft.setRotation()` ni `touch.setRotation()` ne peuvent corriger B ou C

TFT_eSPI n'offre que les 4 rotations propres (0°, 90°, 180°, 270° — §1.2) et TouchLib n'implémente
que l'identité et la transposition (F3). Le résidu B ou C est une **réflexion** ; composer une
réflexion avec des rotations redonne toujours une réflexion. Concrètement : passer
`tft.setRotation(3)` → `(1)` applique 180° à l'image, donc transforme « miroir X » en « miroir Y »
— toujours faux — **et** retourne toute l'UI à l'envers. **Le correctif doit donc être une
réflexion explicite dans le code.** C'est ce qui rend le problème structurel et non un « réglage
oublié ».

### 1.6 H1 est vérifiée (les axes ne sont pas intervertis)

Si `xr` était l'axe long (H2), après transposition `p.x` vaudrait 0..169 et `p.y` 0..319. La zone 4
(bouton ÉQUILIBRE) exige `g_touchX ≥ 208` (`ui.cpp:105`) : elle serait **strictement inatteignable**,
le robot ne pourrait jamais être armé depuis l'écran, et la moitié basse de l'écran
(`g_touchY ≥ 170`) ne tomberait dans aucune zone. Or l'utilisateur arme depuis l'écran et rapporte
qu'« un bouton de droite s'active » — donc `g_touchX` dépasse 207. **H1 tient, `setRotation(1)` est
le bon choix, seul le sens de X est en cause.** (Ce point reste confirmé formellement par le
protocole du §4, critère 3.)

### 1.7 B (miroir X) contre D (180°) : les deux signatures sont très différentes

Zones (`ui.cpp:100-106`), en intervalles fermés :

```
z0 AVANT   x∈[12,99]   y∈[66,111]        z1 ARRIÈRE x∈[108,195] y∈[66,111]
z2 GAUCHE  x∈[12,99]   y∈[116,161]       z3 DROITE  x∈[108,195] y∈[116,161]
z4 ÉQUIL.  x∈[208,307] y∈[66,161]
```

**Hypothèse B** (`x ↦ 319 − x`, `y` inchangé) — image de chaque appui :

| On appuie sur | l'image est | zone effectivement activée |
|---|---|---|
| z0 AVANT (haut-gauche) | `[220,307] × [66,111]` | **z4 → bascule l'ARMEMENT** (inclusion totale) |
| z2 GAUCHE (bas-gauche) | `[220,307] × [116,161]` | **z4 → bascule l'ARMEMENT** (inclusion totale) |
| z1 ARRIÈRE | `[124,211] × [66,111]` | z1 sur `x∈[124,195]` (82 % de la surface) ; z4 sur la bande `x∈[208,211]` |
| z3 DROITE | `[124,211] × [116,161]` | z3 sur 82 % de la surface |
| z4 ÉQUIL. | `[12,111] × [66,161]` | z0 AVANT (haut) ou z2 GAUCHE (bas) → **le gros bouton fait avancer/tourner** |

Signature attendue : *les deux boutons de gauche arment/désarment le robot, les deux boutons du
milieu répondent à peu près normalement, le gros bouton de droite envoie une consigne de
déplacement.* → C'est **exactement** « je clique à gauche, un bouton de droite s'active ».

**Hypothèse D** (180°) — on ajoute `y ↦ 169 − y` :

| On appuie sur | l'image est | zone activée |
|---|---|---|
| z0 AVANT | `[220,307] × [58,103]` | z4 partiellement (bande `y∈[66,103]` seulement) |
| **z2 GAUCHE** | `[220,307] × [8,53]` | **aucune — bouton 100 % inerte** |
| **z3 DROITE** | `[124,211] × [8,53]` | **aucune — bouton 100 % inerte** |
| z1 ARRIÈRE | `[124,211] × [58,103]` | z1 sur une bande partielle |

Signature attendue : *toute la rangée du bas est morte, et la rangée du haut ne répond que sur sa
moitié basse.* Un axe Y inversé n'est **jamais silencieux** avec cette disposition, parce que les
deux rangées de boutons (`[66,111]` et `[116,161]`) ne sont pas symétriques par rapport au centre
`y = 84,5` : l'image de la rangée basse est `[8,53]`, disjointe des deux rangées.

L'absence totale de bouton inerte dans le rapport de l'opérateur écarte D et C. **→ État B, miroir
horizontal.**

### 1.8 Corroboration : pourquoi le mode AUTO ne dit rien

`STOP_X = 60, STOP_W = 200` → `x ∈ [60,259]`. Son image par le miroir X est
`[319−259, 319−60] = [60,259]` : **la zone STOP est exactement son propre miroir**. L'inversion de X
est donc *strictement invisible* en mode AUTO, ce qui explique que la plainte soit cantonnée à
l'écran de commande. (Note : `y ∈ [40,131]` a pour image `[38,129]`, soit 97 % de recouvrement — le
mode AUTO ne permet donc pas non plus de *disqualifier* un miroir Y ; c'est la rangée basse du mode
MANUEL qui le fait, §1.7.)

### 1.9 Conclusion et honnêteté sur le niveau de preuve

* Le raisonnement **prouve** que l'erreur est nécessairement l'un des 4 éléments {A, B, C, D} :
  c'est une conséquence du code, pas une conjecture. Les cas « échange d'axes » et « rotation 90° »
  sont exclus formellement (§1.3, §1.6).
* Le raisonnement **prouve** qu'aucun `setRotation` ne peut corriger le défaut (§1.5).
* Le choix final entre **B** et **D** repose sur le symptôme rapporté (aucun bouton inerte) et non
  sur une mesure. C'est cohérent et fortement discriminant, mais **le sens des axes bruts du CST816
  n'est déductible d'aucun fichier présent sur la machine** — ni datasheet, ni exemple LilyGo
  installé (`grep` sur `~/Arduino` : seules TouchLib et CST816_TouchLib, aucune référence
  d'orientation).
  **→ D'où l'instrumentation du §3 et le protocole du §4, qui tranchent en 4 touches.**
  Le correctif est écrit avec deux drapeaux (`kTouchMirrorX`, `kTouchMirrorY`) précisément pour que
  la mesure puisse choisir l'un des 4 états sans réécrire la fonction.

---

## 2. Constats numérotés

### C1 — `ui.cpp:425-426` — **GRAVE (sécurité)** — coordonnée X non inversée

**Preuve** : §1.4 (l'état ne peut être que A/B/C/D) + §1.7 (la signature de B est celle qui est
rapportée) + §1.8 (silence attendu du mode AUTO, observé).
**Conséquence** : appuyer sur **AVANT** ou **GAUCHE** tombe intégralement dans la zone 4 et exécute
`g_state.cmdEnabled = !Balance::isEnabled()` (`ui.cpp:678`). **Le robot s'arme (ou se désarme) quand
l'opérateur croit lui donner une consigne de direction.** Inversement, le bouton ÉQUILIBRE envoie
`cmdForward = ±100` / `cmdTurn = ±100`. Ce n'est pas seulement une gêne d'ergonomie : c'est un
armement non intentionnel des servos.

### C2 — `ui.cpp:10-11` et `ui.cpp:642` — **MOYEN (documentation trompeuse)**

Le commentaire d'en-tête affirme `tft.setRotation(3) + touch.setRotation(1) → coordonnées directes`
et la boucle répète « coordonnées déjà alignées par setRotation ». **C'est faux** : `setRotation(1)`
de TouchLib est une transposition sans signe (§1.3), elle ne peut pas produire des « coordonnées
directes » — la preuve, aucune combinaison de rotations ne le peut (§1.5). Ce commentaire est ce qui
a rendu C1 invisible en relecture. À corriger en même temps que C1.

### C3 — `ModulesCSTSelf.tpp:99-104` — **INFO (bibliothèque tierce)**

`setRotation(2)` et `setRotation(3)` sont acceptées par `setRotation` (`:108`, `r % 4`) mais
**ignorées** dans `getPoint` : pas de `else`, pas de log, pas d'erreur. Ne jamais compter sur elles ;
elles se comporteraient comme la rotation 0.

### C4 — `CSTSelfConstants.h:60-71` + `ModulesCSTSelf.tpp:88-92,128` — **GRAVE (latent, tierce partie)**

Les registres du second point sont définis `0x09, 0x10, 0x11, 0x12` (des valeurs décimales
déguisées en hexadécimal — le CST816 utilise 0x09..0x0C), alors que le tampon fait 13 octets
(`uint8_t raw_data[13]`). `getPoint(1)` lit donc `raw_data[16]`, `[17]`, `[18]` : **lecture hors
tableau**. Le firmware ne l'appelle jamais (`ui.cpp:423` n'utilise que le point 0) — c'est à
maintenir explicitement, ce que fait le correctif du §3 en le commentant.

### C5 — `TouchLibCommon.tpp:218-234` + `ModulesCSTSelf.tpp:73-76` — **MOYEN (robustesse)**

`readRegister(reg, buf, len)` retourne `-1` **sans toucher `buf`** si le `endTransmission()` échoue,
et `read()` ignore la valeur de retour : `this->readRegister(...); return raw_data[TOUCH_NUM_REG] > 0;`.
Si le bus I²C décroche alors qu'un doigt est posé, `raw_data` reste figé sur la dernière trame :
l'UI voit un **appui permanent** aux mêmes coordonnées → `dirHeld` reste vrai (`ui.cpp:662`) et
`cmdForward`/`cmdTurn` restent bloqués à ±100 jusqu'au rétablissement du bus. Hors périmètre du
correctif d'inversion (il faudrait un wrapper qui vérifie le code retour, la lib ne l'expose pas),
mais à traiter : un garde-fou « même point strictement identique pendant > N ms → on relâche »
serait peu coûteux.

### C6 — `ui.cpp:656-661` — **MINEUR (pré-existant, non causé par C1)**

Sortir d'une zone puis y revenir **sans lever le doigt** ré-arme `z.pressed = false` puis regénère un
front montant. Glisser d'avant en arrière sur le bouton ÉQUILIBRE bascule donc l'armement à chaque
aller-retour. Le correctif d'inversion ne change rien à ce comportement (voir §5).

### C7 — `tuner.cpp:178-189` — **MINEUR (piège d'instrumentation)**

`char buf[256]` pour un JSON qui en consomme déjà ≈ 160 dans le pire cas. Ajouter les champs de
diagnostic tactile (≈ 70 caractères) laisse une marge < 30 : `snprintf` tronquerait silencieusement
et le JSON deviendrait invalide → `fetch().json()` lève, la page affiche « hors ligne… »
(`tuner.cpp:146-148`) et on croit à une panne de radio. **→ Endpoint dédié `/api/touch`** dans le
§3 ; si l'on tient à `/api/state`, passer `buf` à 384.

### C8 — `ui.cpp:425-426` — **MINEUR** — aucun bornage

`p.x`/`p.y` sont des entiers 12 bits (`COMBINE_H4L8`, jusqu'à 4095). Aucune validation : une trame
parasite produit un point arbitraire. Corrigé par le clamp du §3.

---

## 3. Correctif minimal (proposition — **non appliquée**)

Transformation retenue :

```
g_touchX = 319 − clamp(p.x, 0, 319)
g_touchY =       clamp(p.y, 0, 169)
```

Écrite avec deux drapeaux pour que le protocole du §4 puisse sélectionner n'importe lequel des 4
états sans retoucher la logique.

### 3.1 `balance-bot/ui.cpp` — déclarations (après la ligne 87)

```diff
@@ -84,6 +84,27 @@
 // ── Touch ──────────────────────────────────────────────────────────
 static TouchLib* g_touch = nullptr;
 static bool     g_touchedRaw = false;
 static int16_t  g_touchX = -1, g_touchY = -1;
+
+// Orientation du tactile — cf. TOUCH_REVIEW.md §1.
+// TouchLib::setRotation(1) fait UNIQUEMENT un échange x↔y (transposition,
+// ModulesCSTSelf.tpp:100-104). Une transposition aligne les axes mais ne
+// fixe pas leur SENS, et aucune rotation (ni tft.setRotation, ni
+// TouchLib) ne peut annuler une réflexion : il faut la poser en dur.
+// Mesuré par le protocole des 4 coins (§4) : l'axe long du CST816 est
+// orienté à l'inverse de l'axe x écran en rotation 3.
+static constexpr bool kTouchMirrorX = true;
+static constexpr bool kTouchMirrorY = false;
+
+// Instrumentation de vérification (exposée par Ui::touchDebug()).
+// RÉMANENTE : readTouch() remet g_touchX à −1 dès le relâchement, or une
+// requête HTTP arrive toujours après que le doigt est parti. On conserve
+// donc le dernier point VALIDE, brut ET transformé. g_touchSeq compte les
+// fronts montants : il prouve que la valeur lue vient bien du tap qu'on
+// vient de faire et pas du précédent.
+static int16_t  g_touchRawX  = -1, g_touchRawY  = -1;
+static int16_t  g_touchLastX = -1, g_touchLastY = -1;
+static uint32_t g_touchSeq   = 0;
```

### 3.2 `balance-bot/ui.cpp:417-429` — `readTouch()`

```diff
@@ -417,13 +417,52 @@
 void readTouch() {
+  const bool wasTouched = g_touchedRaw;
   g_touchedRaw = false;
   g_touchX = -1; g_touchY = -1;
-  if (g_touch && g_touch->read()) {
-    const uint8_t np = g_touch->getPointNum();
-    if (np > 0) {
-      const TP_Point p = g_touch->getPoint(0);
-      g_touchedRaw = true;
-      g_touchX = (int16_t)p.x;
-      g_touchY = (int16_t)p.y;
-    }
-  }
+  if (!g_touch || !g_touch->read()) return;
+
+  // MULTI-TOUCH : le contrôleur peut annoncer 2 points ; on ne garde QUE
+  // le point 0. getPoint(1) est de toute façon inutilisable : TouchLib le
+  // lit dans raw_data[16..18] alors que le tampon fait 13 octets
+  // (CSTSelfConstants.h:66-71 vs ModulesCSTSelf.tpp:128) — lecture hors
+  // tableau. Ne pas « améliorer » cette fonction en itérant sur les points.
+  if (g_touch->getPointNum() == 0) return;
+  const TP_Point p = g_touch->getPoint(0);
+
+  // ── Repère brut → repère écran (paysage 320×170, tft.setRotation(3)) ──
+  // Le point sort de TouchLib DÉJÀ transposé par son setRotation(1) :
+  // p.x court le long des 320 px, p.y en travers des 170 px. Mais la
+  // transposition est une RÉFLEXION (ModulesCSTSelf.tpp:100-104) : elle
+  // met les axes en face l'un de l'autre sans rien dire de leur sens.
+  // Le sens de l'axe long du CST816 est opposé à celui de l'axe x écran
+  // en rotation 3 (MADCTL = MV|MY, ST7789_Rotation.h:135) : il faut donc
+  // un miroir horizontal explicite. Aucun réglage de rotation ne peut le
+  // faire à notre place — une rotation ne produit jamais une réflexion ;
+  // passer tft.setRotation(3)→(1) transformerait simplement ce miroir X
+  // en miroir Y, en retournant l'UI au passage.
+  // Symptôme d'origine : appuyer sur AVANT/GAUCHE tombait dans la zone du
+  // bouton ÉQUILIBRE et ARMAIT le robot (TOUCH_REVIEW.md §1.7, C1).
+  //
+  // Bornage AVANT le miroir : une valeur aberrante (parasite I²C, bord du
+  // verre qui déborde du gabarit ; p.x/p.y font 12 bits, jusqu'à 4095) est
+  // d'abord ramenée dans le gabarit, donc son miroir y reste. Les quatre
+  // points de bornage — (0,0), (319,0), (0,169), (319,169) — ne tombent
+  // dans AUCUNE zone (les boutons vont de x=12..307 et y=66..161, la zone
+  // STOP de x=60..259 et y=40..131) : un point bridé est inerte et ne peut
+  // pas déclencher de commande fantôme.
+  int32_t x = constrain((int32_t)p.x, 0, WIDTH  - 1);   // 0..319
+  int32_t y = constrain((int32_t)p.y, 0, HEIGHT - 1);   // 0..169
+  if (kTouchMirrorX) x = (WIDTH  - 1) - x;
+  if (kTouchMirrorY) y = (HEIGHT - 1) - y;
+
+  g_touchedRaw = true;
+  g_touchX = (int16_t)x;
+  g_touchY = (int16_t)y;
+
+  // Diagnostic (§4) : brut tel que rendu par TouchLib + transformé.
+  g_touchRawX  = (int16_t)p.x;  g_touchRawY  = (int16_t)p.y;
+  g_touchLastX = g_touchX;      g_touchLastY = g_touchY;
+  if (!wasTouched) {
+    g_touchSeq++;
+    Serial.printf("TOUCH     : brut=(%d,%d) ecran=(%d,%d) n=%lu\n",
+                  (int)p.x, (int)p.y, (int)g_touchX, (int)g_touchY,
+                  (unsigned long)g_touchSeq);
+  }
 }
```

Note : une seule ligne série par front montant (jamais pendant le maintien) — aucun impact sur la
cadence de la boucle. Si on veut s'en passer, supprimer le `Serial.printf` : `/api/touch` suffit.

### 3.3 `balance-bot/ui.h` — accès au diagnostic

```diff
@@ -9,6 +9,17 @@
 namespace Ui {
   // Initialisation écran + touch. Retourne true si OK.
   bool  begin();
+
+  // Diagnostic du repère tactile (TOUCH_REVIEW.md §4). Dernier point
+  // VALIDE, rémanent après relâchement : brut (sortie TouchLib, donc déjà
+  // transposé par son setRotation(1)) et transformé (repère écran
+  // 320×170). seq = numéro du tap, incrémenté à chaque front montant.
+  struct TouchDebug {
+    bool     down;                 // doigt posé à l'instant de la lecture
+    int16_t  rawX, rawY;           // brut TouchLib
+    int16_t  x, y;                 // après transformation (0..319 / 0..169)
+    uint32_t seq;                  // compteur de taps
+    bool     mirrorX, mirrorY;     // drapeaux actifs dans le binaire courant
+  };
+  TouchDebug touchDebug();
```

### 3.4 `balance-bot/ui.cpp` — implémentation (juste avant `Ui::begin()`, ligne 592)

À placer **hors** du `namespace { … }` anonyme (celui-ci se referme en `ui.cpp:521`).

```diff
@@ -591,6 +591,13 @@
+// Diagnostic tactile — cf. TOUCH_REVIEW.md §4.
+Ui::TouchDebug Ui::touchDebug() {
+  Ui::TouchDebug d;
+  d.down = g_touchedRaw;
+  d.rawX = g_touchRawX; d.rawY = g_touchRawY;
+  d.x = g_touchLastX;   d.y = g_touchLastY;
+  d.seq = g_touchSeq;
+  d.mirrorX = kTouchMirrorX; d.mirrorY = kTouchMirrorY;
+  return d;
+}
+
 // ── begin() ────────────────────────────────────────────────────────
 bool Ui::begin() {
```

### 3.5 `balance-bot/tuner.cpp` — endpoint dédié

```diff
@@ -190,6 +190,22 @@
   s_server.send(200, "application/json", buf);
 }
 
+// Diagnostic du repère tactile — TOUCH_REVIEW.md §4. Endpoint séparé
+// (et non un ajout à /api/state) : le tampon de handleState fait 256 o
+// pour ~160 o déjà consommés, une troncature silencieuse produirait un
+// JSON invalide et la page afficherait « hors ligne… ».
+// La valeur est RÉMANENTE : taper un coin, puis charger cette page.
+void handleTouch() {
+  touchReq();
+  const Ui::TouchDebug t = Ui::touchDebug();
+  char buf[192];
+  snprintf(buf, sizeof(buf),
+           "{\"down\":%d,\"brut\":{\"x\":%d,\"y\":%d},"
+           "\"ecran\":{\"x\":%d,\"y\":%d},\"n\":%lu,"
+           "\"mirrorX\":%d,\"mirrorY\":%d}",
+           t.down ? 1 : 0, t.rawX, t.rawY, t.x, t.y,
+           (unsigned long)t.seq, t.mirrorX ? 1 : 0, t.mirrorY ? 1 : 0);
+  s_server.send(200, "application/json", buf);
+}
+
@@ -252,6 +268,7 @@
   s_server.on("/api/state",  HTTP_GET,  handleState);
+  s_server.on("/api/touch",  HTTP_GET,  handleTouch);
   s_server.on("/api/gains",  HTTP_POST, handleGains);
```

### 3.6 Commentaires à rectifier en même temps (C2)

`ui.cpp:10-11` et `ui.cpp:642` affirment que les coordonnées sont « directes » / « déjà alignées ».
Remplacer par : *« setRotation(1) ne fait que transposer x↔y ; le sens de l'axe long est corrigé
dans readTouch() (miroir X) — voir TOUCH_REVIEW.md. »*

---

## 4. Protocole de vérification en 4 touches

### 4.1 Préparation — **sécurité d'abord**

Tant que le correctif n'est pas flashé, **appuyer à gauche de l'écran arme la boucle d'équilibre**
(C1). Faire le test robot **couché / pieds dégagés**, ou alimentation servos coupée. Vérifier que
l'état affiché en haut à droite reste `IDLE` entre deux taps ; s'il passe à `ARME`, retaper au même
endroit pour désarmer.

Deux voies de lecture, au choix :
* **Série** (la plus simple, aucun réseau) : moniteur USB CDC → une ligne `TOUCH : brut=… ecran=… n=…`
  par tap ;
* **HTTP** : appui long sur BOOT pour ouvrir l'AP, puis `http://192.168.4.1/api/touch` — la valeur
  est rémanente, on tape puis on recharge.

### 4.2 Les 4 touches

Taper au centre d'une cible d'environ 20 px placée à **10 px** de chaque coin (les 2-3 px extrêmes
du verre sont peu fiables) :

| # | Coin | Cible écran `(Xe, Ye)` |
|---|---|---|
| 1 | haut-gauche | (10, 10) |
| 2 | haut-droit | (309, 10) |
| 3 | bas-gauche | (10, 159) |
| 4 | bas-droit | (309, 159) |

**Valeurs BRUTES attendues** (`brut.x`, `brut.y` de `/api/touch`, tolérance ±8 px), selon l'état
réel du matériel :

| Tap | B — miroir X *(attendu)* | A — identité | C — miroir Y | D — 180° |
|---|---|---|---|---|
| 1 haut-gauche | **(309, 10)** | (10, 10) | (10, 159) | (309, 159) |
| 2 haut-droit | **(10, 10)** | (309, 10) | (309, 159) | (10, 159) |
| 3 bas-gauche | **(309, 159)** | (10, 159) | (10, 10) | (309, 10) |
| 4 bas-droit | **(10, 159)** | (309, 159) | (309, 10) | (10, 10) |

### 4.3 Lecture du résultat — 4 critères

1. **`n` s'incrémente de 1 à chaque tap.** Sinon on relit une mesure périmée : tout le reste est
   sans valeur.
2. **Sens de X** : `brut.x` **diminue** quand on va vers la droite (taps 1→2) → `kTouchMirrorX = true`.
   S'il augmente → `false`.
3. **Sens de Y** : `brut.y` **augmente** quand on descend (taps 1→3) → `kTouchMirrorY = false`.
   S'il diminue → `true`.
4. **Amplitudes** : `brut.x` doit balayer ≈ 10 → 309 et `brut.y` ≈ 10 → 159.
   **Si au contraire `brut.x` plafonne vers 170 et `brut.y` monte vers 320, l'hypothèse H1 tombe** :
   TouchLib rotation 1 serait alors le mauvais choix pour cette dalle — il faudrait passer
   `setRotation(0)` et faire l'échange à la main dans `readTouch()`. Toute l'analyse du §1 est
   construite pour que ce cas soit détecté et non subi.

### 4.4 Recette d'acceptation (après flash du correctif)

Refaire les 4 taps et lire `ecran` : il doit valoir ≈ la cible tapée, aux 4 coins
(`(10,10) / (309,10) / (10,159) / (309,159)`). Puis, en mode MANUEL :

| Appui | Effet attendu |
|---|---|
| AVANT (haut-gauche) | `cmdForward = +100`, l'état reste `IDLE` — **aucun armement** |
| ARRIÈRE (haut-milieu) | `cmdForward = −100` |
| GAUCHE (bas-gauche) | `cmdTurn = −100` |
| DROITE (bas-milieu) | `cmdTurn = +100` |
| ÉQUILIBRE (droite) | bascule `ARME` / `IDLE`, sans consigne de direction |

Le bouton appuyé doit s'allumer en orange (`drawButton`, `ui.cpp:533-534`) : c'est le contrôle
visuel immédiat que la zone reconnue est bien celle qu'on touche.

---

## 5. Contrôle de cohérence après correctif

### 5.1 Couverture, chevauchements, zones mortes

Une fois `g_touchX/Y` égal au repère écran, les zones sont testées telles quelles
(`ui.cpp:653-655`, semi-ouvertes `[x, x+w[`) :

```
x :  0..11  | z0/z2 12..99 | 100..107 | z1/z3 108..195 | 196..207 | z4 208..307 | 308..319
y :  0..65 (bandeau télémétrie) | rangée haute 66..111 | 112..115 | rangée basse 116..161 | 162..169
```

* **Chevauchements : aucun.** Les trois colonnes sont disjointes (99 < 108, 195 < 208) et les deux
  rangées aussi (111 < 116). La zone 4 couvre les deux rangées mais sur une colonne à elle.
* **Atteignabilité : totale.** Toutes les zones sont incluses dans `[0,319] × [0,169]` (extrêmes :
  `x = 307 ≤ 319`, `y = 161 ≤ 169`). La zone STOP (`[60,259] × [40,131]`) l'est aussi.
* **Zones mortes : uniquement les gouttières entre boutons** (8 à 12 px en x, 4 px en y) et le
  bandeau télémétrie `y < 66`. Elles correspondent exactement aux espaces *visibles* entre les
  rectangles dessinés : `fillRoundRect(z.x, z.y, z.w, z.h, …)` (`ui.cpp:536`) utilise les mêmes
  bornes que le test d'appui. Seule micro-divergence : les coins arrondis (rayon 8) rendent la
  boîte de détection un peu plus grande que le pixel affiché, d'au plus `8·(1 − √2/2) ≈ 2,3 px` en
  diagonale de coin. Sans conséquence.
* **Gouttière de 4 px en y (112..115)** : c'est le point le plus serré de la disposition. Un doigt
  posé pile dessus n'active rien — comportement correct (pas d'ambiguïté), et 4 px ≈ 0,5 mm, donc
  jamais atteint sans le vouloir puisque la surface de contact rapportée est un centroïde.
* **Mode AUTO** : le premier tap ouvre l'écran STOP quel que soit l'endroit (`ui.cpp:462`), le second
  doit tomber dans `[60,259] × [40,131]`, soit 200×92 px au centre — largement atteignable, et
  inchangé par le correctif puisque cette zone est son propre miroir (§1.8).

### 5.2 Front montant et relâchement

Le correctif ne touche **que** les valeurs de `g_touchX/g_touchY` et le moment où `g_touchedRaw`
passe à vrai. Or :

* **Mode AUTO** (`ui.cpp:444-445`) : `tap = g_touchedRaw && !s_prevTouch` ne dépend d'aucune
  coordonnée → strictement inchangé. Sémantique conservée : `g_touchedRaw` reste vrai tant que le
  contrôleur annonce ≥ 1 point.
* **Mode MANUEL** (`ui.cpp:650-663`) : `inZone` est recalculé à chaque tour, `z.pressed` passe à vrai
  sur transition `!pressed → inZone` et à faux dès que `!inZone`. Le correctif étant une bijection
  du plan sur lui-même, le nombre et l'ordre des transitions sont préservés — seule la zone
  *désignée* change (et c'est le but).
* **Doigt qui glisse hors du bouton en restant posé** (le cas commenté `ui.cpp:646-649`) : `dirHeld`
  reste calculé sur `inZone` et non sur `g_touchedRaw`, donc le retour au neutre
  (`ui.cpp:687-690`) fonctionne toujours. Après correctif il fonctionnera même **mieux** : aujourd'hui,
  un glissement vers la gauche fait *entrer* dans la zone 4 et bascule l'armement.
* **Régression restante, non introduite par le correctif** : C6 (sortir puis revenir dans une zone
  sans lever le doigt regénère un front montant). À traiter séparément si l'on veut ; le candidat
  minimal serait de n'autoriser un nouveau front qu'après un relâchement franc (`!g_touchedRaw`).

### 5.3 Ce que le correctif ne corrige pas

C5 (trame I²C figée → appui fantôme permanent) et C6 restent ouverts. Ils sont indépendants de
l'orientation et méritent leur propre passe.

---

## 6. Récapitulatif

| Constat | Fichier:ligne | Gravité | État |
|---|---|---|---|
| C1 inversion de X (arme le robot par erreur) | `ui.cpp:425-426` | **GRAVE** | correctif §3, à valider par §4 |
| C2 commentaires « coordonnées directes » faux | `ui.cpp:10-11`, `ui.cpp:642` | MOYEN | §3.6 |
| C3 rotations 2/3 silencieusement ignorées | `ModulesCSTSelf.tpp:99-104` | INFO | ne pas utiliser |
| C4 `getPoint(1)` lit hors tableau | `CSTSelfConstants.h:60-71` | GRAVE (latent) | point 0 uniquement, commenté §3.2 |
| C5 trame I²C figée → appui fantôme | `TouchLibCommon.tpp:218-234` | MOYEN | ouvert |
| C6 re-entrée sans relâchement = nouveau front | `ui.cpp:656-661` | MINEUR | ouvert |
| C7 `buf[256]` trop juste pour `/api/state` | `tuner.cpp:178` | MINEUR | contourné par `/api/touch` |
| C8 aucun bornage des coordonnées | `ui.cpp:425-426` | MINEUR | clamp §3.2 |
