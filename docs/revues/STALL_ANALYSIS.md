# BalanceBot — enquête « cadence » : chutes de `hz` en mode équilibre

**Statut : RÉSOLU le 09/09/2026.** Cause racine identifiée par mesure, correctif
flashé, validé sur 180 s : **0 chute** (contre 21 en 60 s avant).

---

## 1. Symptôme

`g_state.balanceHz` (nombre d'itérations de `Balance::loop()` par seconde)
s'effondrait par intermittence : **1, 2, 49, 53, 67, 70, 75, 80, 97, 98 Hz**
au lieu de ~199. Le watchdog de cadence coupe l'asservissement sous
**120 Hz** (`balance.cpp`, `kMinLoopHz`) : en équilibre réel, ces chutes
auraient fait tomber le robot.

Caractéristiques relevées :
- uptime **monotone** → pas un redémarrage ;
- reproduit **avec ET sans** le visage animé (test contrôle) ;
- reproduit **avec et sans client HTTP** sur le banc web (8 chutes/60 s sans
  aucun client, 6/60 s avec) → ce n'est pas le polling qui les provoque.

## 2. Instrumentation mise en place (`g_state`, exposée par `/api/state`)

| champ | sens |
|---|---|
| `gap` / `gph` | plus grand écart entre deux départs de `loop()` dans la seconde + **phase exécutée juste avant** (0 balance, 1 ui, 2 head, 3 boot, 4 batterie, 5 aucune) |
| `worst` | plus grand écart depuis le boot |
| `big` / `lgap` / `lgph` / `lglp` | nombre d'écarts > 100 ms et signature du dernier (durée, phase, durée du corps de `loop()` à ce moment) |
| `loop`, `bal`, `ui`, `head`, `bat` | pires durées par seconde, par phase |
| `balmax`, `uimax`, `headmax`, `batmax`, `loopmax` | **max cumulatifs** (jamais remis à zéro) |
| `touchmax`, `drawmax` | pires durées internes à `Ui::loop()` : transaction I²C du CST816 vs blocs de dessin |
| `stalls` | nombre de secondes où `hz < 120` (hors 0) |

Deux leçons d'instrumentation :
1. **Les max par seconde effaçaient la preuve** : la remise à zéro tombait
   pendant la seconde de la chute. D'où les max cumulatifs.
2. **Un compteur par phase désigne le coupable** ; `gap` seul ne suffit pas.

## 3. Ce que les mesures ont montré

- Pendant une chute : `loop` = 11 ms, `bal` = 0 ms, `head` = 0 ms → **le corps
  de `loop()` n'est pas lent**.
- Max cumulatifs : `uimax` = **1002 ms**, `balmax` = 1 ms, `headmax` = 9 ms.
  → tout le temps perdu est dans **`Ui::loop()`**.
- Puis `touchmax` = **1001 ms**, `drawmax` = 0 ms → tout est dans
  **`g_touch->read()`**, la transaction I²C vers le CST816.

### Preuve de causalité (A/B à chaud)

`GET /api/touch?skip=1` coupe la lecture I²C du tactile sans reflasher :

```
avec lecture tactile : 21 chutes / 60 s
sans lecture tactile :  0 chute  / 60 s
```

## 4. Cause racine

Le **CST816 se met en veille** (auto-sleep). Une lecture qui tombe pendant son
cycle de réveil **tient le bus I²C ~1000 ms** : le driver ESP-IDF attend
l'esclave et **le `Wire.setTimeOut(2)` du firmware n'est pas respecté par cette
attente interne**. Comme le tactile et le MPU6050 partagent le même bus, la
boucle d'équilibre est gelée pendant ce temps (~1 lecture sur 60 tombait dans
cette fenêtre).

## 5. Correctif

Désactiver l'auto-sleep du CST816 à l'initialisation (`ui.cpp`, `Ui::begin()`) :

```cpp
Wire.beginTransmission(CTS820_SLAVE_ADDRESS);
Wire.write((uint8_t)0xFE);   // DisAutoSleep
Wire.write((uint8_t)0x01);
Wire.endTransmission();
```

Mesure après correctif (180 s sans client, puis 60 s) : **0 chute, 0 écart
> 100 ms**, `touchmax` = 0 ms, `hz` = 199, pire corps de `loop()` = 13 ms.

## 6. Protections complémentaires ajoutées

- **Rejet des trames poubelles** : le CST816 émet `(4095, 4095)` = 0xFFF
  (3 trames sur 11 au banc) ; sans filtre, chaque trame fantôme passait pour un
  appui et ouvrait l'écran STOP en mode AUTO.
- **Suppression de tout `Serial.printf` dans le chemin chaud** (lecture
  tactile) : une écriture USB-CDC bloque quand l'hôte ne draine pas le port.
- **Garde INT** optionnelle (`GET /api/touch?int=1`, désactivée par défaut) :
  ne lire le contrôleur que si la broche INT est active. Non nécessaire depuis
  le correctif, conservée comme outil de diagnostic.

## 7. Reste à surveiller

- `stalls` et `worst` dans `/api/state` : doivent rester à 0 en fonctionnement
  normal. Toute réapparition de `touchmax > 100 ms` signale un retour du
  problème (ou un autre esclave qui tient le bus).
- Le MPU6050 est sur le **même bus** : une micro-coupure de ses fils volants
  se manifesterait de la même façon (chute de `hz`), mais dans `balmax` cette
  fois — la distinction entre les deux est immédiate avec ces compteurs.
