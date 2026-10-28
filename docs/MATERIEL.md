# Matériel

Liste de ce que le dépôt suppose. Les quantités de vis viennent du
générateur (`chassis/gen_bitcoin_bot.py`) et de `chassis/NOTES_v3.md`.
Aucun de ces éléments n'a été recompté sur un robot assemblé pendant
cette mise à jour.

## Électronique

| Pièce | Rôle | Où c'est dans le code |
|---|---|---|
| LilyGo T-Display-S3-Touch | ESP32-S3, écran ST7789 170×320, tactile CST816 | `balance-bot/config.h` |
| MPU6050 | assiette, I2C | `imu.cpp` |
| HC-SR04 | distance, un seul module | `head.cpp`, `PIN_US_*` |
| 2× servo 9 g **rotation continue** (FS90R ou équivalent, boîtier SG90) | roues | `FEET_MODE_CONTINUOUS 1` |
| 2× SG90 standard | tête, pan et tilt | `SERVO_HEAD_PAN`, `SERVO_HEAD_TILT` |
| LiPo 1S | alimentation carte | `battery.cpp`, seuil 3,5 V |
| Alimentation 5 V séparée pour les servos | BEC ou buck, masse commune | note en bas de `NOTES_v3.md` |

Le boîtier servo codé est **22,8 × 12,2 × 22,5 mm**, pas « 23 × 12,2 × 29 ».
Un continu d'une autre marque qui ne rentre pas dans cette enveloppe ne
rentre pas dans la baie : `review/servo_fit.py` le dira (intersection
non nulle).

## Impression

| Pièce | Matière | Fichier |
|---|---|---|
| Coque avant, coque arrière | PETG | `export/v31/plate1_b_front.stl`, `plate2_b_back.stl` |
| Roue panse (moyeu long) et roue spine (moyeu court) | PETG | `plateR_roue_panse.stl`, `plateR_roue_spine.stl` |
| 2 bandes | TPU 95A | `plateT_tire1.stl`, `plateT_tire2.stl` |

Masses **calculées** sur les STL (PETG 1,27 g/cm³, TPU 1,20 g/cm³), pas
pesées : coques 133 g + 117 g, roue panse 39 g, roue spine 33 g, pneu 5,3 g. Détail dans
`NOTES_v3.md`.

## Visserie

| Vis | Nombre | Où |
|---|---|---|
| M3 × 30, tête cylindrique bombée ou fraisée Ø ≤ 6,4 | 4 | fermeture des coques |
| M2 × 6, ou les vis du sachet servo (≈ Ø1,9 × 6,5) | 3 pour les roues | oreilles. La quatrième oreille (basse, panse) n'a pas de trou utile |
| M2 courtes | 2 + 2 | carte (entraxe des trous réels) et MPU (entraxe 15 mm) |
| Vis de palonnier (livrée) | 2 | centre de l'arbre, **avant** d'enfiler la roue |

Pas de M2 × 8 sur les oreilles : la paroi fait 2,4 mm et l'avant-trou est
borgne, arrêté avant la peau.

## Ce que le dépôt ne fige pas

- la référence exacte du palonnier en croix (voir `docs/MONTAGE.md`) ;
- le trim µs du neutre continu ;
- la longueur réelle de l'arbre au-delà du capot du servo acheté.
