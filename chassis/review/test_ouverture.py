#!/usr/bin/env python3
"""La coque avant est-elle ouverte au joint (design CREUX) ou scellee par une peau ?

Lecture : 2 croisements le long de Y dans une zone de cavite = paroi externe seule -> OUVERTE.
           3+ croisements = il y a une peau/un couvercle au plan de joint.
Usage : python3 test_ouverture.py [chemin.stl]   (defaut : ../v3/b_front.stl)
"""
import os
import sys
from collections import Counter

import numpy as np
import trimesh

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT = os.path.join(HERE, "..", "v3", "b_front.stl")

path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
m = trimesh.load(path, process=True)
m.merge_vertices()
c = Counter(map(tuple, m.edges_sorted))
free = [e for e, n in c.items() if n == 1]
nonman = [e for e, n in c.items() if n > 2]
print("### %s" % os.path.basename(path))
print("    aretes libres: %d | non-manifold: %d | watertight: %s" % (len(free), len(nonman), m.is_watertight))
for (x, z) in ((59.0, 100.0), (59.0, 120.0), (30.0, 100.0), (59.0, 30.0)):
    o = np.array([[x, -5.0, z]]); d = np.array([[0.0, 1.0, 0.0]])
    h = m.ray.intersects_location(o, d, multiple_hits=True)
    ys = sorted(round(float(p[1]), 2) for p in h[0])
    verdict = "OUVERTE au joint (paroi externe seule)" if len(ys) == 2 else (
        "peau/couvercle au joint" if len(ys) >= 3 else "%d croisements" % len(ys))
    print("    (x=%.0f, z=%.0f) : y=%s -> %s" % (x, z, ys, verdict))
