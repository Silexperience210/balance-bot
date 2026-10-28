# Revue finale (lecture seule) — travaux de la nuit du 09/09/2026

Périmètre : `871811f^..HEAD` (5 commits), soit **846 lignes ajoutées / 29 supprimées**
dans 5 fichiers du firmware :

| fichier | + | rôle dans la nuit |
|---|---|---|
| `balance-bot/ui.cpp` | +716 | tactile (miroir X, rejet des trames, verrou), visage AUTO, DisAutoSleep |
| `balance-bot/tuner.cpp` | +64 | `/api/touch`, champs de cadence dans `/api/state`, `/api/face` |
| `balance-bot/balance-bot.ino` | +51 | instrumentation de cadence |
| `balance-bot/interfaces.h` | +23 | champs `dbg*` de `g_state` |
| `balance-bot/ui.h` | +21 | `TouchDebug`, `setTouchSkip`, `setIntGate` |

`head.cpp`, `feet.cpp`, `imu.cpp`, `battery.cpp`, `balance.cpp`, `config.h` n'ont **pas**
été touchés cette nuit.

> Remarque de méthode : `git diff HEAD~3..HEAD` (demandé dans le brief) **ne voit pas
> 871811f**, qui est pourtant le plus gros commit de la nuit (`ui.cpp` +646). La plage
> correcte est `HEAD~4..HEAD` / `871811f^..HEAD`. Cette revue porte sur la plage complète
> et sur la lecture intégrale de l'état final des 5 fichiers.

---

## Compilation (sans flash)

Commande : flags exacts de `build.sh`, `--warnings all`, `--build-path` neuf
(reconstruction complète, aucun objet en cache), **`arduino-cli compile` seul — aucun
`upload`**.

```
Le croquis utilise 1045558 octets (79%) de l'espace de stockage de programmes.
  Le maximum est de 1310720 octets.
Les variables globales utilisent 50884 octets (15%) de mémoire dynamique,
  ce qui laisse 276796 octets pour les variables locales. Le maximum est de 327680 octets.
[exited with code 0]
```

**16 avertissements**, dont **13 en bibliothèque tierce** et **3 dans `ui.cpp`** :

| n | origine | avertissement |
|---|---|---|
| 4 | TFT_eSPI | `#warning` DMA non supporté en parallèle (×2), `TOUCH_CS` non défini (×2) |
| 6 | ESP32Servo + core | MCPWM déprécié (×2), `TAG`/`val`/`ret` non utilisés (×4) |
| 3 | TouchLib `TouchLibCommon.tpp:49` | `array subscript 16/17/18 above array bounds of uint8_t[13]` — c'est **C4 de TOUCH_REVIEW** (lecture hors tableau dans `getPoint(1)`). Le firmware n'appelle jamais `getPoint(1)` (`ui.cpp:568-569` + commentaire d'interdiction) : **latent, non déclenché**. |
| 3 | `ui.cpp:976`, `ui.cpp:1010`, `ui.cpp:1069` | `-Wformat-truncation` |

Les 3 avertissements de `ui.cpp` ont été vérifiés par analyse de domaine et sont **des
faux positifs** (le compilateur ne connaît pas les bornes) :

* `ui.cpp:976` — `pitchDeg` vient d'un `atan2` → ∈ [−180, 180] ⇒ `"-180.0 deg"` = 10 car. < 16 ;
* `ui.cpp:1010` — `foot` borné par `FOOT_HARD_DEG` = 45 ⇒ `"P:+45 deg"` = 9 car. < 16 ;
* `ui.cpp:1069` — `"B:65535 U:255 H:255"` = 19 car. < 24.

---

## Constats numérotés

Gravité : **MOYEN** = à corriger avant de considérer le lot comme clos ·
**FAIBLE** = à corriger au prochain passage · **INFO** = connu/ouvert, documenté.

---

### 1 — MOYEN — `tuner.cpp:178-203` — `/api/state` peut **tronquer son JSON** : tampon 384 o pour 410 o au pire

**Preuve (par le calcul, gabarit `snprintf` reproduit à l'identique) :**

| jeu de valeurs | longueur + NUL | tampon 384 |
|---|---|---|
| nominal (robot calme, 1 h d'uptime) | 330 o | OK |
| **la session de mesure de `STALL_ANALYSIS.md`** (`worst`=1002, `touchmax`=1001, `stalls`=21, `big`=21, `lgap`=1002, `balmax/uimax/loopmax` 4 chiffres) | **354 o** | OK, **30 o de marge** |
| compteurs saturés (`uint16_t` = 65535, `s` = 7 chiffres après 49 j, `pitch` = −180.0) | **410 o** | **TRONQUÉ** |

`TOUCH_REVIEW.md` C7 avait recommandé « passer `buf` à 384 » — mais **pour la charge
utile d'avant la nuit**. Le commit 741ad5b a ajouté **19 champs** (`gap`…`drawmax`,
≈ +150 o) sans relever le tampon.

**Conséquence.** JSON tronqué ⇒ `fetch().json()` lève ⇒ `.catch()` de `tuner.cpp:157`
affiche « hors ligne… » **en permanence** : plus de télémétrie, plus de recalage des
sliders, et on croit à une panne de radio. Exactement le piège que C7 décrivait.
La marge de 30 o est de plus consommée par l'uptime (`"s"` passe à 5 chiffres après 2,8 h,
6 après 27 h) et par `dbgBigGaps`/`dbgStalls` qui ne sont jamais remis à zéro.

**Correctif précis.** `tuner.cpp:178` : `char buf[512];` et tester le retour —
```cpp
const int n = snprintf(buf, sizeof(buf), …);
if (n < 0 || n >= (int)sizeof(buf)) { s_server.send(500, "text/plain", "json trop long"); return; }
```

---

### 2 — MOYEN — `balance-bot.ino:96-103` — la phase **« 1 = ui » n'est jamais affectée** : `gph` accuse toujours la boucle d'équilibre

**Preuve.** `s_lastPhase` vaut 5 à l'initialisation (`ino:58`) et n'est écrit qu'en
quatre endroits : `=0` après `Balance::loop()` (`ino:87`), `=2` après `Head::loop()`
(`ino:115`), `=3` au toggle BOOT (`ino:132`), `=4` après la batterie (`ino:146`).
**Il n'y a aucun `s_lastPhase = 1;` dans le bloc UI.** Comme `Balance::loop()` tourne
toutes les 5 ms, la valeur vue après un blocage de `Ui::loop()` est **0 (balance)**.

**Conséquence.** `gph`/`lgph` ne peuvent **jamais** désigner l'UI — c'est-à-dire
précisément le coupable de l'enquête. Un écart causé par le tactile est étiqueté
« phase 0 = balance », soit la mauvaise attribution que cette instrumentation était
censée éliminer. `STALL_ANALYSIS.md` §2 documente une valeur (`1 ui`) que le firmware
ne peut pas produire. La conclusion de l'enquête n'est pas invalidée (elle a été tirée de
`uimax`/`touchmax`, pas de `gph`), mais l'outil reste faux pour la prochaine fois.

**Correctif précis.** `balance-bot.ino`, juste après la ligne 102 (`if (dt > …dbgUiMaxMs) …`) :
`s_lastPhase = 1;`

Accessoirement, même bloc : `s_prevLoopMs = g_state.dbgLoopMs` (`ino:163`) copie le **max
de la seconde en cours**, pas la durée du corps de l'itération courante ; `lglp` n'est donc
pas « la durée du corps de `loop()` à ce moment » comme l'annonce `STALL_ANALYSIS.md` §2.
Correctif : `s_prevLoopMs = (uint8_t)min(dt, 255UL);` avec le `dt` local.

---

### 3 — MOYEN — `ui.cpp:631-639` + `ui.cpp:726-733` — la **première image du mode AUTO** cumule la bande 0 et le dessin complet du visage : ≈ 21 ms, contre « 15 ms » annoncés

**Preuve.** Le bloc d'effacement en 4 bandes **ne sort pas de la fonction** : il
incrémente `s_clearStep` et l'exécution continue jusqu'au dessin. Or à l'entrée en AUTO,
`faceEnter()` met `s_drawnValid = false` et `s_lastDraw = 0`, donc la même image
déclenche `faceDraw()` (branche `structChanged`). Comptage pixel par pixel (script de
contrôle, expression CALME) :

```
bande 0 (320×54)        =  17 280 px
2 boîtes d'yeux         =  21 120 px
2 amandes               =  10 306 px
2 iris + 2 reflets      =   3 684 px
TOTAL 1re image AUTO    =  52 390 px  →  21,0 ms à 2,5 Mpx/s (débit mesuré cité dans ui.cpp:187)
```

Le commentaire `ui.cpp:628-630` affirme « une [bande] par image pour ne jamais dépasser le
budget de 15 ms » : le code ne fait pas ça.

**Conséquence.** Un trou de ~21 ms dans la boucle 200 Hz (≈ 4 itérations
d'asservissement perdues) **au moment exact de l'armement**, c'est-à-dire quand le robot
commence à équilibrer. Insuffisant pour déclencher le watchdog (`kMinLoopHz` = 120 Hz est
mesuré sur une seconde entière : 21 ms coûtent ~4 Hz), mais c'est le pire blocage
restant du chemin chaud, et il est invisible dans `drawmax` (seul `faceDraw()` est
chronométré, pas les bandes) — visible seulement dans `uimax`.

**Correctif précis.** `ui.cpp:638-639` : `s_clearStep++; return;` à l'intérieur du bloc.
Coût : le visage apparaît 4 images (64 ms) plus tard, et aucune image ne dépasse alors
~13 ms (`faceDraw` seul : 12,6 ms CALME, 12,9 ms SURPRISE — calculés).

---

### 4 — MOYEN — `ui.cpp:561` — `s_latchOff = 0` est placé **avant** les filtres : une trame poubelle empêche la levée du verrou

**Preuve.** Ordre d'exécution dans `readTouch()` :

```
553  if (!ok) { if (g_touchLatch && ++s_latchOff >= 2) {levée}; return; }
561  s_latchOff = 0;                      // ← « un doigt est présent »
568  if (g_touch->getPointNum() == 0) return;        // ← sort SANS incrémenter
576  if (p.x > WIDTH + 40 || p.y > HEIGHT + 40) return;  // trame (4095,4095) : idem
```

Une trame poubelle fait `read() == true` (`ModulesCSTSelf.tpp:74` : `return
raw_data[0x02] > 0`, et `0x02` vaut 0x0F dans une trame à 0xFF), donc elle **remet le
compteur de levée à zéro** puis sort sans l'incrémenter — elle compte comme « doigt
présent » pour le verrou tout en ne comptant pas comme appui pour l'UI. Le périphérique
émet bien ces trames spontanément : 3 sur 11 au banc (`tools/touch_log.json`), et c'est
ce qui ouvrait l'écran STOP tout seul avant le rejet.

**Conséquence.** La levée du verrou exige **2 trames consécutives** sans doigt. Une
trame poubelle intercalée une image sur deux remet le compteur à 0 indéfiniment →
`g_touchLatch` reste armé → **plus aucun tap en AUTO** (plus d'écran STOP, donc plus
d'arrêt au doigt ; il reste le bouton web et le BOOT). Non observé à ce jour — la cadence
mesurée des trames poubelles est bien plus basse —, mais l'ordre est faux et le mode de
défaillance est silencieux.

**Correctif précis.** Déplacer `s_latchOff = 0;` **après** les deux filtres (juste avant
`g_touchedRaw = true;`, ligne 597) et traiter les deux `return` des lignes 568/576 comme
« pas de doigt » :

```cpp
if (g_touch->getPointNum() == 0 || p.x > WIDTH + 40 || p.y > HEIGHT + 40) {
  if (g_touchLatch && ++s_latchOff >= 2) { g_touchLatch = false; s_latchOff = 0; }
  return;
}
```

---

### 5 — FAIBLE — `ui.cpp:610-615` — **code mort + commentaire faux** dans la consommation du verrou

**Preuve.** `g_touchedRaw` est mis à `true` ligne 597, sans retour intermédiaire. Donc
ligne 613, `!g_touchedRaw` est **toujours faux** : la branche
`if (!g_touchedRaw) g_touchLatch = false;  // relâché : on reprend` est **inatteignable**,
et son commentaire décrit une levée qui a en réalité lieu ligne 558.

**Conséquence.** Aucune aujourd'hui. Mais c'est exactement le piège qui a produit le bug
corrigé par 741ad5b : un lecteur qui croit que le relâchement est géré ici peut
« simplifier » la vraie levée (ligne 553-559). Le commentaire de 555-557 explique le
bug ; la ligne qui l'a causé est toujours là.

**Correctif précis.** `ui.cpp:612-615` →
```cpp
if (g_touchLatch) { g_touchedRaw = false; g_touchX = g_touchY = -1; }  // consommé jusqu'au relâchement (levée : l.558)
```

---

### 6 — FAIBLE — `ui.cpp:466-468` — les deux correctifs « batterie faible » et « IMU muette » du visage sont **inatteignables ou mal nommés**

**Preuve (batterie).** `faceCompute()` teste `g_state.batteryLow` → `FX_MEFIANT` rouge.
Or `balance.cpp:422-425` force `g_state.cmdEnabled = false` dès que `batteryLow` est vrai,
et `Balance::isEnabled()` renvoie ce drapeau (`balance.cpp:611`) : `Ui::loop()` quitte donc
le mode AUTO au cycle suivant (≤ 5 ms pour `Balance::loop()`, ≤ 16 ms pour l'UI).
La branche ne peut afficher **qu'une image au plus**. Et dans l'aperçu web — le cas que
FACE_REVIEW constat 14 visait explicitement (« l'aperçu web, lui, reste muet ») —
`faceCompute()` **n'est pas appelée du tout** (`ui.cpp:684-690` : la branche forcée
court-circuite le calcul). Le correctif ne couvre donc ni l'un ni l'autre cas.

**Preuve (IMU).** `Balance::imuOk()` renvoie `s_imuOk`, figé par `Imu::begin()` au boot
(`balance.cpp:374, 618`). La perte d'IMU **à chaud** est `s_imuLost` (`balance.cpp:473`) et
la mise en sécurité de cadence est `s_rateLow` (`balance.cpp:407`) : **aucune des deux n'a
d'accesseur**. Le commentaire `ui.cpp:466` « IMU muette » devrait dire « IMU absente au
boot ». Un robot dont l'IMU décroche en vol, ou dont la cadence s'effondre, garde un
visage normal — ce que constat 14 demandait de corriger.

**Correctif précis.** Ajouter `bool Balance::imuLost();` et `bool Balance::rateLow();`
(interfaces.h), les tester dans `faceCompute()` en tête de cascade, et rectifier le
commentaire. Pour la batterie : soit accepter qu'elle ne soit visible que sur l'écran
MANUEL (« BAT. FAIBLE », déjà en place et correct), soit appliquer la teinte rouge
**aussi** dans la branche forcée de `ui.cpp:684-688`.

---

### 7 — FAIBLE — `ui.cpp:293-297` (`faceStyle`) — `FX_PENCHE` : **1 px d'iris hors de l'amande** à |regard| = 18

**Preuve (script de contrôle, reproduction pixel-exacte de `fillPoly` + `lroundf`).**
Iris (disque ou fente) et reflet testés contre le polygone réellement peint, pour les
8 expressions, les 2 yeux et tous les regards atteignables (−18…+18) :

```
ok FX_CALME    ±1    ok FX_MEFIANT  ±1    ok FX_SURPRISE ±1    ok FX_CLIN  −1
ok FX_PENCHE   +1    FX_CHUTE / FX_CONTENT : pas d'iris (sortie anticipée) — ok
DÉBORDE FX_PENCHE œil droit (inn=−1), regard = −18 : 1 px hors amande → (189, 79)
```

Tous les autres couples (expression, œil, regard) sont **exacts** : iris **et** reflet
entièrement contenus. `gazeMax` par expression (18/6/6/10/18/10) fait donc bien son
travail sauf pour PENCHÉ, resté à la valeur par défaut 18.

**Conséquence.** `faceMoveIris()` efface l'ancien iris en orange : ce pixel reste
**orange sur le fond noir** jusqu'au prochain redessin complet. Atteignable uniquement
par `/api/face?state=1&sweep=1` : en fonctionnement réel, `FX_PENCHE` implique
|pitch| ≤ 8° (au-delà c'est `FX_ENERVE`, `ui.cpp:470`) donc |regard| ≤ 12, et il faut en
plus `18.0f*sinf(...)` exactement égal à −18.0f (pour `f.gaze ∈ (−18, −17]`, la troncature
donne −17, qui est propre).

**Correctif précis.** `ui.cpp:292` : `case FX_PENCHE: s.ang = 13.0f; s.h = 57; s.gazeMax = 16; break;`
(vérifié propre à ±16 par le script).

---

### 8 — FAIBLE — symétrie des yeux : **exacte pour les centres, ±1 px pour les pixels peints**

**Preuve.** `FACE_CX_L` = (320−118−1)/2 = **100**, `FACE_CX_R` = 319−100 = **219**,
(100+219)/2 = **159,5** : l'axe est exact. En revanche la comparaison des **pixels
réellement peints** (miroir x → 319−x) donne, pour les 8 expressions × {ouvert, clignant},
**1 à 24 pixels divergents, d'amplitude maximale 1 px** sur les bords de span. Cause :
`lroundf` arrondit *à l'opposé de zéro*, ce qui n'est pas une opération symétrique
(`lroundf(100.5) = 101` mais `lroundf(218.5) = 219`, alors que le miroir de 101 est 218).

**Conséquence.** Aucune visuellement (1 px sur un bord de 104 px). Mais la formule
« symétrie des yeux **exacte** (axe 159,5) » du message de commit 871811f est vraie des
centres, pas du rendu.

**Correctif** (seulement si l'exactitude est voulue) : calculer l'œil gauche, puis dériver
l'œil droit par `xs[i] = 319 - xsL[i]` au lieu de relancer `faceEyePoints` avec `inn = -1`.

---

### 9 — FAIBLE — `ui.cpp:105-113` + `ui.h:13-22` — `g_touchSeq` **ne compte pas les taps** quand le verrou est actif

**Preuve.** `g_touchSeq` s'incrémente sur `!wasTouched` (`ui.cpp:608`), où `wasTouched`
est le `g_touchedRaw` de l'image précédente. Mais la consommation du verrou
(`ui.cpp:614`) **remet `g_touchedRaw` à false** : tant que le verrou est armé et qu'un
doigt est posé, *chaque image* paraît être un front montant et `n` grimpe à ~60/s.

C'est exactement ce qu'on lit dans `tools/touch_log.json` : `n` passe de **8 à 21 en
0,27 s** (puis 46→58, 65→74). 13 fronts montants réels en 0,27 s sont **impossibles** —
`Ui::loop()` est cadencée à 16 ms (`ino:96`, valeur inchangée depuis l'origine du
fichier), soit 17 images maximum, donc ≤ 8 fronts. La seule explication compatible est
« +1 par image avec doigt », c'est-à-dire **verrou armé** — ce qui était le cas dans le
binaire de 871811f, où la levée était inatteignable (bug corrigé par 741ad5b).

*Note : ces sauts de `n` ne sont donc **pas** la preuve d'un doigt « clignotant » au
niveau du contrôleur — hypothèse examinée et écartée par ce calcul.*

**Conséquence.** `ui.h:16` et `ui.cpp:109-110` documentent `n` comme « compteur de
taps / fronts montants » ; c'est faux pendant les 32 ms de verrou, et la recette
d'acceptation de `TOUCH_REVIEW.md` §4.4 (« un tap → `n` +1 ») n'est pas utilisable telle
quelle juste après un changement de mode.

**Correctif précis.** Séparer l'état physique de l'état filtré : mémoriser
`s_downPhysical` (vrai dès qu'un point valide est lu, avant la consommation du verrou) et
compter les fronts sur lui, ou incrémenter `g_touchSeq` depuis une variable dédiée
inchangée par le verrou.

---

### 10 — FAIBLE — commentaires en décalage avec le code

* `tuner.cpp:223-225` : « le tampon de `handleState` fait **256 o** pour ~160 o déjà
  consommés » → il fait **384 o** pour **354 o** consommés dans la session réelle
  (constat 1). Le commentaire justifie l'endpoint séparé par une marge qui n'existe plus.
* `ui.cpp:861-863` : « Lecture conditionnée par la broche INT […] quand elle est active,
  on lit vraiment à 60 Hz » — décrit un comportement **désactivé par défaut**
  (`s_intGate = false`, `ui.cpp:122`). Placé juste au-dessus du `pinMode`, il se lit comme
  si la garde était en service.
* `ui.cpp:628-630` : budget de 15 ms annoncé, ~21 ms réels (constat 3).
* `ui.cpp:443-446` : « le regard est quantifié par pas de 2 px (une seule fois, à la
  source) » — `gazeQ` ne sert qu'à la **décision** (`sameFrame`, `ui.cpp:735`) ; la
  position dessinée utilise `(int)constrain(f.gaze, …)` non quantifiée
  (`ui.cpp:316, 357`). C'est FACE_REVIEW constat 15, resté ouvert. **Sans conséquence
  visuelle** : `s_irisL/R` mémorise la géométrie *réellement tracée*, donc
  `faceMoveIris()` efface toujours au bon endroit (vérifié).
* `ui.cpp:538` : `digitalRead(PIN_TOUCH_INT)` est exécuté à **chaque** image même quand
  `s_intGate` est faux, et même quand l'init tactile a échoué — auquel cas le `pinMode`
  de la ligne 864 n'a jamais été appliqué (il est dans la branche `else`). Sans effet
  fonctionnel (~1 µs), mais la broche est lue sans avoir été configurée.

---

### 11 — INFO (ouvert, pré-existant) — la levée du verrou repose sur 2 images, pas sur une durée : C5 peut la déclencher doigt posé

**Preuve.** `TouchLibCommon.tpp:218-238` : `readRegister(reg, buf, len)` renvoie `-1`
**sans toucher `buf`** si la transaction échoue, et `ModulesCSTSelf.tpp:73-76`
(`read()`) **ignore ce retour**. Une lecture ratée rejoue donc la trame précédente
(C5 de `TOUCH_REVIEW.md`, explicitement laissé ouvert). Symétriquement, si le contrôleur
cesse de rapporter pendant 2 images (32 ms) alors que le doigt est posé, `g_touchLatch`
se lève **doigt toujours en contact**.

**Conséquence précise, calculée.** Le bouton STOP occupe x 60..259, y 40..131
(`ui.cpp:198`) ; la zone 4 ÉQUILIBRE occupe x 208..307, y 66..161 (`ui.cpp:142`).
**Intersection : 52 × 66 px** (x 208..259, y 66..131), soit le quart droit du bouton
STOP. Un doigt posé là, si le verrou se lève avant le relâchement, **ré-arme le robot** —
exactement le scénario que FACE_REVIEW constat 2 et le verrou devaient supprimer. Ajouté
à C6 (ré-entrer dans une zone sans lever le doigt regénère un front montant), c'est le
point faible résiduel du chemin tactile.

**Correctif recommandé (ceinture).** Doubler le compteur d'images d'un verrou temporel,
insensible aux trames perdues :

```cpp
static unsigned long s_lockUntil = 0;                // à côté de g_touchLatch
// faceEnter()/faceLeave() : s_lockUntil = millis() + 300;
// readTouch(), juste avant « g_touchedRaw = true » :
if ((long)(millis() - s_lockUntil) < 0) { g_touchX = g_touchY = -1; return; }
```

Et, pour C5, un garde-fou « point strictement identique pendant > 2 s → on relâche »
(déjà proposé par `TOUCH_REVIEW.md` C5).

---

### 12 — INFO — le correctif `DisAutoSleep` n'est écrit **qu'une fois**, au boot

`ui.cpp:857-860` écrit `0xFE = 0x01` après le reset du CST816 par `TouchLib::init()` —
ordre correct, adresse correcte (`CTS820_SLAVE_ADDRESS` = 0x15, distincte du MPU6050 à
0x68), retour vérifié et journalisé. Mais ce registre est **volatile** : si le contrôleur
se réinitialise en cours de route (creux d'alimentation, reset de la nappe), l'auto-sleep
revient et les blocages de 1 s avec lui, sans rien pour le ré-armer.
`STALL_ANALYSIS.md` §7 dit déjà de surveiller `touchmax` ; une ré-écriture périodique
(p. ex. toutes les 10 s, ~80 µs) rendrait le correctif auto-réparant.

---

## Points vérifiés et jugés **corrects**

**Le tactile peut toujours détecter un tap** (question 5 du brief, par analyse de code) —
chaîne vérifiée pas à pas :

1. **Garde INT** : `s_intGate = false` par défaut (`ui.cpp:122`), la branche
   `ui.cpp:539-543` est donc entièrement court-circuitée. Aucun effet sur le chemin normal.
2. **Rejet des trames poubelles** : le seuil est `WIDTH+40` / `HEIGHT+40` = 360/210. Les
   11 points réels du banc (x ∈ 15..315, y ∈ 19..156) passent tous ; seules les trames
   0xFFF (4095) sont jetées. Aucun risque de rejeter un vrai tap, même en bord de verre.
3. **Miroir X** : rejoué sur les données du banc — brut 303 → `constrain` → 303 →
   319−303 = **16** ; brut 19 → **300** ; brut 315 → **4** ; brut 18 → **301**. Conforme
   aux quatre coins enregistrés. Le bornage est bien **avant** le miroir, donc une valeur
   aberrante reste dans le gabarit après réflexion.
4. **Levée du verrou** : elle a lieu dans la branche `!ok` (`ui.cpp:553-559`), atteinte
   dès que le doigt est levé (`read()` renvoie `raw_data[0x02] > 0`) → verrou levé après
   2 images = **32 ms**. C'est bien le correctif de 741ad5b, et il fonctionne (le bug de
   871811f — sortie avant la levée, verrou armé à vie — est réellement éliminé).
5. **`s_latchOff` n'est jamais « sale »** au moment où le verrou est armé : il est remis à
   0 à chaque levée et à chaque image avec doigt, et le `&&` court-circuite son
   incrémentation quand le verrou est baissé. Vérifié sur tous les chemins.
6. **`s_prevTouch` n'avale pas le premier tap** après un retour en AUTO : il n'est pas
   réinitialisé par `faceEnter()`, mais le verrou force `g_touchedRaw = false` à la
   première image, ce qui remet `s_prevTouch` à false **avant** que le verrou ne se lève.
   L'ordre est sûr (fragile, mais correct).

**Les deux verrous ne se contredisent pas.** `faceEnter()` et `faceLeave()` arment le même
drapeau, levé en un seul endroit. Aucun état « armé à vie » atteignable hors du cas du
constat 4.

**Aucun drapeau ne reste armé à la sortie du mode AUTO** : `faceEnter()` remet
`s_stopShown`, `s_stopStep`, `s_drawnValid`, `s_lastDraw`, `s_clearStep`, `s_irisL/R` et
purge `cmdForward`/`cmdTurn` (FACE_REVIEW constat 12, correctement traité y compris pour
le chemin web). `faceLeave()` + `resetManualCaches()` remettent les 11 caches du rendu
MANUEL ; croisé avec ce que `drawStatic()` écrit réellement, chaque cache est soit
réécrit, soit cohérent avec la valeur dessinée (`g_lastPitch = 0` ↔ « 0.0 deg »,
`g_lastBat = 0` ↔ « 0.00 V », `g_lastObs = -1` ↔ « -- », `g_lastArmed` réécrit par
`drawButton(4)` appelé depuis `drawStatic()`).

**Couverture de l'effacement d'écran à l'entrée en AUTO : complète, sans trou ni
recouvrement inutile** (vérifié par le calcul) — bandes 0 (y 0..53), 1 (y 142..169),
2 (x 0..40, y 54..141), 3 (x 279..319, y 54..141), plus les deux boîtes d'yeux
(x 40..159 et 159..278, y 54..141). Les trois labels MANUEL qui survivent aux bandes
(« B:… U:… H:… » x 6..155, « PIED » x 166..202, « P:+0 deg » x 206..281 — tous à y 54..62)
tombent dans les boîtes d'yeux, sauf x 279..281 couverts par la bande 3. Aucun résidu.

**Boîte d'effacement des yeux (120 × 88 à `cx−60, 54`) : suffisante pour les 16 cas**
(8 expressions × {ouvert, clignant}), enveloppes réelles calculées : Δx ∈ [−52, +52]
(boîte [−60, +59]), Δy ∈ [−23, +54] (boîte [−30, +57]). Le correctif du constat 6 de
FACE_REVIEW est donc bien dimensionné, y compris pour SURPRISE (Δy max = +54) et CLIN
(+51) qui étaient les cas coupés par l'ancienne boîte. Le X de `FX_CHUTE` (±18, ±17) et la
barre du clin d'œil (x `cx−34..cx+33`, y 82..85) tiennent aussi.

**`fillPoly`** : la borne `y <= ymax` est inclusive (constat 18 de FACE_REVIEW corrigé) ;
le garde-fou `if (cnt & 1) continue` ajouté par bf5e949 est **inoffensif et inatteignable**
avec la géométrie actuelle (la règle `(yi > y) != (yj > y)` donne toujours un nombre pair
d'intersections ; il ne protège que d'une future troncature par `cnt < 8`, ce qui est
précisément son rôle). Les sommets dupliqués en `t = ±1` (points 0/33 et 16/17) ne
produisent pas d'intersection parasite (`yi == yj`). `kEyePts = 34 ≤ 40` garanti par
`static_assert`.

**Cohérence `faceIrisGeom()` ↔ `faceDrawEye()`** : mêmes troncatures (`(int)(h*0.72)`,
`(int)(hb*0.52)`), mêmes sorties anticipées (clignement, CHUTE, CONTENT, œil gauche du
CLIN), même `gazeMax`. `out->w` n'est écrit que dans la branche `slit` — mais
`faceMoveIris` ne lit `oldG.w` que si `oldG.slit`, et les deux sont écrits ensemble.
Aucun désalignement possible entre l'iris effacé et l'iris dessiné.

**Courses entre cœurs** : les champs de l'aperçu web (`s_faceForced`, `s_forcedExpr`,
`s_forcedUntil`, `s_forcedSweep`) sont `volatile` et `s_faceForced` est publié en dernier
(FACE_REVIEW constat 11 correctement traité). `Ui::previewFace` borne la durée à 60 s
(constat 9). Les `dbg*` de `g_state` sont des scalaires ≤ 32 bits écrits par le cœur 1 et
lus par le cœur 0 : pas de déchirure possible sur ESP32-S3, et une valeur d'une
milliseconde de retard est sans conséquence pour de la télémétrie. `s_touchSkip` /
`s_intGate` sont écrits depuis le cœur 0 sans `volatile` — acceptable ici (lus dans une
fonction non inlinable, pas de cache de données sur la SRAM interne), mais ce sont les
deux seules écritures inter-cœurs non qualifiées du lot.

**Chemins d'origine non cassés** : écran MANUEL (télémétrie, libellés et largeurs
revérifiés : tous les `updateLabel` tiennent dans l'écran, aucun chevauchement), bouton
ÉQUILIBRE (reflète `Balance::isEnabled()` et non `g_state.balancing`), flèches
(`dirHeld` = « une zone directionnelle est sous le doigt », retour au neutre préservé),
bandeau obstacle, voyant WEB, watchdog de cadence, refus d'armer sur batterie faible,
gains NVS, `/api/gains` (`argOrNan` : NaN ⇒ gain inchangé), `/api/bal`, appui long BOOT.
`Tuner::loop()` est resté un no-op volontaire, non appelé par le `.ino` — cohérent avec
le commentaire.

**`/api/touch`** : tampon 192 o pour 113 o au pire cas calculé — confortable.
**`/api/face`** : `state` négatif → `(uint8_t)` puis `constrain(…, 0, 7)` ; `t` négatif →
conversion non signée puis plafond 60 s. Les deux entrées sont sûres.

**Écran STOP** : dessin en 2 images (≈ 8,4 ms puis ≈ 8 ms, calculés) puis barre seule
(200 × 4 = 800 px, 0,3 ms toutes les 200 ms) — le constat 3 de FACE_REVIEW est bien
résolu, et le tap sur STOP ne peut pas être confondu avec celui qui a ouvert l'écran
(front montant requis).

---

## Verdict

### **Flashable en l'état** — avec une réserve de confort, pas de sécurité.

Aucun constat n'ouvre un chemin vers un armement accidentel, une perte de contrôle de
l'asservissement ou un blocage du bus I²C. Les trois correctifs de la nuit font ce qu'ils
annoncent : le miroir X est conforme aux mesures des 4 coins, la levée du verrou est
réellement effective (le bug de 871811f est éliminé), et `DisAutoSleep` est écrit au bon
registre, à la bonne adresse, au bon moment. La compilation est propre (aucun
avertissement imputable au firmware).

Les trois choses à corriger **avant la prochaine session de mesure**, parce qu'elles
dégradent l'outil de diagnostic ou le chemin chaud et se corrigent en une ligne chacune :

1. **constat 1** — `char buf[512]` dans `handleState` : sinon la page du banc peut
   s'afficher « hors ligne » de façon permanente et inexplicable, avec 30 o de marge
   seulement dans la configuration déjà mesurée.
2. **constat 2** — `s_lastPhase = 1;` dans le bloc UI : sans lui, `gph` accusera toujours
   la boucle d'équilibre d'un blocage venu de l'UI.
3. **constat 3** — `return` après l'incrément de `s_clearStep` : supprime le seul trou de
   ~21 ms restant dans la boucle 200 Hz, et il tombe pile à l'armement.

Puis, au prochain passage : constats 4 (ordre de `s_latchOff`), 5 (code mort du verrou),
6 (branches batterie/IMU du visage), 7 (`gazeMax` de PENCHÉ) et 11 (verrou temporel).

---

### Méthode de cette revue

* Lecture intégrale de `ui.cpp` (1085 l.), `balance-bot.ino`, `tuner.cpp`, `balance.cpp`,
  `interfaces.h`, `ui.h`, `config.h` ; `STALL_ANALYSIS.md`, `FACE_REVIEW.md` (20 constats),
  `TOUCH_REVIEW.md` (8 constats) ; `tools/touch_check.py`, `tools/touch_log.json` ;
  sources `TouchLib` (`ModulesCSTSelf.tpp`, `TouchLibCommon.tpp`, `CSTSelfConstants.h`).
* Script de contrôle géométrique (`lroundf`, `fillPoly` et `faceEyePoints` reproduits à
  l'identique en Python) : symétrie miroir, contenance iris+reflet, enveloppes, boîtes
  d'effacement, coûts en pixels. Conservé dans `/tmp/bbcheck/geom.py`.
* Calcul des longueurs `snprintf` des deux endpoints JSON sur trois jeux de valeurs.
* Compilation complète `--warnings all` avec les flags de `build.sh`, dans un
  `--build-path` neuf. **Aucun flash, aucun `upload`, aucun commit, aucune modification
  de fichier hors ce rapport.**
