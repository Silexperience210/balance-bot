#!/usr/bin/env python3
"""Extraction de cotes depuis un fichier STEP (AP203/214) sans dépendance CAO.

On ne reconstruit pas les B-Rep : on lit les CARTESIAN_POINT (sommets et
points de contrôle) et les CIRCLE (rayon + centre) pour obtenir le contour
et les perçages réels de la carte. Suffisant pour dimensionner un berceau.
"""
import re
import sys
from collections import Counter, defaultdict

PT = re.compile(r"#(\d+)\s*=\s*CARTESIAN_POINT\s*\(\s*'[^']*'\s*,\s*\(([^)]*)\)")
CIR = re.compile(r"#(\d+)\s*=\s*CIRCLE\s*\(\s*'[^']*'\s*,\s*#(\d+)\s*,\s*([0-9.E+-]+)")
AX2 = re.compile(r"#(\d+)\s*=\s*AXIS2_PLACEMENT_3D\s*\(\s*'[^']*'\s*,\s*#(\d+)")


def load(path):
    raw = open(path, encoding='utf-8', errors='ignore').read()
    # Les entités STEP peuvent être coupées en plusieurs lignes -> on recolle
    return re.sub(r'\s*\n\s*', ' ', raw)


def points(txt):
    out = {}
    for m in PT.finditer(txt):
        vals = [float(v) for v in m.group(2).split(',') if v.strip()]
        if len(vals) == 3:
            out[int(m.group(1))] = tuple(vals)
    return out


def circles(txt, pts):
    """Renvoie (rayon, centre) pour chaque CIRCLE, centre résolu via AXIS2."""
    ax = {int(m.group(1)): int(m.group(2)) for m in AX2.finditer(txt)}
    out = []
    for m in CIR.finditer(txt):
        r = float(m.group(3))
        a = int(m.group(2))
        c = pts.get(ax.get(a, -1))
        if c:
            out.append((r, c))
    return out


def main(path):
    txt = load(path)
    pts = points(txt)
    print(f"points  : {len(pts)}")
    xs = [p[0] for p in pts.values()]
    ys = [p[1] for p in pts.values()]
    zs = [p[2] for p in pts.values()]
    print(f"bbox    : X {min(xs):8.2f}..{max(xs):8.2f} ({max(xs)-min(xs):6.2f})")
    print(f"          Y {min(ys):8.2f}..{max(ys):8.2f} ({max(ys)-min(ys):6.2f})")
    print(f"          Z {min(zs):8.2f}..{max(zs):8.2f} ({max(zs)-min(zs):6.2f})")

    print("\nplans Z les plus peuplés (épaisseurs / faces) :")
    cz = Counter(round(z, 2) for z in zs)
    for z, n in sorted(cz.most_common(18)):
        print(f"   z = {z:8.2f}  ({n} pts)")

    cir = circles(txt, pts)
    print(f"\ncercles : {len(cir)}")
    byr = defaultdict(list)
    for r, c in cir:
        byr[round(r, 2)].append(c)
    for r in sorted(byr):
        if r < 0.4 or r > 6:
            continue
        cs = byr[r]
        uniq = sorted({(round(c[0], 2), round(c[1], 2), round(c[2], 2)) for c in cs})
        print(f"   R={r:5.2f} (Ø{2*r:5.2f})  {len(uniq)} centres uniques")
        for c in uniq[:14]:
            print(f"        {c}")


if __name__ == '__main__':
    main(sys.argv[1])
