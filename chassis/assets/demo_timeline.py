#!/usr/bin/env python3
"""Chronologie de la démonstration du BalanceBot — SOURCE UNIQUE.

Importée à la fois par le rendu 3D (`cinematique.py`) et par le générateur
d'écran (`ecran_firmware.py`) : le mouvement du robot et ce qu'affiche la dalle
sortent donc du MÊME fichier, ils ne peuvent pas se désynchroniser.

Le robot est un balancebot : il tient sur deux roues coaxiales.
- pour AVANCER il penche d'abord en avant (accélération), puis se redresse ;
- pour FREINER il penche en arrière ;
- il « hésite » : micro-oscillations permanentes de l'assiette (~1,7 Hz) ;
- pour TOURNER les deux roues tournent à des vitesses différentes (il pivote),
  et il prend un roulis vers l'intérieur du virage.

RYTHME (choix utilisateur) : « vif et joueur » — sprints courts, virages serrés,
hésitations brèves. Vitesses atteintes ~120 mm/s en pointe et ~120 °/s en
rotation, pour un robot de 200 mm de haut : c'est vif, mais ça reste un vrai
balancebot, qui plonge de 7° quand il accélère et se redresse en vitesse.

VISAGE : le robot joue la scène. Les yeux sont fermés au réveil, plissent à
l'accélération, s'écarquillent au freinage, se plissent en méfiance pendant
l'hésitation, suivent le sens du virage, et finissent en yeux rieurs avec un
clin d'œil. Chaque expression, chaque regard et chaque clignement est décidé
ici — c'est le seul endroit à modifier.
"""
import math

FPS = 30
N_IMAGES = 780

# ── clés d'animation (image, valeur) — interpolation linéaire entre les clés ──

# assiette : + = penché vers l'avant. La chasse de ±1° est PERMANENTE : c'est
# elle qui rend l'hésitation visible (à 0,3° le robot paraît immobile).
TANGAGE = ((1, 0.0), (50, 0.0), (60, -1.6), (95, 7.0), (125, 4.4),
           (150, -6.2), (170, -2.0), (195, 2.6), (215, -1.6), (232, 3.0),
           (262, 2.2), (285, 6.6), (330, 4.2), (368, -6.8), (395, -2.4),
           (420, 3.4), (455, 2.0), (480, -2.6), (520, 1.8), (560, -1.2),
           (600, 0.6), (640, -0.8), (690, 0.5), (740, -0.3), (780, 0.0))
# roulis : on se penche VERS l'intérieur du virage (force centrifuge).
# négatif = penché à gauche. Les virages sont plus serrés donc plus inclinés.
ROULIS = ((1, 0.0), (200, 0.0), (218, -6.2), (240, -4.8), (258, 3.4),
          (278, 5.6), (300, 0.0), (385, 0.0), (405, -6.8), (425, -5.2),
          (445, 4.0), (470, 5.2), (500, 0.0), (780, 0.0))
# lacet : POSITIF = tourne à GAUCHE (rotation +Z de Blender). Virages serrés :
# 90° en 35 images (1,2 s), soit ~77 °/s, puis contre-virage à ~120 °/s.
LACET = ((1, 0.0), (200, 0.0), (240, 90.0), (275, -55.0), (385, -55.0),
         (445, 115.0), (520, 115.0), (585, 40.0), (650, 0.0), (780, 0.0))
# distance parcourue vers l'avant (mm), le long du cap courant. Sa PENTE est la
# vitesse : 4,0 mm/image = 120 mm/s en pointe, −1,55 mm/image en marche arrière.
AVANCE = ((1, 0.0), (55, 0.0), (125, 280.0), (160, 286.0), (205, 294.0),
          (240, 318.0), (275, 342.0), (345, 560.0), (385, 567.0),
          (445, 588.0), (520, 470.0), (585, 570.0), (650, 600.0),
          (700, 602.0), (780, 602.0))

# bouton tactile allumé (écran manuel, conservé pour le firmware) :
# 0 AVANT · 1 ARRIÈRE · 2 GAUCHE · 3 DROITE · 4 EQUIL./STOP · None = aucun
BOUTON = ((1, None), (60, 0), (205, 0), (212, None), (232, 2), (272, 2),
          (280, None), (300, 0), (382, 0), (392, None), (400, 2), (440, 2),
          (448, None), (470, 1), (585, 1), (592, None), (620, 0), (648, 0),
          (655, None), (780, None))
ARME = ((1, False), (40, True), (780, True))

# ── visage : (expr, gaze) par plage, et les clignements ────────────────────
# Expressions disponibles (géométrie portée de ui.cpp) : calme, penche,
# mefiant, enerve, surprise, content, clin.
EXPRESSIONS = (
    (1,   "calme",    0.0),    # réveil : yeux fermés (voir CLIGNEMENTS)
    (24,  "calme",    0.0),    # il ouvre les yeux
    (36,  "calme",  -12.0),    # il regarde à gauche
    (48,  "calme",   12.0),    # puis à droite : il repère la pièce
    (58,  "penche",   0.0),    # il se décide
    (95,  "enerve",   0.0),    # SPRINT 1 : regard déterminé
    (128, "surprise", 0.0),    # FREINAGE : les yeux s'écarquillent
    (165, "mefiant", -10.0),   # HÉSITATION : il se méfie, le regard balaie
    (185, "mefiant",  10.0),
    (205, "penche",  16.0),    # VIRAGE GAUCHE : il regarde DANS le virage
    (242, "penche", -16.0),    # CONTRE-VIRAGE : idem à droite
    (278, "enerve",   0.0),    # SPRINT 2 : droit devant
    (348, "surprise", 0.0),    # FREINAGE
    (390, "mefiant",  14.0),   # PIVOT : il suit son mouvement
    (448, "mefiant",   0.0),   # MARCHE ARRIÈRE : concentré
    (525, "penche",   0.0),    # il repart en avant
    (600, "calme",    0.0),    # il se calme
    (690, "content",  0.0),    # YEUX RIEURS : la chute
    (780, "content",  0.0),
)
# clignements : (image de départ, durée en images)
CLIGNEMENTS = ((8, 20), (78, 3), (155, 3), (252, 3), (368, 3),
               (505, 3), (655, 3), (742, 3))
# clin d'œil final (œil gauche fermé)
CLIN = (748, 14)

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
    """Assiette en degrés, micro-oscillations d'équilibrage incluses."""
    return _interp(TANGAGE, f) + 1.0 * math.sin(2 * math.pi * f / 17.0)


def roulis(f):
    return _interp(ROULIS, f) + 0.5 * math.sin(2 * math.pi * f / 23.0 + 1.0)


def lacet(f):
    return _interp(LACET, f)


def avance(f):
    return _interp(AVANCE, f)


def vitesse(f):
    """Vitesse d'avance en mm/s (pente de la courbe d'avance)."""
    return (avance(f + 1) - avance(f - 1)) * 0.5 * FPS


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


def visage(f):
    """(expression, clignement, regard, clin) à l'image f.

    Le regard est un décalage horizontal en pixels ; le clin ferme l'œil GAUCHE.
    """
    expr, gaze = "calme", 0.0
    for f0, e, g in EXPRESSIONS:
        if f >= f0:
            expr, gaze = e, g
        else:
            break
    blink = any(d <= f < d + n for d, n in CLIGNEMENTS)
    clin = CLIN[0] <= f < CLIN[0] + CLIN[1]
    return expr, blink, gaze, clin


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
    d = avance(f)
    diff = math.radians(lacet(f)) * (VOIE / 2.0)
    circ = 2 * math.pi * RAYON_ROUE
    return (d + diff) / circ, (d - diff) / circ


def vitesse_angulaire(f, dt=1.0 / FPS):
    return (lacet(f + dt * FPS) - lacet(f - dt * FPS)) / (2 * dt)


if __name__ == "__main__":
    print(f"{'img':>5} {'tangage':>8} {'roulis':>7} {'lacet':>7} {'avance':>7} "
          f"{'mm/s':>7} {'°/s':>7} {'x':>7} {'y':>7}  visage")
    for f in range(1, N_IMAGES + 1, 40):
        x, y = position(f)
        e, bl, g, cl = visage(f)
        marque = "CLIN" if cl else ("blink" if bl else f"gaze {g:+.0f}")
        print(f"{f:5d} {tangage(f):8.2f} {roulis(f):7.2f} {lacet(f):7.1f} "
              f"{avance(f):7.1f} {vitesse(f):7.1f} {vitesse_angulaire(f):7.1f} "
              f"{x:7.1f} {y:7.1f}  {e:9s} {marque}")
    # contrôle de cohérence roue / distance
    g, d = tours_roue(N_IMAGES)
    print(f"\nparcours {avance(N_IMAGES):.0f} mm = {avance(N_IMAGES)/(2*math.pi*RAYON_ROUE):.2f} "
          f"tour(s) de roue (roues : {g:.2f} / {d:.2f} tours)")
    vmax = max(vitesse(f) for f in range(1, N_IMAGES + 1))
    wmax = max(abs(vitesse_angulaire(f)) for f in range(1, N_IMAGES + 1))
    print(f"pointe : {vmax:.0f} mm/s ({vmax/1000:.2f} m/s) et {wmax:.0f} °/s")
