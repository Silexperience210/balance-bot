#!/usr/bin/env python3
"""Vérifications spécifiques BalanceBot, en complément de verify_stl.py.

1. Contrôle manifold AVEC UNE CLÉ D'ARÊTE CORRECTE.
   verify_stl.py utilise `sorted(round(v,3) for v in a+b)` : il trie les 6
   COORDONNÉES ensemble, si bien que deux arêtes distinctes partageant le même
   multi-ensemble de valeurs sont confondues. D'où des faux positifs
   « non-manifold ». Ici la clé est la paire ORDONNÉE de sommets.
2. Sondage MATIÈRE/VIDE par lancer de rayon aux emplacements attendus.
   Piège : un point de sonde posé exactement sur un plan de symétrie ou sur
   l'axe d'un cylindre fait longer au rayon une arête de triangulation, et le
   comptage de traversées devient faux. Tous les points sont donc décalés.
"""
import sys
from collections import defaultdict

from measure_ref import load_tris, section
from probe_fast import build_index, solid

ICI = __import__('os').path.dirname(__import__('os').path.abspath(__file__))


def edges_ok(tris, tol=1e-3):
    """Renvoie (bords libres, arêtes non-manifold) avec une clé correcte."""
    cnt = defaultdict(int)
    q = 1.0 / tol
    for t in tris:
        vs = [tuple(round(c * q) for c in v) for v in t]
        for a, b in ((vs[0], vs[1]), (vs[1], vs[2]), (vs[2], vs[0])):
            cnt[(a, b) if a < b else (b, a)] += 1
    return (sum(1 for c in cnt.values() if c == 1),
            sum(1 for c in cnt.values() if c > 2))


def spans(tris, axis, val, idx):
    """Intervalles occupés le long de `idx` dans la coupe `axis = val`."""
    s = section(tris, axis, val)
    vals = sorted(p[idx] for seg in s for p in seg)
    if not vals:
        return []
    runs, start, prev = [], vals[0], vals[0]
    for v in vals[1:]:
        if v - prev > 0.8:
            runs.append((start, prev))
            start = v
        prev = v
    runs.append((start, prev))
    return runs


def fmt(runs):
    return ' '.join(f'[{a:.2f},{b:.2f}]' for a, b in runs)


def main():
    ok = True
    for nom in ('body', 'wheel', 'head_pan', 'head_tilt', 'sensor_mount'):
        t = load_tris(f'{ICI}/{nom}.stl')
        libres, nm = edges_ok(t)
        etat = 'OK' if (libres == 0 and nm == 0) else '*** DÉFAUT ***'
        if libres or nm:
            ok = False
        print(f"{nom:14s} tris={len(t):5d}  bords libres={libres}  "
              f"non-manifold={nm}  -> {etat}")

    # -- Sondage MATIÈRE / VIDE en des points précis -------------------------
    # Un plan de coupe ne suffit pas : les parois planes n'ont de sommets qu'à
    # leurs extrémités, donc « pas de segment ici » ne veut pas dire « vide ».
    # On teste donc l'appartenance au solide par lancer de rayon.
    print("\n--- Sondage matière/vide aux emplacements attendus ---")
    cas = [
        # (pièce, x, y, z, attendu_plein, description)
        ('body', 24.0, 0.0, 32.5, False, "lumière servo roue DROITE traversante"),
        ('body', -24.0, 0.0, 32.5, False, "lumière servo roue GAUCHE traversante"),
        ('body', 24.0, 6.5, 32.5, True, "plaque porte-servo conservée devant"),
        ('body', 24.0, -17.3, 32.5, True, "plaque porte-servo conservée derrière"),
        ('body', 0.3, -3.8, 25.0, False, "logette MPU6050 (creuse)"),
        ('body', 0.3, -3.8, 24.0, True, "matière SOUS la logette MPU"),
        ('body', 8.5, -3.8, 25.5, True, "bord de la logette MPU (bridage)"),
        ('body', 0.3, -8.0, 60.0, False, "mât creux"),
        ('body', 0.3, -17.0, 60.0, True, "paroi arrière du mât"),
        ('body', 0.3, 5.0, 127.0, False, "baie de la carte (libre)"),
        ('body', -28.0, 5.0, 127.0, True, "appui arrière carte côté USB"),
        ('body', 28.5, 5.0, 127.0, True, "appui arrière carte côté zone nue"),
        ('body', 0.3, 3.0, 113.0, True, "tablette basse du berceau"),
        ('body', 0.3, 10.0, 114.5, True, "lèvre de maintien de l'arête basse"),
        ('body', 28.0, 8.4, 114.5, True, "nervure de pince (clipsage)"),
        ('body', -32.0, 5.0, 127.0, False, "échancrure USB-C dans la joue"),
        ('body', -32.0, 5.0, 118.0, True, "joue pleine sous l'échancrure USB"),
        ('body', 5.5, -8.0, 147.0, False, "lumière du servo pan dans l'assise"),
        ('body', 26.0, -14.0, 147.0, False, "avant-trou M3 de la tête"),
        ('wheel', 0.3, 0.3, 4.0, False, "alésage Ø5.2 du moyeu"),
        ('wheel', 4.5, 0.3, 4.0, True, "chair du moyeu autour de l'alésage"),
        ('wheel', 5.0, 0.4, 5.9, False, "trou de vis radiale M2"),
        ('wheel', 0.3, 0.3, 8.5, False, "lamage Ø12.4 du bossage servo"),
        ('wheel', 5.5, 0.3, 8.5, False, "lamage Ø12.4 (rayon 5.5)"),
        ('wheel', 31.0, 0.3, 4.5, True, "bandeau extérieur plein"),
        ('wheel', 17.3, 10.0, 4.5, False, "évidement entre rayons"),
        ('head_pan', 5.8, -8.3, 3.0, False, "lumière du servo pan"),
        ('head_pan', 26.0, -14.0, 2.0, False, "trou M3 passant"),
        ('head_tilt', 0.3, 0.3, 3.0, False, "alésage sur l'axe du servo pan"),
        ('head_tilt', -14.0, 0.0, 34.0, False, "lumière du servo de tangage"),
        ('head_tilt', -14.0, 6.5, 34.0, True, "bras gauche autour de la lumière"),
        ('head_tilt', 5.0, 0.7, 34.3, True, "tourillon libre"),
        ('sensor_mount', 0.3, 4.0, 0.3, False, "baie du HC-SR04"),
        ('sensor_mount', -13.0, 12.0, 0.0, False, "fenêtre capsule gauche"),
        ('sensor_mount', 13.0, 12.0, 0.0, False, "fenêtre capsule droite"),
        ('sensor_mount', 0.3, -6.0, 0.3, True, "moyeu central au dos"),
        ('sensor_mount', -3.5, -2.0, 0.3, False, "alésage de l'axe de tangage"),
        ('sensor_mount', 4.0, -2.0, 0.3, False, "logement du tourillon"),
        ('sensor_mount', 0.3, 2.0, -11.0, True, "rail bas (broches dessous)"),
    ]
    cache = {}
    for nom, x, y, z, attendu, desc in cas:
        if nom not in cache:
            tr = load_tris(f'{ICI}/{nom}.stl')
            cache[nom] = (tr, build_index(tr))
        tr, idx = cache[nom]
        got = solid(tr, idx, x, y, z)
        bon = (got == attendu)
        if not bon:
            ok = False
        print(f"  [{'OK ' if bon else 'ÉCHEC'}] {nom:13s} "
              f"({x:6.1f},{y:6.1f},{z:6.1f}) "
              f"{'plein' if attendu else 'vide ':5s} attendu — {desc}")

    print("\nRÉSULTAT GLOBAL :", "TOUT CONFORME" if ok else "*** ANOMALIES ***")
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
