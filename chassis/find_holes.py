#!/usr/bin/env python3
"""Recherche des perçages du PCB nu : coupe au plan médian du circuit imprimé
puis regroupement des points d'intersection en amas (chaque trou = 1 amas)."""
from measure_ref import load_tris, section

T = load_tris('/tmp/t-display-s3-ref/dimensions/t-display-s3-full.stl')

for z in (-0.60, -0.30, -0.90):
    s = section(T, 2, z)
    pts = [p for seg in s for p in seg]
    inner = [p for p in pts if -12.3 < p[0] < 12.3 and 0.5 < p[1] < 60.3]
    amas = []
    for p in inner:
        for c in amas:
            if abs(c[0][0] - p[0]) < 3.5 and abs(c[0][1] - p[1]) < 3.5:
                c.append(p)
                break
        else:
            amas.append([p])
    print(f"z={z:5.2f}  section={len(pts)} pts, internes={len(inner)}, amas={len(amas)}")
    for c in amas:
        xs = [q[0] for q in c]
        ys = [q[1] for q in c]
        dx, dy = max(xs) - min(xs), max(ys) - min(ys)
        cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
        print(f"   n={len(c):3d}  centre ({cx:7.2f},{cy:7.2f})  Ø~{max(dx, dy):5.2f}")
