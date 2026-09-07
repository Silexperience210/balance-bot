# BalanceBot — Guide d'alimentation des servos (LOT 3)

**Règle d'or : les servos ne tirent JAMAIS sur le 3V3 ou le 5V de la carte.**
Un SG90 en mouvement/blocage tire 200-700 mA (pic ~1 A). Le régulateur USB
de la carte s'effondre → brownout → reboot (déjà observé au test du 06/09).
Les servos ont leur PROPRE rail d'alim, avec la MASSE commune à la carte.

## Consommation réelle
- 2 servos de pieds (équilibre, mouvement quasi continu) : 100-400 mA
- + 2 servos de tête (balayage démo) : +100-200 mA
- Total : ~0,5-1 A en crête → rail 5V/2A+ recommandé

## Options (de la plus simple à la plus propre)

### Option A — Power bank USB (test immédiat, 0 € si tu en as un)
```
Power bank 5V ──┬── servo pied G (rouge) ──┐
                ├── servo pied D (rouge) ──┤  2-3 servos max
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
- [ ] Jamais de fil rouge sur 3V3
- [ ] Carte alimentée en USB (données + 5V logique) — les 2 masses reliées
- [ ] Test : activer la démo (flèches) → les pieds bougent SANS reboot
- [ ] Si reboot : alim servos insuffisante → Option C (buck + condos)
