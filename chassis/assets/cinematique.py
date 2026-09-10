#!/usr/bin/env python3
"""BalanceBot — rendu « métal orange & noir » : image fixe HD + cinématique.

Deux modes :
    blender -b -P cinematique.py -- still     → image fixe haute définition (de face)
    blender -b -P cinematique.py -- cine      → vidéo : orbite → éclaté → remontage → en marche

Réutilise le placement de chassis/assets/vue_eclatee.py (cotes réelles du projet).
Matériaux : orange métallisé (coques), noir métallisé (roues/pneus), écran émissif
avec des yeux animés, sol noir brillant.

Sorties : chassis/render/hero_face.png  et  chassis/render/cinematique.mp4
"""
import math
import os
import sys

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V3 = os.path.join(ROOT, "chassis", "v3")
OUT = os.path.join(ROOT, "chassis", "render")
os.makedirs(OUT, exist_ok=True)

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = argv[0] if argv else "still"

# ── cotes du projet ───────────────────────────────────────────────────────
Z_WHEEL, Y_WHEEL = 41.5, 12.8
X_MID, TRACK = 64.57, 108.0
Z_SCREEN, X_SCREEN = 72.0, 59.5
Z_HEAD, X_HEAD, SR_PITCH = 145.0, 64.4, 26.0
FPS = 30
F_ORBITE_END, F_ECLATE_END, F_REMONTE_END, F_FIN = 240, 420, 570, 780

# ══════════════════════════════════════════════════════════════════════════
# matériaux
# ══════════════════════════════════════════════════════════════════════════
def metal(nom, couleur, rugosite=0.28, metallic=1.0, emission=None, force=0.0):
    m = bpy.data.materials.new(nom)
    m.use_nodes = True
    n = m.node_tree.nodes.get("Principled BSDF")
    n.inputs["Base Color"].default_value = (*couleur, 1.0)
    n.inputs["Metallic"].default_value = metallic
    n.inputs["Roughness"].default_value = rugosite
    if emission:
        n.inputs["Emission Color"].default_value = (*emission, 1.0)
        n.inputs["Emission Strength"].default_value = force
    return m


M_ORANGE = metal("orange_metal", (0.95, 0.32, 0.02), 0.22)
M_ORANGE_FONCE = metal("orange_fonce", (0.55, 0.17, 0.01), 0.34)
M_NOIR = metal("noir_metal", (0.022, 0.022, 0.025), 0.30)
M_CAOUT = metal("noir_caoutchouc", (0.030, 0.030, 0.032), 0.65, metallic=0.15)
M_ECRAN = metal("ecran", (0.01, 0.01, 0.012), 0.15, metallic=0.4,
                emission=(0.85, 0.28, 0.06), force=0.8)
M_YEUX = metal("yeux", (0.02, 0.02, 0.02), 0.2, metallic=0.0, emission=(1.0, 0.42, 0.05), force=14.0)
M_VIS = metal("vis", (0.62, 0.63, 0.66), 0.25)
M_SERVO = metal("servo", (0.06, 0.06, 0.07), 0.4, metallic=0.8)


def supprimer_tout():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)


def habiller(o, mat):
    o.data.materials.clear()
    o.data.materials.append(mat)


def boite(nom, taille, centre, mat, rot=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=centre)
    o = bpy.context.object
    o.name = nom
    o.scale = taille
    if rot:
        o.rotation_euler = rot
    habiller(o, mat)
    return o


def cylindre(nom, rayon, longueur, centre, mat, axe="Z", sommets=64):
    rot = {"Z": (0, 0, 0), "X": (0, math.pi / 2, 0), "Y": (math.pi / 2, 0, 0)}[axe]
    bpy.ops.mesh.primitive_cylinder_add(vertices=sommets, radius=rayon, depth=longueur,
                                       location=centre, rotation=rot)
    o = bpy.context.object
    o.name = nom
    habiller(o, mat)
    return o


def importer(nom, fichier, mat):
    avant = set(bpy.data.objects)
    try:
        bpy.ops.wm.stl_import(filepath=fichier)
    except AttributeError:
        bpy.ops.import_mesh.stl(filepath=fichier)
    neufs = [o for o in set(bpy.data.objects) - avant if o.type == "MESH"]
    for o in neufs:
        o.name = nom
        habiller(o, mat)
    return neufs[0]


supprimer_tout()

# ══════════════════════════════════════════════════════════════════════════
# ensemble mécanique — positions assemblées (A) et éclatées (E)
# ══════════════════════════════════════════════════════════════════════════
PIVOT = (X_MID, Y_WHEEL, Z_WHEEL)

# corps = tout sauf les roues, parenté à un pivot placé sur l'axe des roues
corps = []
front = importer("b_front", os.path.join(V3, "b_front.stl"), M_ORANGE)
back = importer("b_back", os.path.join(V3, "b_back.stl"), M_ORANGE_FONCE)
corps += [front, back]

carte = boite("carte", (62.0, 1.2, 26.0), (X_SCREEN, 18.0, Z_SCREEN), M_NOIR)
ecran = boite("ecran", (56.0, 0.5, 26.0), (X_SCREEN, 19.2, Z_SCREEN), M_ECRAN)
# yeux : deux amandes émissives sur l'écran
yeux = []
for sx in (-1, 1):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=1.0,
                                        location=(X_SCREEN + sx * 12.0, 19.6, Z_SCREEN + 1.0))
    o = bpy.context.object
    o.name = f"oeil_{'G' if sx > 0 else 'D'}"
    o.scale = (9.0, 4.0, 5.0)
    habiller(o, M_YEUX)
    yeux.append(o)

mpu = boite("mpu", (21.0, 16.0, 3.0), (X_SCREEN - 6.0, 10.0, 38.0), M_SERVO)
hc = boite("hc_sr04", (45.0, 1.6, 20.0), (X_HEAD, 23.0, Z_HEAD), M_NOIR)
transducteurs = []
for sx in (-1, 1):
    transducteurs.append(cylindre(f"transducteur_{'D' if sx < 0 else 'G'}", 8.0, 12.0,
                                  (X_HEAD + sx * SR_PITCH / 2, 17.6, Z_HEAD), M_ORANGE, "Y"))
corps += [carte, ecran, mpu, hc] + transducteurs + yeux

servos_pied = []
for cote, sx in (("D", -1), ("G", 1)):
    socle = X_MID + sx * (TRACK / 2 - 13.0 - 1.5)
    servos_pied.append(boite(f"servo_pied_{cote}", (22.5, 12.2, 22.8),
                             (socle - sx * 11.25, Y_WHEEL, Z_WHEEL), M_SERVO))
    servos_pied.append(boite(f"servo_pied_{cote}_bride", (2.5, 22.8, 32.2),
                             (socle, Y_WHEEL, Z_WHEEL), M_SERVO))
corps += servos_pied

for i, sx in enumerate((-1, 1)):
    corps.append(boite(f"servo_tete_{i}", (12.2, 22.8, 22.5),
                       (X_HEAD + sx * 14.0, 2.0, Z_HEAD + 22.0), M_SERVO))

batterie = boite("batterie", (60.0, 18.0, 26.0), (X_MID, -12.0, 70.0), M_NOIR)
corps.append(batterie)

# roues (hors corps : elles tournent)
roues, pneus = [], []
for cote, sx in (("D", -1), ("G", 1)):
    x = X_MID + sx * (TRACK / 2)
    r = importer(f"roue_{cote}", os.path.join(V3, "coin_wheel.stl"), M_NOIR)
    r.rotation_euler = (0, math.pi / 2, 0)
    r.location = (x, Y_WHEEL, Z_WHEEL)
    p = importer(f"pneu_{cote}", os.path.join(V3, "coin_tire.stl"), M_CAOUT)
    p.rotation_euler = (0, math.pi / 2, 0)
    p.location = (x + sx * 4.5, Y_WHEEL, Z_WHEEL)
    roues.append(r)
    pneus.append(p)

# pivot d'équilibrage : le corps bascule autour de l'axe des roues
bpy.ops.object.empty_add(location=PIVOT)
pivot = bpy.context.object
pivot.name = "pivot"
for o in corps:
    o.parent = pivot
    o.matrix_parent_inverse = pivot.matrix_world.inverted()

# directions d'éclatement (par pièce)
ECLATE = {
    "b_front": Vector((0, 62, 0)),
    "b_back": Vector((0, -62, 0)),
    "carte": Vector((0, 46, 0)),
    "ecran": Vector((0, 58, 0)),
    "mpu": Vector((0, 34, 12)),
    "hc_sr04": Vector((0, 52, 0)),
    "transducteur_D": Vector((0, 66, 0)),
    "transducteur_G": Vector((0, 66, 0)),
    "batterie": Vector((0, -46, 0)),
    "oeil_G": Vector((0, 74, 0)),
    "oeil_D": Vector((0, 74, 0)),
    "servo_pied_D": Vector((-42, 22, 0)),
    "servo_pied_D_bride": Vector((-30, 22, 0)),
    "servo_pied_G": Vector((42, 22, 0)),
    "servo_pied_G_bride": Vector((30, 22, 0)),
    "servo_tete_0": Vector((0, 58, 26)),
    "servo_tete_1": Vector((0, 58, 26)),
    "roue_D": Vector((-58, 0, 0)),
    "roue_G": Vector((58, 0, 0)),
    "pneu_D": Vector((-92, 0, 0)),
    "pneu_G": Vector((92, 0, 0)),
}

# ══════════════════════════════════════════════════════════════════════════
# mise en scène : sol, lumières, environnement sombre
# ══════════════════════════════════════════════════════════════════════════
bpy.ops.mesh.primitive_plane_add(size=1400, location=(X_MID, 0, 0))
sol = bpy.context.object
sol.name = "sol"
habiller(sol, metal("sol", (0.012, 0.012, 0.014), 0.18))

monde = bpy.context.scene.world or bpy.data.worlds.new("World")
bpy.context.scene.world = monde
monde.use_nodes = True
fond = monde.node_tree.nodes["Background"]
fond.inputs[0].default_value = (0.055, 0.045, 0.045, 1.0)
fond.inputs[1].default_value = 1.0


def lampe(nom, pos, energie, taille, couleur=(1.0, 0.55, 0.25)):
    bpy.ops.object.light_add(type="AREA", location=pos)
    o = bpy.context.object
    o.name = nom
    o.data.energy = energie
    o.data.size = taille
    o.data.color = couleur
    o.rotation_euler = (Vector((X_MID, 0, 80)) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    return o


lampe("cle_orange", (200, -220, 260), 1700000, 240, (1.0, 0.48, 0.18))
lampe("contre_blanc", (-160, 200, 200), 950000, 200, (0.85, 0.88, 1.0))
lampe("rasante_chaude", (60, -300, 60), 620000, 150, (1.0, 0.62, 0.30))
lampe("dessus_froid", (X_MID, 40, 420), 750000, 300, (0.75, 0.82, 1.0))

# ══════════════════════════════════════════════════════════════════════════
# caméra : orbite parentée à un pivot, distance pilotée
# ══════════════════════════════════════════════════════════════════════════
bpy.ops.object.empty_add(location=(X_MID, 0, 88))
orbite = bpy.context.object
orbite.name = "orbite"
bpy.ops.object.camera_add(location=(0, 0, 0))
cam = bpy.context.object
cam.data.lens = 62
cam.parent = orbite
scene = bpy.context.scene
scene.camera = cam


def viser(objet, cible=(X_MID, 0, 88)):
    objet.rotation_euler = (Vector(cible) - Vector(objet.location)).to_track_quat("-Z", "Y").to_euler()


# ══════════════════════════════════════════════════════════════════════════
# rendu
# ══════════════════════════════════════════════════════════════════════════
def configurer_moteur():
    scene.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    choisi = None
    for type_ in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = type_
            prefs.refresh_devices()
            prefs.get_devices()
            gpus = [d for d in prefs.devices if d.type != "CPU"]
            if gpus:
                for d in prefs.devices:
                    d.use = d.type != "CPU"
                scene.cycles.device = "GPU"
                choisi = f"{type_} → {', '.join(d.name for d in gpus)}"
                break
        except Exception as exc:
            print(f"[GPU] {type_} indisponible : {exc}")
    if choisi is None:
        scene.cycles.device = "CPU"
        print("[GPU] AUCUN GPU UTILISABLE — rendu CPU (lent)")
    else:
        print(f"[GPU] rendu sur {choisi}")
    scene.cycles.samples = 32
    scene.render.use_persistent_data = True     # réutilise la scène entre les images
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 8
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "Standard"


def placer_camera(angle_deg, distance, hauteur, cible_hauteur=104):
    """angle 0 = face (+Y), 90 = côté droit. Positions dans le repère de l'orbite
    (l'orbite est à z=88 : on retranche cette altitude pour rester homogène)."""
    a = math.radians(angle_deg)
    local = Vector((math.sin(a) * distance, math.cos(a) * distance, hauteur - 88.0))
    cam.location = local
    cible = Vector((0.0, 0.0, cible_hauteur - 88.0))
    cam.rotation_euler = (cible - local).to_track_quat("-Z", "Y").to_euler()


# ══════════════════════════════════════════════════════════════════════════
if MODE == "still":
    configurer_moteur()
    scene.cycles.samples = 256
    scene.render.resolution_x = 2560
    scene.render.resolution_y = 1440
    placer_camera(0.0, 800, 120, 104)
    scene.render.filepath = os.path.join(OUT, "hero_face.png")
    bpy.ops.render.render(write_still=True)
    print("RENDU →", scene.render.filepath)
    raise SystemExit(0)

# ── mode cinématique ──────────────────────────────────────────────────────
configurer_moteur()
scene.cycles.samples = 32
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.fps = FPS
FRAMES = os.path.join(OUT, "frames")
os.makedirs(FRAMES, exist_ok=True)
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = os.path.join(FRAMES, "f_")
scene.frame_start = 1
scene.frame_end = F_FIN

# orbite : tour complet lent pendant la phase A
for f, angle in ((1, -30), (F_ORBITE_END, 250)):
    orbite.rotation_euler = (0, 0, math.radians(angle))
    orbite.keyframe_insert("rotation_euler", frame=f)
# la caméra recule pendant l'éclatement puis revient pour la démonstration
for f, (dist, haut) in ((1, (760, 112)), (F_ORBITE_END, (760, 112)),
                        (F_ECLATE_END, (1120, 190)), (F_REMONTE_END, (860, 135)),
                        (F_FIN, (780, 115))):
    placer_camera(0, dist, haut)
    cam.location = cam.location  # position dans le repère de l'orbite
    cam.keyframe_insert("location", frame=f)

# éclatement / remontage de chaque pièce
pieces = {o.name: o for o in bpy.data.objects if o.type == "MESH" and o.name in ECLATE}
for nom, obj in pieces.items():
    d = ECLATE[nom]
    pos_a = Vector(obj.matrix_parent_inverse @ Vector(obj.location)) if obj.parent else Vector(obj.location)
    pos_a = Vector(obj.location)
    pos_e = pos_a + d
    for f, p in ((1, pos_a), (F_ORBITE_END, pos_a), (F_ECLATE_END, pos_e), (F_REMONTE_END, pos_a)):
        obj.location = p
        obj.keyframe_insert("location", frame=f)

# phase D : le robot fonctionne
# roues qui tournent
for r in roues:
    base = r.rotation_euler.copy()
    for f, tours in ((F_REMONTE_END, 0.0), (F_REMONTE_END + 90, 1.0), (F_FIN, 3.2)):
        r.rotation_euler = (base[0] + tours * 2 * math.pi, base[1], base[2])
        r.keyframe_insert("rotation_euler", frame=f)
# équilibrage : le corps tangue doucement autour de l'axe des roues
for f, deg in ((F_REMONTE_END, 0), (F_REMONTE_END + 45, 3.2), (F_REMONTE_END + 90, -3.0),
               (F_REMONTE_END + 135, 2.2), (F_FIN, 0.0)):
    pivot.rotation_euler = (math.radians(deg), 0, 0)
    pivot.keyframe_insert("rotation_euler", frame=f)
# tête qui balaie
for o in (hc, transducteurs[0], transducteurs[1]):
    for f, deg in ((F_REMONTE_END, 0), (F_REMONTE_END + 60, 11), (F_REMONTE_END + 120, -11), (F_FIN, 0)):
        o.rotation_euler = (0, 0, math.radians(deg))
        o.keyframe_insert("rotation_euler", frame=f)
# clignement des yeux
for o in yeux:
    base = o.scale.copy()
    for f, k in ((F_REMONTE_END, 1.0), (F_REMONTE_END + 40, 1.0), (F_REMONTE_END + 44, 0.12),
                 (F_REMONTE_END + 48, 1.0), (F_FIN - 30, 1.0), (F_FIN - 26, 0.12), (F_FIN - 22, 1.0)):
        o.scale = (base[0], base[1], base[2] * k)
        o.keyframe_insert("scale", frame=f)

# (Interpolation : laissée à Bézier/EASE AUTO, le défaut de Blender. Le réglage
#  explicite `action.fcurves` a été retiré par Blender 5 — API « slots ».)

scene.frame_set(1)
bpy.ops.render.render(animation=True)
print("RENDU →", scene.render.filepath)
