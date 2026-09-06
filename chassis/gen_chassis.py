#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BalanceBot — châssis paramétrique pour robot auto-équilibré 2 roues.

    blender --background --python gen_chassis.py
    blender --background --python gen_chassis.py -- --no-preview

1 unité Blender = 1 mm.

CONVENTION D'AXES (robot debout)
    X = axe des roues (gauche −X / droite +X)
    Y = profondeur, +Y = AVANT du robot (l'écran regarde +Y)
    Z = vertical, +Z = haut ; Z = 0 au sol (bas des roues)

Toutes les cotes matérielles proviennent de mesures faites sur les modèles de
référence (cf. FIT_NOTES.md), pas de suppositions :
  - carte nue      : /tmp/t-display-s3-ref/dimensions/t-display-s3-full.stl
  - coque Touch    : /tmp/touch-3d/files/v5/T-Display-S3-Touch_V5 v36.step
"""

import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

ICI = os.path.dirname(os.path.abspath(__file__))

# =============================================================================
#  TOLÉRANCES ET RÈGLES D'IMPRESSION (buse 0.4, PLA)
# =============================================================================
SLIDING_FIT = 0.15     # pièce qui coulisse / se pose sans jeu perceptible
CLEARANCE_FIT = 0.30   # passage libre, insertion sans effort
PRESS_FIT = 0.05       # emmanchement serré
HOLE_BONUS = 0.30      # alésage imprimé = Ø réel + 0.30 (valable Ø <= 10)

WALL = 2.4             # mur courant = 6 x 0.4 (mini imposé 2.0)
WALL_FIN = 2.0         # mur mince (cloisons internes)
CHAM = 1.2             # chanfrein 45° générique (anti-support)
EPS = 0.01             # débord pour que les booléens ne laissent pas de peau

# =============================================================================
#  SERVO SG90 (x4 : 2 roues à rotation continue, 2 tête)
# =============================================================================
SV_L = 22.8            # longueur du corps
SV_W = 12.2            # largeur du corps
SV_H = 22.5            # hauteur du corps (bas -> face de sortie)
SV_FLANGE_Z = 15.9     # hauteur du DESSOUS des pattes depuis le bas du corps
SV_FLANGE_T = 2.5      # épaisseur des pattes
SV_TAB_SPAN = 32.2     # longueur hors-tout pattes comprises
SV_HOLE_PITCH = 27.8   # entraxe des 2 trous de pattes
SV_SHAFT_OFF = 5.9     # axe de sortie, depuis l'extrémité "avant" du corps
SV_SHAFT_D = 4.8       # Ø de l'axe cannelé
SV_SHAFT_PROJ = 4.5    # dépassement de l'axe au-dessus de la face supérieure
SV_BOSS_D = 11.8       # bossage circulaire autour de l'axe
SV_BOSS_H = 1.5
SV_PILOT_D = 1.7       # avant-trou pour vis M2 autotaraudeuse dans le PLA

# Logement : le corps traverse une lumière, les pattes portent SUR la plaque.
SV_SLOT_L = SV_L + CLEARANCE_FIT      # 23.10
SV_SLOT_W = SV_W + CLEARANCE_FIT      # 12.50
SV_POCKET_L = SV_L + SLIDING_FIT      # berceau qui enserre le corps
SV_POCKET_W = SV_W + SLIDING_FIT

# =============================================================================
#  ROUES (x2) — OBSOLÈTE depuis la v2 : remplacées par les PIEDS EN ARC.
#  Les cotes restent la référence d'implantation (rayon, largeur, position X)
#  car le corps n'a PAS changé de géométrie externe.
# =============================================================================
WHEEL_D = 65.0
WHEEL_R = WHEEL_D / 2.0
WHEEL_W = 9.0
RIM_T = 3.0                                  # bandeau extérieur plein et lisse
HUB_D = 14.0                                 # Ø extérieur du moyeu
HUB_BORE_D = SV_SHAFT_D + 0.4                # 5.2 : alésage sur axe Ø4.8
HUB_CB_D = SV_BOSS_D + 0.6                   # 12.4 : lamage sur le bossage servo
HUB_CB_H = SV_BOSS_H + 0.2                   # 1.7
GRUB_D = 2.2                                 # 2 vis M2 radiales de blocage
SPOKES = 6
SPOKE_T = 3.0
RIM_CHAM = 0.6

# =============================================================================
#  PIED EN ARC (x2 identiques) — servos SG90 STANDARD 180°, pas de rotation
#  continue. Le pied est une portion de couronne qui roule sur le sol comme un
#  patin ; le débattement +/-90° du servo est entièrement couvert par l'arc.
# =============================================================================
FOOT_R = WHEEL_R              # 32.5 : rayon extérieur, inchangé
FOOT_W = WHEEL_W              # 9.0  : largeur, inchangée
FOOT_SPAN = 200.0             # ouverture angulaire de l'arc (+/-100° au neutre)
FOOT_RIM_T = 3.2              # bande de roulement PLEINE et lisse
FOOT_HUB_D = 18.0             # moyeu central
FOOT_RIB_T = 3.2              # nervure radiale
FOOT_RIBS = 5                 # dont une à chaque extrémité de l'arc
FOOT_BAND_R0 = 19.0           # arc intermédiaire de rigidification
FOOT_BAND_R1 = 22.2
# --- empreinte du palonnier (horn) SG90 ------------------------------------
# L'axe cannelé 25 dents ne se reprend PAS directement : on visse le palonnier
# fourni sur l'axe (vis M2 centrale), puis le pied sur le palonnier. L'empreinte
# est donc du côté SERVO (face interne) — c'est la seule face qui puisse
# l'accueillir, l'axe ne dépassant que de 4.2 mm dans l'épaisseur du pied.
HORN_ARM_W = 5.0 + SLIDING_FIT    # 5.15 : largeur d'un bras du palonnier
HORN_ARM_R = 10.0                 # longueur d'un bras depuis le centre
HORN_HUB_D = SV_BOSS_D + 0.6      # 12.4 : dégage aussi le bossage du servo
HORN_POCKET_D = 3.4               # profondeur de l'empreinte (face interne)
HORN_RELIEF_D = 8.0               # dégagement de la vis centrale du palonnier
HORN_RELIEF_H = 2.2
HORN_SCREW_R = 5.0                # entraxe nominal des vis du palonnier
HORN_SCREW_D = 2.2                # M2 passant
HORN_SLOT_DR = 1.3                # +/- 1.3 mm d'oblong : absorbe l'incertitude

# =============================================================================
#  CARTE LILYGO T-DISPLAY S3 (TOUCH) — carte NUE, mesurée
#  Repère carte : 60.78 = longueur, 25.95 = largeur, 9.88 = épaisseur totale.
#  Montée en PAYSAGE : longueur -> X du robot, largeur -> Z, épaisseur -> Y.
# =============================================================================
PCB_LEN = 60.78        # bord à bord (mesuré : Y 0.00..60.78)
PCB_WID = 25.51        # (mesuré : X -12.75..12.75)
PCB_T = 1.20           # épaisseur du circuit imprimé seul (z -1.20..0.00)
PCB_BACK = 5.18        # saillie des composants arrière (z -6.38..-1.20)
PCB_FRONT = 3.50       # dalle + nappe tactile en façade (z 0.00..+3.50)
PCB_BARE_END = 8.03    # zone de PCB nu au bout opposé à l'USB (Y 52.75..60.78)
USB_W = 8.09           # USB-C : X -4.18..3.91 mesuré
USB_H = 3.60           # débattement vertical de la prise
CARD_CL = SLIDING_FIT  # jeu d'insertion de la carte dans son berceau
# Trous de fixation RÉELS mesurés au plan médian du PCB : Ø1.95 à
# (-10.09, 57.66) et (+9.92, 57.66) -> entraxe 20.01 mm, dans la zone nue.
PCB_FIX_D = 2.40           # M2 passant imprimé (2.0 + 0.4)
PCB_FIX_PILOT = SV_PILOT_D  # 1.7 : autotaraudage M2 dans le plot imprimé
PCB_FIX_Y = 57.66          # position le long de la LONGUEUR de la carte
PCB_FIX_X = (-10.09, 9.92)  # positions le long de la LARGEUR
# La dalle + le tactile couvrent quasiment toute la face avant : le verre
# n'est en retrait que de 0.23 mm sur un grand côté. AUCUNE lèvre frontale
# n'est donc possible ailleurs que sur les 8 mm de PCB nu.
GLASS_W = 24.01        # verre : X -11.49..12.52
GLASS_L = 52.53        # verre : Y 0.22..52.75
SHROUD_Y0 = 6.66       # composants arrière : Y 6.66..56.53
SHROUD_Y1 = 56.53

# =============================================================================
#  MPU6050 (GY-521) — le plus près possible de l'axe des roues
# =============================================================================
MPU_L = 21.0
MPU_W = 16.0
MPU_T = 2.0
MPU_HOLE_D = 2.2       # 2 vis M2
MPU_HOLE_PITCH = 15.0  # entraxe le long de la longueur

# =============================================================================
#  HC-SR04
# =============================================================================
SR_L = 45.0
SR_W = 20.0
SR_T = 15.0            # transducteurs compris
SR_PCB_T = 1.6
SR_CAN_D = 16.0        # Ø des capsules
SR_CAN_PITCH = 26.0    # entraxe des 2 capsules
# Demi-largeur de la zone à laisser TOTALEMENT libre devant le capteur : les
# capsules Ø16 d'entraxe 26 occupent x = -21 .. +21 ; on dégage x = -16 .. +16,
# c'est-à-dire tout l'espace ENTRE les deux capsules et leur moitié interne.
# Au-delà (|x| > 16) le berceau peut tenir le PCB par ses bords.
SR_FREE_HX = 16.0

# =============================================================================
#  IMPLANTATION GÉNÉRALE DU ROBOT
# =============================================================================
AXLE_Z = WHEEL_R                 # 32.5 : axe des roues
BODY_HW = 25.0                   # demi-largeur du socle = face ext. des plaques
BODY_Y0 = -20.0                  # arrière
BODY_Y1 = 10.0                   # avant
BODY_Z0 = 20.0                   # dessous du socle (12.5 mm de garde au sol)
BODY_Z1 = 148.0                  # dessus du corps = assise de la tête

BASE_Z1 = 42.0                   # haut du socle droit (au-dessus des servos)
CORBEL_Z1 = 50.0                 # fin du raccord 45° socle -> mât
# Raccord de la CAVITÉ. La pente doit rester >= 45° AUSSI dans le plan (Y, Z),
# car body_a s'imprime couchée (axe de construction = Y) : la face avant de la
# cavité devient alors un surplomb. De 10.4 mm en Y sur (50 - 40) = 10 mm en Z,
# soit 46.1° — auto-portant. (v1 : 38.0 -> 40.9°, insuffisant couché.)
CAV_TAPER_Z0 = 40.0              # raccord de la CAVITÉ (pente > 45°)
CAV_TAPER_Z1 = 50.0
DECK_T = WALL                    # épaisseur mini du plancher haut
MAST_HW = 20.0                   # demi-largeur du mât
# Le DOS du mât est aligné sur le dos du socle : le corps présente ainsi une
# face arrière PLANE unique (Y = -20) de z = 20 à z = 148. C'est cette face
# qui sert de plateau d'impression à la moitié arrière (body_b).
MAST_Y0 = BODY_Y0                # -20.0 (v1 : -18.0)
MAST_Y1 = 2.0
HEAD_HW = 33.0                   # demi-largeur de l'épaulement porte-carte
FLARE_Z0 = 94.0                  # début de l'évasement 45°
FLARE_Z1 = FLARE_Z0 + (HEAD_HW - MAST_HW)   # 107.0 : pente exactement 45°

# =============================================================================
#  PLAN DE JOINT AVANT / ARRIÈRE — le corps est livré en DEUX moitiés
#  --------------------------------------------------------------------------
#  Le joint est le plan Y = MAST_Y1 - WALL = -0.4, c'est-à-dire la FACE
#  INTERNE de la paroi avant du mât et du caisson. C'est le SEUL plan qui donne
#  à chacune des deux moitiés une grande face rigoureusement plane à poser sur
#  le plateau, cavités ouvertes vers le haut :
#    body_a (AVANT)   : posée SUR LE PLAN DE JOINT (Y = -0.4), construction +Y.
#                       Empreinte 66 x 128 mm, hauteur 11.4 mm.
#    body_b (ARRIÈRE) : posée sur son DOS PLAN (Y = -20), construction +Y.
#                       Empreinte 66 x 128 mm, hauteur 19.6 mm.
#  Aucun support, aucun volume clos : chaque cavité débouche sur le joint.
# =============================================================================
Y_JOINT = MAST_Y1 - WALL          # -0.4
DOWEL_D = 5.8                     # goujon venu de fonderie sur body_b
DOWEL_BORE_D = 6.0                # alésage correspondant dans body_a (jeu 0.2)
DOWEL_LEN = 7.6                   # longueur du goujon au-delà du joint
ASM_PASS_D = 3.4                  # M3 passant (traverse body_b)
ASM_PILOT_D = 2.6                 # M3 autotaraudeuse (dans body_a)
# Plots de joint : blocs (x0, x1, z0, z1, y1) symétrisés en +/-x. y1 = extension
# vers l'AVANT (au-delà du joint) ; le bloc part toujours du dos (BODY_Y0).
JOINT_BOSS = [
    (9.5, 22.4, 20.0, 26.2, Y_JOINT + DOWEL_LEN + 1.0),  # socle, SOUS les servos
    (22.6, 30.6, 104.0, 116.0, Y_JOINT),                 # caisson, sous la carte
]
# Goujons CYLINDRIQUES Ø5.8 / alésages Ø6 — (x, z) symétrisés  -> 2 goujons.
# Placés dans le gousset du berceau de carte, seule zone haute où body_a a de
# la profondeur (paroi + gousset = 8.2 mm de matière pleine).
JOINT_DOWELS = [(24.0, 108.5)]
# Goujons RECTANGULAIRES au socle — (x, z_centre) symétrisés -> 2 tenons.
# Sous les servos il ne reste que 6.4 mm de hauteur libre (z 20.0 .. 26.4) :
# un tenon 9.0 x 2.9 y tient là où un goujon Ø6 ne tiendrait pas.
JOINT_TENONS = [(17.5, 23.2)]
TEN_W, TEN_H, TEN_CL = 9.0, 2.9, 0.3      # largeur X, hauteur Z, jeu total
# Vis M3 posées PAR L'ARRIÈRE (tête sur la face arrière plane) — (x, z)
# symétrisées -> 4 vis. Le trajet traverse de la matière PLEINE de bout en
# bout : plancher du socle (z 20..22.4) et tablette du berceau de carte.
JOINT_SCREWS = [(5.0, 21.2), (24.0, 112.9)]
# Languette / rainure sur les 2 parois latérales du MÂT : là, body_a se réduit
# à la paroi avant (2.4 mm) et ne peut pas loger de goujon. Un tenon continu
# reprend l'alignement et le cisaillement sur toute la hauteur du mât.
TENON_Z0, TENON_Z1 = 52.0, 92.0
TENON_XC = MAST_HW - WALL / 2.0   # 18.8 : milieu de la paroi latérale
TENON_W = 1.2                     # largeur du tenon
TENON_H = 1.0                     # saillie au-delà du joint
TENON_CL = 0.3                    # jeu de la rainure (largeur ET profondeur)
# Fenêtres de câblage percées dans la paroi avant du caisson, DERRIÈRE la
# carte : les fils soudés sur les pads GPIO plongent dans le caisson (17.2 mm
# de profondeur) puis descendent par le mât. (x0, x1, z0, z1)
CARD_WIRE_WIN = [(-24.0, -7.0, 116.0, 137.0), (17.0, 26.0, 116.0, 137.0)]

# --- DÉRIVÉ : position du servo de roue (côté droit, X > 0) ----------------
SV_PLATE_X1 = BODY_HW                    # 25.0  face extérieure de la plaque
SV_PLATE_X0 = BODY_HW - WALL             # 22.6
SV_CASE_X0 = SV_PLATE_X1 - SV_FLANGE_Z   # 9.10  bas du corps servo
SV_CASE_X1 = SV_CASE_X0 + SV_H           # 31.60 face de sortie
SV_SHAFT_TIP = SV_CASE_X1 + SV_SHAFT_PROJ  # 36.10 bout de l'axe
SV_FLANGE_X0 = SV_PLATE_X1                 # 25.0  les pattes portent sur la plaque
SV_FLANGE_X1 = SV_PLATE_X1 + SV_FLANGE_T   # 27.5
# le servo est posé « axe à Y = 0 » : corps de -16.9 à +5.9
SV_Y0 = -(SV_L - SV_SHAFT_OFF)           # -16.9
SV_Y1 = SV_SHAFT_OFF                     #  +5.9
SV_Z0 = AXLE_Z - SV_W / 2.0              #  26.4
SV_Z1 = AXLE_Z + SV_W / 2.0              #  38.6

# --- DÉRIVÉ : position de la roue -----------------------------------------
WHEEL_X0 = SV_CASE_X1 + 0.3              # 31.9 face interne de la roue
WHEEL_X1 = WHEEL_X0 + WHEEL_W            # 40.9 face externe
WHEEL_CX = (WHEEL_X0 + WHEEL_X1) / 2.0   # 36.4

# --- DÉRIVÉ : berceau de la carte (épaulement avant, haut du corps) -------
# Repère carte -> repère robot :
#   X_robot = Y_carte - PCB_LEN/2     (USB en -X, zone de PCB nu en +X)
#   Z_robot = X_carte + CARD_ZC
#   Y_robot = Z_carte + CARD_PCB_Y    (Z_carte = 0 -> face AVANT du PCB)
CARD_ZC = 127.0                                  # hauteur de l'axe de la carte
CARD_HW = PCB_LEN / 2.0 + CARD_CL                # 30.54 demi-longueur + jeu
CARD_Z0 = CARD_ZC - PCB_WID / 2.0 - CARD_CL      # 114.10 arête basse
CARD_Z1 = CARD_ZC + PCB_WID / 2.0 + CARD_CL      # 139.90 arête haute
CARD_PCB_Y = 9.4                                 # face AVANT du PCB
CARD_PCB_BACK = CARD_PCB_Y - PCB_T               # 8.20 face arrière du PCB
CARD_FRONT_Y = CARD_PCB_Y + PCB_FRONT            # 12.90 avant du verre
CARD_RAIL_Y = 11.0                               # avant des rails de guidage
# zones de PCB nu au DOS (hors capot composants) exploitables en appui
CARD_PAD_XA = -PCB_LEN / 2.0 + SHROUD_Y0 - 0.7   # -24.4  (côté USB)
CARD_PAD_XB = -PCB_LEN / 2.0 + SHROUD_Y1 + 0.7   # +26.8  (côté zone nue)
CARD_FIX_X = -PCB_LEN / 2.0 + PCB_FIX_Y          # +27.27 plots de vis M2
LATCH_X0 = 26.4                                  # verrou : sur la zone nue
LATCH_X1 = CARD_HW
LATCH_H = 3.4                                    # hauteur du crochet

# --- DÉRIVÉ : assise du servo pan (tête) ----------------------------------
PAN_PLATE_Z = BODY_Z1                    # 148.0, face supérieure du corps
PAN_Y = -8.0                             # axe de lacet : centre du mât en Y
PAN_SCREW_X = 26.0                       # 4 vis M3 corps <-> head_pan
PAN_SCREW_Y = (-14.0, -2.0)
PAN_SCREW_D = 3.4                        # M3 passant (3.0 + 0.4)
PAN_SCREW_PILOT = 2.6                    # M3 autotaraudeuse dans le PLA
PAN_PLATE_T = 4.0                        # épaisseur de head_pan

# --- DÉRIVÉ : tête (head_tilt + sensor_mount) -----------------------------
TILT_ARM_X = 16.0                        # demi-écartement des bras du berceau
TILT_ARM_T = 3.0                         # épaisseur d'un bras
TILT_HUB_D = 16.0                        # Ø du moyeu sur l'axe (pan ou tilt)
TILT_HUB_SEAT = SV_BOSS_H                # on porte sur le bossage Ø11.8
IDLER_D = 4.0                            # tourillon libre côté opposé au servo

PARTS = {}   # nom -> objet Blender, rempli par les constructeurs


# =============================================================================
#  OUTILLAGE BPY
# =============================================================================
def raz_scene():
    """Vide la scène (objets + meshes orphelins)."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for m in list(bpy.data.meshes):
        if m.users == 0:
            bpy.data.meshes.remove(m)


def boite(nom, x0, x1, y0, y1, z0, z1):
    """Pavé aligné sur les axes, défini par ses deux coins."""
    me = bpy.data.meshes.new(nom)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x = x0 if v.co.x < 0 else x1
        v.co.y = y0 if v.co.y < 0 else y1
        v.co.z = z0 if v.co.z < 0 else z1
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(nom, me)
    bpy.context.collection.objects.link(ob)
    return ob


def cylindre(nom, diam, long, axe, centre, segments=48):
    """Cylindre de longueur `long` le long de `axe` ('X'|'Y'|'Z'), centré."""
    me = bpy.data.meshes.new(nom)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segments,
                          radius1=diam / 2.0, radius2=diam / 2.0, depth=long)
    if axe == 'X':
        bmesh.ops.rotate(bm, verts=bm.verts,
                         matrix=__import__('mathutils').Matrix.Rotation(
                             math.radians(90), 3, 'Y'))
    elif axe == 'Y':
        bmesh.ops.rotate(bm, verts=bm.verts,
                         matrix=__import__('mathutils').Matrix.Rotation(
                             math.radians(-90), 3, 'X'))
    bmesh.ops.translate(bm, verts=bm.verts, vec=Vector(centre))
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(nom, me)
    bpy.context.collection.objects.link(ob)
    return ob


def prisme(nom, poly, axe, a0, a1):
    """Extrude un polygone 2D (liste de (u, v)) le long de `axe`.

    axe='X' -> (u, v) = (Y, Z) ; axe='Y' -> (X, Z) ; axe='Z' -> (X, Y).
    Sert aux chanfreins 45° et aux goussets anti-support.
    """
    me = bpy.data.meshes.new(nom)
    bm = bmesh.new()
    def pt(u, v, a):
        if axe == 'X':
            return Vector((a, u, v))
        if axe == 'Y':
            return Vector((u, a, v))
        return Vector((u, v, a))
    bas = [bm.verts.new(pt(u, v, a0)) for (u, v) in poly]
    haut = [bm.verts.new(pt(u, v, a1)) for (u, v) in poly]
    bm.faces.new(bas)
    bm.faces.new(list(reversed(haut)))
    n = len(poly)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((bas[i], bas[j], haut[j], haut[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(nom, me)
    bpy.context.collection.objects.link(ob)
    return ob


def booleen(cible, outil, op='DIFFERENCE'):
    """Applique un booléen EXACT puis supprime l'outil."""
    m = cible.modifiers.new(name='bool', type='BOOLEAN')
    m.operation = op
    m.object = outil
    m.solver = 'EXACT'
    bpy.context.view_layer.objects.active = cible
    bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(outil, do_unlink=True)
    return cible


def intersecter(nom, a, b):
    """Intersection booléenne : sert à composer un raccord conique 4 faces
    à partir de deux prismes croisés (X-Z et Y-Z)."""
    a.name = nom
    booleen(a, b, 'INTERSECT')
    return a


def fusionner(nom, objets):
    """Union booléenne d'une liste d'objets -> un seul solide connecté."""
    base = objets[0]
    base.name = nom
    for o in objets[1:]:
        booleen(base, o, 'UNION')
    return base


def soustraire(cible, outils):
    for o in outils:
        booleen(cible, o, 'DIFFERENCE')
    return cible


def dupliquer(ob, nom):
    """Copie indépendante (mesh compris) d'un objet."""
    cp = ob.copy()
    cp.data = ob.data.copy()
    cp.name = nom
    bpy.context.collection.objects.link(cp)
    return cp


def secteur(nom, r, a0, a1, z0, z1, pas=2.0):
    """Prisme en secteur angulaire (centre + arc), degrés, extrudé selon Z."""
    n = max(3, int(round((a1 - a0) / pas)))
    poly = [(0.0, 0.0)]
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        poly.append((r * math.cos(a), r * math.sin(a)))
    return prisme(nom, poly, 'Z', z0, z1)


def miroir_x(ob, nom):
    """Copie miroir d'un objet par rapport au plan YZ."""
    cp = ob.copy()
    cp.data = ob.data.copy()
    cp.name = nom
    bpy.context.collection.objects.link(cp)
    cp.scale.x = -1.0
    bpy.context.view_layer.objects.active = cp
    bpy.ops.object.select_all(action='DESELECT')
    cp.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    cp.select_set(False)
    return cp


def nettoyer(ob):
    """Fusionne les sommets doublons et recalcule les normales."""
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.select_all(action='DESELECT')
    ob.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=1e-4)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    ob.select_set(False)
    return ob


def bbox(ob):
    cs = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    return (min(c.x for c in cs), max(c.x for c in cs),
            min(c.y for c in cs), max(c.y for c in cs),
            min(c.z for c in cs), max(c.z for c in cs))


def exporter(ob, chemin):
    bpy.ops.object.select_all(action='DESELECT')
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    try:
        bpy.ops.wm.stl_export(filepath=chemin, export_selected_objects=True,
                              global_scale=1.0, ascii_format=False,
                              apply_modifiers=True)
    except AttributeError:
        bpy.ops.export_mesh.stl(filepath=chemin, use_selection=True,
                                global_scale=1.0, ascii=False,
                                use_mesh_modifiers=True)
    ob.select_set(False)
    b = bbox(ob)
    print(f"  [STL] {os.path.basename(chemin):18s} "
          f"bbox {b[1]-b[0]:6.2f} x {b[3]-b[2]:6.2f} x {b[5]-b[4]:6.2f} mm "
          f"| {len(ob.data.polygons)} faces")
    return b


def frustum(nom, d0, d1, long, axe, centre, segments=48):
    """Tronc de cône (Ø d0 -> Ø d1) : sert aux chanfreins d'entrée d'alésage."""
    from mathutils import Matrix
    me = bpy.data.meshes.new(nom)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segments,
                          radius1=d0 / 2.0, radius2=d1 / 2.0, depth=long)
    if axe == 'X':
        bmesh.ops.rotate(bm, verts=bm.verts, matrix=Matrix.Rotation(math.radians(90), 3, 'Y'))
    elif axe == 'Y':
        bmesh.ops.rotate(bm, verts=bm.verts, matrix=Matrix.Rotation(math.radians(-90), 3, 'X'))
    bmesh.ops.translate(bm, verts=bm.verts, vec=Vector(centre))
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(nom, me)
    bpy.context.collection.objects.link(ob)
    return ob


def poser(objets, mat):
    """Applique une matrice 4x4 à une liste d'objets (transform_apply)."""
    bpy.ops.object.select_all(action='DESELECT')
    for o in objets:
        o.matrix_world = mat @ o.matrix_world
        o.select_set(True)
    bpy.context.view_layer.objects.active = objets[0]
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.select_all(action='DESELECT')
    return objets


def repere(cols, t):
    """Matrice 4x4 depuis les IMAGES des axes locaux X, Y, Z et une translation.

    Garde-fou : un repère INDIRECT (déterminant -1) est une symétrie, pas une
    rotation. transform_apply inverserait alors les normales de l'outil et le
    booléen DIFFERENCE ne retirerait plus rien. On refuse ce cas.
    """
    from mathutils import Matrix
    (ax, ay, az) = cols
    m = Matrix(((ax[0], ay[0], az[0], t[0]),
                (ax[1], ay[1], az[1], t[1]),
                (ax[2], ay[2], az[2], t[2]),
                (0.0, 0.0, 0.0, 1.0)))
    det = m.to_3x3().determinant()
    if det < 0.99:
        raise ValueError(f"repère indirect (det={det:+.2f}) : "
                         f"utiliser une rotation propre, cols={cols}")
    return m


# =============================================================================
#  BERCEAU SERVO SG90 — outils de découpe génériques
#  Repère local : axe de sortie = +Z ; la face SUPÉRIEURE de la plaque
#  porteuse est en z = 0 ; les pattes reposent dessus (z = 0..SV_FLANGE_T).
#  Corps : X de -SV_SHAFT_OFF à +(SV_L - SV_SHAFT_OFF), Y = ±SV_W/2,
#          z de -SV_FLANGE_Z à (SV_H - SV_FLANGE_Z).
# =============================================================================
SV_BX0 = -SV_SHAFT_OFF                  # -5.9
SV_BX1 = SV_L - SV_SHAFT_OFF            # +16.9
SV_BCX = (SV_BX0 + SV_BX1) / 2.0        # +5.5  centre du corps
SV_SCX0 = SV_BCX - SV_HOLE_PITCH / 2.0  # -8.4  vis 1
SV_SCX1 = SV_BCX + SV_HOLE_PITCH / 2.0  # +19.4 vis 2
SV_TOP_LOCAL = SV_H - SV_FLANGE_Z       # +6.6  face de sortie au-dessus du plan


def outils_servo(prefixe, prof, mat, avec_fil=True):
    """Outils de découpe d'un logement SG90, posés par la matrice `mat`.

    prof : épaisseur de matière à traverser sous le plan de portée (mm).
    Le corps est enserré au SLIDING_FIT (+0.15) : c'est la lumière elle-même
    qui fait berceau, les 2 vis M2 ne font que plaquer les pattes.
    """
    h = SV_POCKET_L / 2.0
    w = SV_POCKET_W / 2.0
    outils = []

    # 1) lumière traversante : le corps y coulisse au SLIDING_FIT
    outils.append(boite(prefixe + '_lumiere',
                        SV_BCX - h, SV_BCX + h, -w, w, -prof - 10.0, EPS))

    # 2) biseau 45° sous la lumière : supprime le plafond horizontal
    outils.append(prisme(prefixe + '_biseau',
                         [(-w - CHAM, EPS), (w + CHAM, EPS),
                          (w, -CHAM), (-w, -CHAM)],
                         'X', SV_BCX - h, SV_BCX + h))

    # 3) avant-trous M2 des pattes (autotaraudage dans le PLA)
    for i, x in enumerate((SV_SCX0, SV_SCX1)):
        outils.append(cylindre(f'{prefixe}_vis{i}', SV_PILOT_D,
                               prof + 6.0, 'Z', (x, 0.0, -prof / 2.0 + EPS), 24))

    # 4) sortie de câble : encoche sous le corps, côté opposé à l'axe
    if avec_fil:
        outils.append(boite(prefixe + '_fil', SV_BX1 - 5.0, SV_BX1 + 6.0,
                            -4.0, 4.0, -prof - 10.0, EPS))

    return poser(outils, mat)


# =============================================================================
#  PIÈCE 1 : ROUE  (x2 identiques, aucune symétrie)
#  Orientation d'impression telle qu'exportée : axe vertical, face EXTERNE en
#  bas (z = 0). Le lamage du bossage servo s'ouvre donc vers le HAUT : aucun
#  plafond en porte-à-faux, alésage traversant simple.
# =============================================================================
def piece_roue():
    zi = WHEEL_W                     # face interne (côté servo), vers le haut
    r_rim_i = WHEEL_R - RIM_T        # 29.5

    # bandeau extérieur plein et lisse
    jante = cylindre('roue', WHEEL_D, WHEEL_W, 'Z', (0, 0, WHEEL_W / 2.0), 96)
    booleen(jante, cylindre('roue_creux', 2 * r_rim_i, WHEEL_W + 2 * EPS, 'Z',
                            (0, 0, WHEEL_W / 2.0), 96), 'DIFFERENCE')

    # moyeu + rayons en étoile (allègement ; la bande de roulement reste lisse)
    pieces = [jante, cylindre('roue_moyeu', HUB_D, WHEEL_W, 'Z',
                              (0, 0, WHEEL_W / 2.0), 48)]
    for i in range(SPOKES):
        a = 2.0 * math.pi * i / SPOKES
        dx, dy = math.cos(a), math.sin(a)
        nx, ny = -dy, dx
        r0, r1 = HUB_D / 2.0 - 0.5, r_rim_i + 0.5
        t = SPOKE_T / 2.0
        poly = [(r0 * dx + t * nx, r0 * dy + t * ny),
                (r1 * dx + t * nx, r1 * dy + t * ny),
                (r1 * dx - t * nx, r1 * dy - t * ny),
                (r0 * dx - t * nx, r0 * dy - t * ny)]
        pieces.append(prisme(f'roue_rayon{i}', poly, 'Z', 0.0, WHEEL_W))
    roue = fusionner('wheel', pieces)

    # alésage Ø5.2 traversant + lamage Ø12.4 du bossage servo (ouvert vers +Z)
    z_cb = zi - HUB_CB_H             # 7.3
    outils = [
        cylindre('r_bore', HUB_BORE_D, WHEEL_W + 4 * EPS, 'Z',
                 (0, 0, WHEEL_W / 2.0), 48),
        cylindre('r_lamage', HUB_CB_D, HUB_CB_H + EPS, 'Z',
                 (0, 0, z_cb + (HUB_CB_H + EPS) / 2.0), 48),
        frustum('r_cham', HUB_BORE_D + 1.6, HUB_BORE_D, 0.8, 'Z',
                (0, 0, 0.4 - EPS), 48),
    ]
    # 2 vis M2 radiales de blocage à 90°, dans la zone réellement occupée
    # par l'axe (l'axe pénètre de z_cb-3.0 à z_cb)
    z_grub = z_cb - 1.5
    outils.append(cylindre('r_grub0', GRUB_D, HUB_D + 4.0, 'X', (0, 0, z_grub), 24))
    outils.append(cylindre('r_grub1', GRUB_D, HUB_D + 4.0, 'Y', (0, 0, z_grub), 24))
    soustraire(roue, outils)
    return nettoyer(roue)


# =============================================================================
#  PIÈCE 1bis : PIED EN ARC  (x2 identiques, aucune symétrie)
#  Repère local identique à celui de la roue : axe = Z, z = 0 = face EXTERNE
#  (montée en +X sur le robot), z = FOOT_W = face INTERNE, côté servo.
#  Orientation d'impression : TELLE QU'EXPORTÉE, face externe sur le plateau.
#  L'empreinte du palonnier et le dégagement de vis s'ouvrent donc vers le
#  HAUT : aucun plafond, aucun support.
#
#  ORIENTATION ANGULAIRE : l'arc est centré sur -Y local (angle 270°) et couvre
#  FOOT_SPAN = 200°, soit 170°..370°. Le palonnier étant monté servo AU NEUTRE
#  (90°) avec le milieu de l'arc vers le BAS, le point de contact est
#  exactement sous l'axe et le robot est vertical, à la même hauteur qu'avec
#  les roues (rayon identique 32.5). Le débattement utile du servo (+/-90°)
#  reste dans l'arc, avec 10° de marge de chaque côté.
# =============================================================================
FOOT_A0 = 270.0 - FOOT_SPAN / 2.0        # 170.0
FOOT_A1 = 270.0 + FOOT_SPAN / 2.0        # 370.0


def piece_foot_arc():
    r_int = FOOT_R - FOOT_RIM_T          # 29.3 : intérieur de la bande

    def anneau(nom, d_ext, d_int):
        """Couronne complète, ensuite limitée au secteur de l'arc."""
        a = cylindre(nom, d_ext, FOOT_W, 'Z', (0, 0, FOOT_W / 2.0), 128)
        booleen(a, cylindre(nom + '_c', d_int, FOOT_W + 4 * EPS, 'Z',
                            (0, 0, FOOT_W / 2.0), 128), 'DIFFERENCE')
        return intersecter(nom, a, secteur(nom + '_s', FOOT_R + 6.0,
                                           FOOT_A0, FOOT_A1, -EPS, FOOT_W + EPS))

    P = [anneau('foot_arc', FOOT_R * 2.0, r_int * 2.0),          # jante pleine
         anneau('foot_band', FOOT_BAND_R1 * 2.0, FOOT_BAND_R0 * 2.0),
         cylindre('foot_hub', FOOT_HUB_D, FOOT_W, 'Z', (0, 0, FOOT_W / 2.0), 64)]
    # nervures radiales : une à chaque extrémité de l'arc (elles ferment les
    # deux flancs), les autres réparties régulièrement.
    for i in range(FOOT_RIBS):
        a = math.radians(FOOT_A0 + (FOOT_A1 - FOOT_A0) * i / (FOOT_RIBS - 1))
        dx, dy = math.cos(a), math.sin(a)
        nx, ny = -dy, dx
        r0, r1, t = FOOT_HUB_D / 2.0 - 1.0, r_int + 0.6, FOOT_RIB_T / 2.0
        P.append(prisme(f'foot_rib{i}',
                        [(r0 * dx + t * nx, r0 * dy + t * ny),
                         (r1 * dx + t * nx, r1 * dy + t * ny),
                         (r1 * dx - t * nx, r1 * dy - t * ny),
                         (r0 * dx - t * nx, r0 * dy - t * ny)],
                        'Z', 0.0, FOOT_W))
    pied = fusionner('foot_arc', P)

    # --- empreinte du palonnier, ouverte vers le HAUT (face interne) ---------
    zp = FOOT_W - HORN_POCKET_D                       # 5.6 : fond de l'empreinte
    C = [cylindre('fa_hub_cl', HORN_HUB_D, HORN_POCKET_D + 2 * EPS, 'Z',
                  (0, 0, zp + HORN_POCKET_D / 2.0), 64)]
    for i, ang in enumerate((0.0, 90.0)):             # croix à 4 branches
        a = math.radians(ang)
        dx, dy = math.cos(a), math.sin(a)
        nx, ny = -dy, dx
        t = HORN_ARM_W / 2.0
        P4 = [(HORN_ARM_R * dx + t * nx, HORN_ARM_R * dy + t * ny),
              (-HORN_ARM_R * dx + t * nx, -HORN_ARM_R * dy + t * ny),
              (-HORN_ARM_R * dx - t * nx, -HORN_ARM_R * dy - t * ny),
              (HORN_ARM_R * dx - t * nx, HORN_ARM_R * dy - t * ny)]
        C.append(prisme(f'fa_arm{i}', P4, 'Z', zp, FOOT_W + EPS))
    # dégagement de la vis centrale M2 du palonnier (elle dépasse du moyeu)
    C.append(cylindre('fa_relief', HORN_RELIEF_D, HORN_RELIEF_H + EPS, 'Z',
                      (0, 0, zp - HORN_RELIEF_H / 2.0 + EPS / 2.0), 64))
    # 2 trous OBLONGS M2 : l'entraxe exact des trous d'un palonnier SG90 varie
    # (4.5 .. 6.0 mm du centre selon la marque) -> lumière radiale +/-1.3 mm.
    for s in (-1, 1):
        C.append(boite(f'fa_vis{s}',
                       min(s * (HORN_SCREW_R - HORN_SLOT_DR),
                           s * (HORN_SCREW_R + HORN_SLOT_DR)),
                       max(s * (HORN_SCREW_R - HORN_SLOT_DR),
                           s * (HORN_SCREW_R + HORN_SLOT_DR)),
                       -HORN_SCREW_D / 2.0, HORN_SCREW_D / 2.0,
                       -EPS, zp + EPS))
    soustraire(pied, C)
    return nettoyer(pied)


# =============================================================================
#  PIÈCE 2 : CORPS
#  Impression DEBOUT (Z = axe de construction), sans support :
#  toutes les parois sont verticales, tous les plafonds sont biseautés à 45°.
# =============================================================================
def _mat_servo_roue(signe):
    """Repère du servo de roue. signe=+1 (droite) / -1 (gauche).

    Les deux servos ont la MÊME implantation en Y et Z ; le gauche est le
    droit tourné de 180° autour de Y (rotation propre, donc corps identiques :
    on inverse simplement un moteur dans le firmware).
    """
    if signe > 0:
        cols = ((0, -1, 0), (0, 0, -1), (1, 0, 0))
    else:
        cols = ((0, -1, 0), (0, 0, 1), (-1, 0, 0))
    return repere(cols, (signe * SV_PLATE_X1, 0.0, AXLE_Z))


def piece_corps():
    # Ordre impératif en 4 temps : les volumes INTERNES (piédestal MPU,
    # bossages de vis) doivent être ajoutés APRÈS l'évidement des coques,
    # sinon les cutters de cavité les effacent purement et simplement.
    P = []      # 1. coques structurelles
    C = []      # 2. évidements de coque
    P2 = []     # 3. volumes internes rapportés
    C2 = []     # 4. perçages de détail

    # -- 1) SOCLE + RACCORD 45° VERS LE MÂT ---------------------------------
    # Pas de plancher horizontal : le socle se raccorde au mât par un tronc
    # de pyramide à 45°, et la cavité intérieure suit le même principe. Il n'y
    # a donc AUCUN plafond à ponter dans toute la partie basse.
    P.append(boite('socle', -BODY_HW, BODY_HW, BODY_Y0, BODY_Y1, BODY_Z0, BASE_Z1))
    P.append(intersecter(
        'corbeau',
        prisme('corbeau_x', [(-BODY_HW, BASE_Z1 - EPS), (BODY_HW, BASE_Z1 - EPS),
                             (MAST_HW, CORBEL_Z1), (-MAST_HW, CORBEL_Z1)],
               'Y', BODY_Y0 - 1.0, BODY_Y1 + 1.0),
        prisme('corbeau_y', [(BODY_Y0, BASE_Z1 - EPS), (BODY_Y1, BASE_Z1 - EPS),
                             (MAST_Y1, CORBEL_Z1), (MAST_Y0, CORBEL_Z1)],
               'X', -BODY_HW - 1.0, BODY_HW + 1.0)))

    # -- 2) SOCLE BAS DE CAISSE : chanfreins 45° pour l'adhérence ------------
    # Le profil déborde HORS de la boîte (pas de sommet posé exactement sur
    # une face du solide) : sinon le booléen crée des triangles dégénérés.
    for s in (-1, 1):
        C.append(prisme(f'socle_ch{s}',
                        [(s * BODY_HW, BODY_Z0 + CHAM),
                         (s * (BODY_HW + CHAM), BODY_Z0),
                         (s * (BODY_HW + 2 * CHAM), BODY_Z0 - 2 * CHAM),
                         (s * (BODY_HW - CHAM), BODY_Z0 - 2 * CHAM)],
                        'Y', BODY_Y0 - 2.0, BODY_Y1 + 2.0))

    # -- 3) PIÉDESTAL MPU6050, entre les deux servos, sur l'axe des roues ----
    ped_hw = 9.0
    ped_z = AXLE_Z - MPU_T - 4.5               # 26.0 : face d'appui du module
    ped_y0, ped_y1 = BODY_Y0 + WALL, BODY_Y1   # le piédestal reste DANS le socle
    mpu_cy = (ped_y0 + ped_y1) / 2.0           # -3.8 : centre du module
    P2.append(boite('mpu_ped', -ped_hw, ped_hw, ped_y0, ped_y1,
                    BODY_Z0 + WALL - EPS, ped_z))
    # logette du module : encastrement 1.5 mm, appui plan, 2 vis M2
    C2.append(boite('mpu_log', -(MPU_W + CLEARANCE_FIT) / 2.0,
                    (MPU_W + CLEARANCE_FIT) / 2.0,
                    mpu_cy - (MPU_L + CLEARANCE_FIT) / 2.0,
                    mpu_cy + (MPU_L + CLEARANCE_FIT) / 2.0,
                    ped_z - 1.5, ped_z + EPS))
    for i, dy in enumerate((-MPU_HOLE_PITCH / 2.0, MPU_HOLE_PITCH / 2.0)):
        C2.append(cylindre(f'mpu_vis{i}', SV_PILOT_D, 12.0, 'Z',
                           (0.0, mpu_cy + dy, ped_z - 6.0), 24))

    # -- 4) MÂT creux + évasement 45° + caisson haut -------------------------
    P.append(boite('mat', -MAST_HW, MAST_HW, MAST_Y0, MAST_Y1,
                   CORBEL_Z1 - EPS, FLARE_Z0))
    # Cavité UNIQUE socle+raccord+mât, obtenue par intersection de deux
    # prismes : elle se rétrécit à plus de 45°, donc aucun plafond.
    cx = [(-SV_PLATE_X0, BODY_Z0 + WALL), (SV_PLATE_X0, BODY_Z0 + WALL),
          (SV_PLATE_X0, CAV_TAPER_Z0), (MAST_HW - WALL, CAV_TAPER_Z1),
          (MAST_HW - WALL, FLARE_Z0 + 2.0), (-MAST_HW + WALL, FLARE_Z0 + 2.0),
          (-MAST_HW + WALL, CAV_TAPER_Z1), (-SV_PLATE_X0, CAV_TAPER_Z0)]
    cy = [(BODY_Y0 + WALL, BODY_Z0 + WALL), (BODY_Y1 + EPS, BODY_Z0 + WALL),
          (BODY_Y1 + EPS, CAV_TAPER_Z0), (MAST_Y1 - WALL, CAV_TAPER_Z1),
          (MAST_Y1 - WALL, FLARE_Z0 + 2.0), (MAST_Y0 + WALL, FLARE_Z0 + 2.0),
          (MAST_Y0 + WALL, CAV_TAPER_Z1), (BODY_Y0 + WALL, CAV_TAPER_Z0)]
    C.append(intersecter(
        'creux_bas',
        prisme('creux_x', cx, 'Y', BODY_Y0 - 1.0, BODY_Y1 + 1.0),
        prisme('creux_y', cy, 'X', -BODY_HW - 1.0, BODY_HW + 1.0)))

    P.append(prisme('evase',
                    [(-MAST_HW, FLARE_Z0), (-HEAD_HW, FLARE_Z1),
                     (HEAD_HW, FLARE_Z1), (MAST_HW, FLARE_Z0)],
                    'Y', MAST_Y0, MAST_Y1))
    C.append(prisme('evase_creux',
                    [(-MAST_HW + WALL + 2.0, FLARE_Z0 - 2.0),
                     (-HEAD_HW + WALL + 2.0, FLARE_Z1 + 2.0),
                     (HEAD_HW - WALL - 2.0, FLARE_Z1 + 2.0),
                     (MAST_HW - WALL - 2.0, FLARE_Z0 - 2.0)],
                    'Y', MAST_Y0 + WALL, MAST_Y1 - WALL))

    P.append(boite('caisson', -HEAD_HW, HEAD_HW, MAST_Y0, MAST_Y1,
                   FLARE_Z1 - EPS, BODY_Z1))
    # Plafond du caisson en BÂTIÈRE à 45° (faîtage sur l'axe Y du mât) : le
    # plancher qui porte la tête n'a ainsi aucune portion horizontale par
    # dessous, et il devient épais (8.4 mm) là où se vissent les M3.
    ey0, ey1 = MAST_Y0 + WALL, MAST_Y1 - WALL          # -15.6 .. -0.4
    faite = (ey0 + ey1) / 2.0                          # -8.0
    avant = BODY_Z1 - DECK_T - (ey1 - ey0) / 2.0       # 138.0 : hauteur d'égout
    C.append(prisme('caisson_creux',
                    [(ey0, FLARE_Z1 - EPS), (ey1, FLARE_Z1 - EPS),
                     (ey1, avant), (faite, BODY_Z1 - DECK_T), (ey0, avant)],
                    'X', -HEAD_HW + WALL, HEAD_HW - WALL))

    # -- 5) ASSISE DE TÊTE : lumière du servo pan + 4 bossages M3 ------------
    # Grâce à la bâtière, le plancher fait 8.4 mm d'épaisseur au droit des vis :
    # les M3 se taraudent directement, aucun bossage suspendu n'est nécessaire.
    for sx in (-1, 1):
        for sy in PAN_SCREW_Y:
            C2.append(cylindre(f'pan_pilot{sx}{sy}', PAN_SCREW_PILOT, 14.0, 'Z',
                               (sx * PAN_SCREW_X, sy, BODY_Z1 - 5.0), 24))
    # Dégagement du corps du servo pan (il plonge dans le caisson). La lumière
    # est prolongée jusqu'au PLAN DE JOINT : sur body_b, imprimée couchée sur
    # le dos, elle débouche ainsi au sommet de la pièce au lieu de se refermer
    # par un pont de 21 mm sous le plancher de tête.
    C2.append(boite('pan_lum', SV_BCX - SV_SLOT_L / 2.0, SV_BCX + SV_SLOT_L / 2.0,
                    PAN_Y - SV_SLOT_W / 2.0, Y_JOINT + EPS,
                    FLARE_Z1, BODY_Z1 + EPS))

    # -- 6) BERCEAU DE CARTE (face avant du caisson) -------------------------
    # tablette basse + rail haut : guident la carte en Z, sans jamais
    # recouvrir le verre (aucune marge exploitable, cf. FIT_NOTES).
    P.append(boite('card_shelf', -CARD_HW - WALL, CARD_HW + WALL,
                   MAST_Y1 - EPS, CARD_RAIL_Y, CARD_Z0 - WALL, CARD_Z0))
    # rail haut : barre inclinée à 45° -> sa sous-face n'est jamais horizontale
    P.append(prisme('card_rail',
                    [(MAST_Y1 - EPS, CARD_Z1), (6.0, CARD_Z1 + 4.0),
                     (6.0, CARD_Z1 + 4.0 + WALL), (MAST_Y1 - EPS, CARD_Z1 + WALL)],
                    'X', -CARD_HW - WALL, CARD_HW + WALL))
    # gousset 45° reprenant TOUTE la sous-face de la tablette
    P.append(prisme('card_gousset',
                    [(MAST_Y1, CARD_Z0 - WALL), (CARD_RAIL_Y, CARD_Z0 - WALL),
                     (MAST_Y1, CARD_Z0 - WALL - (CARD_RAIL_Y - MAST_Y1))],
                    'X', -CARD_HW - WALL, CARD_HW + WALL))
    # joues d'extrémité (butée en X) — la carte s'introduit par +X
    P.append(boite('card_joue_g', -CARD_HW - WALL, -CARD_HW,
                   MAST_Y1 - EPS, CARD_RAIL_Y, CARD_Z0 - WALL, CARD_Z1))
    # échancrure USB-C sur la joue gauche (prise mesurée : 8.09 de large)
    C.append(boite('card_usb', -CARD_HW - WALL - EPS, -CARD_HW + EPS,
                   MAST_Y1 - EPS, CARD_PCB_Y + EPS,
                   CARD_ZC - 7.0, CARD_ZC + 7.0))
    # appuis arrière : uniquement là où le dos de la carte est nu
    P.append(boite('card_pad_a', -CARD_HW, CARD_PAD_XA,
                   MAST_Y1 - EPS, CARD_PCB_BACK, CARD_Z0, CARD_Z1))
    P.append(boite('card_pad_b', CARD_PAD_XB, CARD_HW,
                   MAST_Y1 - EPS, CARD_PCB_BACK, CARD_Z0, CARD_Z1))
    # 2 plots de vis M2 en face des trous RÉELS de la carte
    for i, xc in enumerate(PCB_FIX_X):
        C.append(cylindre(f'card_fix{i}', PCB_FIX_PILOT, 9.0, 'Y',
                          (CARD_FIX_X, CARD_PCB_BACK - 3.5, CARD_ZC + xc), 24))
    # Lèvre de maintien de l'arête BASSE, sur toute la longueur. Hauteur 1.0 mm
    # seulement : le verre commence 1.26 mm plus haut que l'arête du PCB
    # (mesuré), donc aucun pixel n'est masqué.
    P.append(boite('card_lip_bas', -CARD_HW, CARD_HW,
                   CARD_PCB_Y + CARD_CL, CARD_PCB_Y + CARD_CL + 1.2,
                   CARD_Z0, CARD_Z0 + 1.0))

    # -- 7) PINCE D'ENCLIQUETAGE (maintien SANS OUTIL) -----------------------
    # Nervure de 0.4 mm sur l'appui arrière, en vis-à-vis de la lèvre basse :
    # l'entrée du logement se referme à 0.95 mm pour un PCB de 1.20 -> la carte
    # se clipse en glissant par +X et tient seule. Les 2 vis M2 dans les trous
    # RÉELS de la carte ne servent qu'à verrouiller (voir FIT_NOTES).
    P.append(boite('card_pince', LATCH_X0, CARD_HW,
                   CARD_PCB_BACK, CARD_PCB_BACK + 0.4,
                   CARD_Z0, CARD_Z0 + 1.0))
    # rampe d'entrée 45° sur la nervure : évite de râper le PCB à l'insertion
    C.append(prisme('card_pince_rampe',
                    [(CARD_HW + EPS, CARD_PCB_BACK - EPS),
                     (CARD_HW + EPS, CARD_PCB_BACK + 0.5),
                     (CARD_HW - 1.5, CARD_PCB_BACK + 0.5)],
                    'Z', CARD_Z0 - EPS, CARD_Z0 + 1.0 + EPS))

    # -- 8) PLOTS DE JOINT (goujons + vis) -----------------------------------
    # Ajoutés dans P2, donc APRÈS l'évidement des coques : ils doivent rester
    # pleins. Chaque plot part du dos (il est ainsi porté par le plateau quand
    # body_b est imprimée couchée) et monte jusqu'à `y1`.
    for (bx0, bx1, bz0, bz1, by1) in JOINT_BOSS:
        for s in (-1, 1):
            P2.append(boite(f'joint_plot{s}_{bz0:.0f}',
                            min(s * bx0, s * bx1), max(s * bx0, s * bx1),
                            BODY_Y0, by1, bz0, bz1))

    # -- 9) FENÊTRES DE CÂBLAGE derrière la carte ----------------------------
    # Les pads GPIO (servos 1/2/3/10, I2C 17/18, ultrason 11/12) sont au dos de
    # la carte : 6.2 mm de dégagement + ces deux fenêtres qui donnent sur le
    # caisson (17.2 mm de profondeur), lui-même relié au mât puis au socle.
    # Elles évitent les 2 appuis arrière et les 2 plots de vis de la carte.
    for i, (wx0, wx1, wz0, wz1) in enumerate(CARD_WIRE_WIN):
        C2.append(boite(f'card_win{i}', wx0, wx1, MAST_Y1 - WALL - EPS,
                        MAST_Y1 + EPS, wz0, wz1))
    # passe-fil arrière (sortie optionnelle des faisceaux hors du caisson)
    C2.append(boite('pass_arr', -12.0, 12.0, BODY_Y0 - EPS, MAST_Y0 + WALL + EPS,
                    108.0, 118.0))

    # -- assemblage ----------------------------------------------------------
    for s in (1, -1):
        # avec_fil=False : le câble sort déjà librement par la lumière, on ne
        # perce pas la paroi arrière (raideur du socle = couple d'équilibre).
        C2 += outils_servo(f'sv{s}', BODY_HW - SV_PLATE_X0 + 2.0,
                           _mat_servo_roue(s), avec_fil=False)
    corps = fusionner('body', P)     # 1. coques
    soustraire(corps, C)             # 2. évidements
    for v in P2:                     # 3. volumes internes (après évidement !)
        booleen(corps, v, 'UNION')
    soustraire(corps, C2)            # 4. perçages
    return nettoyer(corps)


# =============================================================================
#  PIÈCE 2 : CORPS EN DEUX MOITIÉS  (body_a avant / body_b arrière)
#  Le corps complet est construit puis tranché par le plan Y = Y_JOINT ; on
#  ajoute ensuite ce qui appartient en propre à chaque moitié :
#    body_a : alésages Ø6 des goujons, avant-trous M3, rainures du mât.
#    body_b : goujons Ø5.8 venus de fonderie, tenons du mât, passages M3 +
#             lamages de tête sur la face arrière plane.
# =============================================================================
def pieces_corps():
    plein = piece_corps()
    a = plein
    a.name = 'body_a'
    b = dupliquer(plein, 'body_b')
    GD = 200.0
    booleen(a, boite('coupe_a', -GD, GD, -GD, Y_JOINT, -GD, GD), 'DIFFERENCE')
    booleen(b, boite('coupe_b', -GD, GD, Y_JOINT, GD, -GD, GD), 'DIFFERENCE')

    # --- body_a : alésages, avant-trous, rainures ---------------------------
    Ca = []
    for (dx, dz) in JOINT_DOWELS:
        for s in (-1, 1):
            LB = DOWEL_LEN + 1.4       # 9.0 : traversant, dégage le bout conique
            Ca.append(cylindre(f'da{s}_{dz:.0f}', DOWEL_BORE_D, LB, 'Y',
                               (s * dx, Y_JOINT - 0.6 + LB / 2.0, dz), 32))
    for (tx, tz) in JOINT_TENONS:
        for s in (-1, 1):
            # mortaise TRAVERSANTE : ni plafond à ponter, ni volume clos
            Ca.append(boite(f'mo{s}_{tz:.0f}',
                            s * tx - (TEN_W + TEN_CL) / 2.0,
                            s * tx + (TEN_W + TEN_CL) / 2.0,
                            Y_JOINT - EPS, Y_JOINT + DOWEL_LEN + 1.1,
                            tz - (TEN_H + TEN_CL) / 2.0,
                            tz + (TEN_H + TEN_CL) / 2.0))
    for (sx, sz) in JOINT_SCREWS:
        for s in (-1, 1):
            Ca.append(cylindre(f'pa{s}_{sz:.0f}', ASM_PILOT_D, 9.0, 'Y',
                               (s * sx, Y_JOINT - 0.5 + 4.5, sz), 24))
    for s in (-1, 1):
        Ca.append(boite(f'rainure{s}',
                        s * TENON_XC - (TENON_W + TENON_CL) / 2.0,
                        s * TENON_XC + (TENON_W + TENON_CL) / 2.0,
                        Y_JOINT - EPS, Y_JOINT + TENON_H + TENON_CL,
                        TENON_Z0 - TENON_CL, TENON_Z1 + TENON_CL))
    soustraire(a, Ca)
    nettoyer(a)

    # --- body_b : goujons, tenons, passages de vis --------------------------
    Pb = []
    L = 3.4 + DOWEL_LEN - 0.8          # 10.2 : ancrage 3.4 + saillie 6.8
    for (dx, dz) in JOINT_DOWELS:
        for s in (-1, 1):
            Pb.append(cylindre(f'db{s}_{dz:.0f}', DOWEL_D, L, 'Y',
                               (s * dx, Y_JOINT - 3.4 + L / 2.0, dz), 32))
            # Bout tronconique : entrée sans forcer dans l'alésage Ø6. Il
            # CHEVAUCHE le cylindre de 0.2 mm — deux faces Ø5.8 exactement
            # coplanaires donneraient 32 arêtes non-manifold par goujon.
            Pb.append(frustum(f'dc{s}_{dz:.0f}', DOWEL_D, DOWEL_D - 1.6, 1.2, 'Y',
                              (s * dx, Y_JOINT - 3.4 + L - 0.2 + 0.6, dz), 32))
    for (tx, tz) in JOINT_TENONS:
        for s in (-1, 1):
            Pb.append(boite(f'te{s}_{tz:.0f}',
                            s * tx - TEN_W / 2.0, s * tx + TEN_W / 2.0,
                            Y_JOINT - 3.4, Y_JOINT + DOWEL_LEN - 0.8,
                            tz - TEN_H / 2.0, tz + TEN_H / 2.0))
    for s in (-1, 1):
        Pb.append(boite(f'tenon{s}',
                        s * TENON_XC - TENON_W / 2.0, s * TENON_XC + TENON_W / 2.0,
                        Y_JOINT - 1.0, Y_JOINT + TENON_H, TENON_Z0, TENON_Z1))
    for o in Pb:
        booleen(b, o, 'UNION')
    Cb = []
    for (sx, sz) in JOINT_SCREWS:
        for s in (-1, 1):
            Cb.append(cylindre(f'pb{s}_{sz:.0f}', ASM_PASS_D, 24.0, 'Y',
                               (s * sx, BODY_Y0 - 0.1 + 12.0, sz), 24))
    soustraire(b, Cb)
    nettoyer(b)
    return [a, b]


# =============================================================================
#  PIÈCE 3 : HEAD_PAN — berceau du servo de lacet + interface corps
#  Repère local : z = 0 sur la face supérieure du corps (BODY_Z1).
#  Impression à plat, face z = 0 sur le plateau.
# =============================================================================
def piece_head_pan():
    hw = PAN_SCREW_X + 6.0                     # 32.0
    P = [boite('head_pan', -hw, hw, PAN_Y - 13.0, PAN_Y + 13.0,
               0.0, PAN_PLATE_T)]
    # collerette de rigidification autour de la lumière du servo
    P.append(boite('hp_col', SV_BCX - SV_SLOT_L / 2.0 - 3.0,
                   SV_BCX + SV_SLOT_L / 2.0 + 3.0,
                   PAN_Y - SV_SLOT_W / 2.0 - 3.0, PAN_Y + SV_SLOT_W / 2.0 + 3.0,
                   0.0, PAN_PLATE_T + 3.0))
    plaque = fusionner('head_pan', P)

    C = []
    # 4 trous M3 passants vers les bossages du corps
    for sx in (-1, 1):
        for sy in PAN_SCREW_Y:
            C.append(cylindre(f'hp_m3_{sx}_{sy}', PAN_SCREW_D, 20.0, 'Z',
                              (sx * PAN_SCREW_X, sy, PAN_PLATE_T / 2.0), 24))
    soustraire(plaque, C)
    # lumière du servo : la portée des pattes est la face SUPÉRIEURE
    z_portee = PAN_PLATE_T + 3.0
    soustraire(plaque, outils_servo('hp_sv', z_portee + 2.0,
                                    repere(((1, 0, 0), (0, 1, 0), (0, 0, 1)),
                                           (0.0, PAN_Y, z_portee))))
    return nettoyer(plaque)


# =============================================================================
#  PIÈCE 4 : HEAD_TILT — liaison pan -> tilt (axes perpendiculaires)
#  Moyeu sur l'axe du servo pan (vertical), 2 bras verticaux portant le servo
#  de tangage (axe selon X). Repère local : z = 0 = face SUPÉRIEURE du
#  bossage du servo pan (on porte sur le bossage Ø11.8, donc AUCUN lamage
#  en plafond : impression debout sans support).
# =============================================================================
TILT_AXE_Z = 34.0        # hauteur de l'axe de tangage au-dessus du moyeu pan
TILT_BASE_T = 5.0
# L'axe de sortie du SG90 est décentré : les 2 trous de pattes tombent à
# -8.4 et +19.4 de l'axe (SV_SCX0/SV_SCX1). Les bras doivent donc couvrir
# TOUTE cette plage, sinon la 2e vis n'a plus de matière à mordre.
TILT_ARM_Y0 = -SV_SCX1 - 3.0     # -22.4
TILT_ARM_Y1 = -SV_SCX0 + 3.0     # +11.4
TILT_BASE_HY = 11.0              # demi-profondeur de la platine du moyeu


def piece_head_tilt():
    P = [cylindre('ht_moyeu', TILT_HUB_D, TILT_BASE_T + 6.0, 'Z',
                  (0, 0, (TILT_BASE_T + 6.0) / 2.0), 48),
         boite('ht_base', -TILT_ARM_X, TILT_ARM_X, -TILT_BASE_HY, TILT_BASE_HY,
               0.0, TILT_BASE_T)]
    # deux bras verticaux ; celui de gauche porte le servo de tangage
    for s in (-1, 1):
        x0 = s * (TILT_ARM_X - TILT_ARM_T) if s > 0 else s * TILT_ARM_X
        x1 = s * TILT_ARM_X if s > 0 else s * (TILT_ARM_X - TILT_ARM_T)
        P.append(boite(f'ht_bras{s}', min(x0, x1), max(x0, x1),
                       TILT_ARM_Y0, TILT_ARM_Y1, 0.0, TILT_AXE_Z + 11.0))
        # congé 45° bras <-> base (pas de porte-à-faux, raideur)
        P.append(prisme(f'ht_conge{s}',
                        [(s * (TILT_ARM_X - TILT_ARM_T), TILT_BASE_T),
                         (s * (TILT_ARM_X - TILT_ARM_T - 7.0), TILT_BASE_T),
                         (s * (TILT_ARM_X - TILT_ARM_T), TILT_BASE_T + 7.0)],
                        'Y', TILT_ARM_Y0, TILT_ARM_Y1))
    tilt = fusionner('head_tilt', P)

    # Alésage du moyeu : la pièce PORTE SUR LE BOSSAGE Ø11.8 du servo pan.
    # Aucun lamage -> aucun plafond horizontal, impression debout sans support.
    # L'axe dépasse alors de SV_SHAFT_PROJ - SV_BOSS_H = 3.0 mm : les 2 vis
    # radiales sont placées dans cette hauteur utile.
    z_vis = (SV_SHAFT_PROJ - SV_BOSS_H) / 2.0        # 1.5
    C = [cylindre('ht_bore', HUB_BORE_D, 40.0, 'Z', (0, 0, 5.0), 48)]
    for s in (-1, 1):
        C.append(cylindre(f'ht_grub{s}', SV_PILOT_D, 26.0, 'Y', (0, 0, z_vis), 24))
    soustraire(tilt, C)

    # Servo de tangage : les pattes portent sur la face INTÉRIEURE du bras
    # gauche, le corps ressort vers -X, l'axe pointe vers +X.
    # Repère local servo : +Z -> +X monde, +X -> -Y monde, donc +Y -> -Z monde
    # (rotation propre : det = +1).
    mat = repere(((0, -1, 0), (0, 0, -1), (1, 0, 0)),
                 (-(TILT_ARM_X - TILT_ARM_T), 0.0, TILT_AXE_Z))
    soustraire(tilt, outils_servo('ht_sv', TILT_ARM_T + 2.0, mat, avec_fil=False))

    # Tourillon libre côté droit : reprend le porte-à-faux du capteur.
    # Il pointe vers -X et vient jusqu'au même X que le bout de l'axe servo.
    x_axe = -(TILT_ARM_X - TILT_ARM_T) + SV_TOP_LOCAL + SV_SHAFT_PROJ   # -1.9
    x_bras = TILT_ARM_X - TILT_ARM_T                                    # 13.0
    L = x_bras - (-x_axe)                                               # 11.1
    booleen(tilt, cylindre('ht_tourillon', IDLER_D, L, 'X',
                           (x_bras - L / 2.0, 0.0, TILT_AXE_Z), 24), 'UNION')
    return nettoyer(tilt)


# =============================================================================
#  PIÈCE 5 : SENSOR_MOUNT — berceau HC-SR04 sur l'axe de tangage
#  Berceau OUVERT à l'avant (+Y) : les deux capsules sont totalement dégagées.
#  Broches vers le BAS. Impression debout sur l'arête basse (dos vertical).
# =============================================================================
def piece_sensor():
    bw = SR_L / 2.0 + CLEARANCE_FIT / 2.0        # 22.65 demi-largeur utile
    bh = SR_W / 2.0 + CLEARANCE_FIT / 2.0        # 10.15 demi-hauteur utile
    dos_y0, dos_y1 = 0.0, WALL                   # dos du berceau
    pcb_y0 = dos_y1 + 1.0                        # portée du PCB du capteur
    pcb_y1 = pcb_y0 + SR_PCB_T + SLIDING_FIT

    P = [boite('sm_dos', -bw - WALL, bw + WALL, dos_y0, dos_y1, -bh - WALL, bh + WALL)]
    # joues latérales + rail haut/bas formant la glissière du PCB
    for s in (-1, 1):
        P.append(boite(f'sm_joue{s}', s * bw, s * (bw + WALL), dos_y0,
                       pcb_y1 + 1.2, -bh - WALL, bh + WALL))
    P.append(boite('sm_bas', -bw, bw, dos_y0, pcb_y1 + 1.2, -bh - WALL, -bh))
    # RAIL HAUT : limité aux BORDS LATÉRAUX (|x| >= SR_FREE_HX). La barre pleine
    # de la v1 passait au-dessus des deux capsules et devant elles ; le champ
    # des transducteurs doit rester libre de bout en bout vers +Y. Le PCB n'est
    # donc plus retenu que par le dos, le rail bas et les deux bords latéraux.
    for s in (-1, 1):
        xa, xb = sorted((s * SR_FREE_HX, s * bw))
        P.append(boite(f'sm_haut{s}', xa, xb, dos_y0, pcb_y1 + 1.2, bh, bh + WALL))
    # Moyeu central AU DOS : reçoit à gauche l'axe du servo de tangage et à
    # droite le tourillon. Axe à Y = -2 (donc entièrement derrière le dos, la
    # partie qui déborderait dans la baie est retirée par sm_log).
    # 64 segments et non 48 : avec un nombre de segments MULTIPLE DE 12, le
    # 48-gone place un sommet pile à 30°, soit Y = -2 - 8*sin(30°) = -6.00 —
    # une arête franche de la facette tombe alors sur le plan de sonde Y = -6,
    # le rayon la longe, la traversée est comptée deux fois et le moyeu (pourtant
    # bien plein) est lu « vide ». 64 n'est pas multiple de 12 : les sommets
    # voisins tombent à -5.771 et -6.445, la sonde traverse une facette franche.
    # Bonus : facettes de 0.79 mm au lieu de 1.05 sur une portée de pivot.
    P.append(cylindre('sm_moyeu', TILT_HUB_D, 11.8, 'X', (0.7, -2.0, 0.0), 64))
    capot = fusionner('sensor_mount', P)

    C = []
    # biseau 45° sous le rail haut : supprime le plafond horizontal
    for s in (-1, 1):
        xa, xb = sorted((s * SR_FREE_HX, s * bw))
        C.append(prisme(f'sm_biseau{s}',
                        [(pcb_y1 + 1.2 + EPS, bh - EPS),
                         (pcb_y1 + 1.2 + EPS, bh + WALL),
                         (pcb_y1 + 1.2 - WALL, bh - EPS)],
                        'X', xa, xb))
    # garantie « champ libre » : rien au-dessus ni entre les capsules
    C.append(boite('sm_champ', -SR_FREE_HX, SR_FREE_HX, dos_y1 - EPS, 40.0,
                   bh - EPS, bh + WALL + EPS))
    # Baie du capteur, dégagée de bout en bout vers l'AVANT : retire aussi la
    # part du moyeu qui déborderait devant le dos.
    C.append(boite('sm_log', -bw, bw, dos_y1 - EPS, 40.0, -bh, bh))
    # sortie des 4 broches VERS LE BAS
    C.append(boite('sm_broches', -18.0, 18.0, dos_y1 - EPS, pcb_y1 + 1.4,
                   -bh - WALL - EPS, -bh + EPS))
    # fenêtres des capsules : ouverture totale vers l'avant
    for s in (-1, 1):
        C.append(cylindre(f'sm_capsule{s}', SR_CAN_D + 2.0, 30.0, 'Y',
                          (s * SR_CAN_PITCH / 2.0, pcb_y1 + 8.0, 0.0), 48))
    # À gauche : alésage sur l'axe du servo de tangage (qui va de X = -4.9 à
    # -1.9 dans le repère commun avec head_tilt) + 2 vis M2 de blocage.
    C.append(cylindre('sm_bore', HUB_BORE_D, 4.4, 'X', (-3.2, -2.0, 0.0), 48))
    for i, x in enumerate((-4.4, -2.2)):
        C.append(cylindre(f'sm_grub{i}', SV_PILOT_D, 20.0, 'Z',
                          (x, -2.0, 0.0), 24))
    # À droite : logement du tourillon libre (tige Ø4 de head_tilt, X 1.9..13)
    C.append(cylindre('sm_tour', IDLER_D + HOLE_BONUS, 5.4, 'X',
                      (4.0, -2.0, 0.0), 48))
    soustraire(capot, C)

    # lèvres de retenue du PCB du capteur (en dehors de la zone des broches)
    for s in (-1, 1):
        xa, xb = sorted((s * 18.0, s * bw))
        capot = booleen(capot, boite(f'sm_lip_b{s}', xa, xb,
                                     pcb_y1, pcb_y1 + 1.2,
                                     -bh - EPS, -bh + 1.5), 'UNION')
        capot = booleen(capot, boite(f'sm_lip_h{s}', xa, xb,
                                     pcb_y1, pcb_y1 + 1.2,
                                     bh - 1.5, bh + EPS), 'UNION')
    return nettoyer(capot)


# =============================================================================
#  RENDU DE CONTRÔLE
# =============================================================================
CAM_TILT = 72.0       # inclinaison caméra : 90 = horizontale, < 90 = plongée
CAM_YAW = 22.0        # lacet : donne une vue 3/4 qui révèle la profondeur
RENDU_MARGE = 1.06    # 6 % de marge autour du contenu


def _materiau(nom, rgba):
    """Principled BSDF mat, sans dépendre du NOM des sockets (il bouge d'une
    version de Blender à l'autre) : on repère le nœud par son type."""
    m = bpy.data.materials.new(nom)
    m.use_nodes = True
    bsdf = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    for cle, val in (('Base Color', rgba), ('Roughness', 0.42), ('Metallic', 0.0)):
        if cle in bsdf.inputs:
            bsdf.inputs[cle].default_value = val
    m.diffuse_color = rgba          # utile si un moteur retombe sur la couleur
    return m


def _etiquette(txt, taille, rot):
    cu = bpy.data.curves.new(f'lbl_{txt}', type='FONT')
    cu.body = txt
    cu.size = taille
    cu.align_x = 'CENTER'
    cu.align_y = 'TOP'
    cu.extrude = 0.0
    ob = bpy.data.objects.new(f'lbl_{txt}', cu)
    bpy.context.collection.objects.link(ob)
    ob.rotation_euler = rot          # face à la caméra (billboard)
    return ob


def _sommets_monde(ob):
    """Sommets en coordonnées monde, mesh ou texte (le texte est converti à la
    volée dans une évaluation du depsgraph : sa bbox brute n'est pas fiable)."""
    dg = bpy.context.evaluated_depsgraph_get()
    oe = ob.evaluated_get(dg)
    try:
        me = oe.to_mesh()
    except RuntimeError:
        return []
    pts = [ob.matrix_world @ v.co.copy() for v in me.vertices]
    oe.to_mesh_clear()
    return pts


def rendu(chemin):
    """Vue éclatée orthographique des 5 pièces, rendue en EEVEE.

    Le cadrage n'est PAS déduit de la bbox monde : avec une caméra inclinée,
    X/Z monde ne sont plus les axes de l'image et on cadre à côté. On projette
    donc tous les sommets sur les axes PROPRES de la caméra (droite, haut,
    avant) et on en déduit ortho_scale et la position exactement.
    """
    from mathutils import Euler
    scn = bpy.context.scene
    scn.render.engine = 'BLENDER_EEVEE'
    # format large : les 5 pièces alignées font ~360 x 140 mm une fois projetées,
    # un 16/10 laisserait 40 % de l'image vide au-dessus et en dessous.
    scn.render.resolution_x = 2200
    scn.render.resolution_y = 900
    scn.render.film_transparent = False
    scn.render.image_settings.file_format = 'PNG'
    if hasattr(scn, 'eevee'):
        if hasattr(scn.eevee, 'taa_render_samples'):
            scn.eevee.taa_render_samples = 64
        if hasattr(scn.eevee, 'use_raytracing'):
            scn.eevee.use_raytracing = True
    scn.view_settings.look = 'None'

    # -- monde : ciel neutre légèrement bleuté, sert d'éclairage d'ambiance ----
    world = bpy.data.worlds.new('W')
    world.use_nodes = True
    fond = next(n for n in world.node_tree.nodes if n.type == 'BACKGROUND')
    fond.inputs[0].default_value = (0.085, 0.10, 0.125, 1.0)
    fond.inputs[1].default_value = 1.6
    scn.world = world

    # -- soleil : rasant depuis l'avant-gauche-haut, ombres douces ------------
    soleil = bpy.data.objects.new('soleil', bpy.data.lights.new('soleil', 'SUN'))
    scn.collection.objects.link(soleil)
    soleil.data.energy = 4.5
    soleil.data.angle = math.radians(3.0)          # pénombre douce
    soleil.rotation_euler = (math.radians(52), 0.0, math.radians(-38))

    couleurs = {'body_a': (0.16, 0.42, 0.78, 1), 'body_b': (0.24, 0.58, 0.90, 1),
                'foot_arc': (0.82, 0.32, 0.17, 1),
                'head_pan': (0.20, 0.64, 0.38, 1), 'head_tilt': (0.90, 0.70, 0.16, 1),
                'sensor_mount': (0.62, 0.34, 0.74, 1)}
    for nom, ob in PARTS.items():
        ob.data.materials.clear()
        ob.data.materials.append(_materiau(nom, couleurs.get(nom, (0.7, .7, .7, 1))))
        for p in ob.data.polygons:
            p.use_smooth = False

    # -- éclaté : rangée le long de X, pièces recentrées verticalement --------
    # (le corps fait 128 mm de haut, les autres < 45 : sans recentrage la ligne
    #  part en biais et la moitié de l'image reste vide)
    tous = list(PARTS.values())
    poses = [(o.location.x, o.location.z) for o in tous]
    bb = [bbox(o) for o in tous]
    ecart = 26.0
    largeur = sum(b[1] - b[0] for b in bb) + ecart * (len(tous) - 1)
    curseur = -largeur / 2.0
    for ob, b in zip(tous, bb):
        ob.location.x += curseur - b[0]
        ob.location.z += -(b[4] + b[5]) / 2.0
        curseur += (b[1] - b[0]) + ecart
    bpy.context.view_layer.update()

    # -- repère caméra --------------------------------------------------------
    rot = Euler((math.radians(CAM_TILT), 0.0, math.radians(CAM_YAW)), 'XYZ')
    R = rot.to_matrix()
    droite, haut, avant = R @ Vector((1, 0, 0)), R @ Vector((0, 1, 0)), R @ Vector((0, 0, -1))

    # -- étiquettes sous chaque pièce, orientées face caméra ------------------
    # Profondeur : TOUTES au premier plan (min global - 25), pas à la profondeur
    # moyenne de leur pièce — sinon une pièce à plat comme `wheel` passe devant
    # son propre texte et le masque. Ligne de base commune : la plus basse.
    nuages = {ob.name: _sommets_monde(ob) for ob in tous}
    prof_avant = min(p.dot(avant) for pts in nuages.values() for p in pts) - 25.0
    base = min(p.dot(haut) for pts in nuages.values() for p in pts) - 7.0
    etiq = []
    for ob in tous:
        pts = nuages[ob.name]
        centre_u = (min(p.dot(droite) for p in pts) + max(p.dot(droite) for p in pts)) / 2.0
        lb = _etiquette(ob.name, 8.0, rot)
        lb.location = droite * centre_u + haut * base + avant * prof_avant
        lb.data.materials.append(_materiau(f'txt_{ob.name}', (0.88, 0.90, 0.94, 1)))
        etiq.append(lb)
    bpy.context.view_layer.update()

    # -- sol : reçoit les ombres, ancre visuellement la rangée ----------------
    z_sol = min(bbox(o)[4] for o in tous) - 1.0
    sol = boite('sol', -600, 600, -400, 400, z_sol - 4.0, z_sol)
    sol.data.materials.append(_materiau('sol', (0.20, 0.21, 0.24, 1)))

    # -- cadrage EXACT dans le repère caméra ---------------------------------
    pts = [p for o in tous + etiq for p in _sommets_monde(o)]
    us = [p.dot(droite) for p in pts]
    vs = [p.dot(haut) for p in pts]
    ws = [p.dot(avant) for p in pts]
    cu, cv = (min(us) + max(us)) / 2.0, (min(vs) + max(vs)) / 2.0
    larg, haut_img = max(us) - min(us), max(vs) - min(vs)
    aspect = scn.render.resolution_x / scn.render.resolution_y

    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    scn.collection.objects.link(cam)
    cam.data.type = 'ORTHO'
    # ortho_scale porte sur la PLUS GRANDE dimension du rendu (ici X)
    cam.data.ortho_scale = max(larg, haut_img * aspect) * RENDU_MARGE
    recul = (max(ws) - min(ws)) + 800.0
    cam.location = droite * cu + haut * cv + avant * (min(ws) - recul)
    cam.rotation_euler = rot
    cam.data.clip_start = 1.0
    cam.data.clip_end = recul + (max(ws) - min(ws)) + 800.0
    scn.camera = cam

    scn.render.filepath = chemin
    bpy.ops.render.render(write_still=True)
    print(f"  [PNG] {os.path.basename(chemin)}  "
          f"({scn.render.resolution_x}x{scn.render.resolution_y}, "
          f"ortho {cam.data.ortho_scale:.0f} mm)")

    # remise en place : l'éclaté ne doit pas polluer un ré-export ultérieur
    bpy.data.objects.remove(sol, do_unlink=True)
    for lb in etiq:
        bpy.data.objects.remove(lb, do_unlink=True)
    for ob, (x, z) in zip(tous, poses):
        ob.location.x, ob.location.z = x, z


# =============================================================================
#  POINT D'ENTRÉE
# =============================================================================
def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    raz_scene()

    print("\n=== BalanceBot / génération du châssis ===")
    print(f"  tolérances  : sliding {SLIDING_FIT} | clearance {CLEARANCE_FIT} "
          f"| press {PRESS_FIT} | alésage +{HOLE_BONUS}")
    print(f"  axe roues   : z = {AXLE_Z} mm | voie {2*WHEEL_CX:.1f} mm | "
          f"hors-tout {2*WHEEL_X1:.1f} mm")
    print(f"  servo roue  : corps X {SV_CASE_X0:.2f}..{SV_CASE_X1:.2f}, "
          f"axe jusqu'à {SV_SHAFT_TIP:.2f}, roue dès {WHEEL_X0:.2f}")
    engagement = SV_SHAFT_TIP - (WHEEL_X0 + HUB_CB_H)
    print(f"  engagement axe/moyeu : {engagement:.2f} mm "
          f"({'OK' if engagement >= 2.0 else '*** INSUFFISANT ***'})")
    print(f"  carte       : {PCB_LEN} x {PCB_WID} x {PCB_T} (PCB nu) ; "
          f"logement Z {CARD_Z0:.2f}..{CARD_Z1:.2f}")
    print(f"  MPU6050     : à {AXLE_Z - (AXLE_Z - MPU_T - 4.5):.1f} mm "
          f"sous l'axe des roues, sur l'axe médian")

    # `wheel` est OBSOLÈTE (servos 180° standard) : elle n'est plus exportée.
    constructeurs = [pieces_corps, piece_foot_arc, piece_head_pan,
                     piece_head_tilt, piece_sensor]
    print("\n--- pièces ---")
    for fn in constructeurs:
        res = fn()
        for ob in (res if isinstance(res, (list, tuple)) else [res]):
            PARTS[ob.name] = ob
            exporter(ob, os.path.join(ICI, ob.name + '.stl'))

    if '--no-preview' not in argv:
        print("\n--- rendu ---")
        rendu(os.path.join(ICI, 'preview.png'))
    print("\n=== terminé ===")


if __name__ == '__main__':
    main()
