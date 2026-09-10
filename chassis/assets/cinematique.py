#!/usr/bin/env python3
"""BalanceBot — rendu « métal orange & noir » : image fixe HD + cinématique.

Deux modes :
    blender -b -P cinematique.py -- still     → image fixe haute définition (de face)
    blender -b -P cinematique.py -- cine      → vidéo : orbite → éclaté → remontage → en marche

Réutilise le placement de chassis/assets/vue_eclatee.py (cotes réelles du projet).
Matériaux : orange métallisé (coques), noir métallisé (roues/pneus), aluminium
(transducteurs HC-SR04), sol noir brillant. L'écran du LilyGo est ÉMISSIF et
ANIMÉ : chassis/assets/ecran_firmware.py génère une séquence 320×170 fidèle au
firmware (écran de commande manuel, puis le visage en auto-équilibre).

Sorties : chassis/render/hero_face.png  et  chassis/render/cinematique.mp4
"""
import math
import os
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V3 = os.path.join(ROOT, "chassis", "v3")
OUT = os.path.join(ROOT, "chassis", "render")
os.makedirs(OUT, exist_ok=True)

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = argv[0] if argv else "still"
# plage d'images optionnelle pour les essais : `-- cine 560 566`
DEB, FIN = (int(argv[1]), int(argv[2])) if len(argv) >= 3 and argv[1].isdigit() else (1, None)

# ── cotes du projet — SOURCE : chassis/gen_bitcoin_bot.py ─────────────────
# AXLE_Z = WHEEL_R = WHEEL_D/2 − GROOVE_D + TIRE_T = 40 − 0.5 + 2.5 = 42.0
AXLE_Z = 42.0
X_MID = 64.57          # centre de l'enveloppe du corps (mesuré sur b_front)
Y_AXLE = 0.0           # l'axe des roues est dans le plan de joint (y = 0)
# Roues : origine = FACE EXTERNE du disque imprimé (cf. assemblage_pour_rendu) ; le
# moyeu (13 mm) part vers l'intérieur, son bout tombe sur le plan de la paroi
# (xL = GW − x_wall_R + 1 = 12.13 ; xR = GW − 1 = 117.0).
# « D » = côté paroi courbe (x≈11) ; « G » = côté spine (x≈118).
ROUE = {"D": (-8.87, +1), "G": (138.00, -1)}       # (x origine, sens du moyeu)
PNEU = {"D": -8.37, "G": 137.50}                   # origine de la bande TPU
SERVO = {"D": 24.93, "G": 104.35}                  # x du centre du corps de servo
SERVO_BRIDE = {"D": 13.53, "G": 115.60}            # x de la platine (côté sortie)
SERVO_Z = 47.50                # corps z∈[36.1, 58.9] → arbre à 42 (= axe)
X_SCREEN, Z_SCREEN = 58.5, 72.0    # counter_center(LOW) → miroir : 118 − 59.5
X_HEAD, Z_HEAD, SR_PITCH = 64.4, 145.0, 26.0       # counter_center(HIGH) miroir
MPU_CENTRE = (80.0, 0.0, 41.0)     # GW − MPU_X = 80 ; dessus du piédestal à z=42
Z_WHEEL, Y_WHEEL = AXLE_Z, Y_AXLE  # alias (noms historiques)
FPS = 30
F_ORBITE_END, F_ECLATE_END, F_REMONTE_END, F_FIN = 240, 420, 570, 780

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import demo_timeline as TL  # noqa: E402  (chronologie partagée avec l'écran)

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
# HC-SR04 réel : culs de transducteurs en aluminium, grille sombre en façade
M_ALU = metal("aluminium_transducteur", (0.72, 0.73, 0.76), 0.30)
M_GRILLE = metal("grille_transducteur", (0.055, 0.055, 0.06), 0.55, metallic=0.7)


def materialiser_ecran(fichier_sequence):
    """Dalle ST7789 320×170 dont l'ÉMISSION est une séquence d'images : c'est
    l'écran réel du firmware (écran de commande → visage en auto)."""
    m = bpy.data.materials.new("ecran_anime")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.01, 0.01, 0.012, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.18
    bsdf.inputs["Emission Strength"].default_value = 0.9
    img = bpy.data.images.load(fichier_sequence)
    img.source = "SEQUENCE"
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.extension = "CLIP"
    tex.image_user.use_auto_refresh = True
    tex.image_user.frame_start = 1
    tex.image_user.frame_duration = 780
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
    return m


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


def dalle(nom, largeur, hauteur, centre, mat):
    """Dalle = PLAN (et non un cube) : le plan a un UV 0→1 sur toute sa surface,
    alors que le cube par défaut de Blender a un dépliage en CROIX — la texture
    n'en affichait qu'un fragment (gros triangle orange au lieu de l'interface)."""
    bpy.ops.mesh.primitive_plane_add(size=1, location=centre,
                                     rotation=(math.pi / 2, 0, 0))
    o = bpy.context.object
    o.name = nom
    o.scale = (largeur, hauteur, 1.0)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    # U inversé : devant le robot, l'axe +X du monde tombe à GAUCHE de l'image
    # (caméra en +Y) → sans ce miroir, l'interface s'affiche en miroir.
    for boucle in o.data.uv_layers.active.data:
        boucle.uv.x = 1.0 - boucle.uv.x
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
# ensemble mécanique — placement aux cotes EXACTES du générateur de châssis
# ══════════════════════════════════════════════════════════════════════════
PIVOT = (X_MID, Y_AXLE, AXLE_Z)          # axe d'équilibrage = axe des roues

corps = []
front = importer("b_front", os.path.join(V3, "b_front.stl"), M_ORANGE)
back = importer("b_back", os.path.join(V3, "b_back.stl"), M_ORANGE_FONCE)
corps += [front, back]

# T-Display S3 : PCB 62 × 26 dans sa poche, dalle 1,9" 320×170 devant la fenêtre
# (zone active 40,8 × 21,7 mm). L'écran est ANIMÉ : une séquence d'images
# reproduit le firmware — écran de commande, puis le visage en auto-équilibre.
carte = boite("carte", (62.0, 1.2, 26.0), (X_SCREEN, 18.0, Z_SCREEN), M_NOIR)
ecran = dalle("ecran", 40.8, 21.7, (X_SCREEN, 19.6, Z_SCREEN),
              materialiser_ecran(os.path.join(OUT, "ecran", "ecran_0001.png")))

# MPU6050 : piédestal dont le dessus est à z = 42 (l'axe de tangage), centré en y = 0
mpu = boite("mpu", (21.0, 16.0, 2.0), MPU_CENTRE, M_SERVO)
# HC-SR04 : PCB 45 × 20 debout derrière les 2 trous Ø16,6 (entraxe 26) de la baie haute
hc = boite("hc_sr04", (45.0, 1.6, 20.0), (X_HEAD, 12.0, Z_HEAD), M_NOIR)
transducteurs = []
for sx in (-1, 1):
    cote = "D" if sx < 0 else "G"
    x = X_HEAD + sx * SR_PITCH / 2
    # culot aluminium (Ø16, comme le vrai composant) + grille sombre en façade
    transducteurs.append(cylindre(f"transducteur_{cote}", 8.0, 10.0,
                                  (x, 18.0, Z_HEAD), M_ALU, "Y"))
    transducteurs.append(cylindre(f"cage_{cote}", 6.5, 0.6,
                                  (x, 23.1, Z_HEAD), M_GRILLE, "Y"))
corps += [carte, ecran, mpu, hc] + transducteurs

# 2 servos de roue (le design n'en comporte aucun autre) : couchés, axe selon X,
# corps dans la cavité (z 36,1 → 58,9 ; arbre à 42), sortie au travers de la paroi.
servos = []
for cote in ("D", "G"):
    servos.append(boite(f"servo_pied_{cote}", (22.5, 12.2, 22.8),
                        (SERVO[cote], Y_AXLE, SERVO_Z), M_SERVO))
    servos.append(boite(f"servo_pied_{cote}_bride", (2.5, 12.2, 32.2),
                        (SERVO_BRIDE[cote], Y_AXLE, SERVO_Z), M_SERVO))
corps += servos

# roues et bandes TPU — positions du générateur ; elles tournent autour de l'axe X
roues, pneus = [], []
for cote in ("D", "G"):
    x, sens = ROUE[cote]
    r = importer(f"roue_{cote}", os.path.join(V3, "coin_wheel.stl"), M_NOIR)
    r.rotation_mode = "QUATERNION"
    r.rotation_quaternion = Quaternion((0, 1, 0), sens * math.pi / 2)
    r.location = (x, Y_AXLE, AXLE_Z)
    p = importer(f"pneu_{cote}", os.path.join(V3, "coin_tire.stl"), M_CAOUT)
    p.rotation_mode = "QUATERNION"
    p.rotation_quaternion = Quaternion((0, 1, 0), sens * math.pi / 2)
    p.location = (PNEU[cote], Y_AXLE, AXLE_Z)
    roues.append(r)
    pneus.append(p)

# ── hiérarchie PHYSIQUE ───────────────────────────────────────────────────
# `robot` : porte le déplacement et le cap (le contact au sol).
# `pivot` : enfant de `robot`, porte l'ASSIETTE — le corps penche autour de
#           l'axe des roues pour tenir l'équilibre.
# roues   : enfants de `robot` SEULEMENT : elles roulent et pivotent avec lui
#           mais ne penchent pas avec le corps. C'est ce qui est vrai.
bpy.ops.object.empty_add(location=PIVOT)
robot = bpy.context.object
robot.name = "robot"

bpy.ops.object.empty_add(location=(0.0, 0.0, 0.0))
pivot = bpy.context.object
pivot.name = "pivot"
pivot.parent = robot
# le pivot est à l'origine LOCALE du robot (qui est déjà sur l'axe des roues) :
# son inverse de parent doit donc rester l'IDENTITÉ. Y mettre PIVOT⁻¹ en plus
# décale tout le corps (mesuré : dalle à (-6,07 ; 19,6 ; 30) au lieu de
# (58,5 ; 19,6 ; 72)) — les pièces partent avec le pivot, les roues non, et le
# robot se retrouve monté de travers.
pivot.matrix_parent_inverse = Matrix.Identity(4)
inv_robot = Matrix.Translation(PIVOT).inverted()

for o in corps:
    o.parent = pivot
    o.matrix_parent_inverse = inv_robot
for o in roues + pneus:
    o.parent = robot
    o.matrix_parent_inverse = inv_robot

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
    # PAS de use_persistent_data : avec des objets animés, Cycles reconstruit de
    # toute façon et la donnée persistante le fait s'effondrer (5 min/image au
    # lieu de 2 s). Mesuré : image fixe 2560×1440 @128 éch. = 20 s sans lui.
    scene.render.use_persistent_data = False
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
    scene.cycles.samples = 128
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
scene.frame_start = DEB
scene.frame_end = FIN or F_FIN

# ── CAMÉRA : gros plan d'ouverture sur l'écran (l'interface doit être lisible),
#    puis on SUIT le robot pendant la démonstration — suivi PARTIEL (60 %) pour
#    qu'il se déplace dans le cadre au lieu de rester collé au centre — et gros
#    plan final sur l'écran. L'azimut vient de la rotation Z de l'orbite ;
#    placer_camera() ne fournit que la distance et la hauteur (angle 0, sinon
#    l'angle est compté deux fois).
CAM_KEYS = (
    (1,     0.0,  115,  72,  72, 1.0),   # gros plan : écran de commande, IDLE
    (70,    0.0,  115,  72,  72, 1.0),   # on tient le plan
    (150,   8.0,  680, 122, 104, 0.8),   # recul : robot entier
    (215,  14.0,  760, 128, 104, 0.7),   # il hésite (l'assiette oscille)
    (310,  18.0,  830, 120, 108, 0.6),   # IL AVANCE
    (400,  20.0,  800, 118, 106, 0.6),   # il freine, puis recule
    # PENDANT LES VIRAGES LA CAMÉRA GARDE SON AZIMUT : c'est ce qui rend le
    # lacet lisible à l'image. Si elle orbitait dans le même sens que le robot,
    # les deux rotations s'annuleraient et il paraîtrait toujours de face.
    (505,  22.0,  780, 115, 100, 0.6),   # virage
    (620,  24.0,  800, 118, 100, 0.6),   # contre-virage
    (706,  20.0,  700, 118, 100, 0.7),   # il se stabilise
    (780,   2.0,  240,  92,  78, 1.0),   # gros plan final : l'écran lisible
)
for f, angle, dist, haut, cible, suivi in CAM_KEYS:
    tx, ty = TL.position(f)
    orbite.location = (X_MID + suivi * tx, suivi * ty, 88.0)
    orbite.keyframe_insert("location", frame=f)
    orbite.rotation_euler = (0, 0, math.radians(angle))
    orbite.keyframe_insert("rotation_euler", frame=f)
    placer_camera(0.0, dist, haut, cible)
    cam.keyframe_insert("location", frame=f)

# ── DÉMONSTRATION : le robot roule, tourne et tient son équilibre ───────────
# Tout sort de chassis/assets/demo_timeline.py — le MÊME fichier qui dessine
# l'écran : le mouvement et l'affichage ne peuvent pas se désynchroniser.
# Échantillonnage toutes les 2 images : l'assiette porte une micro-oscillation
# permanente, des clés éparses la lisseraient et tueraient l'effet « il hésite ».
for f in range(1, (FIN or F_FIN) + 1, 2):
    tx, ty = TL.position(f)
    robot.location = (PIVOT[0] + tx, PIVOT[1] + ty, PIVOT[2])
    robot.rotation_euler = (0.0, 0.0, math.radians(TL.lacet(f)))
    robot.keyframe_insert("location", frame=f)
    robot.keyframe_insert("rotation_euler", frame=f)

    # signe : dans le repère de Blender, une rotation +X fait basculer le HAUT du
    # corps vers −Y, soit vers l'ARRIÈRE (le robot regarde +Y). Le tangage du
    # fichier est exprimé « + = vers l'avant », donc on l'inverse ici.
    pivot.rotation_euler = (-math.radians(TL.tangage(f)), math.radians(TL.roulis(f)), 0.0)
    pivot.keyframe_insert("rotation_euler", frame=f)

    # les deux roues tournent à des vitesses DIFFÉRENTES en virage, et leur
    # rotation colle à la distance parcourue (sinon on les voit patiner)
    tr_g, tr_d = TL.tours_roue(f)
    for obj, tours, cote in ((roues[0], tr_d, "D"), (roues[1], tr_g, "G"),
                             (pneus[0], tr_d, "D"), (pneus[1], tr_g, "G")):
        sens = ROUE[cote][1]
        base = Quaternion((0, 1, 0), sens * math.pi / 2)
        obj.rotation_quaternion = Quaternion((1, 0, 0), tours * 2 * math.pi) @ base
        obj.keyframe_insert("rotation_quaternion", frame=f)

# (Interpolation : laissée à Bézier/EASE AUTO, le défaut de Blender. Le réglage
#  explicite `action.fcurves` a été retiré par Blender 5 — API « slots ».)

scene.frame_set(1)
bpy.ops.render.render(animation=True)
print("RENDU →", scene.render.filepath)
