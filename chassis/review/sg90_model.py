#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Modèle SOLIDE du micro-servo TowerPro SG90, reconstruit à partir des cotes du
datasheet + recalage sur un modèle CAO réel téléchargé.

RÉFÉRENCE CAO : FreeCAD-library / Electrical Parts / Servos / SG-90 / Servo-SG90.stl
  https://github.com/FreeCAD/FreeCAD-library  (licence LGPL, auteur « juan », 2015)
  copie locale : chassis/assets/servo/Servo-SG90.stl  (+ Servo-sg90.step)

Cotes mesurées sur ce modèle de référence (mm) :
  corps            11.80 (l) x 22.50 (L) x 22.70 (h)
  oreilles         32.40 d'envergure, 2.50 d'épaisseur, base à z = 15.90 du fond
  centre oreilles  à 11.50 du fond du corps (corps centré à 11.25) -> oreilles centrées sur le CORPS
  arbre            Ø 4.58, centre à 5.90 d'un bout du corps  <- SV_SHAFT_OFF confirmé
  bossage/capot    Ø ~11.8 sur 4.0 de haut, débordant de 2.9 vers le bout long
  sortie de câble  encoche 3.6 (l) x 3.0 (p) x 1.2 (h), à 4.5 du fond, sur le
                   petit côté LE PLUS PROCHE de l'arbre

Ce modèle de référence est LÉGÈREMENT SOUS-COTÉ par rapport au datasheet
TowerPro (11.80 au lieu de 12.20 en largeur, 22.50 au lieu de 22.80 en longueur)
et NE CONTIENT NI LES TAQUETS DE MOULAGE NI LE CÂBLE. Il ne peut donc pas
servir tel quel de gabarit de montage.

=> On reconstruit ici un solide aux cotes NOMINALES du datasheet (celles déjà
   présentes dans gen_bitcoin_bot.py), en y ajoutant explicitement :
     - les taquets de moulage / bavure de joint de coque  (SG_TAB, en saillie)
     - la sortie de câble + le toron
   et on fournit une version « enveloppe pire-cas » (nominal + SG_TAB) qui est
   celle contre laquelle la baie du châssis doit être validée.

Repère local du servo (avant mise en place) :
  X = hauteur   : 0 = face de sortie (dessus, côté palonnier), +X vers le fond
  Y = largeur   : 0 = plan médian
  Z = longueur  : 0 = bout du corps côté arbre, +Z vers le bout long
  arbre à (0, 0, SG_SHAFT_OFF), axe +X sortant (vers les X négatifs)
"""
import math
import bmesh
import bpy

# ── Cotes nominales datasheet TowerPro SG90 ─────────────────────────────────
SG_L, SG_W, SG_H = 22.8, 12.2, 22.5      # corps : longueur, largeur, hauteur
SG_FLANGE_Z, SG_FLANGE_T, SG_TAB_SPAN = 15.9, 2.5, 32.2   # oreilles
SG_HOLE_PITCH, SG_HOLE_D = 27.8, 2.0
SG_SHAFT_OFF = 5.9                        # axe -> bout court du corps
SG_SHAFT_D, SG_SHAFT_PROJ = 4.8, 4.5
SG_BOSS_D, SG_BOSS_H = 11.8, 1.5          # bossage de sortie (datasheet)
SG_HUMP_OVER, SG_HUMP_H = 2.9, 4.0        # capot surélevé mesuré sur la CAO ref
SG_CABLE_D = 3.6                          # toron 3 fils
SG_CABLE_Z0, SG_CABLE_H = 4.5, 1.2        # encoche de sortie (mesurée CAO ref)

# Taquets de moulage / bavure du joint des 2 demi-coques du servo.
# Non cotés au datasheet : valeur d'ingénierie, appliquée en SAILLIE sur tout
# le pourtour du corps (c'est ce qui empêche le servo réel d'entrer).
SG_TAB = 0.5


def _boite(nom, x0, x1, y0, y1, z0, z1):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1)
    for v in bm.verts:
        v.co.x = x0 if v.co.x < 0 else x1
        v.co.y = y0 if v.co.y < 0 else y1
        v.co.z = z0 if v.co.z < 0 else z1
    me = bpy.data.meshes.new(nom)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(nom, me)
    bpy.context.collection.objects.link(ob)
    return ob


def _cyl_x(nom, d, x0, x1, cy, cz, n=64):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=n, radius1=d / 2, radius2=d / 2, depth=abs(x1 - x0))
    me = bpy.data.meshes.new(nom)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(nom, me)
    bpy.context.collection.objects.link(ob)
    ob.rotation_euler = (0, math.radians(90), 0)
    ob.location = ((x0 + x1) / 2, cy, cz)
    bpy.context.view_layer.update()
    ob.data.transform(ob.matrix_world)
    ob.matrix_world.identity()
    return ob


def _cyl_z(nom, d, z0, z1, cx, cy, n=48):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=n, radius1=d / 2, radius2=d / 2, depth=abs(z1 - z0))
    me = bpy.data.meshes.new(nom)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(nom, me)
    bpy.context.collection.objects.link(ob)
    ob.location = (cx, cy, (z0 + z1) / 2)
    bpy.context.view_layer.update()
    ob.data.transform(ob.matrix_world)
    ob.matrix_world.identity()
    return ob


def sg90_parts(tab=0.0, cable_len=12.0, with_shaft=True, cable='both', hump=False):
    """Solide SG90 dans son repère local. `tab` = saillie ajoutée sur le corps
    (taquets/bavure de moulage) ; tab=0 -> nominal datasheet.

    `cable` : 'near' = toron au bout COURT (z=0, côté arbre) — c'est ce que
    montre la CAO de référence ; 'far' = bout long ; 'both' = les deux (cas
    pire-cas retenu pour la validation, l'orientation du toron n'étant pas
    cotée au datasheet et variant selon les lots)."""
    t = tab
    parts = []
    # corps (+ taquets en saillie sur les 4 flancs et le fond ; PAS sur la face de sortie x=0,
    # qui est la face d'appui usinée du capot — c'est la référence de position du servo)
    parts.append(_boite('corps', 0.0, SG_H + t, -SG_W / 2 - t, SG_W / 2 + t, -t, SG_L + t))
    # oreilles : centrées sur la LONGUEUR du corps, épaisseur SG_FLANGE_T,
    # face « basse » (côté fond) à SG_FLANGE_Z du fond -> en X : SG_H - SG_FLANGE_Z
    x_ear1 = SG_H - SG_FLANGE_Z - SG_FLANGE_T     # 4.1  (face côté dessus)
    x_ear0 = SG_H - SG_FLANGE_Z                   # 6.6  (face côté fond)
    zc = SG_L / 2
    parts.append(_boite('pattes', x_ear1, x_ear0, -SG_W / 2, SG_W / 2,
                        zc - SG_TAB_SPAN / 2, zc + SG_TAB_SPAN / 2))
    # bossage de sortie (datasheet : Ø11.8 x 1.5)
    parts.append(_cyl_x('boss', SG_BOSS_D, -SG_BOSS_H, 0.5, 0.0, SG_SHAFT_OFF))
    # Capot surélevé oblong mesuré sur la CAO de référence (débord SG_HUMP_OVER vers le bout long).
    # NON coté au datasheet et la CAO de référence est par ailleurs sous-cotée : variante
    # pessimiste, désactivée par défaut, à activer pour vérifier un servo qui la présente.
    if hump:
        parts.append(_boite('hump', -SG_BOSS_H, 0.5, -SG_BOSS_D / 2, SG_BOSS_D / 2,
                            SG_SHAFT_OFF, SG_SHAFT_OFF + SG_BOSS_D / 2 + SG_HUMP_OVER))
    if with_shaft:
        parts.append(_cyl_x('arbre', SG_SHAFT_D, -SG_BOSS_H - SG_SHAFT_PROJ, -SG_BOSS_H + 0.2,
                            0.0, SG_SHAFT_OFF))
    # sortie de câble : sur le petit côté LE PLUS PROCHE de l'arbre (z = 0),
    # à SG_CABLE_Z0 du fond du corps -> x = SG_H - SG_CABLE_Z0 - SG_CABLE_H/2
    x_cab = SG_H - SG_CABLE_Z0 - SG_CABLE_H / 2
    if cable_len > 0:
        if cable in ('near', 'both'):
            parts.append(_cyl_z('cable_n', SG_CABLE_D, -cable_len, 0.5, x_cab, 0.0))
        if cable in ('far', 'both'):
            parts.append(_cyl_z('cable_f', SG_CABLE_D, SG_L - 0.5, SG_L + cable_len, x_cab, 0.0))
    return parts
