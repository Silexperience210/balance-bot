#!/usr/bin/env python3
"""Verification finale apres corrections (pores bouches) — a lancer sur les STL courants."""
import os
import trimesh
import numpy as np
from collections import Counter

V3 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "v3") + os.sep
nok = ntot = 0


def load(p):
    m = trimesh.load(p, process=True); m.merge_vertices(); return m


def report(label, ok, detail):
    global nok, ntot
    ntot += 1; nok += 1 if ok else 0
    print("  %s %-52s %s" % ("OK " if ok else "KO ", label, detail))


f = load(V3 + "b_front.stl"); b = load(V3 + "b_back.stl"); w = load(V3 + "coin_wheel.stl"); t = load(V3 + "coin_tire.stl")

print("=== topologie ===")
for label, m in (("b_front", f), ("b_back", b), ("coin_wheel", w), ("coin_tire", t)):
    c = Counter(map(tuple, m.edges_sorted))
    free = sum(1 for e, n in c.items() if n == 1)
    nonman = sum(1 for e, n in c.items() if n > 2)
    comps = len(m.split(only_watertight=False))
    report("%s : aretes libres = 0" % label, free == 0, "%d libre(s), %d non-manifold, %d composante(s), watertight=%s" % (free, nonman, comps, m.is_watertight))

print("=== cotes ===")
report("b_front bbox", np.allclose(f.bounds[1] - f.bounds[0], [132.13, 23.02, 201.0], atol=0.05), str(np.round(f.bounds[1] - f.bounds[0], 2)))
report("b_back bbox", np.allclose(b.bounds[1] - b.bounds[0], [132.13, 29.0, 201.0], atol=0.05), str(np.round(b.bounds[1] - b.bounds[0], 2)))
report("coin_wheel bbox", np.allclose(w.bounds[1] - w.bounds[0], [80.0, 80.0, 21.01], atol=0.05), str(np.round(w.bounds[1] - w.bounds[0], 2)))
report("coin_tire bbox", np.allclose(t.bounds[1] - t.bounds[0], [83.0, 83.0, 7.0], atol=0.05), str(np.round(t.bounds[1] - t.bounds[0], 2)))
report("front volume ~106 cm3", abs(float(f.volume) / 1000 - 105.8) < 1.5, "%.1f cm3" % (float(f.volume) / 1000))
report("back volume ~91 cm3", abs(float(b.volume) / 1000 - 91.5) < 1.5, "%.1f cm3" % (float(b.volume) / 1000))

print("=== fonctionnel ===")
def ray(m, o, d):
    h = m.ray.intersects_location(np.array([o]), np.array([d]), multiple_hits=True)
    return h[0]
for side, x0, x1 in (("GAUCHE", -6, 14), ("DROIT", 104, 122)):
    hits = [float(p[0]) for p in ray(f, [x0, 12.8, 41.5], [1, 0, 0])]
    report("palier %s : paroi du tube a y=12.8" % side, len(hits) >= 2, "croisements x=%s" % [round(h, 2) for h in sorted(hits)])
for (x, z) in ((108.0, 75.5), (108.0, 144.8), (48.0, 33.0), (57.8, 184.6)):
    hits = sorted(float(p[1]) for p in ray(f, [x, -5, z], [0, 1, 0]))
    report("avant-trou M3 (%.1f,%.1f) vide 0.5-16.5" % (x, z), len(hits) == 4 and abs(hits[1] - 0.5) < 0.2 and abs(hits[2] - 16.5) < 0.2, "y=%s" % [round(h, 2) for h in hits])
for (x, z) in ((108.0, 38.0), (108.0, 179.0), (6.4, 72.0), (18.2, 145.0)):
    hits = sorted(float(p[1]) for p in ray(f, [x, -5, z], [0, 1, 0]))
    report("goujon Ø6 (%.1f,%.1f) vide jusqu'a 8.5" % (x, z), len(hits) >= 1 and abs(hits[0] - 8.5) < 0.4, "y=%s" % [round(h, 2) for h in hits])
for (x, z) in ((77.4, 145.0), (51.4, 145.0)):
    hits = sorted(float(p[1]) for p in ray(f, [x, -5, z], [0, 1, 0]))
    report("oeil HC-SR04 (%.1f,%.1f) debouchant" % (x, z), len(hits) == 0, "y=%s" % [round(h, 2) for h in hits])
hits = sorted(float(p[1]) for p in ray(f, [59.0, -5, 66.8], [0, 1, 0]))
report("fenetre ecran debouchante", len(hits) == 0, "y=%s" % [round(h, 2) for h in hits])
hits = sorted(float(p[2]) for p in ray(w, [0.0, 35.0, -5], [0, 0, 1]))
report("roue : jante presente (r=35)", len(hits) >= 2, "z=%s" % [round(h, 2) for h in hits])
hits = sorted(float(p[2]) for p in ray(t, [0.0, 40.0, -5], [0, 0, 1]))
report("pneu : matiere (r=40)", len(hits) >= 2, "z=%s" % [round(h, 2) for h in hits])

print()
print("RESULTAT FINAL : %d/%d" % (nok, ntot))
