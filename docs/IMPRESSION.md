# Impression

Plaques prêtes à trancher : `export/v31/`. Elles sont produites par
`python3 chassis/make_plates.py` à partir de `chassis/v3/`. Après toute
modification du générateur, régénérer les deux :

```bash
blender --background --python chassis/gen_bitcoin_bot.py
python3 chassis/make_plates.py
python3 chassis/review/chaine_roue.py
python3 chassis/review/verif_ultime.py
```

`chaine_roue.py` et `verif_ultime.py` tournent en CI, sans Blender. Le
contrôle servo × coque (`review/servo_fit.py`, avec et sans `--hump`)
demande Blender : il a été relancé sur les STL de cette révision,
intersection 0 mm³ dans les deux cas.

## Orientation

| Pièce | Sur le plateau | Pourquoi |
|---|---|---|
| `b_front`, `b_back` | face externe en bas, creux vers le haut | la gravure du ₿ et les contre-poinçons ne sont pas imprimés en l'air |
| `plateR_roue_panse.stl` | face ₿ en bas, moyeu long en l'air | côté des deux ronds, quand on regarde le ₿ de face : à gauche |
| `plateR_roue_spine.stl` | face ₿ en bas, moyeu court en l'air | côté de la barre droite : à droite |
| pneus | à plat | anneau, aucun surplomb |

Les coques font 201 mm de long. Un export CLI de certains trancheurs
refuse au-delà de ~195 mm : ouvrir les plaques dans l'interface
(Bambu Studio ou équivalent), plateau 256 × 256.

## Réglages qui restent valables

Profil d'origine, toujours pertinent pour un PETG 0,4 mm :

| | Coques | Roue | Pneu |
|---|---|---|---|
| Couche | 0,28 mm | 0,20 mm (gravure et peau des poches) | 0,24 mm |
| Parois | 6 (l'épaisseur de paroi du modèle est 2,4 mm) | 4 | 3 |
| Remplissage | sans objet, les parois font la pièce | gyroid, les poches sont déjà vides | léger |
| Support | aucun | aucun | aucun |
| Adhérence | bordure 5 mm, lit 70–80 °C | bordure | bordure, TPU lent (~25 mm/s) |
| Ponts | débit 0,9, 25 mm/s, ventilateur 100 % | — | — |

Les deux roues ont six poches ouvertes vers le moyeu, peau externe de
1,8 mm (la gravure en prend 1,0). Couche 0,20 mm : cette peau fait neuf
couches. Ne pas descendre le plancher dans le trancheur. Le moyeu panse
fait 27,9 mm de haut au total (disque compris), le spine 16,8 mm. On
imprime les deux : une seule plaque ne suffit plus. Les coques gardent
la même boîte ; `make_plates.py` a décalé leur translation de 5,56 mm
pour que le bord reste à 5 mm du plateau (le recentrage a bougé l'origine
de la boîte, pas sa taille).

## Ce qui n'a pas été changé, et pourquoi

- **Dépouille à 45° dans les creux du ₿.** Le contre-poinçon fait 1,6 mm
  de profond sur une grande largeur. Un chanfrein ne ferme le pont que
  sur le bord ; le milieu reste un pont. Le remplir changerait le dessin
  de la face. On pont.
- **Interférence du pneu.** 1,0 mm au diamètre, pas 0,9. La note ancienne
  parlait d'une gorge Ø69, qui était une autre roue. Ici le fond de gorge
  est Ø79, la bande Ø78 intérieur, l'extérieur STL Ø83. Desserrer
  l'interférence changerait ce diamètre. Si le TPU résiste au montage, on
  le fait en main (`docs/MONTAGE.md`), on ne change pas le modèle sans
  mesure.
- **Trou d'axe Ø12,4.** Horizontal, donc ovalisé par l'impression. Ce
  n'est pas un centrage d'outillage. S'il sort sous-cote, un alésoir ou
  une lime douce. Le servo est tenu par les vis d'oreille.

## Contrôle rapide au trancheur

Avant de lancer les huit heures : chaque roue montre six bras, le moyeu
n'est pas percé de part en part, et les coques montrent quatre avant-trous
M3 borgnes côté face. La plaque la plus haute est la roue de panse
(27,9 mm), pas le spine. `verif_ultime.py` a vérifié les deux STL
(29/29 au moment de la régénération) et `chaine_roue.py` 43/43.
