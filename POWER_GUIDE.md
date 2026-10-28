# BalanceBot — Alimentation des servos

**Les servos ne tirent jamais sur le 3V3 ou le 5V de la carte.**
Un SG90 en mouvement ou en blocage tire 200 à 700 mA, pic vers 1 A. Le
régulateur USB de la carte s'effondre, brownout, reboot. Déjà observé au
test du 06/09. Rail séparé, masse commune avec la carte.

Le robot imprimé a **deux** servos de roues, 9 g, rotation continue
(FS90R ou équivalent, boîtier 22,8 × 12,2 × 22,5). Le firmware a aussi
deux broches de tête (`GPIO 3` et `GPIO 10`) : le châssis v3 n'a pas la
mécanique pan/tilt (`ROADMAP` 4.4). Tant que la tête n'est pas montée,
le rail n'alimente que les deux roues.

Un continu au neutre 1500 µs peut ramper si le trim (`kTrimUsL` /
`kTrimUsR` dans `feet.cpp`) n'est pas fait. Le détachement du PWM
(chute, perte d'IMU, cadence basse, BOOT long) met les broches à 0. Il
ne coupe pas ce rail : un interrupteur sur le 5 V reste utile
(`ROADMAP` 5.2).

## Consommation

- 2 servos de roues, équilibre, mouvement presque continu : 100–400 mA
- 2 servos de tête, seulement si la mécanique existe : +100–200 mA
- Crête : prévoir un rail 5 V capable de 2 A dès que les quatre sont là

Les chiffres sont des ordres de grandeur de SG90, pas une mesure sur
ce robot.

## Options (de la plus simple à la plus propre)

### Option A — Power bank USB (test immédiat, 0 € si tu en as un)
```
Power bank 5V ──┬── servo roue G (rouge) ──┐
                ├── servo roue D (rouge) ──┤  + tête seulement si montée
                └── servo tête (rouge) ────┘
Toutes les MASSE (marron) ──┐
                            ├──→ GND de la carte (INDISPENSABLE)
                            └──→ GND du power bank (via la prise)
Signaux (orange) ──→ GPIO 1/2/3/10 de la carte (aucun courant)
```
⚠️ Power banks qui se coupent à faible charge : si les servos tirent peu
(robot immobile), certains power banks se mettent en veille après ~30 s.
Solution : garder un petit mouvement continu OU utiliser l'option B/C.

### Option B — 4× piles AA (1,5V ×4 = 6V) ou 1× pile 9V + régulateur
- 4× AA alcalines : 6V nominal — dans la plage SG90 (4,8-6V), OK sans
  régulateur, ~1,5-2 A dispo. Simple et sûr. À jeter/charger ensuite.
- 1× pile 9V + module buck MP1584/XL4015 réglé à 5,0V : plus propre,
  ~0,5 A utile seulement (les piles 9V n'aiment pas les forts courants).

### Option C — Module buck 5V/3A + alim secteur (la meilleure pour les tests)
```
Chargeur USB-C 5V/2A+ ou alim 7-12V
   → module buck réglé à 5,0-5,5V (MP1584 ~2 €, XL4015 ~4 €)
   → rail servos (+ condos 470-1000 µF sur le rail, près des servos)
```
Les condos encaissent les pics de courant des servos (le module buck seul
peut avoir un temps de réponse trop lent).

### Option D — Batterie LiPo 2S (7,4V) + BEC 5V/3A (pour le robot autonome)
C'est l'option « produit fini » : le robot sans fil. La carte accepte la
batterie sur son connecteur (PIN_BAT_VOLT GPIO4 = mesure), les servos sur
le BEC. À faire APRÈS les tests USB.

## Câblage type (4 servos + carte)
```
[Alim 5V rail] ──────┬─────┬─────┬─────┐
                     R     R     R     R      (rouges servos 1,2,3,10)
[GND commun] ────────┬─────┬─────┬─────┬──── GND carte
                     N     N     N     N      (marron servos)
Signaux : S1→GPIO1  S2→GPIO2  S3→GPIO3  S10→GPIO10
+ 470-1000 µF entre rail 5V et GND, AU PLUS PRÈS des servos
```

## Checklist avant d'armer l'équilibre
- [ ] Masse commune carte ↔ alim servos (sans ça : comportements fous)
- [ ] Jamais de fil rouge servo sur le 3V3 ou le 5V de la carte
- [ ] Carte alimentée (USB ou LiPo 1S sur son connecteur) — les deux masses reliées
- [ ] Trim du neutre : roues immobiles, consigne nulle, sans ramper
- [ ] Démo (flèches, équilibre OFF) : les roues tournent sans reboot
- [ ] Si reboot : rail servos insuffisant → option C (buck + condensateurs)
- [ ] Le palonnier et le capot ont été comparés à `docs/MONTAGE.md`
