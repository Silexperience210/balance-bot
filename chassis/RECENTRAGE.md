# Recentrage des roues — appliqué

Le milieu des peaux n'est pas le centre du glyphe. C'est mesuré sur la
géométrie de `chassis/cotes.py`, pas au pied à coulisse. Les peaux n'ont
pas bougé. On a déplacé les tubes.

| | mm |
|---|---|
| Peau du spine, avant miroir | 0 |
| Peau de la panse à hauteur d'axe | 106,87 |
| Milieu des peaux | 53,44 |
| Centre du glyphe (`GW / 2`) | 59,00 |
| Écart des peaux | −5,56 vers le spine |
| Delta appliqué | +5,56 |

`cotes.proposition_recentrage()` renvoie `applique = True`. Le générateur
lit `TUBE_PANSE` et `TUBE_SPINE`.

## Ce qui a été fait

Allonger le tube **panse** de 5,56 mm et raccourcir le tube **spine** de
5,56 mm. La somme des tubes ne change pas : la voie des pneus non plus,
ni la taille de la boîte des coques.

| | Avant | Appliqué | Mesuré sur les STL |
|---|---|---|---|
| Tube au-delà de la peau | 12,13 / 12,13 | panse 17,69, spine 6,56 | bouches x = −7,06 et 125,06 |
| Moyeu | 14,33 / 14,33 | panse 19,89, spine 8,76 | hauteurs de roue 27,90 et 16,77 (disque 8 mm compris) |
| Engagement dans le palier | 13,33 | panse 18,89, spine 7,76 | alésages utiles 19,29 et 8,16, jeu 0,40 des deux côtés |
| Empreinte en croix | 4,80 | 4,80 des deux côtés | 4,81 sur les deux roues |
| Entraxe des faces | 150,13 | 150,13 | 150,13 |
| Milieu des faces, après miroir | 64,56 | 59,00 | 59,00 |
| Boîte `b_front` | 132,13 × 23,02 × 201 | inchangée | inchangée |
| Boîte `b_back` | 132,13 × 29 × 201 | inchangée | inchangée |

Faces externes après miroir : x = −16,06 et 134,06 mm.

Deux STL :

- `chassis/v3/coin_wheel_panse.stl` — moyeu long. Quand on regarde le ₿
  de face, c'est le côté gauche, celui des deux ronds. Plaque
  `export/v31/plateR_roue_panse.stl`.
- `chassis/v3/coin_wheel_spine.stl` — moyeu court. Côté droit, la barre
  droite du glyphe. Plaque `plateR_roue_spine.stl`.

L'écart de volume entre les deux roues (5,03 cm³) est celui d'un cylindre
Ø24 × 11,13 mm, la différence des moyeux. Les vides (empreinte, capot,
arbre) ont la même profondeur depuis le bout, des deux côtés.

## Compromis acceptés

- **Palier spine plus court.** L'engagement passe à 7,76 mm. L'empreinte
  de 4,80 mm y tient, avec environ 3 mm de marge avant la bouche. Le
  servo spine porte la roue avec moins de portée : plus de flexion
  possible sur l'arbre. Ça se juge en roulant, pas sur le maillage.
- **La panse dépasse de 5,6 mm de plus**, le spine de 5,6 mm de moins.
  La boîte du robot complet, roues comprises, se décale. Sa largeur
  hors tout (entraxe des faces + rien au-delà, les faces SONT les bouts)
  reste 150,13 mm.
- **Le simulateur dynamique ne suit pas le milieu.** `TRACK = 0,13887` m
  reste le littéral de `engine.js`, `balancebot_sim.py` et `selfcheck.js`.
  Il décrivait déjà un entraxe plus ancien (146,87 mm). Le recentrage ne
  change pas la voie géométrique des pneus, donc il n'y a pas de nouvelle
  référence à régénérer. Le viewer, lui, relit `cotes.roues_apres_miroir()` :
  le milieu des roues est l'origine, le glyphe est centré dessus. La dalle
  est à 0,5 mm du milieu (`ecran` z = 0,0005 m).

## Options toujours écartées

- Déplacer le glyphe dans l'enveloppe. Ça changerait le dessin du ₿.
- N'allonger que la panse. La voie s'ouvrirait.
- Tourner les servos pour la quatrième vis. Les oreilles selon Y ne
  tiennent pas dans la cavité sans entailler les parois.

`chaine_roue.py` et `scripts/verifier-cotes.py` échouent si le milieu
quitte `GW / 2` ou si l'entraxe quitte la valeur du montage symétrique.
