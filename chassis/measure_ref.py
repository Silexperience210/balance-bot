#!/usr/bin/env python3
"""Mesure des STL de référence (coques T-Display S3) — ASCII ou binaire.

But : extraire les cotes RÉELLES de la carte LilyGo (contour, épaisseur,
positions des trous/encoches) au lieu de les supposer.

Méthode : coupes planes (plan-triangle) + histogrammes d'occupation, jamais
« à vue ». Voir references/parametric-enclosure.md.
"""
import struct
import sys
from collections import defaultdict


def load_tris(path):
    """Charge un STL ASCII ou binaire -> liste de triangles (3 sommets xyz)."""
    with open(path, 'rb') as f:
        data = f.read()
    # Détection ASCII : mot-clé "facet normal" dans les 1000 premiers octets
    head = data[:1000].lower()
    if head.lstrip().startswith(b'solid') and b'facet' in head:
        tris = []
        cur = []
        for line in data.decode('utf-8', 'ignore').splitlines():
            s = line.strip()
            if s.startswith('vertex'):
                cur.append(tuple(float(x) for x in s.split()[1:4]))
                if len(cur) == 3:
                    tris.append(cur)
                    cur = []
            elif s.startswith('outer loop'):
                cur = []
        return tris
    n = struct.unpack_from('<I', data, 80)[0]
    tris = []
    for i in range(n):
        off = 84 + i * 50
        tris.append([struct.unpack_from('<3f', data, off + 12 + j * 12)
                     for j in range(3)])
    return tris


def bbox(tris):
    xs = [v[0] for t in tris for v in t]
    ys = [v[1] for t in tris for v in t]
    zs = [v[2] for t in tris for v in t]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


def section(tris, axis, val):
    """Intersection plan-triangle -> segments 2D dans les 2 autres axes."""
    other = [i for i in range(3) if i != axis]
    segs = []
    for t in tris:
        pts = []
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            da, db = a[axis] - val, b[axis] - val
            if da * db <= 0 and abs(a[axis] - b[axis]) > 1e-9:
                u = (val - a[axis]) / (b[axis] - a[axis])
                pts.append((a[other[0]] + (b[other[0]] - a[other[0]]) * u,
                            a[other[1]] + (b[other[1]] - a[other[1]]) * u))
        if len(pts) == 2:
            segs.append(pts)
    return segs


def extents(segs):
    if not segs:
        return None
    us = [p[0] for s in segs for p in s]
    vs = [p[1] for s in segs for p in s]
    return min(us), max(us), min(vs), max(vs)


def spans_along(segs, idx, step=0.5):
    """Occupation 1D : renvoie les intervalles [a,b] occupés le long de l'axe idx.

    Sert à localiser les trous / encoches : les creux entre intervalles.
    """
    vals = sorted(p[idx] for s in segs for p in s)
    if not vals:
        return []
    runs = []
    start = prev = vals[0]
    for v in vals[1:]:
        if v - prev > step:
            runs.append((start, prev))
            start = v
        prev = v
    runs.append((start, prev))
    return runs


def report(path):
    tris = load_tris(path)
    b = bbox(tris)
    print(f"\n=== {path}")
    print(f"  triangles : {len(tris)}")
    print(f"  bbox : X {b[0]:8.2f}..{b[1]:8.2f}  ({b[1]-b[0]:6.2f})")
    print(f"         Y {b[2]:8.2f}..{b[3]:8.2f}  ({b[3]-b[2]:6.2f})")
    print(f"         Z {b[4]:8.2f}..{b[5]:8.2f}  ({b[5]-b[4]:6.2f})")
    return tris, b


if __name__ == '__main__':
    for p in sys.argv[1:]:
        report(p)
