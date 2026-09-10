#!/usr/bin/env python3
"""BalanceBot v3 — vue éclatée + vue interne, style dessin d'ingénieur (Blender).

Repère du design (identique au générateur du châssis) :
    X = gauche→droite (largeur)   Y = arrière→avant (profondeur, avant = +Y)
    Z = hauteur (sol = 0)

Cotes utilisées (celles du projet, chassis/gen_bitcoin_bot.py) :
    carte T-Display-S3 Touch 62 × 26 × 1,2       servo 9 g 22,8 × 12,2 × 22,5
    axe des roues z = 41,5 (WHEEL_R)             voie des roues 108
    roue ₿ Ø80 × 8 + moyeu Ø24 × 13              bande TPU Ø83 × 7
    HC-SR04 45 × 20 + transducteurs Ø16, entraxe 26 (z = 145)
    MPU6050 : dessus du piédestal z = 36,5

Rendus : chassis/render/eclate_iso.png et chassis/render/interne_avant.png
Usage  : blender --background --python chassis/assets/vue_eclatee.py
"""
import math
import os
import sys

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # .../balance-bot
V3 = os.path.join(ROOT, "chassis", "v3")
OUT = os.path.join(ROOT, "chassis", "render")
os.makedirs(OUT, exist_ok=True)

# ── cotes de référence ────────────────────────────────────────────────────
Z_WHEEL = 41.5          # axe des roues
Y_WHEEL = 12.8          # profondeur des paliers
X_MID = 64.57           # centre du corps (bbox)
TRACK = 108.0           # voie (plans médians des roues)
Z_SCREEN = 72.0         # centre de la fenêtre écran
X_SCREEN = 59.5
Z_HEAD = 145.0          # axe des transducteurs HC-SR04
X_HEAD = 64.4
SR_PITCH = 26.0

# décalages d'éclatement
E_SHELL = 55.0
E_WHEEL = 40.0
E_SERVO = 18.0
E_BOARD = 40.0
E_HEAD = 45.0
E_MPU = 30.0


def nettoyer():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


def materiau(nom, couleur):
    m = bpy.data.materials.get(nom) or bpy.data.materials.new(nom)
    m.diffuse_color = (*couleur, 1.0)
    m.use_nodes = False
    return m


def habiller(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def boite(nom, taille, centre, mat, rotation=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=centre)
    o = bpy.context.object
    o.name = nom
    o.scale = (taille[0], taille[1], taille[2])
    if rotation:
        o.rotation_euler = rotation
    habiller(o, mat)
    return o


def cylindre(nom, rayon, longueur, centre, mat, axe="Z"):
    rot = {"Z": (0, 0, 0), "X": (0, math.pi / 2, 0), "Y": (math.pi / 2, 0, 0)}[axe]
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=rayon, depth=longueur,
                                       location=centre, rotation=rot)
    o = bpy.context.object
    o.name = nom
    habiller(o, mat)
    return o


def importer_stl(nom, chemin, mat):
    avant = set(bpy.data.objects)
    try:
        bpy.ops.wm.stl_import(filepath=chemin)
    except AttributeError:
        bpy.ops.import_mesh.stl(filepath=chemin)
    nouveaux = [o for o in set(bpy.data.objects) - avant if o.type == "MESH"]
    for o in nouveaux:
        o.name = nom
        habiller(o, mat)
    return nouveaux[0] if nouveaux else None


def texte(nom, contenu, centre, taille=6.0, rotation=(math.pi / 2, 0, 0)):
    bpy.ops.object.text_add(location=centre, rotation=rotation)
    o = bpy.context.object
    o.name = nom
    o.data.body = contenu
    o.data.size = taille
    o.data.align_x = "CENTER"
    habiller(o, MAT_TEXTE)
    return o


# ── matériaux ─────────────────────────────────────────────────────────────
MAT_COQUE = materiau("coque", (0.83, 0.72, 0.42))      # PETG doré (thème ₿)
MAT_ROUE = materiau("roue", (0.72, 0.62, 0.34))
MAT_TPU = materiau("tpu", (0.20, 0.20, 0.22))
MAT_SERVO = materiau("servo", (0.25, 0.45, 0.80))
MAT_CARTE = materiau("carte", (0.10, 0.28, 0.16))
MAT_ECRAN = materiau("ecran", (0.05, 0.06, 0.09))
MAT_US = materiau("ultrason", (0.75, 0.76, 0.78))
MAT_MPU = materiau("mpu", (0.15, 0.35, 0.55))
MAT_VIS = materiau("vis", (0.55, 0.56, 0.60))
MAT_BAT = materiau("batterie", (0.55, 0.15, 0.15))
MAT_TEXTE = materiau("texte", (0.05, 0.05, 0.05))

nettoyer()

# ── coques (pièces réelles) ───────────────────────────────────────────────
front = importer_stl("b_front", os.path.join(V3, "b_front.stl"), MAT_COQUE)
front.location = (0, E_SHELL, 0)
back = importer_stl("b_back", os.path.join(V3, "b_back.stl"), MAT_COQUE)
back.location = (0, -E_SHELL, 0)

# ── roues + bandes TPU (pièces réelles) ───────────────────────────────────
for cote, sx in (("D", -1), ("G", 1)):
    x = X_MID + sx * (TRACK / 2 + E_WHEEL)
    roue = importer_stl(f"roue_{cote}", os.path.join(V3, "coin_wheel.stl"), MAT_ROUE)
    # la roue est modélisée axe en Z (impression) : on la couche axe en X
    roue.rotation_euler = (0, math.pi / 2, 0)
    roue.location = (x, Y_WHEEL, Z_WHEEL)
    pneu = importer_stl(f"pneu_{cote}", os.path.join(V3, "coin_tire.stl"), MAT_TPU)
    pneu.rotation_euler = (0, math.pi / 2, 0)
    pneu.location = (x + sx * 10.0, Y_WHEEL, Z_WHEEL)

# ── servos (4 × 9 g) : 2 de pied (axe horizontal) + 2 de tête ─────────────
for cote, sx in (("D", -1), ("G", 1)):
    x_axe = X_MID + sx * (TRACK / 2 - 13.0 - 1.5)          # flange côté moyeu
    socle = X_MID + sx * (TRACK / 2 - 13.0 - 1.5 + E_SERVO)
    boite(f"servo_pied_{cote}", (22.5, 12.2, 22.8), (socle - sx * 11.25, Y_WHEEL, Z_WHEEL), MAT_SERVO)
    boite(f"servo_pied_{cote}_bride", (2.5, 22.8, 32.2), (socle, Y_WHEEL, Z_WHEEL), MAT_SERVO)
    cylindre(f"servo_pied_{cote}_axe", 2.4, 6.0, (x_axe + sx * -3.0, Y_WHEEL, Z_WHEEL), MAT_VIS, "X")
for i, sx in enumerate((-1, 1)):
    x = X_HEAD + sx * 14.0
    boite(f"servo_tete_{i}", (12.2, 22.8, 22.5), (x, 2.0 + E_SERVO, Z_HEAD + 22.0), MAT_SERVO)
    boite(f"servo_tete_{i}_bride", (22.8, 2.5, 32.2), (x, 2.0 + E_SERVO, Z_HEAD + 22.0 + 11.25), MAT_SERVO)

# ── tête ultrason (HC-SR04) + 2 transducteurs ─────────────────────────────
boite("hc_sr04", (45.0, 1.6, 20.0), (X_HEAD, 23.0 + E_HEAD, Z_HEAD), MAT_US)
for sx in (-1, 1):
    cylindre(f"transducteur_{'G' if sx > 0 else 'D'}", 8.0, 12.0,
             (X_HEAD + sx * SR_PITCH / 2, 23.0 + E_HEAD - 5.4, Z_HEAD), MAT_US, "Y")

# ── carte T-Display-S3 Touch + dalle ──────────────────────────────────────
boite("carte_tdisplay", (62.0, 1.2, 26.0), (X_SCREEN, 18.0 + E_BOARD, Z_SCREEN), MAT_CARTE)
boite("dalle_st7789", (56.0, 0.6, 26.0), (X_SCREEN, 18.0 + E_BOARD + 1.0, Z_SCREEN), MAT_ECRAN)
cylindre("usb_c", 1.9, 3.0, (X_SCREEN - 12.0, 18.0 + E_BOARD, Z_SCREEN - 16.0), MAT_VIS, "Y")

# ── MPU6050 sur son piédestal ─────────────────────────────────────────────
boite("mpu6050", (21.0, 16.0, 3.0), (X_SCREEN - 6.0, 10.0 + E_MPU, 38.0), MAT_MPU)

# ── batterie (à adapter : voir POWER_GUIDE.md) ────────────────────────────
boite("batterie", (60.0, 18.0, 26.0), (X_MID, -6.0 + -E_SHELL * 0.35, 70.0), MAT_BAT)

# ── goujons Ø6 (×4) + vis M3×30 (×4) ──────────────────────────────────────
for x, z in ((108.0, 38.0), (108.0, 179.0), (6.4, 72.0), (18.2, 145.0)):
    cylindre(f"goujon_{x:.0f}_{z:.0f}", 3.0, 12.0, (x, -E_SHELL + 20.0, z), MAT_VIS, "Y")
    cylindre(f"vis_{x:.0f}_{z:.0f}", 1.5, 30.0, (x, -E_SHELL - 20.0, z), MAT_VIS, "Y")

# ── étiquettes numérotées (vue éclatée) ───────────────────────────────────
etiquettes = [
    ("1  coque avant (imprimée)", (X_SCREEN, E_SHELL + 4, 205.0)),
    ("2  carte T-Display-S3 Touch", (X_SCREEN, 18 + E_BOARD, Z_SCREEN + 22.0)),
    ("3  MPU6050 (piédestal z=36,5)", (X_SCREEN - 6, 10 + E_MPU, 52.0)),
    ("4  servos de pied 9 g", (X_MID, Y_WHEEL - 20, Z_WHEEL - 26.0)),
    ("5  roue ₿ + bande TPU", (X_MID + TRACK / 2 + E_WHEEL, Y_WHEEL - 22, Z_WHEEL - 34.0)),
    ("6  tête HC-SR04", (X_HEAD, 23 + E_HEAD - 22, Z_HEAD + 34.0)),
    ("7  batterie + BEC", (X_MID, -6 - E_SHELL * 0.35, 104.0)),
    ("8  goujons Ø6 + vis M3 ×30", (120.0, -E_SHELL + 20, 205.0)),
]
for contenu, pos in etiquettes:
    pass  # créées après la caméra, orientées face à elle

# ── caméra orthographique + rendu style plan technique ───────────────────
scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
sh = scene.display.shading
sh.light = "STUDIO"
sh.color_type = "MATERIAL"
sh.show_object_outline = True
sh.object_outline_color = (0.08, 0.08, 0.08)
sh.show_cavity = True
sh.cavity_type = "BOTH"
sh.background_type = "VIEWPORT"
sh.background_color = (0.97, 0.97, 0.97)
scene.render.resolution_x = 2400
scene.render.resolution_y = 1800
scene.render.film_transparent = False

bpy.ops.object.camera_add(location=(520, -260, 330),
                          rotation=(math.radians(68), 0, math.radians(58)))
cam = bpy.context.object
cam.data.type = "ORTHO"
cam.data.ortho_scale = 620
scene.camera = cam

# étiquettes créées maintenant, orientées pile face caméra (lisibles)
from mathutils import Vector  # noqa: E402

for contenu, pos in etiquettes:
    o = texte(contenu, contenu, pos, taille=9.0)
    o.rotation_euler = (Vector(cam.location) - Vector(pos)).to_track_quat("Z", "Y").to_euler()

scene.render.filepath = os.path.join(OUT, "eclate_iso.png")
bpy.ops.render.render(write_still=True)

# ── seconde vue : interne, coque avant masquée (montage) ─────────────────
for o in bpy.data.objects:
    if o.name == "b_front" or o.name.startswith("etiquette") or o.name.startswith("Texte"):
        o.hide_render = True
front.hide_render = True
for o in bpy.data.objects:
    if o.type == "FONT":
        o.hide_render = True
# les éléments mobiles reviennent à leur place réelle
for cote, sx in (("D", -1), ("G", 1)):
    x = X_MID + sx * (TRACK / 2)
    bpy.data.objects[f"roue_{cote}"].location = (x, Y_WHEEL, Z_WHEEL)
    bpy.data.objects[f"pneu_{cote}"].location = (x + sx * 4.5, Y_WHEEL, Z_WHEEL)
    bpy.data.objects[f"servo_pied_{cote}"].location = (
        X_MID + sx * (TRACK / 2 - 13.0 - 1.5 - 11.25), Y_WHEEL, Z_WHEEL)
    bpy.data.objects[f"servo_pied_{cote}_bride"].location = (
        X_MID + sx * (TRACK / 2 - 13.0 - 1.5), Y_WHEEL, Z_WHEEL)
bpy.data.objects["carte_tdisplay"].location = (X_SCREEN, 18.0, Z_SCREEN)
bpy.data.objects["dalle_st7789"].location = (X_SCREEN, 19.0, Z_SCREEN)
bpy.data.objects["mpu6050"].location = (X_SCREEN - 6.0, 10.0, 38.0)
bpy.data.objects["hc_sr04"].location = (X_HEAD, 23.0, Z_HEAD)
for i in ("D", "G"):
    bpy.data.objects[f"transducteur_{i}"].location = (
        X_HEAD + (SR_PITCH / 2 if i == "G" else -SR_PITCH / 2), 17.6, Z_HEAD)

cam.location = (330, -330, 210)
cam.rotation_euler = (math.radians(70), 0, math.radians(45))
cam.data.ortho_scale = 330
scene.render.filepath = os.path.join(OUT, "interne_avant.png")
bpy.ops.render.render(write_still=True)

print("RENDUS →", OUT)
print("  eclate_iso.png   (vue éclatée, 8 repères)")
print("  interne_avant.png (interne, coque avant masquée)")
