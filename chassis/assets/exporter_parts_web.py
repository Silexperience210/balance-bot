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
Y = arrière→avant, Z = haut ; sol z = 0 ; axe des roues z = cotes.AXLE_Z
(42,0 mm, rayon monté). La physique du simulateur reste à 41,5 mm :
selfcheck.js fige des références sur cette valeur. Voir cotes.py.

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
import sys

import numpy as np
import trimesh

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "chassis"))
import cotes  # noqa: E402

V3 = os.path.join(ROOT, "chassis", "v3")
OUT = os.path.join(ROOT, "sim", "web", "parts.js")

# ── constantes d'assemblage — SOURCE : cotes.py + assemblage_pour_rendu().
#    NE PAS reprendre vue_eclatee.py : ses cotes sont celles du dessin éclaté.
#    Les origines de roue sont les FACES externes (z local = 0).
_face_g, _face_d, X_MID, TRACK = cotes.roues_apres_miroir()
Y_WHEEL = 0.0           # l'axe des roues est DANS le plan de joint (y = 0)
Z_WHEEL = cotes.AXLE_Z  # 42,0 mm — rayon monté, pas le brut non étiré 41,5
E_PNEU = (cotes.WHEEL_W - cotes.TIRE_W) / 2.0

CENTRE = np.array([X_MID, Y_WHEEL, Z_WHEEL])   # → origine du repère robot
RAYON_ROULEMENT = Z_WHEEL * 0.001              # hauteur visuelle de l'axe
# Le module ultrason n'est pas dans les STL. 0,098 m était calé sur un axe
# à 41,5 mm : on le suit pour qu'il reste dans le lobe haut du glyphe.
YEUX_Y = 0.098 - (Z_WHEEL - 41.5) * 0.001
ECRAN = cotes.ecran_viewer()


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

# D (sx=−1, x petit) = panse, moyeu long. G = spine, moyeu court.
# L'origine reste la face externe : X_MID ± entraxe/2 est encore juste,
# les deux faces étant symétriques autour du glyphe.
FICHIERS_ROUE = {"D": "coin_wheel_panse.stl", "G": "coin_wheel_spine.stl"}
v_pneu, f_pneu = charge_indexe("coin_tire.stl")
for cote, sx in (("D", -1), ("G", 1)):
    v_roue, f_roue = charge_indexe(FICHIERS_ROUE[cote])
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
L.append('    "source": "chassis/v3/b_front.stl, b_back.stl, coin_wheel_panse.stl, coin_wheel_spine.stl, coin_tire.stl",')
L.append('    "assemblage": "gen_bitcoin_bot.py (assemblage reel : roues a X_MID+/-(TRACK/2), Y_WHEEL=0, pneu a +0.5 mm local)",')
L.append('    "unites": "m",')
L.append(f'    "rayonRoulement": {RAYON_ROULEMENT},')
L.append(f'    "voie": {TRACK * 0.001},')
L.append(f'    "ecran": [{ECRAN[0]}, {ECRAN[1]}, {ECRAN[2]}],')
L.append(f'    "yeuxY": {YEUX_Y}')
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
