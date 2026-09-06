#!/usr/bin/env python3
"""Carte matière/vide rapide (raycast +Z avec pré-filtrage par grille XY)."""
import sys
from collections import defaultdict

from measure_ref import load_tris, bbox

CELL = 2.0  # mm, taille de case du index spatial


def build_index(tris):
    idx = defaultdict(list)
    for k, t in enumerate(tris):
        x0 = min(v[0] for v in t)
        x1 = max(v[0] for v in t)
        y0 = min(v[1] for v in t)
        y1 = max(v[1] for v in t)
        for i in range(int(x0 // CELL), int(x1 // CELL) + 1):
            for j in range(int(y0 // CELL), int(y1 // CELL) + 1):
                idx[(i, j)].append(k)
    return idx


def solid(tris, idx, x, y, z):
    cnt = 0
    for k in idx.get((int(x // CELL), int(y // CELL)), ()):
        a, b, c = tris[k]
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-12:
            continue
        l1 = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / den
        l2 = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / den
        l3 = 1.0 - l1 - l2
        if l1 < 0 or l2 < 0 or l3 < 0:
            continue
        if l1 * a[2] + l2 * b[2] + l3 * c[2] > z:
            cnt += 1
    return cnt % 2 == 1


def show(tris, z, nx=100, ny=40):
    idx = build_index(tris)
    b = bbox(tris)
    print(f"--- z = {z:.2f} | X {b[0]:.1f}..{b[1]:.1f} ({(b[1]-b[0])/nx:.2f} mm/col)"
          f" | Y {b[2]:.1f}..{b[3]:.1f} ({(b[3]-b[2])/ny:.2f} mm/ligne)")
    hdr = ''.join(str(int((b[0] + (b[1]-b[0])*(i+0.5)/nx) // 10 % 10)) for i in range(nx))
    print(f"        |{hdr}|  (dizaines de X)")
    for j in range(ny):
        y = b[2] + (b[3] - b[2]) * (j + 0.5) / ny
        row = ''.join('#' if solid(tris, idx, b[0] + (b[1]-b[0])*(i+0.5)/nx, y, z)
                      else '.' for i in range(nx))
        print(f"{y:7.2f} |{row}|")


if __name__ == '__main__':
    tris = []
    files = [a for a in sys.argv[1:] if not a.replace('.', '').replace('-', '').isdigit()]
    zs = [float(a) for a in sys.argv[1:] if a not in files]
    for f in files:
        tris += load_tris(f)
    for z in zs:
        show(tris, z)
