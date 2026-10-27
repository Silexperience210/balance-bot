# Revue du visage animé (mode AUTO) — firmware BalanceBot

Périmètre : `balance-bot/ui.cpp` (bloc visage), `balance-bot/ui.h`, `balance-bot/tuner.cpp`
(`/api/face`), lus contre `balance-bot.ino`, `interfaces.h` et `balance.cpp`.
Revue **en lecture seule** : aucun fichier du firmware n'a été modifié.

Vérifications faites pendant la revue :

* compilation complète `--clean --warnings all` avec les flags de `build.sh` : **OK**
  (1 042 898 o de flash, 50 812 o de RAM globale). Aucun avertissement dans le code du
  visage ; les 3 `-Wformat-truncation` restants (`ui.cpp:718`, `752`, `811`) sont
  antérieurs et sans effet (bornes réelles largement sous `sizeof(b)`).
* boîtes englobantes réelles des 8 expressions recalculées hors carte, à partir des
  formules de `faceEyePoints()` (voir constat 6) ;
* recouvrement iris / amande calculé pixel par pixel (voir constat 10) ;
* budgets temps déduits du débit **mesuré par vous** (~2,5 Mpx/s), cohérent avec votre
  propre mesure de 14 ms pour `faceDraw()` (2 × 120 × 100 = 24 000 px → 9,6 ms + tracés).

---

## 1. — BLOQUANT — Le passage MANUEL → AUTO n'efface pas l'écran : le visage s'affiche par-dessus les débris de l'écran de commande

`ui.cpp:628-640` (transition), `ui.cpp:338-352` (`faceDraw`)

**Preuve.** `Ui::loop()` ne fait rien de particulier à l'entrée en AUTO :

```cpp
if (autoMode) { s_wasAuto = true; uiAutoLoop(); return; }
```

et le premier rendu du visage n'efface que deux rectangles :

```cpp
g_tft.fillRect(FACE_CX_L - 60, FACE_CY - 56, 120, 100, C_BG);   // x 41..160, y 28..127
g_tft.fillRect(FACE_CX_R - 60, FACE_CY - 56, 120, 100, C_BG);   // x 159..278, y 28..127
```

Aucun `fillScreen()` n'existe sur ce chemin (`fillScreen` n'apparaît que dans `begin()`,
`drawStatic()` et `faceDrawStop()`). Tout ce qui est hors de `x∈[41,278] ∧ y∈[28,127]`
reste donc à l'écran :

| élément de l'écran MANUEL | position | sort de la zone effacée ? |
|---|---|---|
| titre « BALANCEBOT » | y 2..17 | **oui** (y < 28) |
| séparateur | y 22 | **oui** |
| état (`IDLE`/`ARME`…) | (240, 8) | **oui** |
| labels « PITCH » / « BAT » | x 6..35 | **oui** (x < 41) |
| ligne debug `B:… U:… H:…` | x 6..156 | **oui**, tronquée à `B:2` |
| bas des 5 boutons | y 128..162 | **oui** — bande de ~35 px sur toute la largeur |
| bord gauche boutons 0/2, bord droit bouton 4 | x 12..40, x 279..307 | **oui** |

**Pourquoi ça n'a pas été vu en test.** L'armement au doigt passe systématiquement par
l'écran STOP (voir constat 7), et `faceDrawStop()` fait un `fillScreen()` — l'écran est
donc nettoyé par accident. Le défaut n'apparaît que sur les chemins **sans tap** :
armement par `/api/bal?on=1` et aperçu `/api/face`.

**Correctif.** Sortir les états de `uiAutoLoop()` au niveau du namespace anonyme et
ajouter une fonction d'entrée appelée sur le front MANUEL → AUTO :

```cpp
// namespace anonyme, à la place des statiques locales de uiAutoLoop()
bool s_stopShown = false; unsigned long s_stopUntil = 0, s_lastDraw = 0;
bool s_prevTouch = false, s_drawnValid = false;
FaceFrame s_drawn; IrisGeom s_irisL, s_irisR;
uint8_t s_clearStep = 0;      // effacement du pourtour étalé sur 4 images

void faceEnter() {            // MANUEL → AUTO
  s_stopShown  = false;
  s_drawnValid = false;       // ← corrige aussi le constat 4
  s_lastDraw   = 0;
  s_clearStep  = 0;
  s_irisL.valid = s_irisR.valid = false;
  g_state.cmdForward = 0; g_state.cmdTurn = 0;   // ← corrige aussi le constat 12
}
```

```cpp
// Ui::loop()
if (autoMode) {
  if (!s_wasAuto) { s_wasAuto = true; faceEnter(); }
  uiAutoLoop();
  return;
}
```

et, en tête de `uiAutoLoop()` (après la gestion du tap), effacer le pourtour **en quatre
bandes, une par image**, pour ne jamais dépasser le budget de 15 ms (un `fillScreen()`
d'un coup coûterait 320 × 170 / 2,5 Mpx/s ≈ **22 ms**) :

```cpp
if (s_clearStep < 4) {
  switch (s_clearStep) {           // 4 bandes hors des deux zones d'yeux
    case 0: g_tft.fillRect(0,   0, 320,  28, C_BG); break;  // 8 960 px → 3,6 ms
    case 1: g_tft.fillRect(0, 128, 320,  42, C_BG); break;  // 13 440 px → 5,4 ms
    case 2: g_tft.fillRect(0,  28,  41, 100, C_BG); break;  // 4 100 px → 1,6 ms
    case 3: g_tft.fillRect(279,28,  41, 100, C_BG); break;
  }
  s_clearStep++;
}
```

(Si vous préférez rester simple : `g_tft.fillScreen(C_BG)` dans `faceEnter()` — un seul
trou de 22 ms, au moment précis où le PID démarre. Je le déconseille, cf. constat 3.)

---

## 2. — BLOQUANT — Le bouton STOP peut RÉ-ARMER le robot : la zone tactile du mode AUTO retombe sur la zone 4 du mode MANUEL

`ui.cpp:160` (zone STOP), `ui.cpp:447-453` (action STOP), `ui.cpp:100-106` + `651-684`
(zones MANUEL), `balance.cpp:611` (`isEnabled()` renvoie `g_state.cmdEnabled`, sans délai)

**Preuve.** Le tap sur STOP fait :

```cpp
g_state.cmdEnabled = false;
s_stopShown = false; s_drawnValid = false;
return;                       // ← le doigt est toujours posé
```

`Balance::isEnabled()` renvoyant directement `g_state.cmdEnabled`, l'appel **suivant** de
`Ui::loop()` (16 ms plus tard, `.ino:68`) voit `autoMode == false`, redessine l'écran
MANUEL, puis relit le tactile. Le doigt n'a pas eu le temps d'être relevé (un tap humain
dure 80-200 ms). Les zones MANUEL ont `pressed == false`, donc `inZone && !z.pressed`
déclenche un **front montant**.

Géométrie du recouvrement :

| zone | rectangle | intersection avec STOP (60..259 × 40..131) |
|---|---|---|
| STOP (AUTO) | x 60..259, y 40..131 | — |
| zone 4 « ÉQUIL./STOP » | x 208..307, y 66..161 | **x 208..259, y 66..131** = 52 × 66 px, soit ~19 % de la surface du bouton STOP |
| zones 0..3 (flèches) | x 12..195, y 66..161 | x 60..195, y 66..131, soit ~44 % de la surface |

Conséquences :

* appui dans le quart **droit** de STOP → `g_state.cmdEnabled = !isEnabled() = true` →
  **le robot se ré-arme dans les 16 ms. Le bouton STOP ne stoppe pas.**
* appui au **centre** de STOP (x = 160, y = 86 : le réflexe naturel) → zone 1 « ARRIÈRE »
  → `cmdForward = -100` tant que le doigt reste posé → `demoStep()` (`balance.cpp:446`)
  fait reculer les pieds pendant l'appui sur STOP.

Le même mécanisme joue depuis l'aperçu web : un tap sur STOP pendant `previewFace()`
(robot non armé) peut **armer** le robot.

**Correctif.** Consommer l'appui en cours à chaque changement de mode, dans les deux sens.
Un seul verrou au niveau fichier suffit et corrige aussi le constat 7 :

```cpp
static bool g_touchLatch = false;   // ignore l'appui en cours après un changement de mode

void readTouch() {
  ...  // corps actuel inchangé
  if (g_touchLatch) {
    if (!g_touchedRaw) g_touchLatch = false;      // relâché : on reprend
    else { g_touchedRaw = false; g_touchX = g_touchY = -1; }
  }
}
```

`g_touchLatch = true;` dans `faceEnter()` (constat 1) **et** dans la branche de retour au
mode MANUEL (`ui.cpp:636-640`), juste avant `drawStatic()`.

À défaut, déplacer le bouton STOP hors des zones MANUEL est impossible : `g_zones`
couvre y 66..162 sur x 12..308, il ne reste que le bandeau y < 66.

---

## 3. — BLOQUANT — L'écran STOP redessine tout l'écran 10 fois par seconde, pendant que le robot équilibre

`ui.cpp:355-373` (`faceDrawStop`), `ui.cpp:455-458` (cadence)

**Preuve.**

```cpp
if (now - s_lastDraw >= 100) { s_lastDraw = now; faceDrawStop(s_stopUntil - now); }
```

et `faceDrawStop()` commence par `g_tft.fillScreen(C_BG)` puis redessine le
`fillRoundRect` 200 × 92, le texte taille 4, deux chaînes et la barre — **alors que seule
la barre de 200 × 4 px change**.

Budget, au débit de 2,5 Mpx/s que vous avez mesuré (et que confirme votre propre mesure
de 14 ms pour `faceDraw`) :

| opération | pixels | durée |
|---|---|---|
| `fillScreen` 320 × 170 | 54 400 | 21,8 ms |
| `fillRoundRect` 200 × 92 | 18 400 | 7,4 ms |
| textes + barres | ~2 000 | ~1 ms |
| **total par rafraîchissement** | | **≈ 30 ms** |

Soit **30 ms toutes les 100 ms pendant 6 s**, c'est-à-dire :

* un passage `Ui::loop()` à **~30 ms**, le double du plafond de 15 ms que vous fixez ;
* `Balance::loop()` et `Ui::loop()` étant sur la **même tâche** (`.ino:49-114`), 30 % du
  temps CPU disparaît : `balanceHz ≈ (1000 − 300) / 5 = 140 Hz`, à 20 Hz seulement du
  `kMinLoopHz = 120` (`balance.cpp:164`) qui déclenche `s_rateLow` → `halt()` →
  **pieds figés, le robot tombe** ;
* même sans franchir le seuil : un **trou de 30 ms dans un asservissement à 200 Hz**, dix
  fois par seconde, avec `dt` écrêté à `kDtMaxS = 50 ms` (`balance.cpp:462`). Le terme D
  travaille sur un échantillon vieux de 30 ms. C'est très largement suffisant pour faire
  décrocher un balancier.

Et l'écran STOP s'ouvre au **pire moment possible** : au tap qui suit l'armement (constat 7).

**Correctif.** Scinder en un dessin statique (une fois à l'ouverture) et une mise à jour
de la seule barre :

```cpp
void faceDrawStopStatic() {          // appelé UNE fois, à l'ouverture
  g_tft.fillRect(FACE_CX_L - 60, FACE_CY - 30, 120, 88, C_BG);  // efface les 2 yeux
  g_tft.fillRect(FACE_CX_R - 60, FACE_CY - 30, 120, 88, C_BG);  // (cf. constat 6)
  g_tft.fillRoundRect(STOP_X, STOP_Y, STOP_W, STOP_H, 16, C_ORANGE);
  ... texte "STOP" + "retour au visage" ...
  g_tft.fillRect(STOP_X, 160, STOP_W, 4, C_DARK);               // fond de barre
}

void faceUpdateStopBar(unsigned long resteMs) {   // 200 x 4 px = 800 px -> 0,3 ms
  const int bw = constrain((int)(STOP_W * (resteMs / (float)kStopHoldMs)), 0, STOP_W);
  g_tft.fillRect(STOP_X, 160, bw, 4, C_ORANGE);
  g_tft.fillRect(STOP_X + bw, 160, STOP_W - bw, 4, C_DARK);
}
```

Le dessin statique lui-même reste à ~17 ms : l'étaler sur deux images (effacement des
yeux à la 1ʳᵉ, bouton à la 2ᵉ) ramène chaque passage sous 10 ms. Passer la barre à 200 ms
au lieu de 100 ms est gratuit visuellement.

Note : `kStopHoldMs` vaut 6000 et `faceDrawStop` réécrit `6000.0f` en dur (`ui.cpp:370`) —
utiliser la constante.

---

## 4. — IMPORTANT — AUTO → MANUEL → AUTO : les caches du visage ne sont pas réinitialisés, le visage n'est pas redessiné et l'iris se dessine sur l'écran MANUEL

`ui.cpp:496-518` (caches), `ui.cpp:636-640` (retour au MANUEL : seuls les caches *manuels*
sont remis à zéro par `resetManualCaches()`)

**Preuve.** `s_drawn`, `s_drawnValid`, `s_irisL`, `s_irisR` sont des statiques locales de
`uiAutoLoop()` que rien ne réinitialise au retour du mode MANUEL. Or ce retour appelle
`drawStatic()`, qui fait un `fillScreen()` : **l'écran ne contient plus le visage, mais le
code croit toujours l'avoir dessiné.** Au ré-armement :

```cpp
if (s_drawnValid && sameFrame(f, s_drawn)) return;      // ui.cpp:496
```

* si l'expression et le quantum de regard sont identiques à ceux d'avant le désarmement
  (cas très probable : robot posé, `FX_CALME` ou `FX_CHUTE`, `gaze` ≈ 0), la fonction
  **sort sans rien dessiner** : l'écran MANUEL reste affiché alors que le robot est armé ;
* dès que `gaze` bouge d'un quantum, on tombe dans la branche incrémentale, qui appelle
  `faceMoveIris(s_irisL, …)` avec une géométrie **périmée** : deux disques orange
  (`col`) sont peints en plein milieu de la télémétrie, suivis de deux disques noirs.

Le déclencheur n'a rien d'exotique : désarmement par le bouton STOP, par `/api/bal?on=0`,
ou automatique sur batterie faible (`balance.cpp:422-425`), puis ré-armement.

**Correctif.** `s_drawnValid = false;` et `s_irisL.valid = s_irisR.valid = false;` dans
`faceEnter()` (constat 1). Le chemin de sortie de l'écran STOP le fait déjà correctement
(`ui.cpp:453`, `454`) — c'est la transition de mode qui a été oubliée.

---

## 5. — IMPORTANT — Aucune hystérésis sur les expressions : redessin complet à 20 Hz pendant l'équilibre

`ui.cpp:376-393` (`faceCompute`), `ui.cpp:502-509` (`structChanged` → `faceDraw`)

**Preuve.** Les seuils sont des comparaisons franches, sans bande morte ni durée minimale :

```cpp
else if (ap > 8.0f || ar > 40.0f) { f.expr = FX_ENERVE; ... }
else if (g_state.obstacleWarn || fabsf(foot) > 20.0f) f.expr = FX_MEFIANT;
else if (ap < 1.5f && ar < 6.0f) f.expr = FX_CONTENT;
else if (ap > 3.0f)             f.expr = FX_PENCHE;
```

Un robot qui équilibre oscille en permanence autour de son point neutre ; `ar < 6 °/s`
(condition d'entrée dans `FX_CONTENT`) est franchi plusieurs fois par seconde par le
simple bruit gyro. Chaque franchissement change `f.expr`, donc `structChanged`, donc un
`faceDraw()` **complet** — les 14 ms que vous avez mesurées, mais **à chaque image** :

* 20 images/s × 14 ms = **280 ms/s** de CPU pris à la boucle d'équilibre ;
* `balanceHz ≈ (1000 − 280) / 5 ≈ 145 Hz`, contre 196-200 mesurés en aperçu (où
  l'expression est **figée** par `previewFace` : votre mesure « 0 ms en régime établi » ne
  couvre pas ce cas) ;
* marge résiduelle avant le `halt()` à 120 Hz : 25 Hz. `Head::loop()` et un obstacle
  peuvent la consommer.

Même bruit sur `foot` autour de 20° et sur `obstacleWarn`.

**Correctif.** Deux garde-fous cumulatifs dans `faceCompute()` / `uiAutoLoop()` :

1. hystérésis : mémoriser l'expression courante et élargir les seuils de sortie
   (ex. on entre dans `FX_CONTENT` sous 1,5° / 6 °/s, on n'en sort qu'au-dessus de
   2,5° / 12 °/s ; idem pour `FX_PENCHE` 3,0 → 2,2 et `FX_ENERVE` 8,0 → 6,5) ;
2. durée de maintien minimale, sauf urgence :

```cpp
constexpr unsigned long kExprHoldMs = 400;
static unsigned long s_exprSince = 0;
static FaceExpr      s_exprCur   = FX_CALME;
// dans uiAutoLoop, après f = faceCompute() :
if (f.expr != s_exprCur) {
  if (f.expr == FX_CHUTE || now - s_exprSince >= kExprHoldMs) {   // la chute passe tout de suite
    s_exprCur = f.expr; s_exprSince = now;
  } else {
    f.expr = s_exprCur;                                            // on garde l'ancienne
  }
}
```

Plafond garanti : un redessin complet toutes les 400 ms → 14 ms / 400 ms = 3,5 % de CPU,
`balanceHz` ≥ 193.

---

## 6. — IMPORTANT — La zone effacée est trop courte en bas : résidu orange sous les yeux au changement d'expression

`ui.cpp:342-343`

**Preuve.** La zone effacée s'étend de `FACE_CY − 56` à `FACE_CY + 43` (hauteur 100).
J'ai recalculé les boîtes englobantes réelles à partir de `faceEyePoints()` (mêmes
formules, mêmes constantes `LID_TOP`, `EXP_TOP`, `EXP_BOT`, même rotation) :

| expression | Δx | Δy | dépasse `+43` ? |
|---|---|---|---|
| CALME | ±51,7 | −19,3 … **+48,9** | **oui, +6 px** |
| PENCHÉ | ±50,7 | −17,8 … +41,3 | non |
| MÉFIANT | ±50,2 | −15,7 … +32,9 | non |
| ÉNERVÉ | ±46,7 | −22,8 … +27,6 | non |
| SURPRISE | ±49,9 | −21,3 … **+54,6** | **oui, +12 px** |
| CONTENT | ±47,4 | −15,5 … +39,5 | non |
| CLIN (œil droit) | ±49,9 | −20,5 … **+52,4** | **oui, +10 px** |
| clignement | ±51,7 | −5,4 … +7,6 | non |

Toute transition depuis CALME, SURPRISE ou CLIN vers une expression plus basse laisse donc
une **bande orange de 6 à 12 px de haut sous chaque œil**, sur une centaine de pixels de
large. CALME étant l'expression par défaut, le cas se produit à chaque clignement
(CALME h=68 → clignement h=8) et à chaque changement d'humeur.

Symétriquement, la marge en haut est inutilement grande (−56 alors que −22,8 suffit) : le
correctif est **à la fois correct et moins coûteux**.

**Correctif.**

```cpp
-  g_tft.fillRect(FACE_CX_L - 60, FACE_CY - 56, 120, 100, C_BG);
-  g_tft.fillRect(FACE_CX_R - 60, FACE_CY - 56, 120, 100, C_BG);
+  // couvre Δy = −30 … +57 (max mesuré : −22,8 … +54,6) et Δx = ±60 (max ±51,7)
+  g_tft.fillRect(FACE_CX_L - 60, FACE_CY - 30, 120, 88, C_BG);
+  g_tft.fillRect(FACE_CX_R - 60, FACE_CY - 30, 120, 88, C_BG);
```

Vérifications : `84 − 30 = 54 ≥ 0`, `54 + 88 = 142 ≤ 170`. Coût : 2 × 10 560 px = 21 120 px
→ **8,4 ms** au lieu de 9,6 ms. Le commentaire « chaque zone fait 120x100 px → ~10 ms »
est à mettre à jour. Penser à répercuter la même zone dans `faceDrawStopStatic()`
(constat 3).

---

## 7. — IMPORTANT — L'armement au doigt ouvre immédiatement l'écran STOP

`ui.cpp:443-446`, `ui.cpp:673-681`

**Preuve.** L'appui sur le bouton 4 met `cmdEnabled = true`, sans que le doigt soit
relevé. 16 ms plus tard, `Ui::loop()` bascule en AUTO et `uiAutoLoop()` fait :

```cpp
const bool tap = g_touchedRaw && !s_prevTouch;   // s_prevTouch = false (session précédente)
```

Le doigt est encore posé → `tap == true` → écran STOP pendant 6 s, à 30 ms de rendu tous
les 100 ms (constat 3), **exactement au moment où le PID vient d'être remis à zéro et où
le robot doit être rattrapé**. Le visage n'apparaît qu'au bout de 6 s.

**Correctif.** Le verrou `g_touchLatch` du constat 2 (armé dans `faceEnter()`) supprime le
faux tap : le premier appui pris en compte en AUTO sera le premier appui **postérieur au
relâchement**.

---

## 8. — IMPORTANT — Le regard est **mirroité** : les yeux louchent au lieu de suivre le tangage

`ui.cpp:266` (`faceIrisGeom`), `ui.cpp:307-308` (`faceDrawEye`)

**Preuve.**

```cpp
g.x = cx + inn * (int)constrain(f.gaze, -18.0f, 18.0f);   // inn = +1 à gauche, −1 à droite
```

`inn` sert légitimement à **mirroiter la forme de l'amande** (inclinaison vers l'intérieur)
et le reflet, mais il est aussi appliqué au regard. Résultat : pour `gaze > 0`, l'iris
gauche part vers la droite et l'iris droit vers la gauche — les deux iris **convergent**
(strabisme) au lieu de regarder du même côté. Le commentaire `ui.cpp:391` annonce pourtant
« le regard suit le tangage ».

**Correctif.** Retirer `inn` du seul calcul de position horizontale, aux deux endroits
(les deux formules doivent rester identiques, cf. constat 15) :

```cpp
-  g.x = cx + inn * (int)constrain(f.gaze, -18.0f, 18.0f);
+  g.x = cx + (int)constrain(f.gaze, -18.0f, 18.0f);
```

```cpp
-  const int ix = cx + inn * gx;
+  const int ix = cx + gx;
```

Le reflet (`ix - inn * r / 2`) doit **rester** mirroité : c'est la symétrie de l'éclairage,
elle est correcte.

---

## 9. — IMPORTANT — `/api/face` peut confisquer l'écran pendant des heures, sans aucune sortie par le tactile

`ui.h:20`, `ui.cpp:820-825` (`previewFace`), `tuner.cpp:233-243` (`handleFace`)

**Preuve.** `handleFace()` ne borne pas la durée :

```cpp
const unsigned long ms = s_server.hasArg("t")
    ? (unsigned long)s_server.arg("t").toInt() * 1000UL : 5000UL;
Ui::previewFace((uint8_t)st, ms, s_server.hasArg("sweep"));
```

`GET /api/face?state=0&t=100000` force le visage pendant **27 h**. Or `autoMode`
(`ui.cpp:629-630`) est vrai tant que l'aperçu dure : l'écran MANUEL — donc le bouton
ÉQUILIBRE/STOP — est **inaccessible**, et le seul geste tactile disponible (le tap) ouvre
l'écran STOP, dont la sortie renvoie… au visage. Aucun moyen d'annuler depuis la carte
(hors reset ou fermeture de l'AP par appui long BOOT, qui ne change rien à `s_faceForced`).

`t` négatif est inoffensif (`(unsigned long)(-1) * 1000` repasse dans le passé, l'aperçu
expire aussitôt) ; `state` est correctement borné par le `constrain` de `previewFace`.

**Correctif.** Borner côté firmware **et** offrir une sortie tactile :

```cpp
// ui.cpp — previewFace()
-  s_forcedUntil = millis() + ms;
+  s_forcedUntil = millis() + (ms > 60000UL ? 60000UL : ms);   // 60 s maxi
```

```cpp
// uiAutoLoop(), dans la branche « if (tap) »
if (tap) {
  if (!Balance::isEnabled()) { s_faceForced = false; return; }  // aperçu : un tap rend la main
  s_stopShown = true; ...
}
```

---

## 10. — MINEUR — L'iris déborde de l'amande : l'effacement incrémental laisse des taches orange sur le fond

`ui.cpp:324-336` (`faceMoveIris`), `ui.cpp:255-270` (`faceIrisGeom`)

**Preuve.** `faceMoveIris()` efface l'ancien iris en le repeignant **à la couleur de
l'œil** — ce qui n'est correct que si l'iris était entièrement à l'intérieur de l'amande.
Comptage pixel par pixel de la forme réellement tracée (disque, ou rectangle pour les
expressions `slit`) contre le polygone de l'œil :

| expression | regard −18 | regard +18 | taille de l'iris |
|---|---|---|---|
| CALME | 0 px dehors | 0 px dehors | 1 793 px |
| PENCHÉ | 0 | 5 | 1 373 px |
| MÉFIANT | 0 | 9 | 297 px |
| **ÉNERVÉ** | 11 | **29** | **95 px** (30 % de la fente !) |
| **SURPRISE** | 46 | **60** | 2 453 px |
| CLIN | 23 | 32 | 2 289 px |

Tant que l'iris est noir sur fond noir, le débordement est invisible. Mais au premier
déplacement du regard, `fillCircle(oldG.x, oldG.y, oldG.r, col)` peint ces pixels **en
orange sur le fond noir** : une tache qui persiste jusqu'au prochain redessin complet.
Le cas ÉNERVÉ est le plus voyant (fente de 5 × 19 px dans une amande de 27 px de haut
inclinée à 26°).

**Correctif (exact).** Effacer par l'intérieur du polygone plutôt que par un disque :
ajouter un fenêtrage à `fillPoly()` et l'utiliser pour l'effacement.

```cpp
void fillPolyClip(const int16_t* xs, const int16_t* ys, int n, uint16_t color,
                  int yMin, int yMax, int xMin, int xMax);   // bornes incluses
```

Dans `faceMoveIris()`, remplacer le `fillCircle`/`fillRect` d'effacement par un
`fillPolyClip` limité à la boîte de l'ancien iris. Surcoût : recalcul des 34 points
(~50 µs de `powf`) pour la même surface peinte, et le contour de l'amande est réparé au
passage.

**Correctif (économique).** Réduire l'amplitude du regard selon la géométrie de l'œil,
p. ex. dans `faceStyle()` exposer `gazeMax` (18 pour CALME/PENCHÉ, 10 pour SURPRISE/CLIN,
6 pour MÉFIANT/ÉNERVÉ) et remplacer les deux `constrain(f.gaze, -18.0f, 18.0f)` par
`constrain(f.gaze, -s.gazeMax, s.gazeMax)`.

---

## 11. — MINEUR — `previewFace()` écrit depuis le cœur 0 des variables lues depuis le cœur 1, sans `volatile` ni ordre garanti

`ui.cpp:396-402`, `ui.cpp:820-825`, `tuner.cpp:239` + `tuner.cpp:260`
(`xTaskCreatePinnedToCore(serverTask, …, 0)`)

**Preuve.** `handleFace()` s'exécute sur la tâche « tuner » épinglée au **cœur 0** ;
`Ui::loop()` tourne sur `loopTask` (cœur 1). `s_faceForced`, `s_forcedExpr`,
`s_forcedUntil`, `s_forcedSweep` sont de simples statiques non `volatile`, sans barrière.
De plus l'ordre d'écriture est :

```cpp
s_forcedExpr = …; s_forcedUntil = …; s_faceForced = true; s_forcedSweep = sweep;
```

`s_forcedSweep` est publié **après** le drapeau : une image peut être rendue avec l'ancien
mode `sweep`. Conséquences bénignes (une image erronée) mais le motif est faux.

**Correctif.** Déclarer les quatre variables `volatile` et publier le drapeau en dernier :

```cpp
s_forcedExpr  = (FaceExpr)constrain((int)expr, 0, (int)FX_CHUTE);
s_forcedSweep = sweep;
s_forcedUntil = millis() + ms;
s_faceForced  = true;          // publié en dernier
```

---

## 12. — MINEUR — Consignes `cmdForward`/`cmdTurn` figées si l'armement vient du web pendant un appui sur une flèche

`ui.cpp:434-519` (aucune écriture de `cmdForward`), `tuner.cpp:222-228` (`handleBal`)

**Preuve.** Le relâchement d'une flèche n'est détecté que par la boucle MANUEL
(`ui.cpp:687-690`). Si `/api/bal?on=1` arme le robot alors qu'une flèche est tenue, la
boucle MANUEL cesse d'être exécutée : `cmdForward` reste à ±100 pour **toute la session
AUTO**, et `balance.cpp:521-529` la consomme (consigne de vitesse). Le chemin tactile est
protégé (`ui.cpp:679-680` remet les consignes à zéro), pas le chemin web.

**Correctif.** `g_state.cmdForward = 0; g_state.cmdTurn = 0;` dans `faceEnter()`
(constat 1) — ou dans `handleBal()`.

---

## 13. — MINEUR — Comparaisons de `millis()` non robustes au rebouclage (49,7 jours)

`ui.cpp:454` (`now >= s_stopUntil`), `ui.cpp:473` et `630` (`now < s_forcedUntil`),
`ui.cpp:482` (`now >= s_nextBlink`), `ui.cpp:489-494` (`now > s_winkCooldown`,
`now < s_winkUntil`)

**Preuve.** Ce sont des comparaisons d'instants absolus. Le reste du firmware utilise
partout la forme robuste `now - t0 >= delai` (`.ino:57`, `68`, `79`, `106` ;
`ui.cpp:456`, `469`). Au rebouclage, l'écran STOP peut rester bloqué 49 jours ou un
aperçu ne jamais expirer.

**Correctif.** Forme signée, p. ex. `if ((long)(now - s_stopUntil) >= 0)`,
`if (s_faceForced && (long)(now - s_forcedUntil) < 0)`, etc. Impact pratique faible
(le robot ne tourne pas 49 jours), mais l'incohérence de style est réelle.

---

## 14. — MINEUR — La batterie et les pannes capteur ne sont pas reflétées dans le visage

`ui.cpp:376-393` (`faceCompute`)

**Preuve.** La description de la fonctionnalité annonce des expressions pilotées par
« tangage, vitesse angulaire, obstacle, **batterie**, chute ». `faceCompute()` lit
`pitchDeg`, `pitchRateDps()`, `obstacleWarn`, `footLDeg/RDeg` et `isFallen()` — **jamais
`g_state.batteryLow`**, ni `Balance::imuOk()`, ni la mise en sécurité `s_rateLow`. Un robot
dont l'IMU est muette ou dont la cadence s'est effondrée affiche un visage « content ».

**Correctif.** Ajouter en tête de la cascade, avant `isFallen()` :

```cpp
if (g_state.batteryLow)  { f.expr = FX_MEFIANT; f.red = true; return f; }   // ou une expression dédiée
if (!Balance::imuOk())   { f.expr = FX_CHUTE;   return f; }
```

(Remarque : sur batterie faible, `balance.cpp:422-425` désarme, donc l'écran MANUEL affiche
déjà « BAT. FAIBLE » — mais l'aperçu web, lui, reste muet.)

---

## 15. — MINEUR — Le regard n'est quantifié que pour la **décision**, pas pour la **position** dessinée

`ui.cpp:410` (`gazeQ`), `ui.cpp:266` / `307` (position réelle)

**Preuve.** `sameFrame()`/le test `ui.cpp:510` comparent `gazeQ(gaze) = (int)g / 2 * 2`,
mais la position tracée utilise `(int)constrain(f.gaze, …)`, non quantifiée. Le commentaire
« Le regard est quantifié par pas de 2 px » ne décrit donc pas ce que fait le code : le
déclenchement se fait par pas de 2, le déplacement effectif peut valoir 1 ou 3 px. Aucun
artefact (la géométrie mémorisée dans `s_irisL/R` est bien celle qui a été tracée), mais la
logique est double. Accessoirement `(int)g / 2 * 2` tronque vers zéro : le pas autour de 0
vaut 3 px (−1, 0, +1 → 0) au lieu de 2.

**Correctif.** Quantifier une seule fois, à la source : `f.gaze = (float)gazeQ(constrain(pitch * 1.6f, -18.0f, 18.0f));`
dans `faceCompute()` (et dans la branche `sweep`), puis supprimer `gazeQ` des comparaisons.

---

## 16. — MINEUR — Débordements silencieux possibles dans `fillPoly` / `faceEyePoints` si la géométrie évolue

`ui.cpp:174-199` (`xi[8]`, garde `cnt < 8`), `ui.cpp:275` (`xs[40]`, `ys[40]`),
`ui.cpp:202-225` (`N = 16` → **34 points écrits**)

**Preuve.** Aujourd'hui c'est correct : 2 × (N+1) = 34 ≤ 40, et l'amande est un domaine
**convexe** (bord supérieur `ht·t²−ht` convexe, bord inférieur `hb(1−t²)^0,62` concave pour
tout exposant < 1), donc au plus 2 intersections par ligne ≤ 8. Aucun risque immédiat, et
la division `(float)(yj - yi)` est bien protégée par le test `(yi > y) != (yj > y)` qui
impose `yi != yj`. Mais rien ne relie `N` à la taille 40 : passer `N` à 20 pour lisser le
contour déborde de 42 points sur un tableau de 40, silencieusement, **sur la pile de
`loopTask`**. De même, si un futur `EXP_BOT > 1` rendait la forme concave, `cnt` serait
tronqué à 8 et les paires de spans seraient décalées (remplissage inversé), sans alerte.

**Correctif.** Rendre la contrainte explicite :

```cpp
constexpr int kEyeN = 16;
constexpr int kEyePts = 2 * (kEyeN + 1);
static_assert(kEyePts <= 40, "xs/ys trop petits pour faceEyePoints()");
// et dans faceDrawEye : int16_t xs[kEyePts], ys[kEyePts];
```

et, dans `fillPoly`, ignorer la ligne si `cnt` est impair plutôt que de dessiner des spans
décalés. Empreinte pile actuelle : 2 × 40 × 2 = 160 o pour `xs`/`ys` + 16 o pour `xi` — sans
commune mesure avec les 8 Ko de `loopTask`, rien à signaler côté mémoire par ailleurs
(aucune allocation, aucun `String`, aucun `std::` dans tout le bloc visage).

---

## 17. — MINEUR — Le trait du clin d'œil ignore la teinte colère

`ui.cpp:345`

**Preuve.** `g_tft.fillRect(FACE_CX_L - 34, FACE_CY - 2, 68, 4, C_ORANGE);` — couleur en
dur, alors que `faceDrawEye()` utilise `f.red ? C_RED : C_ORANGE`. Le clin d'œil est
déclenché après une récupération de chute (`ui.cpp:489-494`), où `f.red` peut valoir vrai
si `ap > 8°` : un œil rouge et une paupière orange.

**Correctif.** `const uint16_t col = f.red ? C_RED : C_ORANGE;` en tête de `faceDraw()` et
l'utiliser pour le trait.

---

## 18. — COSMÉTIQUE — `fillPoly` omet la dernière ligne du polygone

`ui.cpp:180-197`

**Preuve.** À `y == ymax`, le sommet le plus bas donne `(ys[i] > y) == false` pour lui et
pour ses deux voisins → `cnt == 0` → aucune ligne tracée. Le bas de chaque amande perd
1 px. (À `y == ymin` le compte vaut 2, la ligne est tracée : l'asymétrie vient de la
convention `>` du test.) Invisible à l'œil, mentionné pour l'exactitude.

---

## 19. — COSMÉTIQUE — Commentaires en décalage avec le code

* `ui.cpp:469` : `// 25 Hz max` alors que `kFaceHz = 20` → 50 ms (le commentaire de
  `ui.cpp:405` dit bien 20 Hz).
* `ui.cpp:340-341` : « Chaque zone fait 120x100 px → ~10 ms pour les deux » — à corriger
  avec le constat 6 (120 × 88 → 8,4 ms).
* `ui.cpp:370` : `6000.0f` en dur au lieu de `kStopHoldMs`.
* `ui.h:17` / `ui.cpp:818` : « 0..7 » est juste, mais `Ui::previewFace` n'est pas déclarée
  dans `interfaces.h` (`namespace Ui` y liste seulement `begin`/`loop`). Le contrat annoncé
  « gelé » de `interfaces.h` et `ui.h` divergent désormais — à trancher (ajouter la
  signature au contrat, ou assumer que `ui.h` l'étend).

---

## 20. — COSMÉTIQUE — Micro-coûts inutiles dans `faceEyePoints`

`ui.cpp:204-219`

* `powf(x, EXP_TOP)` avec `EXP_TOP = 1.00f` : 17 appels par œil pour une multiplication par
  1. Remplaçable par la valeur directe (`EXP_TOP` reste utile comme point de réglage — un
  `if constexpr`-like ou un simple commentaire suffit).
* `angDeg * DEG_TO_RAD` : `DEG_TO_RAD` est un `double` Arduino → multiplication double
  émulée en logiciel. Écrire `angDeg * 0.017453293f`.

Total en jeu : ~100 µs par redessin complet, à comparer aux 14 ms de trafic écran. Aucun
impact temps réel — c'est bien le **nombre de pixels** qui gouverne, pas le calcul.

---

## Points vérifiés et jugés **corrects**

* `drawArc(cx, FACE_CY+6, w/2-8, w/2-18, …)` en `FX_CONTENT` : `w` vaut toujours 95 pour
  cette expression → `r = 39 > ir = 29`. Pas d'inversion possible, et la branche est
  inatteignable en clignement (retour anticipé `ui.cpp:289`).
* `constrain((int)expr, 0, (int)FX_CHUTE)` sur un `uint8_t` : bornage correct, pas
  d'index hors énumération.
* Divisions : `(float)(yj - yi)` protégée par le test de traversée ; `1000 / kFaceHz` sur
  constantes ; `resteMs / 6000.0f` toujours dans `]0, 1]`.
* `f.blink` combiné à une expression : `faceStyle()` force `h = 8` et `faceDrawEye()` sort
  après le remplissage — les branches `FX_CHUTE`/`FX_CONTENT`/iris ne sont pas atteintes.
  La boîte du clignement (−5,4 … +7,6) tient dans la zone effacée.
* Cohérence `faceIrisGeom()` ↔ `faceDrawEye()` : mêmes formules `hb`, `r`, `iy`, mêmes
  exclusions (`blink`, `FX_CHUTE`, `FX_CONTENT`, `FX_CLIN` œil gauche). `IrisGeom::w` n'est
  pas mis à jour hors mode `slit` mais n'est jamais lu dans ce cas.
* `resetManualCaches()` : valeurs de réamorçage cohérentes avec ce que `drawStatic()`
  dessine (`0.0 deg`, `0.00 V`, `--`, `MANUEL`), pas de faux « rien n'a changé ».
* Le bouton 4 reste piloté par `Balance::isEnabled()`, pas par `g_state.balancing` ; les
  écritures servo restent l'apanage de la boucle d'équilibre ; aucune de ces garanties
  n'est cassée par le visage.
* Style : commentaires en français, aucun `std::`, aucun `delay()` dans le code du visage
  (le seul `delay(120)` est dans la séquence d'init du panneau, antérieure).
* Mémoire : ~90 octets de statiques ajoutés, aucune allocation dynamique, aucun `String`,
  160 octets de pile au pire — sans effet sur les 8 Ko de `loopTask`.

---

## Verdict

**À corriger avant flash.**

Trois défauts sont bloquants et se manifestent au premier usage réel :

* **constat 3** — l'écran STOP fait un `fillScreen()` toutes les 100 ms pendant que le
  robot équilibre : ~30 ms par passage `Ui::loop()` (le double du plafond que vous vous
  êtes fixé), `balanceHz` autour de 140 pour un seuil de coupure à 120, et un trou de
  30 ms dans l'asservissement dix fois par seconde ;
* **constat 2** — le bouton STOP recouvre la zone 4 de l'écran MANUEL et l'appui n'est pas
  consommé au changement de mode : appuyer à droite de STOP **ré-arme** le robot dans les
  16 ms ; appuyer au centre envoie une consigne « arrière » ;
* **constat 1** — l'entrée en mode AUTO n'efface pas l'écran : le visage s'affiche sur les
  restes de l'écran de commande (titre, labels, bas des cinq boutons). Masqué en test par
  le constat 7, mais systématique dès qu'on arme depuis le web.

S'y ajoutent quatre défauts importants à traiter dans la même passe : caches du visage non
réinitialisés au ré-armement (**4**, corruption visible de l'écran MANUEL), absence
d'hystérésis sur les expressions (**5**, redessins complets à 20 Hz en équilibre), zone
d'effacement trop courte en bas (**6**, résidus orange — le correctif est aussi plus
rapide que le code actuel), et regard mirroité (**8**).

Bonne nouvelle : les constats 1, 2, 4, 7 et 12 se corrigent tous avec **deux ajouts**
— une fonction `faceEnter()` appelée sur le front MANUEL → AUTO, et un verrou
`g_touchLatch` consommant l'appui en cours à chaque changement de mode. Les constats 3, 5
et 6 sont trois modifications locales et indépendantes. L'architecture du rendu incrémental
elle-même est saine : c'est bien le nombre de pixels poussés sur le bus parallèle qui
gouverne le temps réel, et le code l'a compris partout sauf sur l'écran STOP.
