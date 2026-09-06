#!/usr/bin/env python3
"""Cartographie matière/vide d'un STL par lancer de rayons.

Permet de LIRE la cavité interne d'une coque (poche PCB, fenêtre écran,
découpes USB) au lieu de la déduire des bbox. On tire un rayon +Z depuis
(x, y, -inf) et on compte les traversées : impair = intérieur matière.
"""
import sys

from measure_ref import load_tris, bbox


def ray_hits_z(tris, x, y):
    """Altitudes z où le rayon vertical en (x,y) traverse une face."""
    zs = []
    for (a, b, c) in tris:
        # Test barycentrique en projection XY
        x1, y1 = a[0], a[1]
        x2, y2 = b[0], b[1]
        x3, y3 = c[0], c[1]
        den = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
        if abs(den) < 1e-12:
            continue
        l1 = ((y2 - y3) * (x - x3) + (x3 - x2) * (y - y3)) / den
        l2 = ((y3 - y1) * (x - x3) + (x1 - x3) * (y - y3)) / den
        l3 = 1.0 - l1 - l2
        if l1 < 0 or l2 < 0 or l3 < 0:
            continue
        zs.append(l1 * a[2] + l2 * b[2] + l3 * c[2])
    return sorted(zs)


def solid_at(tris, x, y, z):
    """True si (x,y,z) est dans la matière (nb de faces au-dessus impair)."""
    zs = ray_hits_z(tris, x, y)
    return sum(1 for zz in zs if zz > z) % 2 == 1


def occupancy(tris, z, nx=90, ny=70, box=None):
    """Grille ASCII matière('#')/vide('.') dans le plan XY à l'altitude z."""
    b = box or bbox(tris)
    rows = []
    for j in range(ny):
        y = b[2] + (b[3] - b[2]) * (j + 0.5) / ny
        row = ''
        for i in range(nx):
            x = b[0] + (b[1] - b[0]) * (i + 0.5) / nx
            row += '#' if solid_at(tris, x, y, z) else '.'
        rows.append((y, row))
    return b, rows


def show(tris, z, nx=90, ny=44, box=None):
    b, rows = occupancy(tris, z, nx, ny, box)
    print(f"--- z = {z:.2f}   X {b[0]:.1f}..{b[1]:.1f}  Y {b[2]:.1f}..{b[3]:.1f}"
          f"   (1 col = {(b[1]-b[0])/nx:.2f} mm, 1 ligne = {(b[3]-b[2])/ny:.2f} mm)")
    for y, row in rows:
        print(f"{y:7.2f} |{row}|")


if __name__ == '__main__':
    path = sys.argv[1]
    tris = load_tris(path)
    for z in [float(a) for a in sys.argv[2:]]:
        show(tris, z)
