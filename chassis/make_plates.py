#!/usr/bin/env python3
"""BalanceBot v3.1 — regenere les plaques de slicing export/v31 depuis chassis/v3/*.stl.

Orientations identiques aux plaques validees (verifiees par alignement de 100 % des sommets) :
  b_front : face externe (y=+23) vers le BAS   -> rotation [[0,0,-1],[1,0,0],[0,-1,0]], t=(218, 6.5, 23)
  b_back  : face externe (y=-23) vers le BAS   -> rotation [[0,0,1],[1,0,0],[0,1,0]],   t=(-7, 6.5, 23)
  roues   : telles quelles (face gravee en bas) -> translations (45,45,0) / (45,145,0)
  pneus   : a plat                              -> translations (46.5,46.5,0) / (46.5,146.5,0)

Usage : python3 chassis/make_plates.py   (trimesh requis ; ne modifie pas chassis/v3)
"""
import os
import numpy as np
import trimesh

ROOT = os.path.dirname(os.path.abspath(__file__))
V3 = os.path.join(ROOT, "v3")
OUT = os.path.normpath(os.path.join(ROOT, "..", "export", "v31"))

I3 = np.eye(3)
PLAN = [
    ("plate1_b_front.stl", "b_front.stl", np.array([[0, 0, -1], [1, 0, 0], [0, -1, 0]], float), (218.0, 6.5, 23.0)),
    ("plate2_b_back.stl", "b_back.stl", np.array([[0, 0, 1], [1, 0, 0], [0, 1, 0]], float), (-7.0, 6.5, 23.0)),
    ("plateR_wheel1.stl", "coin_wheel.stl", I3, (45.0, 45.0, 0.0)),
    ("plateR_wheel2.stl", "coin_wheel.stl", I3, (45.0, 140.0, 0.0)),
    ("plateT_tire1.stl", "coin_tire.stl", I3, (46.5, 46.5, 0.0)),
    ("plateT_tire2.stl", "coin_tire.stl", I3, (46.5, 141.5, 0.0)),
]


def main():
    os.makedirs(OUT, exist_ok=True)
    for out_name, src_name, M, t in PLAN:
        mesh = trimesh.load(os.path.join(V3, src_name), process=False)
        T = np.block([[M, np.asarray(t, float).reshape(3, 1)], [np.zeros(3), 1.0]])
        mesh.apply_transform(T)
        path = os.path.join(OUT, out_name)
        mesh.export(path)
        b = mesh.bounds
        print("  %-22s %6.2f x %6.2f x %6.2f mm  (min %6.2f,%6.2f,%6.2f)  %d tris" % (
            out_name, b[1][0] - b[0][0], b[1][1] - b[0][1], b[1][2] - b[0][2],
            b[0][0], b[0][1], b[0][2], len(mesh.faces)))


if __name__ == "__main__":
    main()
