#!/usr/bin/env python3
"""BalanceBot v3.1 — audit impression : topologie, parois, surplombs par orientation, boucles ouvertes."""
import json, os, sys
import numpy as np
import trimesh

HERE = os.path.dirname(os.path.abspath(__file__))
V3 = os.path.join(HERE, "..", "v3")
PETG = 1.27  # g/cm3
OUT = {}

def loop_bboxes(mesh):
    """Boucles de bord libre : regroupement grossier par proximité, bbox + longueur."""
    edges = mesh.edges_sorted
    # edges appearing once = boundary
    from collections import Counter
    c = Counter(map(tuple, edges))
    bnd = [e for e, n in c.items() if n == 1]
    if not bnd:
        return []
    # union-find sur sommets partageant une arête de bord
    parent = {}
    def find(a):
        while parent.setdefault(a, a) != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra
    for a, b in bnd:
        union(int(a), int(b))
    groups = {}
    for a, b in bnd:
        groups.setdefault(find(int(a)), []).append((int(a), int(b)))
    res = []
    for _, es in groups.items():
        vids = sorted({v for e in es for v in e})
        pts = mesh.vertices[vids]
        L = sum(float(np.linalg.norm(mesh.vertices[a] - mesh.vertices[b])) for a, b in es)
        res.append({
            "edges": len(es), "verts": len(vids),
            "length_mm": round(L, 2),
            "bbox_min": [round(float(x), 2) for x in pts.min(axis=0)],
            "bbox_max": [round(float(x), 2) for x in pts.max(axis=0)],
            "size": [round(float(x), 2) for x in (pts.max(axis=0) - pts.min(axis=0))],
            "center": [round(float(x), 2) for x in pts.mean(axis=0)],
        })
    return sorted(res, key=lambda r: -r["length_mm"])

def orient_stats(mesh):
    """Pour les 6 orientations axe-aligned : aire au sol, aire descendante <45°, % et aire de pont."""
    out = []
    axes = [0, 1, 2]
    for ax in axes:
        for sign in (1, -1):
            m = mesh.copy()
            # rotate so that -sign*ax becomes -Z (face down)
            if ax == 0:
                R = trimesh.transformations.rotation_matrix(np.radians(90 * (1 if sign > 0 else -1)), [0, 1, 0])
            elif ax == 1:
                R = trimesh.transformations.rotation_matrix(np.radians(90 * (-1 if sign > 0 else 1)), [1, 0, 0])
            else:
                R = np.eye(4) if sign > 0 else trimesh.transformations.rotation_matrix(np.pi, [1, 0, 0])
            m.apply_transform(R)
            n = m.face_normals
            a = m.area_faces
            down = n[:, 2] < 0
            # angle entre normale et verticale bas : 0 = face horizontale vers le bas
            ang = np.degrees(np.arccos(np.clip(-n[:, 2], -1, 1)))
            below = down & (ang < 45.0)
            flat = down & (ang < 5.0)
            zmin = m.bounds[0][2]
            contact = flat & (np.abs(m.triangles[:, :, 2].mean(axis=1) - zmin) < 0.05)
            out.append({
                "orientation": f"{'xyz'[ax]}{'+' if sign>0 else '-'} down",
                "bbox": [round(float(x), 1) for x in (m.bounds[1] - m.bounds[0])],
                "z_height": round(float(m.bounds[1][2] - m.bounds[0][2]), 1),
                "footprint_mm2": round(float(m.bounds[1][0] - m.bounds[0][0]) * float(m.bounds[1][1] - m.bounds[0][1]), 0),
                "plate_contact_mm2": round(float(a[contact].sum()), 0),
                "down_below45_mm2": round(float(a[below].sum()), 0),
                "down_below45_pct": round(100 * float(a[below].sum()) / float(a.sum()), 1),
                "flat_down_mm2": round(float(a[flat].sum()), 0),
                "largest_flat_down_mm2": round(float(a[flat].max()) if flat.any() else 0.0, 1),
            })
    return out

files = {
    "b_front": os.path.join(V3, "b_front.stl"),
    "b_back": os.path.join(V3, "b_back.stl"),
    "coin_wheel": os.path.join(V3, "coin_wheel.stl"),
    "coin_tire": os.path.join(V3, "coin_tire.stl"),
}
for name, path in files.items():
    raw = trimesh.load(path, process=False)
    m = trimesh.load(path, process=True)
    m.merge_vertices()
    vol = None
    try:
        vol = float(m.volume)
    except Exception:
        pass
    d = {
        "raw_tris": len(raw.faces),
        "merged_verts": len(m.vertices),
        "watertight_after_merge": bool(m.is_watertight),
        "winding_consistent": bool(m.is_winding_consistent),
        "components": len(m.split(only_watertight=False)),
        "euler": int(m.euler_number),
        "bbox": [round(float(x), 2) for x in (m.bounds[1] - m.bounds[0])],
        "volume_mm3": round(vol, 1) if vol else None,
        "mass_g_PETG": round(vol * PETG / 1000, 1) if vol else None,
        "area_mm2": round(float(m.area), 0),
        "boundary_loops": loop_bboxes(m)[:12],
    }
    try:
        from trimesh.proximity import thickness
        d["orientations"] = orient_stats(m)
    except Exception as e:
        d["orientations_err"] = str(e)
    OUT[name] = d

print(json.dumps(OUT, indent=1))
