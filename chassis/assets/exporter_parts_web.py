#!/usr/bin/env python3
"""Exporte les VRAIES pièces du châssis (STL binaires) vers sim/web/parts.js.

Pourquoi : le viewer sim/web/index.html doit s'ouvrir en file:// (double-clic) —
un fetch/XHR de STL est bloqué par CORS. Les géométries sont donc embarquées
en base64 (positions Float32 + indices Uint32, géométrie INDEXÉE après
dédoublonnage exact des sommets de la soupe STL).

Assemblage : COPIÉ de chassis/assets/vue_eclatee.py (référence visuelle) :
    coques  : b_front / b_back à leur place STL (joint à y = 0)
    roues   : pour chaque côté (D : sx=-1, G : sx=+1)
                  x = X_MID + sx·TRACK/2,  rotation (0, -sx·π/2, 0),
                  location (x, Y_WHEEL, Z_WHEEL)
    pneus   : même rotation, location (x + sx·10, Y_WHEEL, Z_WHEEL)  (déport de la vue éclatée)

Repère design (Blender, gen_bitcoin_bot.py) : X = gauche→droite (voie),
Y = arrière→avant, Z = haut ; sol z = 0 ; axe des roues z = WHEEL_R = 41.5 mm.

Repère robot exporté (Three.js, Y-up) — conversion Z_up → Y_up :
    x_three = y_design   (avance / roulement)
    y_three = z_design   (verticale)
    z_three = x_design   (axe transverse = axe des ROUES = axe de tangage)
Permutation cyclique, déterminant +1 : l'orientation des triangles est conservée.
ORIGINE : point central de l'axe des roues (X_MID, Y_WHEEL, Z_WHEEL) du repère
design — le tangage θ du corps et le spin (θ+φ) des roues se font autour de
l'axe Z passant par l'origine. Unités : MÈTRES (×0.001).

Usage : ~/.hermes/venvs/dfam/bin/python chassis/assets/exporter_parts_web.py
"""
import base64
import os

import numpy as np
import trimesh

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V3 = os.path.join(ROOT, "chassis", "v3")
OUT = os.path.join(ROOT, "sim", "web", "parts.js")

# ── constantes d'assemblage — SOURCE : gen_bitcoin_bot.py, la fonction
#    d'assemblage RÉELLE (« assembled »). NE PAS reprendre vue_eclatee.py : ses
#    cotes de pneu/palier sont celles de la vue ÉCLATÉE, donc fausses ici
#    (déport +10 mm, y = 12,8). En cas de divergence, le générateur fait foi.
X_MID = 64.565          # centre de l'axe des roues (roues à −8,87 et +138,00)
TRACK = 146.87          # entraxe des ORIGINES de roue (faces externes) = 138,00 − (−8,87)
Y_WHEEL = 0.0           # l'axe des roues est DANS le plan de joint (y = 0), PAS 12,8
Z_WHEEL = 41.5          # axe des roues = rayon de roulement WHEEL_R
E_PNEU = 0.5            # dt = (WHEEL_W − TIRE_W)/2 : pneu centré sur le disque de jante

CENTRE = np.array([X_MID, Y_WHEEL, Z_WHEEL])   # → origine du repère robot
RAYON_ROULEMENT = Z_WHEEL * 0.001              # 0.0415 m


def charge_indexe(nom):
    """Charge un STL (soupe de triangles) et dédoublonne les sommets :
    géométrie indexée (positions uniques + indices)."""
    m = trimesh.load(os.path.join(V3, nom))
    v = np.asarray(m.vertices, dtype=np.float64)
    f = np.asarray(m.faces, dtype=np.int64)
    # Les sommets partagés sont bit-identiques dans le STL binaire exporté par
    # Blender : un np.unique exact suffit (fait AVANT toute transformation).
    uniq, inv = np.unique(v, axis=0, return_inverse=True)
    return uniq, inv[f].astype(np.uint32)


def rot_y(alpha):
    """Rotation autour de Y (repère design), équivalent de rotation_euler=(0,α,0)."""
    c, s = np.cos(alpha), np.sin(alpha)
    return np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]])


IDENT = np.eye(3)
ZERO = np.zeros(3)


def transforme(v, rot, loc):
    """Assemblage repère design (mm) → repère robot Three.js (m, Y-up)."""
    p = v @ rot.T + loc                     # pose dans le repère design
    p = (p - CENTRE) * 0.001                # origine = axe des roues, mm → m
    return p[:, [1, 2, 0]]                  # (x,y,z)_design → (y,z,x)_three


# ── les 4 STL → 6 pièces posées ────────────────────────────────────────────
pieces = []   # (id, role, positions Nx3 float64 en m, indices Mx3 uint32)

v, f = charge_indexe("b_front.stl")
pieces.append(("b_front", "coque", transforme(v, IDENT, ZERO), f))

v, f = charge_indexe("b_back.stl")
pieces.append(("b_back", "coque", transforme(v, IDENT, ZERO), f))

v_roue, f_roue = charge_indexe("coin_wheel.stl")
v_pneu, f_pneu = charge_indexe("coin_tire.stl")
for cote, sx in (("D", -1), ("G", 1)):
    x = X_MID + sx * (TRACK / 2)
    rot = rot_y(-sx * np.pi / 2)                    # rotation_euler = (0, -sx·π/2, 0)
    loc_roue = np.array([x, Y_WHEEL, Z_WHEEL])
    # Le pneu est centré sur le DISQUE de la jante : décalage de E_PNEU dans le
    # repère LOCAL de la roue (+z local, AVANT rotation) — sémantique exacte de
    # gen_bitcoin_bot.py (`dt = (WHEEL_W - TIRE_W)/2`, puis xw ∓ 21 ± dt).
    loc_pneu = loc_roue + rot @ np.array([0.0, 0.0, E_PNEU])
    pieces.append((f"roue_{cote}", "roue", transforme(v_roue, rot, loc_roue), f_roue))
    pieces.append((f"pneu_{cote}", "pneu", transforme(v_pneu, rot, loc_pneu), f_pneu))


def b64(tableau):
    return base64.b64encode(tableau.tobytes()).decode("ascii")


# ── écriture de parts.js (JS plain, zéro fetch : utilisable en file://) ────
L = []
L.append("/* GÉNÉRÉ par chassis/assets/exporter_parts_web.py — ne pas éditer à la main.")
L.append("   Vraies pièces du châssis (chassis/v3/*.stl) assemblées, géométrie INDEXÉE.")
L.append("   Encodage : positions Float32 LE + indices Uint32 LE, en base64 (zéro fetch,")
L.append("   utilisable en file://). Décodage dans ui.js (decodeB64).")
L.append("")
L.append("   REPÈRE (conversion Z_up design → Y_up Three.js, permutation cyclique dét +1) :")
L.append("     x = avance (ex-Y design)   y = haut (ex-Z design)   z = axe des roues (ex-X design)")
L.append("   Origine : point central de l'axe des roues ; unités : mètres. */")
L.append("window.BALANCEBOT_PARTS = {")
L.append('  "meta": {')
L.append('    "source": "chassis/v3/b_front.stl, b_back.stl, coin_wheel.stl, coin_tire.stl",')
L.append('    "assemblage": "gen_bitcoin_bot.py (assemblage reel : roues a X_MID+/-(TRACK/2), Y_WHEEL=0, pneu a +0.5 mm local)",')
L.append('    "unites": "m",')
L.append(f'    "rayonRoulement": {RAYON_ROULEMENT},')
L.append(f'    "voie": {TRACK * 0.001}')
L.append("  },")
L.append('  "pieces": {')
total_tri = 0
for i, (pid, role, pos, idx) in enumerate(pieces):
    assert idx.shape[0] > 0, f"{pid}: aucun triangle"
    total_tri += idx.shape[0]
    virgule = "," if i < len(pieces) - 1 else ""
    L.append(f'    "{pid}": {{ "role": "{role}", "triangles": {idx.shape[0]}, "sommets": {pos.shape[0]},')
    L.append(f'      "positions": "{b64(pos.astype(np.float32))}",')
    L.append(f'      "indices": "{b64(idx.astype(np.uint32))}" }}{virgule}')
L.append("  }")
L.append("};")
L.append("")

with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(L))

# ── résumé de contrôle ─────────────────────────────────────────────────────
print(f"ÉCRIT → {OUT} ({os.path.getsize(OUT)} octets)")
for pid, role, pos, idx in pieces:
    mn, mx = pos.min(axis=0) * 1000, pos.max(axis=0) * 1000
    print(f"  {pid:9s} {role:5s} {idx.shape[0]:6d} triangles, {pos.shape[0]:6d} sommets | "
          f"bbox x[{mn[0]:6.1f},{mx[0]:6.1f}] y[{mn[1]:6.1f},{mx[1]:6.1f}] z[{mn[2]:6.1f},{mx[2]:6.1f}] mm")
print(f"  TOTAL {total_tri} triangles")
