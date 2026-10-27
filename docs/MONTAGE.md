# Montage

Les cotes viennent de `chassis/cotes.py`. Ce qui est marqué « à mesurer »
n'a pas été relevé au pied à coulisse : ne pas le traiter comme une cote
du dépôt.

## Avant d'imprimer un second jeu

1. Palonnier en croix livré avec le servo (SG90 standard ou FS90R continu,
   même famille de palonnier, pas le même produit). L'empreinte de la roue
   est prévue pour **20 × 5,2 × 1,8 mm**, jeu 0,35 mm par face. Mesurer le
   sien. S'il est plus grand, il ne rentre pas : il faudra regénérer
   `HORN_*` dans `cotes.py`, pas limer au hasard.
2. Capot autour de l'arbre. Le dépôt dégage deux cas :
   - bossage datasheet Ø11,8 × 1,5 mm ;
   - capot oblong de 4,0 mm de haut, débord 2,9 mm, **mesuré sur le STL
     FreeCAD** `chassis/assets/servo/Servo-SG90.stl`, pas sur un servo.
   Si le capot en main fait 4 mm et que la pointe d'arbre n'est qu'à 6 mm
   de la face (datasheet), les cannelures n'engagent le palonnier que de
   **1,7 mm**. C'est court pour un couple de roue. Le STL de référence a
   un arbre plus long. À vérifier avant de compter sur l'entraînement.
3. Sens des servos continus. `feet.cpp` garde `kDirL = −1` et `kDirR = +1`
   parce que les deux servos sont montés en miroir. On ne l'a pas inversé
   sans essai. Au premier banc, une roue qui part du mauvais côté se
   corrige par ce signe, pas par un démontage du châssis.

## Ordre

1. **Coques.** Quatre goujons Ø5,8 du dos dans les alésages Ø6 de la face.
   Quatre vis M3 × 30, tête noyée côté dos, avant-trou Ø2,5 dans les plots
   (autotaraudage PETG). Ne pas serrer à fond avant que les servos soient
   en place : les baies s'ouvrent par le joint.
2. **Servos de roues**, tête vers le bas, face de sortie contre la paroi
   latérale intérieure. Quatre oreilles, **trois vis** : le spine a ses
   deux oreilles, la panse seulement l'oreille haute. L'oreille basse de
   la panse tombe hors de la peau (mesuré sur le maillage : peau x = 97,3,
   face d'oreille x = 100,4 avant miroir). Une semelle sous le corps,
   0,7 mm sous la cote nominale, empêche le servo de descendre dans le jeu
   de la baie. Elle ne le centre pas : ce sont les vis.
   Vis : celles du sachet SG90, ou M2 × 6. Pas M2 × 8 (la peau est à 2,4 mm,
   la vis longue débouche).
   Câble : il sort du bout court, vers le bas. La semelle s'arrête avant
   cette sortie. `servo_fit.py` mesure une course libre de 4,3 mm côté
   panse et 7,7 mm côté spine avant le prochain obstacle (le plancher de
   la cavité, pas la semelle).
3. **Palonnier.** Le visser sur l'arbre **avant** d'enfiler la roue. La vis
   centrale le plaque. La face ₿ de la roue n'est pas percée : on ne peut
   plus passer un tournevis après coup.
4. **Roue.** Moyeu Ø24 dans le palier Ø24,5. Il s'arrête 0,40 mm avant
   l'épaulement (mesuré : alésage utile 13,73 mm, moyeu engagé 13,33 mm).
   L'empreinte en croix fait 4,80 mm de profondeur pour admettre un
   palonnier posé sur le bossage de 1,5 mm **ou** sur un capot de 4 mm.
   Dans le premier cas il y a du jeu axial : c'est la vis du palonnier qui
   retient, pas le fond de l'empreinte.
   La roue n'est pas au milieu du glyphe (écart −5,6 mm vers le spine).
   C'est la géométrie de la panse ronde. On ne recentre pas.
5. **Pneu.** Bande TPU, Ø intérieur 78, fond de gorge Ø79 : 1,0 mm
   d'interférence au diamètre. L'étirer à la main. Si elle refuse, la
   tiédir ; ne pas agrandir la gorge dans le modèle sans régénérer, le Ø83
   du STL en dépend.
6. **Carte** T-Display-S3, paysage, dalle dans la fenêtre, USB-C vers le
   bas. **MPU6050** sur le piédestal : le dessus du plot est 2 mm sous
   l'axe, la carte amène le capteur à hauteur d'axe. **HC-SR04** dans la
   baie haute, transducteurs dans les deux Ø16,6.

## Après le vissage, avant la première mise sous tension

- Les deux roues tournent à la main sans frotter le tube ni le capot.
- Un servo dont les vis sont serrées ne porte pas sur la semelle. S'il
  porte, le boîtier est plus haut que l'enveloppe prévue : ne pas forcer.
- Neutre du continu : 1500 µs n'est jamais exact. `kTrimUsL` / `kTrimUsR`
  dans `feet.cpp` se règlent servo arrêté, roue qui ne rampe plus.
- `kUsPerDegS` (défaut 1,0) se cale en envoyant la pleine consigne et en
  regardant si l'impulsion reste dans ±500 µs. Ce n'est pas calculable
  depuis le dépôt.

Lire `TEST_PROTOCOL.md` avant d'armer la boucle d'équilibre.
