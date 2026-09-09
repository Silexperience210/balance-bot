#!/usr/bin/env python3
"""Retrouve la transformation (rotation propre + translation) qui place une piece dans une plaque.

Sert a VALIDER chassis/make_plates.py : si l'alignement des sommets est a 100 %, la transformation
de la plaque est bien celle attendue (aucun miroir, aucune rotation parasite).

Usage :
    python3 find_transform.py <piece.stl> <plaque.stl>
    # ex. python3 find_transform.py ../v3/b_front.stl ../../export/v31/plate1_b_front.stl
"""
import itertools
import sys

import numpy as np
import trimesh
from scipy.spatial import cKDTree


def rot_mats():
    """24 rotations propres du cube (det = +1)."""
    out = []
    for perm in itertools.permutations(range(3)):
        for signs in itertools.product((1, -1), repeat=3):
            M = np.zeros((3, 3))
            for i, (p, s) in enumerate(zip(perm, signs)):
                M[i, p] = s
            if abs(np.linalg.det(M) - 1.0) < 1e-9:
                out.append(M)
    return out


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    src = trimesh.load(sys.argv[1], process=True); src.merge_vertices()
    tgt = trimesh.load(sys.argv[2], process=True); tgt.merge_vertices()
    sv = np.asarray(src.vertices)
    tree = cKDTree(np.asarray(tgt.vertices))
    best = None
    for M in rot_mats():
        rv = sv @ M.T
        t = tgt.bounds[0] - rv.min(axis=0)
        d, _ = tree.query(rv + t, k=1)
        frac = float((d < 0.01).mean())
        if best is None or frac > best[0]:
            best = (frac, M, t)
    frac, M, t = best
    print("sommets alignes : %d/%d (%.1f %%)" % (int(frac * len(sv)), len(sv), frac * 100))
    print("rotation :\n%s" % np.array_str(M, precision=0))
    print("translation : %s" % np.round(t, 2))
    print("bbox piece transformee : %s -> %s" % (np.round(src.bounds[0] @ M.T + t, 2), np.round(src.bounds[1] @ M.T + t, 2)))
    print("bbox plaque reelle     : %s -> %s" % (np.round(tgt.bounds[0], 2), np.round(tgt.bounds[1], 2)))


if __name__ == "__main__":
    main()
