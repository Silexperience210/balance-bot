#!/usr/bin/env blender --background --python
"""Rendu de contrôle : coque b_back vue du plan de joint, avec les 2 SG90 en place.
Usage : blender --background --python chassis/review/servo_view.py -- [sortie.png]"""
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import servo_fit as F  # noqa: E402  (importe aussi sg90_model, et exécute la mesure)
import sg90_model as SG  # noqa: E402

OUT = os.path.join(HERE, 'servo_view.png')

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

bpy.ops.wm.stl_import(filepath=os.path.join(HERE, '..', 'v3', 'b_back.stl'))
coque = bpy.context.selected_objects[0]
coque.name = 'b_back'
m = bpy.data.materials.new('orange')
m.use_nodes = False
m.diffuse_color = (0.95, 0.45, 0.05, 1)
coque.data.materials.append(m)

mv = bpy.data.materials.new('vert')
mv.use_nodes = False
mv.diffuse_color = (0.10, 0.75, 0.25, 1)
for lbl, x_face, d in (('SPINE', F.WALL, +1), ('PANSE', F.X_WALL_R - F.WALL, -1)):
    parts = SG.sg90_parts(tab=SG.SG_TAB, cable_len=8.0)
    F.placer_servo(parts, x_face, d)
    for p in parts:
        p.data.materials.append(mv)

sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sc.render.resolution_x, sc.render.resolution_y = 1100, 1500
sc.render.film_transparent = False
cam_d = bpy.data.cameras.new('cam')
cam_d.type = 'ORTHO'
cam_d.ortho_scale = 215
cam = bpy.data.objects.new('cam', cam_d)
sc.collection.objects.link(cam)
sc.camera = cam
cam.location = (59.0, 400.0, 100.0)
cam.rotation_euler = (1.5708, 0, 3.14159)    # regarde vers -Y : intérieur de la coque back
sc.render.filepath = (sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv and
                      len(sys.argv) > sys.argv.index('--') + 1 else OUT)
bpy.ops.render.render(write_still=True)
print('rendu ->', sc.render.filepath)
