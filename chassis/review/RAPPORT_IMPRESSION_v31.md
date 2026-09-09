# ₿ BalanceBot v3.1 — REVUE IMPRESSION 3D (audit mesuré)

> **SUITE APPLIQUÉE le 09/09/2026** (commits `eda934a` + `fe0570b`) — voir `NOTES_v3.md`, section
> « Révision du 09/09/2026 ». Résumé : alésages de palier débouchants (le tube gauche était bouché
> dans les STL committés → roue non montable), purge des voiles d'épaisseur nulle, bouchage du
> micro-trou 6,4 mm, plaques `export/v31` régénérées, `chassis/make_plates.py` ajouté.
> **Vérification finale : `chassis/review/verif_ultime.py` → 25/25** (0 arête libre, 0 non-manifold,
> watertight sur les 4 pièces, cotes et fonctions conformes).
> Les points de la section 5 (COUNTER 1,6 mm, interférence pneu, masse des roues) restent des choix
> de conception non tranchés — les réglages de slicing sont dans `NOTES_v3.md`.

Date : 09/09/2026 · Pièces auditées : `chassis/v3/*.stl` (état courant, 08/09 22:11-22:16)
Méthode : trimesh 5.1.0 + `dfam_tool.py` (45°) + `verify_stl.py` (bords libres, composantes, watertight) — mesures sur les STL, pas sur le générateur.

## 1. Fiche pièces (mesuré)

| Pièce | BBox (mm) | Volume | Masse 100 % PETG | Watertight | Composantes | Bords libres | Non-manifold |
|---|---|---|---|---|---|---|---|
| b_front | 132,1 × 23,0 × 201,0 | 109,0 cm³ | 138 g | non (ouvert au joint) | 4 | 164 | 39 |
| b_back | 132,1 × 34,9 × 201,0 | 94,9 cm³ | 121 g | non (ouvert au joint) | 3 | 157 | 102 |
| coin_wheel ×2 | 80 × 80 × 21 | 42,6 cm³ | 54 g | oui | 1 | 0 | 1927 |
| coin_tire ×2 | 83 × 83 × 7 | 4,4 cm³ | 5,6 g (TPU) | oui | 1 | 0 | 585 |

Total ≈ **378 g** (367 g PETG + 11 g TPU), temps estimé ≈ 10 h au profil actuel.

## 2. Ce qui est déjà bon

- **Orientation d'impression correcte** : face externe sur le plateau. Contact plateau : front 10 060 mm², back 17 093 mm², roue 4 244 mm² → adhérence large, aucun besoin de radeau.
- **Parois saines** : médiane 2,4 mm (= `WALL`), p05 1,6 mm (front), 2,4 mm (back). Aucune paroi sous 1,2 mm. Le `min_mm 0,129` du rapport DfAM est un échantillon parasite (piège connu).
- **Surplombs réels faibles** (faces descendantes HORS contact plateau) :
  - b_front : 5 831 mm² à 1,6 mm (creux COUNTER ₿), 593 mm² à 1,2 mm, 285 mm² à 13,5 mm → **~6,7 k mm²**
  - b_back : 702 mm² à 1,2 mm, 285 mm² à 13,5 mm → **~1,05 k mm²**
  - coin_wheel : 277 mm² à 0,8 mm + 314 mm² à 1,0 mm → **~590 mm²** (creux ₿ gravé)
  - coin_tire : **0**
- **Pneus** : 2,5 mm d'épaisseur constante, aucun surplomb, watertight.
- Roues/pneus des `export/v31/` sont **identiques** aux STL courants (4 474 / 1 024 triangles, mêmes volumes).

## 3. Anomalies de maillage (fiabilité slicer)

1. **Disque à épaisseur nulle dans l'alésage de palier GAUCHE** à x = −1,5 : Ø24,5, séparé en deux moitiés par le plan de joint (68 triangles dans le front + 68 dans le back), **non connecté à la coque**. Le moyeu Ø24×13 doit coulisser dans ce tube (12 mm) : ce voile réduit la profondeur utile à ~10,5 mm. Slicer = soit supprimé, soit imprimé sur 1 couche.
2. **Front** : 2 triangles isolés de 1,2 × 0,3 mm (slivers) à x = −1,5, z ≈ 30 → non-manifold.
3. **Back** : voile carré 3,4 × 3,4 mm au plan de joint (x ≈ 108, z ≈ 145), flottant (62 triangles).
4. **Micro-trou front** : boucle de 6,4 mm de périmètre (0,6 × 2,4 × 0,55 mm) à (45,5–46,1 ; 19,0–21,4 ; 138,6–139,1) → défaut booléen sous-millimétrique dans la paroi.
5. **Non-manifold** : 39 (front), 102 (back), 1 927 (roue), 585 (pneu). Les roues/pneus sont pourtant watertight (euler 0) : ce sont des sommets non soudés + triangles coplanaires du ₿ gravé → à nettoyer (`remove_doubles` + `dissolve_degenerate` + suppression des faces dupliquées + `recalc_face_normals`).

## 4. ⚠️ Incohérence de dépôt : les plaques `export/v31/` sont périmées

| Fichier | Triangles | Profondeur | Watertight | État |
|---|---|---|---|---|
| `chassis/v3/b_front.stl` (22:16) | 7 598 | 23,0 | non (OUVERT) | courant |
| `export/v31/plate1_b_front.stl` (14:44) | 8 298 | 23,0 | **oui (peau)** | **ancien** |
| `chassis/v3/b_back.stl` (22:11) | 8 207 | 34,9 | non (OUVERT) | courant |
| `export/v31/plate2_b_back.stl` (14:44) | 8 886 | **29,0** | non | **ancien** |

Le générateur a la peau sacrificielle **désactivée** (commentée, 08/09 soir) : version CREUSE validée par l'utilisateur. Les plaques du dossier `export/v31/` datent d'avant (version FERMÉE, peau 0,6 au joint, et profondeur de back différente). **Slicer ces plaques imprimerait l'ancien design.** À régénérer.

## 5. Optimisations proposées (par gain)

**A. Temps d'impression (−30 % ≈ −1 h 30 sur les 2 coques)**
- Hauteur de couche **0,28 mm** pour b_front/b_back (grandes surfaces plates, 2,4 mm de parois = 6 périmètres ; PETG OK jusqu'à 75 % du Ø buse). Garder 0,20 pour la roue (gravure ₿) et 0,24 pour le pneu.
- `brim` 5 mm + lit 70–80 °C + 1re couche 0,24 (pièce de 201 mm en PETG : gauchissement).

**B. Ponts / creux ₿ (le seul vrai surplomb)**
- 5 831 mm² de plafond plat à 1,6 mm (creux COUNTER du front) : soit garder et régler les ponts (débit 0,9 ; 25 mm/s ; ventilateur 100 %), soit **donner un dépouille 45° aux parois du creux** → le plafond plat disparaît, plus rien à ponter. Même correctif pour la roue (590 mm²).
- Les 285 mm² à 13,5 mm (identiques sur les 2 coques : lèvres de fenêtre / rails PCB) : chanfrein 45° sous la face ou vérification visuelle après première couche.

**C. Masse (optionnel — attention à l'inertie des roues)**
- Roues : 54 g pleines chacune. 4 périmètres + 20 % gyroid ≈ 30–32 g → −45 g au total, mais **l'inertie des roues participe à l'équilibrage** : à valider en simulation avant de trancher.
- Coques : ne pas descendre sous 2,4 mm de paroi (c'est la rigidité du châssis).

**D. Assemblage / tolérances**
- Pilote M3 autotaraudeuse : Ø2,6 → **Ø2,5** + chanfrein 0,5 mm en entrée (morsure PETG).
- Bande TPU : interférence 0,9 mm → **0,5–0,6 mm** (montage à la main sans étirer à outrance).
- Goujons Ø5,8 / alésages Ø6,0 : OK (0,2 de jeu).

**E. Nettoyage maillage** (avant export, dans le générateur)
- Supprimer le voile de palier gauche (le bore doit traverser jusqu'à x = −12,5), le voile carré du back et les slivers.
- `remove_doubles` + `dissolve_degenerate` + dédoublonnage des faces + `recalc_face_normals` avant export → non-manifold à 0.

**F. Documentation**
- `chassis/NOTES_v3.md` annonce encore « coques FERMÉES pour le slicer » alors que l'état validé est CREUX → à corriger (et la note équivalente du skill `balance-bot`).

## 6. Répartition des plaques (inchangée)
plate1 = b_front (201 × 132 au sol, h 23) · plate2 = b_back (h 34,9) · plateR = 2 roues · plateT = 2 pneus TPU.
Le CLI headless refuse les coques > 195 mm (dimension 201) → **slicer en GUI Bambu Studio** (déjà la pratique).
