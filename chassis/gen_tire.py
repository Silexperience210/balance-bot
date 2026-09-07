#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_tire.py — Pneu TPU antiderapant pour foot_arc.stl (BalanceBot)

Manchon en U (section de pneu de velo) qui s'emboite par elasticite sur la
jante exterieure du pied en arc. Le PLA/PETG lisse patine ; le TPU 95A accroche.

  * PIECE NOUVELLE : ne touche ni foot_arc.stl ni gen_chassis.py.
  * Repere identique a foot_arc.stl : axe de revolution = Z, jante en
    Z=[0, 9], arc centre sur 270 deg (-Y). On peut donc superposer
    foot_tire.stl et foot_arc.stl directement pour verifier l'emboitage.
  * Genere en pur numpy (revolution d'un profil 2D + capots par ear-clipping),
    puis auto-verifie : bbox, composantes connexes, aretes libres, volume.

Usage :
    python3 gen_tire.py              # ecrit foot_tire.stl (+ preview si mpl)
    python3 gen_tire.py --no-preview
"""

import math
import sys

import numpy as np
from stl import mesh as stlmesh

# ---------------------------------------------------------------------------
# PARAMETRES  (toutes cotes en mm / degres)
# ---------------------------------------------------------------------------

# --- Geometrie de la jante cible, relevee dans gen_chassis.py (verifiee) ----
RIM_R = 32.5          # FOOT_R      : rayon exterieur de la jante
RIM_W = 9.0           # FOOT_W      : largeur de la jante
RIM_T = 3.2           # FOOT_RIM_T  : epaisseur radiale (R=29.3 -> 32.5)
RIM_SPAN = 200.0      # FOOT_SPAN   : ouverture de l'arc
RIM_Z0 = 0.0          # la jante occupe Z = [0, RIM_W]

# --- Pneu -------------------------------------------------------------------
TIRE_SPAN = 195.0     # 5 deg de moins que l'arc -> jeu d'emboitage aux bouts
TIRE_R_IN = 32.3      # rayon interieur : 0.2 mm d'interference (mettre 32.5
                      # si trop dur a enfiler ; 32.1 si ca ne tient pas)
SOLE_T = 1.6          # gomme sous la semelle, mesuree depuis RIM_R (32.5)
                      # -> rayon exterieur = RIM_R + SOLE_T = 34.1

# Flancs : lèvres qui remontent sur les cotes de la jante et capturent
# lateralement le pneu.
#   FLANK_T : epaisseur AXIALE de chaque flanc. La spec donne une largeur
#             totale de 9.0 + 2*2.5 = 14 mm, ce qui impose 2.5 mm par flanc et
#             laisse une gorge de exactement RIM_W = 9.0 mm (ajustement juste).
#   FLANK_H : hauteur RADIALE dont le flanc descend le long du flanc de jante.
FLANK_T = 2.5
FLANK_H = 2.5         # 32.3 -> 29.8 : reste au-dessus de l'interieur de
                      # jante (29.3), le pneu ne talonne pas les nervures.

SLOT_W = RIM_W        # gorge interne (contact glissant sur les faces de jante)
SLOT_CLR = 0.0        # jeu axial ajoute a la gorge (0 = ajustement juste)

# --- Details ----------------------------------------------------------------
SOLE_FILLET = 0.3     # arrondi des aretes vives de la semelle (contact sol)
SOLE_FILLET_SEG = 4   # segments par arrondi
MOUTH_CHAMF = 0.4     # chanfrein d'entree de gorge (aide a enfiler)

# --- Discretisation ---------------------------------------------------------
ANG_SEG = 260         # segments sur les 195 deg (~0.75 deg -> corde 0.42 mm)

OUT_STL = "foot_tire.stl"
OUT_PNG = "foot_tire_preview.png"

# Bornes angulaires : arc centre sur 270 deg (-Y), comme foot_arc.
A_MID = 270.0
A0 = A_MID - TIRE_SPAN / 2.0          # 172.5
A1 = A_MID + TIRE_SPAN / 2.0          # 367.5

# Cotes derivees
R_OUT = RIM_R + SOLE_T                # 34.1  rayon de roulement
R_FLK = TIRE_R_IN - FLANK_H           # 29.8  bas des flancs
SLOT_Z0 = RIM_Z0                      # 0.0
SLOT_Z1 = RIM_Z0 + SLOT_W + SLOT_CLR  # 9.0
Z0 = SLOT_Z0 - FLANK_T                # -2.5
Z1 = SLOT_Z1 + FLANK_T                # 11.5


# ---------------------------------------------------------------------------
# Outils de profil 2D  (plan (r, z))
# ---------------------------------------------------------------------------

def fillet_corner(prev_p, corner, next_p, radius, segments):
    """Remplace un coin a 90 deg par un arc tangent de rayon `radius`.
    Retourne la liste de points de l'arc (de l'entree vers la sortie)."""
    p, c, n = map(np.asarray, (prev_p, corner, next_p))
    u = (p - c) / np.linalg.norm(p - c)      # vers le point precedent
    w = (n - c) / np.linalg.norm(n - c)      # vers le point suivant
    cosang = float(np.clip(np.dot(u, w), -1.0, 1.0))
    ang = math.acos(cosang)                  # angle interieur du coin
    d = radius / math.tan(ang / 2.0)         # recul le long de chaque arete
    a_in, a_out = c + u * d, c + w * d
    bis = (u + w)
    bis /= np.linalg.norm(bis)
    ctr = c + bis * (radius / math.sin(ang / 2.0))
    th_in = math.atan2(*(a_in - ctr)[::-1])
    th_out = math.atan2(*(a_out - ctr)[::-1])
    # chemin court entre les deux angles
    dth = (th_out - th_in + math.pi) % (2 * math.pi) - math.pi
    return [tuple(ctr + radius * np.array([math.cos(th_in + dth * k / segments),
                                           math.sin(th_in + dth * k / segments)]))
            for k in range(segments + 1)]


def build_profile():
    """Section transversale du pneu dans le plan (r, z), polygone ferme.

        z=11.5  +--------------------+ R_OUT (34.1)
                |                    |
        z= 9.4  |  +--\              |   <- chanfrein d'entree de gorge
        z= 9.0  |  |   +-------------+ ... gorge (contact jante)
                |  |   |             .
        z= 0.0  |  |   +-------------+ TIRE_R_IN (32.3)
        z=-0.4  |  +--/              |
        z=-2.5  +--------------------+
              R_FLK (29.8)        R_OUT
    """
    # Coins nominaux, sens direct dans le plan (r, z)
    c_flkA_in = (R_FLK, Z0)          # bas du flanc A, cote exterieur
    c_soleA = (R_OUT, Z0)            # arete vive semelle, cote A
    c_soleB = (R_OUT, Z1)            # arete vive semelle, cote B
    c_flkB_in = (R_FLK, Z1)          # bas du flanc B, cote exterieur
    c_mouthB = (R_FLK, SLOT_Z1)      # entree de gorge, cote B
    c_slotB = (TIRE_R_IN, SLOT_Z1)   # fond de gorge, cote B
    c_slotA = (TIRE_R_IN, SLOT_Z0)   # fond de gorge, cote A
    c_mouthA = (R_FLK, SLOT_Z0)      # entree de gorge, cote A

    pts = []
    pts.append(c_flkA_in)
    # -- semelle : les deux aretes vives au sol sont arrondies -------------
    pts += fillet_corner(c_flkA_in, c_soleA, c_soleB, SOLE_FILLET, SOLE_FILLET_SEG)
    pts += fillet_corner(c_soleA, c_soleB, c_flkB_in, SOLE_FILLET, SOLE_FILLET_SEG)
    pts.append(c_flkB_in)
    # -- entree de gorge cote B : chanfrein de guidage ---------------------
    pts.append((R_FLK, SLOT_Z1 + MOUTH_CHAMF))
    pts.append((R_FLK + MOUTH_CHAMF, SLOT_Z1))
    pts.append(c_slotB)
    pts.append(c_slotA)
    # -- entree de gorge cote A -------------------------------------------
    pts.append((R_FLK + MOUTH_CHAMF, SLOT_Z0))
    pts.append((R_FLK, SLOT_Z0 - MOUTH_CHAMF))

    # dedoublonnage (le fillet peut retomber sur un point deja pose)
    out = []
    for p in pts:
        if not out or (abs(p[0] - out[-1][0]) > 1e-9 or abs(p[1] - out[-1][1]) > 1e-9):
            out.append(p)
    if (abs(out[0][0] - out[-1][0]) < 1e-9 and abs(out[0][1] - out[-1][1]) < 1e-9):
        out.pop()
    poly = np.array(out, dtype=float)
    if signed_area(poly) < 0:
        poly = poly[::-1].copy()
    return poly


def signed_area(poly):
    x, y = poly[:, 0], poly[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


# ---------------------------------------------------------------------------
# Triangulation du capot (polygone concave -> ear clipping)
# ---------------------------------------------------------------------------

def _in_tri(p, a, b, c):
    def cr(u, v, w):
        return (v[0] - u[0]) * (w[1] - u[1]) - (v[1] - u[1]) * (w[0] - u[0])
    d1, d2, d3 = cr(a, b, p), cr(b, c, p), cr(c, a, p)
    return (d1 >= -1e-12 and d2 >= -1e-12 and d3 >= -1e-12)


def ear_clip(poly):
    """poly : (N,2) suppose CCW. Retourne une liste de triplets d'indices."""
    pts = [tuple(p) for p in poly]
    idx = list(range(len(pts)))
    tris = []
    guard = 0
    while len(idx) > 3 and guard < 20000:
        guard += 1
        n = len(idx)
        clipped = False
        for i in range(n):
            a, b, c = idx[(i - 1) % n], idx[i], idx[(i + 1) % n]
            A, B, C = pts[a], pts[b], pts[c]
            cross = (B[0] - A[0]) * (C[1] - A[1]) - (B[1] - A[1]) * (C[0] - A[0])
            if cross <= 1e-12:
                continue                      # coin reflex ou degenere
            if any(_in_tri(pts[j], A, B, C) for j in idx if j not in (a, b, c)):
                continue                      # oreille contaminee
            tris.append((a, b, c))
            idx.pop(i)
            clipped = True
            break
        if not clipped:
            raise RuntimeError("ear clipping bloque (profil non simple ?)")
    if len(idx) == 3:
        tris.append(tuple(idx))
    return tris


# ---------------------------------------------------------------------------
# Revolution
# ---------------------------------------------------------------------------

def build_mesh(poly, a0_deg, a1_deg, nseg):
    n = len(poly)
    angs = np.radians(np.linspace(a0_deg, a1_deg, nseg + 1))
    ca, sa = np.cos(angs), np.sin(angs)
    # verts[k*n + i]
    verts = np.empty(((nseg + 1) * n, 3), dtype=float)
    for k in range(nseg + 1):
        verts[k * n:(k + 1) * n, 0] = poly[:, 0] * ca[k]
        verts[k * n:(k + 1) * n, 1] = poly[:, 0] * sa[k]
        verts[k * n:(k + 1) * n, 2] = poly[:, 1]

    tris = []
    # -- surface laterale (revolution du profil) ---------------------------
    for k in range(nseg):
        b0, b1 = k * n, (k + 1) * n
        for i in range(n):
            j = (i + 1) % n
            v00, v01 = b0 + i, b0 + j
            v10, v11 = b1 + i, b1 + j
            tris.append((v00, v01, v11))
            tris.append((v00, v11, v10))
    # -- capots aux deux extremites de l'arc -------------------------------
    cap = ear_clip(poly)
    base_last = nseg * n
    for (a, b, c) in cap:
        tris.append((a, c, b))                             # capot a0
        tris.append((base_last + a, base_last + b, base_last + c))  # capot a1

    tris = np.array(tris, dtype=np.int64)
    # -- orientation globale : volume signe > 0 ----------------------------
    if signed_volume(verts, tris) < 0:
        tris = tris[:, ::-1].copy()
    return verts, tris


def signed_volume(verts, tris):
    a = verts[tris[:, 0]]
    b = verts[tris[:, 1]]
    c = verts[tris[:, 2]]
    return float(np.sum(np.einsum('ij,ij->i', a, np.cross(b, c))) / 6.0)


# ---------------------------------------------------------------------------
# Sondes de verification
# ---------------------------------------------------------------------------

def verify(verts, tris):
    ok = True

    def line(label, val, good):
        nonlocal ok
        if not good:
            ok = False
        print("  [%s] %-34s %s" % ("OK" if good else "!!", label, val))

    print("\n--- Verification du maillage --------------------------------")
    print("  triangles : %d   sommets : %d" % (len(tris), len(verts)))

    # --- bbox ------------------------------------------------------------
    lo, hi = verts.min(axis=0), verts.max(axis=0)
    r = np.hypot(verts[:, 0], verts[:, 1])
    line("Z  (attendu %.2f .. %.2f)" % (Z0, Z1),
         "%.3f .. %.3f" % (lo[2], hi[2]),
         abs(lo[2] - Z0) < 1e-6 and abs(hi[2] - Z1) < 1e-6)
    line("rayon min (bas de flanc %.2f)" % R_FLK, "%.3f" % r.min(),
         abs(r.min() - R_FLK) < 1e-6)
    line("rayon max (roulement %.2f)" % R_OUT, "%.3f" % r.max(),
         abs(r.max() - R_OUT) < 1e-6)
    line("largeur hors-tout (attendu %.1f)" % (Z1 - Z0),
         "%.3f" % (hi[2] - lo[2]), abs((hi[2] - lo[2]) - (Z1 - Z0)) < 1e-6)

    # --- aretes : chaque arete non orientee doit apparaitre 2x ------------
    e = np.vstack([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]])
    und = np.sort(e, axis=1)
    uniq, cnt = np.unique(und, axis=0, return_counts=True)
    free = int(np.sum(cnt == 1))
    weird = int(np.sum(cnt > 2))
    line("aretes libres (watertight)", "%d" % free, free == 0)
    line("aretes non-manifold (>2 faces)", "%d" % weird, weird == 0)

    # --- coherence d'orientation : chaque arete dirigee exactement 1x -----
    _, dcnt = np.unique(e, axis=0, return_counts=True)
    line("aretes dirigees dupliquees", "%d" % int(np.sum(dcnt > 1)),
         int(np.sum(dcnt > 1)) == 0)

    # --- composantes connexes (union-find sur les sommets) ---------------
    parent = np.arange(len(verts))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for u, v in uniq:
        ru, rv = find(u), find(v)
        if ru != rv:
            parent[ru] = rv
    used = np.unique(tris)
    ncomp = len({find(i) for i in used})
    line("composantes connexes", "%d" % ncomp, ncomp == 1)

    # --- volume / masse --------------------------------------------------
    vol = signed_volume(verts, tris)
    # volume analytique : aire du profil x longueur de l'arc au centroide
    poly = build_profile()
    area = signed_area(poly)
    rbar = float(np.mean(poly[:, 0]))  # approx grossiere, indicatif seulement
    line("volume signe > 0", "%.1f mm3 (%.2f cm3)" % (vol, vol / 1000.0), vol > 0)
    print("       aire du profil %.2f mm2, densite TPU 1.21 -> ~%.1f g"
          % (area, vol / 1000.0 * 1.21))

    # --- ajustement sur la jante ----------------------------------------
    print("\n--- Ajustement sur foot_arc ---------------------------------")
    print("  interference radiale   : %.2f mm  (pneu %.2f / jante %.2f)"
          % (RIM_R - TIRE_R_IN, TIRE_R_IN, RIM_R))
    print("  gorge / largeur jante  : %.2f / %.2f mm  (jeu %.2f)"
          % (SLOT_Z1 - SLOT_Z0, RIM_W, (SLOT_Z1 - SLOT_Z0) - RIM_W))
    print("  garde bas de flanc     : %.2f mm au-dessus de l'ID de jante (%.1f)"
          % (R_FLK - (RIM_R - RIM_T), RIM_R - RIM_T))
    print("  debattement angulaire  : arc %.0f deg / pneu %.0f deg -> %.1f deg"
          % (RIM_SPAN, TIRE_SPAN, (RIM_SPAN - TIRE_SPAN) / 2.0)
          + " de jeu a chaque bout")
    print("  diametre de roulement  : %.1f mm (etait %.1f nu)"
          % (2 * R_OUT, 2 * RIM_R))
    return ok


def check_against_foot(path="foot_arc.stl"):
    """Relit la piece cible et confirme que les cotes codees en dur collent."""
    try:
        m = stlmesh.Mesh.from_file(path)
    except Exception as exc:
        print("\n  (foot_arc.stl non relu : %s)" % exc)
        return
    v = m.vectors.reshape(-1, 3)
    r = np.hypot(v[:, 0], v[:, 1])
    print("\n--- Sonde de foot_arc.stl -----------------------------------")
    print("  rayon exterieur mesure : %.3f  (parametre RIM_R = %.2f)"
          % (r.max(), RIM_R))
    print("  Z mesure               : %.3f .. %.3f  (RIM_W = %.2f)"
          % (v[:, 2].min(), v[:, 2].max(), RIM_W))
    if abs(r.max() - RIM_R) > 1e-3 or abs(v[:, 2].max() - RIM_W) > 1e-3:
        print("  !! ecart avec les parametres du pneu -- verifier gen_chassis.py")


# ---------------------------------------------------------------------------

def write_stl(verts, tris, path):
    data = np.zeros(len(tris), dtype=stlmesh.Mesh.dtype)
    data['vectors'] = verts[tris]
    stlmesh.Mesh(data).save(path)


def write_preview(verts, tris, path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    except Exception as exc:
        print("  (pas d'apercu : %s)" % exc)
        return
    fig = plt.figure(figsize=(9, 4.5))
    for n, (elev, azim, title) in enumerate(
            [(22, -60, "3/4"), (0, -90, "face (plan de l'arc)")]):
        ax = fig.add_subplot(1, 2, n + 1, projection='3d')
        pc = Poly3DCollection(verts[tris], facecolor="#3a3a3a",
                              edgecolor="none", linewidths=0)
        pc.set_alpha(1.0)
        ax.add_collection3d(pc)
        lo, hi = verts.min(axis=0), verts.max(axis=0)
        ctr, rad = (lo + hi) / 2, (hi - lo).max() / 2
        ax.set_xlim(ctr[0] - rad, ctr[0] + rad)
        ax.set_ylim(ctr[1] - rad, ctr[1] + rad)
        ax.set_zlim(ctr[2] - rad, ctr[2] + rad)
        ax.set_box_aspect((1, 1, 1))
        ax.view_init(elev=elev, azim=azim)
        ax.set_title(title, fontsize=9)
        ax.set_axis_off()
    fig.suptitle("foot_tire — TPU 95A — span %.0f deg, OD %.1f, largeur %.1f"
                 % (TIRE_SPAN, 2 * R_OUT, Z1 - Z0), fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    print("  apercu   -> %s" % path)


def main():
    poly = build_profile()
    print("Profil : %d points, aire %.2f mm2, r %.2f..%.2f, z %.2f..%.2f"
          % (len(poly), signed_area(poly), poly[:, 0].min(), poly[:, 0].max(),
             poly[:, 1].min(), poly[:, 1].max()))
    verts, tris = build_mesh(poly, A0, A1, ANG_SEG)
    ok = verify(verts, tris)
    check_against_foot()
    write_stl(verts, tris, OUT_STL)
    print("\n  maillage -> %s (%d triangles)" % (OUT_STL, len(tris)))
    if "--no-preview" not in sys.argv:
        write_preview(verts, tris, OUT_PNG)
    print("\n%s" % ("Toutes les sondes passent." if ok
                    else "!! DES SONDES ONT ECHOUE -- ne pas imprimer."))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
