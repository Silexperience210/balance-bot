# chassis/review — audit & vérification du châssis ₿ BalanceBot v3.1

Outils d'analyse **mesurée** des STL (aucune confiance dans le générateur : on sonde les maillages).
Tous les scripts tournent avec le venv DfAM (`trimesh` + `scipy`) :

```bash
~/.hermes/venvs/dfam/bin/python chassis/review/<script>.py
```

| Fichier | Rôle |
|---|---|
| `RAPPORT_IMPRESSION_v31.md` | Revue d'impression complète (cotes, surplombs, anomalies, optimisations) — état AVANT corrections |
| `audit.py` | Audit topologique : bbox, volume, composantes, boucles ouvertes, non-manifold, surplombs par orientation d'impression |
| `verif_ultime.py` | Vérification des maillages : arêtes libres, non-manifold, cotes, volumes, paliers, avant-trous M3, goujons, yeux, fenêtre, bras de roue, pneu. Code de sortie 1 si un point échoue. |
| `chaine_roue.py` | Chaîne servo → moyeu → roue mesurée sur les STL (épaulement, capot, semelle, empreinte, allègement) contre `cotes.py`. |
| `servo_fit.py` | Intersection booléenne EXACTE servo × coques (Blender). `--hump` ajoute le capot oblong. |
| `test_ouverture.py` | Vérifie que les coques sont bien OUVERTES au joint (design CREUX) et non scellées par une peau |
| `faces.py` | Surplombs réels dans l'orientation d'impression : liste les plafonds plats par altitude (ponts vs support) |
| `find_transform.py` | Retrouve la transformation plaque↔pièce par alignement de sommets (sert à valider `chassis/make_plates.py`) |
| `diag_roue.py` | Diagnostic roue : sections, moyeu, jante, gorge de pneu |
| `mesures_baseline.json` | Mesures de référence du 09/09 (avant corrections) — sert de témoin de non-régression |

## Chaîne complète après un changement de châssis

```bash
blender --background --python chassis/gen_bitcoin_bot.py
python3 chassis/make_plates.py
python3 chassis/review/chaine_roue.py
python3 chassis/review/verif_ultime.py
blender --background --python chassis/review/servo_fit.py -- chassis/v3
blender --background --python chassis/review/servo_fit.py --hump -- chassis/v3
```

La CI (`.github/workflows/verifier.yml`) lance `cotes.py`, `chaine_roue.py` et
`verif_ultime.py`. Elle ne lance pas Blender.

## Repères historiques (09/09/2026, roue encore pleine)

Les volumes ci-dessous ne sont plus ceux des STL courants. Lancer
`chaine_roue.py` pour les chiffres du jour.

- b_front 132,13 × 23,02 × 201,00 — 105,8 cm³ (134 g PETG) — watertight, 5 composantes (1 coque + 4 vides d'avant-trous M3)
- b_back 132,13 × 29,00 × 201,00 — 91,5 cm³ (116 g PETG) — watertight, 1 composante
- coin_wheel Ø80 × 21 — 42,6 cm³ (54 g) · coin_tire Ø83 × 7 — 4,4 cm³ (5,6 g TPU)
- Surplombs réels : 6,7 k mm² (front, dont 5,8 k = fond des creux ₿), 1,05 k (back), 0,59 k (roue), 0 (pneu) → **zéro support**
- Réglages : coques 0,28 mm / roue 0,20 / pneu 0,24 · brim 5 mm · lit 70-80 °C · ponts 0,9 / 25 mm/s

## Pièges déjà payés (ne pas les réintroduire)

- **Outil de perçage coplanaire à une face** → voile/bouchon d'épaisseur nulle. Tout alésage doit DÉPASSER
  la face de sortie de 2 mm (c'est ce qui bouchait le palier gauche).
- **Composante reliée seulement par un sommet** = déchet, pas du solide : purger par connectivité d'ARÊTES.
- **Vide interne légitime** (avant-trou borgne) = composante fermée séparée : ce n'est PAS une pièce flottante.
- **Plaques de slicing périmées** : `make_plates.py` après chaque régénération, sinon on slice l'ancien design.
- **Sonder sur l'axe d'un palier donne un vide** (c'est normal) : sonder dans la paroi du tube (y = ±12,8).
