#!/usr/bin/env python3
"""Chronologie de la démonstration du BalanceBot — SOURCE UNIQUE.

Importée à la fois par le rendu 3D (`cinematique.py`) et par le générateur
d'écran (`ecran_firmware.py`) : le mouvement du robot et ce qu'affiche la dalle
sortent donc du MÊME fichier, ils ne peuvent pas se désynchroniser.

Le robot est un balancebot : il tient sur deux roues coaxiales.
- pour AVANCER il penche d'abord légèrement en avant (accélération), puis se
  redresse en vitesse de croisière ;
- pour FREINER il penche en arrière ;
- il « hésite » : micro-oscillations permanentes de l'assiette (~1,7 Hz) ;
- pour TOURNER, les deux roues tournent à des vitesses différentes (le robot
  pivote sur place), et il prend un léger roulis.
"""
import math

FPS = 30
N_IMAGES = 780

# ── clés d'animation (image, valeur) — interpolation linéaire entre les clés ──

# assiette : + = penché vers l'avant. Amplitudes calées sur un vrai balancebot
# (il chasse en permanence de ±1°, et penche de 5-6° pour accélérer ou freiner)
TANGAGE = ((1, 0.0), (90, 0.0), (120, -1.2), (150, 1.4), (180, 0.0),
           (215, 6.2), (250, 4.6), (300, 3.4), (330, -4.4), (355, -5.4),
           (390, -1.4), (420, 2.2), (460, 1.8), (505, -2.0), (545, 1.6),
           (590, -2.4), (625, 1.6), (660, -0.8), (700, 0.9), (740, -0.5),
           (780, 0.0))
# roulis (prise d'angle : on se penche VERS l'intérieur du virage, pour encaisser
# la force centrifuge — signe négatif = penché à gauche)
ROULIS = ((1, 0.0), (395, 0.0), (430, -4.6), (465, -3.6), (500, 0.0),
          (545, 2.2), (580, 4.2), (620, 2.2), (660, 0.0), (780, 0.0))
# lacet (rotation sur place) : POSITIF = tourne à GAUCHE (sens antihoraire vu de
# dessus, comme la rotation +Z de Blender) — doit correspondre au bouton allumé
LACET = ((1, 0.0), (395, 0.0), (505, 52.0), (540, 46.0),
         (620, -34.0), (665, -44.0), (780, -44.0))
# distance parcourue vers l'avant (mm), le long du cap courant
AVANCE = ((1, 0.0), (185, 0.0), (300, 165.0), (330, 160.0), (395, 25.0),
          (430, -55.0), (465, -85.0), (480, -85.0), (780, -85.0))

# bouton tactile allumé sur l'écran : 0 AVANT · 1 ARRIÈRE · 2 GAUCHE · 3 DROITE
# 4 EQUIL./STOP · None = aucun
BOUTON = ((1, None), (205, 0), (312, 0), (318, None), (345, 1), (392, 1),
          (398, None), (425, 2), (500, 2), (508, None), (545, 3), (618, 3),
          (624, None), (780, None))
# équilibre armé (le bouton de droite passe au vert « STOP » sur l'écran)
ARME = ((1, False), (72, True), (780, True))

RAYON_ROUE = 42.0        # mm (WHEEL_R)
VOIE = 115.0             # entraxe des plans de roue (mm)


def _interp(cles, f):
    if f <= cles[0][0]:
        return cles[0][1]
    for (f0, v0), (f1, v1) in zip(cles, cles[1:]):
        if f <= f1:
            t = (f - f0) / (f1 - f0) if f1 > f0 else 0.0
            return v0 + (v1 - v0) * t
    return cles[-1][1]


def tangage(f):
    """Assiette en degrés, micro-oscillations d'équilibrage incluses.

    L'amplitude de la chasse (±1°) n'est pas cosmétique : c'est elle qui rend
    l'hésitation VISIBLE. À 0,3° le robot paraît simplement immobile.
    """
    return _interp(TANGAGE, f) + 1.0 * math.sin(2 * math.pi * f / 17.0)


def roulis(f):
    return _interp(ROULIS, f) + 0.5 * math.sin(2 * math.pi * f / 23.0 + 1.0)


def lacet(f):
    return _interp(LACET, f)


def avance(f):
    return _interp(AVANCE, f)


def _escalier(cles, f):
    """Valeur en ESCALIER : la dernière clé atteinte (pour un booléen ou un
    bouton — jamais interpolé, sinon on obtient des états bâtards)."""
    v = cles[0][1]
    for f0, v0 in cles:
        if f >= f0:
            v = v0
        else:
            break
    return v


def bouton(f):
    v = _escalier(BOUTON, f)
    return None if v is None else int(v)


def arme(f):
    return bool(_escalier(ARME, f))


def _positions_pas(n=N_IMAGES, pas=1):
    """Intègre l'avance le long du cap : (x, y) pour chaque image."""
    pts = []
    x = y = 0.0
    prev_a = avance(0)
    for f in range(0, n + 1, pas):
        a = avance(f)
        d = a - prev_a
        prev_a = a
        cap = math.radians(lacet(f))
        y += d * math.cos(cap)
        x += d * math.sin(cap)
        pts.append((f, x, y))
    return pts


_POS = _positions_pas()


def position(f):
    """Position monde du robot (x latéral, y avant) en mm."""
    if f <= 0:
        return 0.0, 0.0
    i = min(int(f), len(_POS) - 1)
    return _POS[i][1], _POS[i][2]


def tours_roue(f):
    """Tours effectués par chaque roue : (gauche, droite).

    Le déplacement des deux roues doit COLLER à la distance parcourue, sinon on
    voit la roue patiner. En virage, la roue intérieure tourne moins vite :
    écart = lacet(rad) × (voie / 2).
    """
    d = avance(f) * 1000.0 if abs(avance(f)) < 1 else avance(f)
    diff = math.radians(lacet(f)) * (VOIE / 2.0)
    circ = 2 * math.pi * RAYON_ROUE
    return (d + diff) / circ, (d - diff) / circ


def vitesse_angulaire(f, dt=1.0 / FPS):
    return (lacet(f + dt * FPS) - lacet(f - dt * FPS)) / (2 * dt)


if __name__ == "__main__":
    print(f"{'img':>5} {'tangage':>8} {'lacet':>7} {'avance':>7} {'x':>7} {'y':>7} "
          f"{'trG':>6} {'trD':>6}  bouton")
    for f in range(1, N_IMAGES + 1, 60):
        x, y = position(f)
        g, d = tours_roue(f)
        b = bouton(f)
        noms = {0: "AVANT", 1: "ARRIERE", 2: "GAUCHE", 3: "DROITE", 4: "EQUIL"}
        print(f"{f:5d} {tangage(f):8.2f} {lacet(f):7.1f} {avance(f):7.1f} "
              f"{x:7.1f} {y:7.1f} {g:6.2f} {d:6.2f}  {noms.get(b if b is not None else -1, '-')}")
