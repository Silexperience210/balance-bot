#!/usr/bin/env blender --background --python
# -*- coding: utf-8 -*-
"""
VÉRIFICATION GÉOMÉTRIQUE de la baie servo — intersection booléenne EXACTE
entre le solide SG90 et les coques b_front / b_back réellement exportées.

Usage :  blender --background --python chassis/review/servo_fit.py -- [dossier_stl]

Le servo est placé EXACTEMENT là où gen_bitcoin_bot.py l'implante, puis la même
symétrie x -> GW - x que miroir_x() est appliquée (les STL sont mirrorés).

Sortie : volume d'intersection par pièce du servo et par coque, avec la boîte
englobante de chaque zone de collision (repère des STL, donc mirroré).
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sg90_model as SG  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
STLDIR = argv[0] if argv else os.path.join(HERE, '..', 'v3')
CLR = float(argv[1]) if len(argv) > 1 else 0.0   # jeu de montage ajouté au servo

# ── constantes reprises telles quelles de gen_bitcoin_bot.py ────────────────
GW, GH, Z0 = 118.0, 165.0, 26.0
STROKE, WALL = 19.0, 2.4
Z_MID = Z0 + GH * 0.50
LOW = dict(zb=Z0, zt=Z_MID + STROKE * 0.5, xr=GW)
AXLE_Z = 42.0

r_low = (LOW['zt'] - LOW['zb']) / 2
cz_low = (LOW['zt'] + LOW['zb']) / 2
X_WALL_R = (LOW['xr'] - r_low) + math.sqrt(r_low ** 2 - (AXLE_Z - cz_low) ** 2)


def raz():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for m in list(bpy.data.meshes):
        if m.users == 0:
            bpy.data.meshes.remove(m)


def volume(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    v = bm.calc_volume(signed=False)
    bm.free()
    return v


def bbox(ob):
    vs = [ob.matrix_world @ v.co for v in ob.data.vertices]
    if not vs:
        return None
    return (min(v.x for v in vs), max(v.x for v in vs),
            min(v.y for v in vs), max(v.y for v in vs),
            min(v.z for v in vs), max(v.z for v in vs))


def inter(a, b):
    """a ∩ b (EXACT) -> nouvel objet (a est dupliqué)."""
    bpy.ops.object.select_all(action='DESELECT')
    a.select_set(True)
    bpy.context.view_layer.objects.active = a
    bpy.ops.object.duplicate()
    d = bpy.context.active_object
    m = d.modifiers.new('bool', 'BOOLEAN')
    m.operation, m.object, m.solver = 'INTERSECT', b, 'EXACT'
    m.use_self = True
    bpy.ops.object.modifier_apply(modifier=m.name)
    return d


def placer_servo(parts, x_face, d):
    """Repère local servo -> repère châssis NON mirroré, puis symétrie x->GW-x.

    local : +X = vers le fond du servo, Y = largeur, Z = longueur (0 = bout côté arbre)
    cible : X = x_face + d*x_local, Y = y_local, Z = (AXLE_Z - SG.SG_SHAFT_OFF) + z_local
    """
    z0 = AXLE_Z - SG.SG_SHAFT_OFF
    M = Matrix.Translation((x_face, 0.0, z0)) @ Matrix.Diagonal((d, 1.0, 1.0, 1.0))
    # miroir global x -> GW - x (comme miroir_x du générateur)
    M = (Matrix.Translation((GW, 0, 0)) @ Matrix.Scale(-1, 4, (1, 0, 0))) @ M
    for p in parts:
        p.data.transform(M)
        if M.determinant() < 0:
            bm = bmesh.new()
            bm.from_mesh(p.data)
            bmesh.ops.reverse_faces(bm, faces=bm.faces)
            bm.to_mesh(p.data)
            bm.free()
    return parts


def main():
    raz()
    coques = {}
    for nom in ('b_front', 'b_back'):
        p = os.path.join(STLDIR, nom + '.stl')
        bpy.ops.wm.stl_import(filepath=p)
        ob = bpy.context.selected_objects[0]
        ob.name = nom
        coques[nom] = ob
        print('  import %-8s %s' % (nom, os.path.relpath(p)))

    print()
    print('x_wall_R = %.3f   corps servo z = %.1f .. %.1f   jeu ajouté = %.2f mm' %
          (X_WALL_R, AXLE_Z - SG.SG_SHAFT_OFF, AXLE_Z - SG.SG_SHAFT_OFF + SG.SG_L, CLR))
    print()

    hump = '--hump' in sys.argv
    total = 0.0
    lignes = []
    for lbl, x_face, d in (('SPINE', WALL, +1), ('PANSE', X_WALL_R - WALL, -1)):
        parts = SG.sg90_parts(tab=SG.SG_TAB + CLR, cable_len=0.0, hump=hump)
        placer_servo(parts, x_face, d)
        for p in parts:
            for cn, coque in coques.items():
                r = inter(p, coque)
                v = volume(r)
                if v > 0.5:
                    b = bbox(r)
                    total += v
                    lignes.append((lbl, p.name, cn, v, b))
                bpy.data.objects.remove(r, do_unlink=True)
        for p in parts:
            bpy.data.objects.remove(p, do_unlink=True)

    print('=== COLLISIONS servo x coques (repère STL, mirroré)%s ===' % (' [+capot oblong]' if hump else ''))
    if not lignes:
        print('  aucune — intersection = 0 mm3')
    for lbl, pn, cn, v, b in sorted(lignes, key=lambda t: -t[3]):
        print('  %-5s %-8s %-8s %9.1f mm3   x[%7.2f,%7.2f] y[%6.2f,%6.2f] z[%6.2f,%6.2f]'
              % (lbl, pn, cn, v, b[0], b[1], b[2], b[3], b[4], b[5]))
    print()
    print('VOLUME D\'INTERSECTION TOTAL = %.1f mm3' % total)

    # ── sortie de câble : longueur de course LIBRE en ligne droite hors du corps ──────────
    print()
    print('=== sortie de câble : course libre en sortie du corps ===')
    z0 = AXLE_Z - SG.SG_SHAFT_OFF
    x_loc = SG.SG_H - SG.SG_CABLE_Z0 - SG.SG_CABLE_H / 2
    for lbl, x_face, d in (('SPINE', WALL, +1), ('PANSE', X_WALL_R - WALL, -1)):
        xg = GW - (x_face + d * x_loc)          # repère STL (mirroré)
        for sens, zdep in (('bout court (côté arbre)', z0), ('bout long', z0 + SG.SG_L)):
            dz = -1.0 if zdep == z0 else 1.0
            best = 99.0
            for dy in (-1.8, 0.0, 1.8):
                for dx in (-1.8, 0.0, 1.8):
                    for coque in coques.values():
                        ok, loc, _, _ = coque.ray_cast((xg + dx, dy, zdep + dz * 0.05), (0, 0, dz))
                        if ok:
                            best = min(best, abs(loc.z - zdep))
            print('  %-5s %-24s x=%6.2f z=%5.1f  ->  %s' %
                  (lbl, sens, xg, zdep,
                   'libre > 99 mm' if best > 98 else 'obstacle a %.1f mm' % best))


if __name__ == '__main__':
    main()
