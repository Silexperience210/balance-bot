#!/usr/bin/env python3
"""Identifier précisément les faces plates descendantes dans l'orientation d'impression prévue
(externe vers le bas) : b_front -> +Y bas ; b_back -> -Y bas ; coin_wheel -> +Z bas."""
import os
import numpy as np, trimesh, json

HERE = os.path.dirname(os.path.abspath(__file__))
V3 = os.path.join(HERE, "..", "v3")

def analyse(path, down_axis, down_sign, top=8):
    m = trimesh.load(path, process=False)
    m.merge_vertices()
    if down_axis == 0:
        R = trimesh.transformations.rotation_matrix(np.radians(90 if down_sign > 0 else -90), [0, 1, 0])
    elif down_axis == 1:
        R = trimesh.transformations.rotation_matrix(np.radians(-90 if down_sign > 0 else 90), [1, 0, 0])
    else:
        R = np.eye(4) if down_sign > 0 else trimesh.transformations.rotation_matrix(np.pi, [1, 0, 0])
    m.apply_transform(R)
    n = m.face_normals
    a = m.area_faces
    ang = np.degrees(np.arccos(np.clip(-n[:, 2], -1, 1)))
    down = n[:, 2] < -0.05
    flat = down & (ang < 3.0)
    zmin = m.bounds[0][2]
    zc = m.triangles[:, :, 2].mean(axis=1)
    contact = flat & (zc - zmin < 0.1)
    rows = []
    idx = np.argsort(-a * flat)
    for i in idx[:400]:
        if not flat[i]:
            break
        c = m.triangles[i].mean(axis=0)
        rows.append({"area": round(float(a[i]), 1), "x": round(float(c[0]), 1), "y": round(float(c[1]), 1),
                     "z_above_plate": round(float(c[2] - zmin), 2)})
    # regroupement grossier par altitude
    by_z = {}
    for r in rows:
        k = round(r["z_above_plate"], 1)
        by_z.setdefault(k, {"area": 0.0, "n": 0})
        by_z[k]["area"] += r["area"]
        by_z[k]["n"] += 1
    out = {
        "file": path.split("/")[-1],
        "orientation": "axis%d%s down" % (down_axis, "+" if down_sign > 0 else "-"),
        "height_mm": round(float(m.bounds[1][2] - zmin), 1),
        "contact_mm2": round(float(a[contact].sum()), 0),
        "down_lt3deg_mm2": round(float(a[flat].sum()), 0),
        "down_lt45deg_mm2": round(float(a[down & (ang < 45)].sum()), 0),
        "largest_flat_faces": rows[:top],
        "flat_area_by_altitude": {str(k): {"area": round(v["area"], 1), "n_faces": v["n"]} for k, v in sorted(by_z.items())},
    }
    return out

res = [
    analyse(os.path.join(V3, "b_front.stl"), 1, +1),
    analyse(os.path.join(V3, "b_back.stl"), 1, -1),
    analyse(os.path.join(V3, "coin_wheel.stl"), 2, +1),
]
print(json.dumps(res, indent=1))
