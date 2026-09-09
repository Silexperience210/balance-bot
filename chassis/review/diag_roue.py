#!/usr/bin/env python3
"""Diagnostic roue : ou est la matiere ?"""
import os
import trimesh
import numpy as np

w = trimesh.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "v3", "coin_wheel.stl"), process=True)
w.merge_vertices()
print("bbox:", [round(float(x), 2) for x in w.bounds[0]], "->", [round(float(x), 2) for x in w.bounds[1]])
for (x, y) in ((0, 0), (3, 0), (0, 5), (0, 11), (0, 12.5), (0, 20), (0, 30), (0, 39), (0, 41)):
    o = np.array([[float(x), float(y), -5.0]]); d = np.array([[0.0, 0.0, 1.0]])
    h = w.ray.intersects_location(o, d, multiple_hits=True)
    zs = sorted(round(float(p[2]), 2) for p in h[0])
    print("  (x=%5.1f, y=%5.1f) : croisements z=%s" % (x, y, zs))
print()
for z in (2.0, 5.0, 11.0, 15.0, 20.0):
    sec = w.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    p2, _ = sec.to_2D()
    areas = sorted((round(float(p.area), 1) for p in p2.polygons_full), reverse=True)
    print("  section z=%5.1f : %d polygones, aires %s" % (z, len(areas), areas[:6]))
