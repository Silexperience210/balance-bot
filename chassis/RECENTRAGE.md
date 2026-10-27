# Recentrage des roues — proposition, non appliquée

Le milieu des deux axes n'est pas le centre du glyphe. C'est mesuré sur
la géométrie de `chassis/cotes.py`, pas au pied à coulisse.

| | mm |
|---|---|
| Peau du spine, avant miroir | 0 |
| Peau de la panse à hauteur d'axe | 106,87 |
| Milieu des peaux | 53,44 |
| Centre du glyphe (`GW / 2`) | 59,00 |
| Écart | −5,56 vers le spine |

Les deux tubes ont la même longueur (12,13 mm) pour qu'une seule roue
s'imprime. Le milieu des roues est donc le milieu des peaux. L'enveloppe
des coques n'a pas été touchée pour corriger ça.

## Option retenue pour plus tard (pas dans le générateur)

Allonger le tube **panse** de 5,56 mm et raccourcir le tube **spine** de
5,56 mm. La voie des pneus ne change pas. Le milieu se déplace de 5,56 mm
vers le centre du glyphe. `python3 chassis/cotes.py` imprime les longueurs
(`proposition_recentrage`, drapeau `applique = False`).

Conséquences, à accepter ensemble le jour où on l'applique :

- **Deux STL de roue.** Les moyeux ne font plus la même longueur
  (environ 19,9 mm côté panse, 8,8 mm côté spine). On ne peut plus
  imprimer le même fichier deux fois.
- **Palier spine plus court.** L'engagement du moyeu passe d'environ
  13,3 mm à 7,8 mm. L'empreinte du palonnier (4,8 mm) tient encore dans
  le moyeu court. Le servo spine porte la roue avec moins de portée :
  plus de flexion sur l'arbre, à juger en main, pas sur le maillage.
- **La panse dépasse de 5,6 mm de plus**, le spine de 5,6 mm de moins.
  La boîte des coques (132 × 23 × 201 et 132 × 29 × 201) ne change pas.
  La boîte du robot complet, roues comprises, se décale.
- **Le simulateur dynamique ne suit pas.** `TRACK = 0,13887` m est figé
  par `selfcheck.js`. Recentrer les STL ne doit pas « corriger » ce
  nombre sans régénérer toutes les références, des deux langages, à
  1e-12 près. Le viewer, lui, relit `cotes.roues_apres_miroir()`.
- **Plaques d'impression** : `make_plates.py` n'a qu'un STL de roue.
  Il faudrait une seconde pièce.

## Options écartées

- Déplacer le glyphe dans l'enveloppe pour que son centre tombe sur le
  milieu des axes. Ça change le dessin du ₿ ou l'enveloppe.
- N'allonger que la panse de 11,1 mm. Une seule roue reste symétrique
  seulement si l'autre tube ne bouge pas : le milieu se corrige, mais
  la voie s'ouvre de 11 mm et la panse porte un bras de levier plus long.
- Tourner les servos pour gagner la quatrième vis en même temps. Les
  oreilles selon Y ne tiennent pas dans la cavité sans entailler les
  parois, et l'arbre quitte le plan y = 0.

Tant que `chaine_roue.py` et `scripts/verifier-cotes.py` passent, cette
option n'est pas dans les STL.
