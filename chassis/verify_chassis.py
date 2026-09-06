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
    for nom in ('body_a', 'body_b', 'foot_arc', 'head_pan', 'head_tilt',
                'sensor_mount'):
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
        # ---- body_a : MOITIÉ AVANT (posée sur le plan de joint Y = -0.4) ----
        # NB : y = 2.0 (= MAST_Y1) est un sommet du raccord 45° -> rayon dégénéré.
        ('body_a', 23.9, 3.4, 32.5, False, "avant de la lumière servo DROITE"),
        ('body_a', -23.9, 3.4, 32.5, False, "avant de la lumière servo GAUCHE"),
        ('body_a', 23.9, 6.8, 32.5, True, "plaque porte-servo conservée devant"),
        ('body_a', 0.3, 3.0, 25.0, False, "logette MPU6050 (moitié avant)"),
        ('body_a', 3.0, 6.0, 23.0, True, "piédestal MPU sous la logette"),
        ('body_a', 0.3, 0.5, 60.0, True, "paroi avant du mât (posée sur le joint)"),
        ('body_a', 0.3, 5.0, 60.0, False, "au-delà de la paroi : vide (body_b)"),
        ('body_a', 18.6, 0.1, 70.3, False, "rainure du tenon latéral du mât"),
        ('body_a', 5.0, 1.0, 127.0, True, "montant central de la paroi de caisson"),
        ('body_a', -15.0, 1.0, 127.0, False, "fenêtre de câblage GAUCHE (pins GPIO)"),
        ('body_a', 21.0, 1.0, 127.0, False, "fenêtre de câblage DROITE (pins GPIO)"),
        ('body_a', 0.3, 5.0, 127.0, False, "espace de câblage au dos de la carte"),
        ('body_a', 10.0, 6.0, 120.0, False, "dégagement des fils au dos de la carte"),
        ('body_a', -28.0, 5.0, 127.0, True, "appui arrière carte côté USB"),
        ('body_a', 28.5, 5.0, 127.0, True, "appui arrière carte côté zone nue"),
        ('body_a', 0.3, 3.0, 113.0, True, "tablette basse du berceau"),
        ('body_a', 0.3, 10.0, 114.5, True, "lèvre de maintien de l'arête basse"),
        ('body_a', 28.0, 8.4, 114.5, True, "nervure de pince (clipsage)"),
        ('body_a', -32.0, 5.0, 127.0, False, "échancrure USB-C dans la joue"),
        ('body_a', -32.0, 5.0, 118.0, True, "joue pleine sous l'échancrure USB"),
        ('body_a', 16.0, 3.0, 23.5, False, "mortaise du tenon de socle"),
        ('body_a', 11.0, 3.0, 23.5, True, "chair du plot de joint (socle)"),
        # décalé de l'axe X du perçage : le 32-gone y place un sommet au zénith
        ('body_a', 25.2, 4.0, 110.0, False, "alésage Ø6 du goujon (caisson)"),
        ('body_a', 28.0, 4.0, 108.5, True, "chair du gousset autour de l'alésage"),
        ('body_a', 5.6, 3.0, 21.2, False, "avant-trou M3 dans le plancher"),
        ('body_a', 2.0, 6.0, 21.2, True, "plancher plein entre les avant-trous"),
        # ---- body_b : MOITIÉ ARRIÈRE (posée sur son dos plan Y = -20) -------
        ('body_b', 23.9, -10.0, 32.5, False, "arrière de la lumière servo DROITE"),
        ('body_b', -23.9, -10.0, 32.5, False, "arrière de la lumière servo GAUCHE"),
        ('body_b', 23.9, -18.5, 32.5, True, "plaque porte-servo conservée derrière"),
        ('body_b', 0.3, -8.0, 25.0, False, "logette MPU6050 (moitié arrière)"),
        ('body_b', 0.3, -3.8, 24.0, True, "matière SOUS la logette MPU"),
        ('body_b', 8.5, -8.0, 25.5, True, "bord de la logette MPU (bridage)"),
        ('body_b', 0.3, -10.0, 60.0, False, "mât creux = goulotte de câbles"),
        ('body_b', 0.3, -19.0, 60.0, True, "dos PLAN du mât (Y = -20 .. -17.6)"),
        ('body_b', 18.6, 0.1, 70.3, True, "tenon latéral du mât"),
        ('body_b', 0.3, -10.0, 127.0, False, "caisson creux (chemin des fils)"),
        ('body_b', 0.3, -19.0, 112.0, False, "passe-fil arrière ouvert"),
        ('body_b', 0.3, -19.0, 130.0, True, "dos plein au-dessus du passe-fil"),
        ('body_b', 16.0, 3.0, 23.5, True, "tenon de socle (venu de fonderie)"),
        ('body_b', 23.0, 3.0, 109.0, True, "goujon Ø5.8 du caisson"),
        ('body_b', 5.5, -10.0, 21.2, False, "passage M3 du socle"),
        ('body_b', 24.5, -10.0, 112.9, False, "passage M3 du caisson"),
        ('body_b', 27.5, -10.0, 112.9, True, "plot de joint plein (caisson)"),
        ('body_b', 5.5, -8.0, 147.0, False, "lumière du servo pan dans l'assise"),
        ('body_b', 26.0, -14.0, 147.0, False, "avant-trou M3 de la tête"),
        # ---- foot_arc : pied en arc (repère local, z = 0 = face EXTERNE) ----
        ('foot_arc', 0.3, -31.0, 4.5, True, "bande de roulement pleine (bas)"),
        ('foot_arc', -31.0, 0.3, 4.5, True, "bande de roulement pleine (flanc)"),
        ('foot_arc', 0.3, 20.0, 4.5, False, "hors de l'arc (secteur ouvert)"),
        ('foot_arc', 13.0, -25.0, 4.5, False, "évidement entre nervures"),
        ('foot_arc', 0.3, -20.6, 4.5, True, "arc intermédiaire de rigidification"),
        ('foot_arc', 0.3, 0.3, 1.5, True, "moyeu plein sous l'empreinte"),
        ('foot_arc', 0.3, 0.3, 7.0, False, "empreinte du palonnier (moyeu)"),
        ('foot_arc', 8.0, 0.3, 7.0, False, "empreinte du palonnier (bras)"),
        ('foot_arc', 6.2, 5.8, 7.0, True, "matière entre deux bras du palonnier"),
        ('foot_arc', 0.3, 0.3, 4.5, False, "dégagement de la vis centrale"),
        ('foot_arc', 5.0, 0.4, 2.0, False, "trou oblong M2 du palonnier"),
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
        ('sensor_mount', 0.3, 20.0, 0.3, False, "champ des transducteurs dégagé"),
        ('sensor_mount', 0.3, 12.0, 11.5, False, "AUCUNE matière entre les capsules"),
        ('sensor_mount', 0.3, 4.0, 11.5, False, "rail haut supprimé au centre"),
        ('sensor_mount', 20.0, 3.0, 11.5, True, "bord latéral haut conservé"),
        ('sensor_mount', 20.0, 5.8, 9.4, True, "lèvre haute latérale (retenue PCB)"),
        ('sensor_mount', 20.0, 5.8, -9.4, True, "lèvre basse latérale (retenue PCB)"),
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
