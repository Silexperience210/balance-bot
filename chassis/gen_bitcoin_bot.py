#!/usr/bin/env blender --background --python
# =============================================================================
#  ₿ BalanceBot v3 — châssis « symbole Bitcoin » (généré par Hermes)
#
#  Robot auto-équilibré 2 roues. Le CORPS est le glyphe ₿ vu de face, debout.
#  Roues = pièces ₿ Ø70 (+ pneu TPU). Servos 9 g rotation continue (SG90 size).
#
#  REPÈRE : X = gauche→droite (face), Y = arrière→avant (profondeur), Z = haut.
#  Face AVANT = y = +DEPTH/2 ; plan de joint des coques = y = 0.
#  Sol z = 0 ; axe des roues z = WHEEL_R (rayon de roulement avec pneu).
#
#  Impression : b_front / b_back COUCHÉES (face externe sur le plateau, cavités
#  vers le haut), coin_wheel face externe en bas, pneu TPU à plat. Zéro support.
# =============================================================================
import math, os, sys
import bmesh, bpy
from mathutils import Vector, Matrix

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'v3')
os.makedirs(OUT, exist_ok=True)
EPS = 0.02

# ── Cotes mesurées (héritées de gen_chassis.py v2) ──────────────────────────
SLIDING_FIT, CLEARANCE_FIT, HOLE_BONUS = 0.15, 0.30, 0.30
SV_L, SV_W, SV_H = 22.8, 12.2, 22.5      # corps servo 9 g
SV_FLANGE_Z, SV_FLANGE_T, SV_TAB_SPAN = 15.9, 2.5, 32.2
SV_HOLE_PITCH, SV_SHAFT_OFF = 27.8, 5.9
SV_SHAFT_D, SV_SHAFT_PROJ, SV_BOSS_D, SV_BOSS_H = 4.8, 4.5, 11.8, 1.5
SV_PILOT_D = 1.7
# Jeu de montage de la baie servo (10/09). Le SG90 réel porte des TAQUETS DE MOULAGE et une
# bavure au joint de ses 2 demi-coques (~0.5 mm en saillie, non cotés au datasheet) : la fenêtre
# au SLIDING_FIT (0.15) était au plus juste et le servo n'entrait pas. 1.0 mm par face.
SV_CLR = 1.0
PCB_LEN, PCB_WID, PCB_T = 62.00, 26.00, 1.20   # T-Display-S3 Touch RÉEL 62×26 (confirmé user 08/09 soir)
PCB_FIX_PITCH = 20.01                    # trous réels de la carte
MPU_L, MPU_W, MPU_T, MPU_HOLE_PITCH = 21.0, 16.0, 2.0, 15.0
SR_W, SR_H, SR_T = 45.0, 20.0, 1.6       # HC-SR04 pcb
SR_TR_D, SR_TR_PITCH, SR_TR_H = 16.0, 26.0, 12.0   # transducteurs Ø16, entraxe 26

# ── Glyphe ₿ (face, mm) ──────────────────────────────────────────────────────
GW, GH = 118.0, 165.0        # B hors barres (v3.1 : ratio 1.40)
Z0 = 26.0                   # bas du B (v3.1)
SPINE_W = 20.0
STROKE = 19.0               # trait des panses (v3.1)
HIGH_SCALE = 0.90           # panse haute (v3.1)
BAR_W, BAR_H = 11.0, 22.0   # traits du ₿ (v3.1)
BARS_X = (4.0, SPINE_W + 5.0)
DEPTH = 46.0                # profondeur totale du corps (v3.1)
WALL = 2.4
CHAM = 1.2                  # chanfrein arêtes extérieures
COUNTER = 1.6                 # creux des contre-poinçons (1.6 : supports minuscules, review v3.1)
LEG_H = 14.0                # barres du bas → z = Z0-LEG_H = 12 → garde au sol 12 (v3.1)

# ── Roues ────────────────────────────────────────────────────────────────────
WHEEL_D, WHEEL_W = 80.0, 8.0    # v3.1 : Ø80, allégée (6 bras, voir build_wheel)
GROOVE_D, GROOVE_W = 0.5, 7.0   # gorge de bande de roulement sur la jante
TIRE_T, TIRE_W = 2.5, 7.0       # bande TPU pleine, montée en tension (Ø int. < Ø fond de gorge)
TIRE_STRETCH = 1.0              # interférence diamétrale
WHEEL_R = WHEEL_D/2 - GROOVE_D + TIRE_T   # 41.5 rayon de roulement → axe z
AXLE_Z = WHEEL_R
HUB_BORE_D = SV_SHAFT_D + 0.4
HUB_CB_D, HUB_CB_H = SV_BOSS_D + 0.6, SV_BOSS_H + 0.2
HORN_ARM_W, HORN_ARM_L, HORN_T = 5.2, 20.0, 1.8   # empreinte palonnier en croix 21T (4 bras)
HORN_SCREW_R0, HORN_SCREW_R1 = 3.7, 6.3
# Moyeu-tube : la roue porte un tube Ø HUB_D × HUB_L côté interne, guidé dans un tube-palier du corps (Ø HUB_D + 0.5).
# Le palonnier en croix (21 mm !) du servo s'emboîte au FOND du moyeu → Ø ≥ 24 pour le loger sans le couper.
# L'axe servo n'est jamais en flexion, le palier reprend les efforts radiaux.
HUB_D, HUB_L = 24.0, 13.0
BEAR_D = HUB_D + 0.5        # alésage du palier dans le corps
BEAR_WALL = 1.0             # paroi du tube-palier (Ø ext 26.5 → bas du tube à z = 36.5-13.25 = 23.25 > plancher cavité 22.4 : pas de sliver)
WHEEL_GAP = 1.0             # jeu roue / corps

# =============================================================================
#  OUTILLAGE BPY (v2)
# =============================================================================
def raz_scene():
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
    for m in list(bpy.data.meshes):
        if m.users == 0: bpy.data.meshes.remove(m)

def _obj(nom, bm):
    me = bpy.data.meshes.new(nom); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(nom, me); bpy.context.collection.objects.link(ob); return ob

def boite(nom, x0, x1, y0, y1, z0, z1):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x = x0 if v.co.x < 0 else x1; v.co.y = y0 if v.co.y < 0 else y1; v.co.z = z0 if v.co.z < 0 else z1
    return _obj(nom, bm)

def cylindre(nom, diam, long, axe, centre, segments=64):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segments, radius1=diam/2, radius2=diam/2, depth=long)
    if axe == 'X': bmesh.ops.rotate(bm, verts=bm.verts, matrix=Matrix.Rotation(math.radians(90), 3, 'Y'))
    elif axe == 'Y': bmesh.ops.rotate(bm, verts=bm.verts, matrix=Matrix.Rotation(math.radians(-90), 3, 'X'))
    bmesh.ops.translate(bm, verts=bm.verts, vec=Vector(centre))
    return _obj(nom, bm)

def frustum(nom, d0, d1, long, axe, centre, segments=64):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segments, radius1=d0/2, radius2=d1/2, depth=long)
    if axe == 'X': bmesh.ops.rotate(bm, verts=bm.verts, matrix=Matrix.Rotation(math.radians(90), 3, 'Y'))
    elif axe == 'Y': bmesh.ops.rotate(bm, verts=bm.verts, matrix=Matrix.Rotation(math.radians(-90), 3, 'X'))
    bmesh.ops.translate(bm, verts=bm.verts, vec=Vector(centre))
    return _obj(nom, bm)

def prisme(nom, poly, axe, a0, a1):
    """Extrude un polygone 2D le long de `axe`. axe='Y' -> (u,v)=(X,Z)."""
    bm = bmesh.new()
    def pt(u, v, a):
        return Vector((a, u, v)) if axe == 'X' else (Vector((u, a, v)) if axe == 'Y' else Vector((u, v, a)))
    bas = [bm.verts.new(pt(u, v, a0)) for (u, v) in poly]
    haut = [bm.verts.new(pt(u, v, a1)) for (u, v) in poly]
    bm.faces.new(bas); bm.faces.new(list(reversed(haut)))
    n = len(poly)
    for i in range(n):
        j = (i+1) % n; bm.faces.new((bas[i], bas[j], haut[j], haut[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _obj(nom, bm)

def booleen(cible, outil, op='DIFFERENCE', solver='EXACT'):
    m = cible.modifiers.new(name='bool', type='BOOLEAN'); m.operation = op; m.object = outil; m.solver = solver
    bpy.context.view_layer.objects.active = cible; bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(outil, do_unlink=True); return cible

def fusionner(nom, objets):
    base = objets[0]; base.name = nom
    for o in objets[1:]: booleen(base, o, 'UNION')
    return base

def soustraire(cible, outils):
    for o in outils: booleen(cible, o, 'DIFFERENCE')
    return cible

def dupliquer(ob, nom):
    cp = ob.copy(); cp.data = ob.data.copy(); cp.name = nom; bpy.context.collection.objects.link(cp); return cp

def purger_dechets(ob, min_dim=0.05):
    """Supprime les composantes à ÉPAISSEUR NULLE (voiles/plaques d'un seul plan) laissées par les
    booléens EXACT quand une face de l'outil est coplanaire à une face du corps — ex. un alésage dont
    le fond tombait pile sur le bout du tube, ou le capuchon d'un outil traversant. Connectivité par
    ARÊTES (un voile relié seulement par un sommet n'appartient pas au solide). La matière réelle
    (min_dim ≥ 1 mm) n'est jamais touchée."""
    bm = bmesh.new(); bm.from_mesh(ob.data)
    bm.faces.ensure_lookup_table(); bm.faces.index_update()
    vus, a_supprimer, gardees = set(), [], 0
    for f in bm.faces:
        if f.index in vus:
            continue
        pile, comp = [f], []
        vus.add(f.index)
        while pile:
            g = pile.pop(); comp.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in vus:
                        vus.add(h.index); pile.append(h)
        vs = {v for g in comp for v in g.verts}
        dims = [max(v.co[i] for v in vs) - min(v.co[i] for v in vs) for i in range(3)]
        if min(dims) < min_dim:
            a_supprimer.extend(comp)
        else:
            gardees += 1
    if a_supprimer:
        bmesh.ops.delete(bm, geom=a_supprimer, context='FACES')
        print(f"  [purge] {ob.name}: {len(a_supprimer)} faces à épaisseur nulle supprimées ({gardees} solide(s) gardé(s))")
    bm.to_mesh(ob.data); bm.free()
    return ob

def boucher_micropores(ob, perim_max=30.0):
    """Bouche les boucles de bord LIBRES de petit périmètre (trous sous-millimétriques laissés par les
    booléens). Ne touche jamais aux ouvertures de conception : l'ouverture de joint et les passages
    (écran, yeux, USB, interrupteur) ont des périmètres de plusieurs centaines de mm."""
    bm = bmesh.new(); bm.from_mesh(ob.data)
    bnd = [e for e in bm.edges if len(e.link_faces) == 1]
    if not bnd:
        bm.free(); return ob
    adj = {}
    for e in bnd:
        for v in e.verts:
            adj.setdefault(v, []).append(e)
    vus, boucles = set(), []
    for e in bnd:
        if e in vus:
            continue
        pile, comp = [e], []
        vus.add(e)
        while pile:
            x = pile.pop(); comp.append(x)
            for v in x.verts:
                for y in adj.get(v, []):
                    if y not in vus:
                        vus.add(y); pile.append(y)
        boucles.append(comp)
    petites = [c for c in boucles if sum(e.calc_length() for e in c) < perim_max]
    if petites:
        for comp in petites:
            bmesh.ops.holes_fill(bm, edges=comp, sides=0)
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        print(f"  [pores] {ob.name}: {len(petites)} micro-trou(s) bouché(s) (périmètre < {perim_max} mm)")
    bm.to_mesh(ob.data); bm.free()
    return ob

def nettoyer(ob):
    bpy.context.view_layer.objects.active = ob; bpy.ops.object.select_all(action='DESELECT'); ob.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=1e-4)
    bpy.ops.mesh.dissolve_degenerate()          # élimine triangles/arêtes dégénérés (artefacts EXACT sur la face de joint)
    bpy.ops.mesh.delete_loose()                 # sommets/arêtes isolés
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT'); ob.select_set(False)
    return boucher_micropores(purger_dechets(ob))

def bbox(ob):
    cs = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    return (min(c.x for c in cs), max(c.x for c in cs), min(c.y for c in cs), max(c.y for c in cs), min(c.z for c in cs), max(c.z for c in cs))

def exporter(ob, chemin):
    bpy.ops.object.select_all(action='DESELECT'); ob.select_set(True); bpy.context.view_layer.objects.active = ob
    bpy.ops.wm.stl_export(filepath=chemin, export_selected_objects=True, global_scale=1.0, ascii_format=False, apply_modifiers=True)
    ob.select_set(False); b = bbox(ob)
    print(f"  [STL] {os.path.basename(chemin):16s} {b[1]-b[0]:6.2f} x {b[3]-b[2]:6.2f} x {b[5]-b[4]:6.2f} mm | {len(ob.data.polygons)} faces")
    return b

# =============================================================================
#  GLYPHE ₿ — polygones 2D (x, z)
# =============================================================================
def arc(cx, cz, r, a0, a1, n=32):
    return [(cx + r*math.cos(math.radians(a)), cz + r*math.sin(math.radians(a))) for a in [a0 + (a1-a0)*i/(n-1) for i in range(n)]]

def bowl(z_bot, z_top, x_left, x_right):
    """Panse : rectangle à gauche + demi-disque à droite."""
    r = (z_top - z_bot)/2; cz = (z_top + z_bot)/2; cx = x_right - r
    return [(x_left, z_bot), (cx, z_bot)] + arc(cx, cz, r, -90, 90) + [(x_left, z_top)]

Z_MID = Z0 + GH*0.50
LOW  = dict(zb=Z0,                zt=Z_MID + STROKE*0.5, xr=GW)
HIGH = dict(zb=Z_MID - STROKE*0.5, zt=Z0 + GH,           xr=GW*HIGH_SCALE)

def glyph_solids(y0, y1, inset=0.0):
    """Solides du ₿ (spine + 2 panses + 4 barres) extrudés de y0 à y1, réduits de `inset` (pour le chanfrein)."""
    i = inset
    parts = [prisme('spine', [(i, Z0-LEG_H+i), (SPINE_W-i, Z0-LEG_H+i), (SPINE_W-i, Z0+GH-i), (i, Z0+GH-i)], 'Y', y0, y1)]
    for k, b in enumerate((LOW, HIGH)):
        parts.append(prisme(f'bowl{k}', bowl(b['zb']+i, b['zt']-i, i, b['xr']-i), 'Y', y0, y1))
    for k, bx in enumerate(BARS_X):
        parts.append(prisme(f'bart{k}', [(bx+i, Z0+GH-4), (bx+BAR_W-i, Z0+GH-4), (bx+BAR_W-i, Z0+GH+BAR_H-i), (bx+i, Z0+GH+BAR_H-i)], 'Y', y0, y1))  # ancrage 4 mm dans la panse (union robuste)
        parts.append(prisme(f'barb{k}', [(bx+i, Z0-LEG_H+i), (bx+BAR_W-i, Z0-LEG_H+i), (bx+BAR_W-i, Z0+4), (bx+i, Z0+4)], 'Y', y0, y1))  # ancrage 4 mm dans la panse
    return fusionner('glyph', parts)

def counters(y0, y1):
    """Contre-poinçons (intérieurs des panses) : panses rétrécies du trait."""
    parts = []
    for k, b in enumerate((LOW, HIGH)):
        parts.append(prisme(f'ctr{k}', bowl(b['zb']+STROKE, b['zt']-STROKE, SPINE_W, b['xr']-STROKE), 'Y', y0, y1))
    return fusionner('counters', parts)

def counter_center(b):
    return ((SPINE_W + b['xr'] - STROKE)/2, (b['zb'] + b['zt'])/2)

# =============================================================================
#  CORPS — enveloppe extérieure chanfreinée, puis creusée, puis coupée en 2
# =============================================================================
def corps_enveloppe():
    yf, yb = DEPTH/2, -DEPTH/2
    core = glyph_solids(yb + CHAM, yf - CHAM)
    # chanfrein avant/arrière : tranche réduite de CHAM sur les faces avant et arrière
    front = glyph_solids(yf - CHAM - EPS, yf, inset=CHAM); front.name = 'gf'
    back  = glyph_solids(yb, yb + CHAM + EPS, inset=CHAM); back.name = 'gb'
    env = fusionner('body_env', [core, front, back])
    # contre-poinçons en creux sur la face avant (COUNTER mm)
    ctr = counters(yf - COUNTER, yf + 1.0)
    booleen(env, ctr, 'DIFFERENCE')
    return env

def corps_cavite(y0=None, y1=None):
    """Cavité intérieure = glyphe réduit de WALL, entre y0 et y1 (défaut : tout le corps)."""
    if y0 is None: y0 = -DEPTH/2 + WALL
    if y1 is None: y1 = DEPTH/2 - WALL - COUNTER
    return glyph_solids(y0, y1, inset=WALL)

SKIN = 0.6  # peau sacrificielle au joint : la cavité s'arrête à ±SKIN du plan y=0 → le corps reste PLEIN sur 1.2 mm,
# ce qui FERME chaque coque après la coupe (mesh WATERFIGHT, exigé par le slicer Bambu : les coques ouvertes
# sont rejetées « Nothing to be sliced »). Cette peau de 0.6 mm par moitié se coupe au cutter après impression
# pour ouvrir la cavité (pattern v2 — coque « avec peau » validée par slice le 08/09).

def build_body():
    env = corps_enveloppe()
    booleen(env, corps_cavite(), 'DIFFERENCE')
    # PEAU SACRIFICIELLE DÉSACTIVÉE (SKIN=0.6 en constante, union commentée le 08/09 soir) : l'utilisateur a validé la
    # version « CREUSE » — les 2 coques restent OUVERTES au plan de joint, le hardware se monte par l'ouverture avant de
    # visser (4 goujons + 4 vis M3). Les coques ouvertes se slicent dans Bambu Studio GUI (le CLI headless les refuse).
    # booleen(env, glyph_solids(-SKIN, SKIN, inset=WALL - 0.1), 'UNION') (union franche, pas coplanaire)


    yf = DEPTH/2
    y_cav_f = yf - WALL - COUNTER          # fond de cavité côté avant (derrière les creux)
    y_cav_b = -DEPTH/2 + WALL              # fond de cavité côté arrière
    lcx, lcz = counter_center(LOW)
    hcx, hcz = counter_center(HIGH)

    # ═══ AJOUTS INTÉRIEURS (unions) ════════════════════════════════════════
    ajouts = []
    # ── Servos : couchés, axe selon X, sortant par les parois latérales à z = AXLE_Z.
    #    Le corps (SV_L=22.8 selon Z, SV_W=12.2 selon Y, SV_H=22.5 selon X) est monté TÊTE EN BAS :
    #    l'axe (à SV_SHAFT_OFF du bout) est en BAS → corps de z = AXLE_Z-5.9 = 30.7 à 53.5, au-dessus du plancher (22.4).
    #    Fixation standard : le servo traverse une CLOISON verticale (⊥ X) par une fenêtre 22.8×12.2 ; les pattes
    #    (SV_FLANGE_Z=15.9 du fond, 2.5 épaisses, 32.2 d'envergure) s'appuient sur la face intérieure de la cloison.
    r_low = (LOW['zt'] - LOW['zb'])/2; cz_low = (LOW['zt'] + LOW['zb'])/2
    x_wall_R = (LOW['xr'] - r_low) + math.sqrt(r_low**2 - (AXLE_Z - cz_low)**2)   # paroi courbe droite à la hauteur de l'axe
    z_sv0, z_sv1 = AXLE_Z - SV_SHAFT_OFF, AXLE_Z - SV_SHAFT_OFF + SV_L
    servo_x = []   # (x_face_boss, direction vers l'intérieur, x face d'appui des oreilles)
    # Les 2 servos sont collés à leur paroi (face de sortie = face interne de la paroi) ; les tubes-paliers sont EXTERNES.
    #
    # CORRECTION 10/09 — la cloison tombait PILE dans le volume des oreilles.
    #   Les oreilles occupent, mesuré depuis la face de sortie, x_face + d·[4.1 ; 6.6]
    #   (SV_H - SV_FLANGE_Z - SV_FLANGE_T = 4.1 et SV_H - SV_FLANGE_Z = 6.6).
    #   L'ancien code posait la cloison sur x_face + d·[4.1 ; 6.6] : recouvrement 2.5 / 2.5 mm,
    #   le servo butait sur elle avant d'être en place. En plus, la boîte 'bulk' n'était pas
    #   limitée à la cavité : elle SORTAIT de la peau de la panse (bosse mesurée jusqu'à r = 50.3
    #   pour une peau à r = 46, sous l'axe, z ≈ 30…34).
    # Nouvelle implantation : cloison SOUDÉE à la paroi latérale, en AMONT des oreilles
    #   -> x_face … x_face + d·4.1 (4.1 mm d'épaisseur), face d'appui des oreilles à x_bulk_in.
    #   Les oreilles restent alors du côté CAVITÉ : les vis se vissent depuis l'intérieur, tête
    #   accessible (avant, tête et tournevis tombaient dans l'espace mort de 4.1 mm côté paroi).
    #   Et la boîte est INTERSECTÉE avec la cavité -> plus aucune bosse hors peau.
    #   La boîte mord 0.6 mm DANS la paroi latérale (union franche, jamais coplanaire) et le clip
    #   se fait sur le glyphe réduit de WALL-0.6 : la cloison s'arrête donc 1.8 mm sous la peau.
    for x_face, d in ((WALL, +1), (x_wall_R - WALL, -1)):
        x_bulk_in = x_face + d*(SV_H - SV_FLANGE_Z - SV_FLANGE_T)   # face d'appui des oreilles
        x_bulk_out = x_face - d*0.6                                  # soudée à la paroi latérale
        bulk = boite('bulk', min(x_bulk_in, x_bulk_out), max(x_bulk_in, x_bulk_out), y_cav_b - 1, y_cav_f + 1, z_sv0 - 6.0, z_sv1 + 6.0)
        booleen(bulk, glyph_solids(y_cav_b - 3, y_cav_f + 3, inset=WALL - 0.6), 'INTERSECT')   # jamais hors de la peau
        ajouts.append(bulk)
        servo_x.append((x_face, d, x_bulk_in))
    # ── Tubes-paliers EXTERNES (coaxiaux, z = AXLE_Z, y = 0), Ø BEAR_D + 2·BEAR_WALL. Le moyeu Ø24 × 13 de la roue tourne dedans.
    #    Côté panse : la panse déborde jusqu'à x=GW à z=66.8 → plan interne roue à x_in_R = GW + GAP.
    #    Côté spine : MÊME longueur de tube (roues identiques, voie centrée sur GW/2) → x_in_L = GW − x_in_R = −GAP…
    #    mais la panse impose un tube de 12 mm à droite ; on met 12 mm à gauche aussi et on garde le centre à GW/2 :
    TUBE = (GW + WHEEL_GAP) - x_wall_R            # ≈ 12.0
    x_in_R = x_wall_R + TUBE                      # = GW + GAP
    x_in_L = -TUBE                                # tube externe 12 mm côté spine
    # (voie asymétrique de (x_in_R − GW) − TUBE = 1 − 12 = −11 mm par rapport au centre du glyphe : compensée par le
    #  décalage du CENTRE DE MASSE → la batterie est côté panse. Voir bilan des masses dans NOTES.)
    # Ancrage : le manchon-palier ne pénètre QUE l'épaisseur de la paroi (1.4 mm — union franche sans entrer dans la
    # cavité, pour ne pas bloquer le montage du servo ni frôler le plancher). Ø ext 26.5 → bas du tube à 23.25 > plancher 22.4.
    tube_R = cylindre('tubeR', BEAR_D + 2*BEAR_WALL, (x_in_R + 0.5) - (x_wall_R - 1.4), 'X', (((x_in_R + 0.5) + (x_wall_R - 1.4))/2, 0.0, AXLE_Z))
    tube_L = cylindre('tubeL', BEAR_D + 2*BEAR_WALL, (WALL - 1.0) - (x_in_L - 0.5), 'X', (((WALL - 1.0) + (x_in_L - 0.5))/2, 0.0, AXLE_Z))
    for tb in (tube_R, tube_L):
        booleen(env, tb, 'UNION')
    # ── Piédestal MPU6050 : DESSUS à z = AXLE_Z (axe de tangage = axe des roues), entre les 2 servos
    # MPU_X 38.0 -> 39.0 (10/09) : le piédestal commençait à x = 26.0 pour un servo spine dont le
    # fond est à x = 24.9 -> 1.1 mm seulement, moins que le jeu de montage SV_CLR. À 39.0 : 2.1 mm.
    MPU_X = 39.0
    ajouts.append(boite('mpu_ped', MPU_X - MPU_L/2 - 1.5, MPU_X + MPU_L/2 + 1.5, -MPU_W/2 - 1.5, MPU_W/2 + 1.5, LOW['zb'] + WALL - 1, AXLE_Z - MPU_T))
    # ── Berceau carte T-Display : 2 rails horizontaux (haut/bas de la dalle) où le PCB vient se clipser, écran vers +Y
    #    La carte (60.78 × 25.51) est en PAYSAGE : 60.78 selon X, 25.51 selon Z. Dalle affleure y = yf - COUNTER - 0.5.
    y_pcb = y_cav_f - 0.5 - PCB_T                 # face arrière du PCB
    for zz in (lcz - PCB_WID/2 - 3.0, lcz + PCB_WID/2):
        ajouts.append(boite('rail', lcx - PCB_LEN/2 - 2, lcx + PCB_LEN/2 + 2, y_pcb - 4.0, y_cav_f + 1, zz, zz + 3.0))
    # 2 plots de vis M2 en face des trous RÉELS de la carte : à 57.66 mm le long de la LONGUEUR
    # (un seul bout de la carte, côté opposé à l'USB-C), écartés de 20.01 sur la LARGEUR.
    # Carte en paysage, USB-C vers le BAS (x = lcx - PCB_LEN/2) → trous à x = lcx - PCB_LEN/2 + 57.66, z = lcz ± 10.
    # Les plots sont ADOSSÉS au rail haut/bas (z) pour ne pas flotter.
    PCB_FIX_X = lcx - PCB_LEN/2 + 57.66
    # CORRECTION 10/09 — ces plots traversaient TOUTE la cavité (y −20.6 → 17.3). Celui du bas
    # (x 83.7…88.7, z 59.5…64.5) coupait donc le plan du servo panse : 0.6 mm seulement au-dessus
    # du corps (z 58.9) et pile devant la sortie de câble. On les arrête à y = PCB_PLOT_Y0 = 8.0,
    # au-delà de la largeur du servo (y ±6.1 + 1 de jeu = ±7.1). Ils restent tenus par la nervure
    # 'pcbrib' (y 13.3…20) qui les relie au rail, lui-même soudé aux parois.
    PCB_PLOT_Y0 = 8.0
    for sz in (-1, 1):
        zz = lcz + sz*PCB_FIX_PITCH/2
        ajouts.append(cylindre('pcbplot', 5.0, (y_pcb - PCB_PLOT_Y0) + 1, 'Y', (PCB_FIX_X, (y_pcb + PCB_PLOT_Y0)/2, zz)))
        # nervure qui relie le plot au rail voisin (rail bas z∈[lcz-PCB_WID/2-3, lcz-PCB_WID/2], rail haut symétrique)
        z_rail = lcz + sz*(PCB_WID/2 + 1.5)
        ajouts.append(boite('pcbrib', PCB_FIX_X - 2.0, PCB_FIX_X + 2.0, y_pcb - 4.0, y_cav_f + 1, min(zz, z_rail), max(zz, z_rail)))
    # ── Berceau HC-SR04 : 2 rails derrière la face avant de la panse haute (PCB 45 × 20 debout, transducteurs vers +Y)
    y_sr = y_cav_f - 0.5 - SR_T
    for zz in (hcz - SR_H/2 - 3.0, hcz + SR_H/2):
        ajouts.append(boite('srrail', hcx - SR_W/2 - 2, hcx + SR_W/2 + 2, y_sr - 4.0, y_cav_f + 1, zz, zz + 3.0))
    for a in ajouts:
        booleen(env, a, 'UNION')

    # ═══ SOUSTRACTIONS ═════════════════════════════════════════════════════
    outils = []
    # ── Fenêtre écran (paysage) — demande user 10/09 : 56 × 26.
    #    Ancien : 40.6 × 22.6 (ne laissait pas passer la dalle + son encadrement).
    #    26 mm = largeur réelle du PCB T-Display-S3 Touch ; 56 mm sur 62 laisse
    #    une lèvre de 3 mm de chaque côté. La poche PCB derrière (62.6 × 26.6)
    #    reste plus large → l'épaulement d'appui de la carte est conservé.
    sw, sh = 56.0, 26.0
    outils.append(boite('win_screen', lcx-sw/2, lcx+sw/2, y_cav_f - 1, yf + 1, lcz-sh/2, lcz+sh/2))
    # ── Dégagement de la dalle : pavé PCB_LEN × PCB_WID juste derrière la face (la dalle+PCB affleurent)
    outils.append(boite('pcb_pocket', lcx - PCB_LEN/2 - 0.3, lcx + PCB_LEN/2 + 0.3, y_pcb - EPS, y_cav_f + EPS, lcz - PCB_WID/2 - 0.3, lcz + PCB_WID/2 + 0.3))
    # ── Yeux HC-SR04 : 2 trous Ø16.6, entraxe 26 + poche PCB derrière
    for sx in (-1, 1):
        outils.append(cylindre(f'eye{sx}', SR_TR_D + 0.6, WALL + COUNTER + 2, 'Y', (hcx + sx*SR_TR_PITCH/2, yf - (WALL+COUNTER)/2, hcz)))
    outils.append(boite('sr_pocket', hcx - SR_W/2 - 0.3, hcx + SR_W/2 + 0.3, y_sr - EPS, y_cav_f + EPS, hcz - SR_H/2 - 0.3, hcz + SR_H/2 + 0.3))
    # ── Vis M2 carte : avant-trous Ø1.7 dans les plots (trous réels : x = lcx - PCB_LEN/2 + 57.66, z = lcz ± 10)
    for sz in (-1, 1):
        outils.append(cylindre('pcbpil', SV_PILOT_D, 8.0, 'Y', (lcx - PCB_LEN/2 + 57.66, y_pcb - 3.0, lcz + sz*PCB_FIX_PITCH/2)))
    # ── MPU : 2 avant-trous Ø1.7 (entraxe 15 selon X) dans le piédestal
    for sx in (-1, 1):
        outils.append(cylindre('mpupil', SV_PILOT_D, 8.0, 'Z', (MPU_X + sx*MPU_HOLE_PITCH/2, 0.0, AXLE_Z - MPU_T - 3.0)))
    # ── Lumière USB-C sous la carte (USB-C vers le BAS) : 12 × 8 dans le plancher bas de la panse basse
    outils.append(boite('usb', lcx-6, lcx+6, y_pcb - 2.0, y_cav_f + 1, LOW['zb']-1, LOW['zb']+WALL+1))
    # ── Alésages des tubes-paliers : Ø BEAR_D du plan de roue jusqu'à la face interne de la paroi (le moyeu y tourne ;
    #    le bossage/axe/palonnier du servo est dans le moyeu).
    # ── Alésages des tubes-paliers LIMITÉS AU TUBE (ne touchent pas la paroi : quasi-coplanarités → EXACT instable)
    #    Ø BEAR_D de 79.2 (fond, après l'épaulement d'ancrage) à 92.5 ; côté gauche de -12.5 à -0.2.
    #    Les alésages DÉPASSENT le bout des tubes de 2 mm (09/09) : un fond d'alésage coplanaire au bout
    #    du tube laissait un voile Ø24.5 d'épaisseur nulle dans le palier (artefact EXACT → moyeu freiné).
    x_bearR_out, x_bearL_out = x_in_R + 2.5, -14.0
    outils.append(cylindre('bearR', BEAR_D, x_bearR_out - (x_wall_R + 0.2), 'X', ((x_bearR_out + (x_wall_R + 0.2))/2, 0.0, AXLE_Z)))  # palier droit : entrée x_in_R+0.5 → fond x_wall_R+0.2 (épaulement 1.6 mm, symétrique de bearL)
    outils.append(cylindre('bearL', BEAR_D, -0.2 - x_bearL_out, 'X', ((-0.2 + x_bearL_out)/2, 0.0, AXLE_Z)))
    # ── Trou de passage du bossage servo (Ø 11.8 + jeu) à TRAVERS la paroi seulement, pour rejoindre l'alésage
    outils.append(cylindre('axR', SV_BOSS_D + 1.0, WALL + 0.6, 'X', (x_wall_R - WALL/2, 0.0, AXLE_Z)))  # de x_wall_R-WALL-0.3 (cavité) à x_wall_R+0.3 (tube) : traverse la paroi ENTIÈRE (valeur review Grok)
    outils.append(cylindre('axL', SV_BOSS_D + 1.0, 2.6 - (-0.4), 'X', ((2.6 + (-0.4))/2, 0.0, AXLE_Z)))
    # ── Fenêtres servo dans les cloisons (SV_L × SV_W + SV_CLR par face) + avant-trous Ø1.7 des pattes
    #    Le servo se pose LATÉRALEMENT (selon Y, par le plan de joint ouvert) : la fenêtre est une
    #    RAINURE débouchant en y = 0, le corps y descend, les oreilles viennent porter sur x_bulk_in.
    #    Jeu porté de SLIDING_FIT (0.15) à SV_CLR (1.0) par face : taquets de moulage + bavure de joint.
    for x_face, d, x_bulk_in in servo_x:
        # Rainure du CORPS : sur TOUTE la profondeur du servo (x_face → x_face + d·SV_H), pas
        # seulement jusqu'à la cloison. Côté panse la paroi courbe rentre jusqu'à x = 95.3 sous
        # l'axe (z ≈ 35) : une rainure arrêtée à la cloison laissait 802 mm3 de matière dans le
        # corps du servo. La cavité étant déjà vide partout ailleurs, ce surcreusement n'enlève
        # de la matière QUE dans ce coin (relief déjà présent avant correction).
        x_a, x_b = x_face, x_face + d*(SV_H + 0.6)
        outils.append(boite('svwin', min(x_a, x_b), max(x_a, x_b), -SV_W/2 - SV_CLR, SV_W/2 + SV_CLR, z_sv0 - SV_CLR, z_sv1 + SV_CLR))
        z_mid = (z_sv0 + z_sv1)/2
        # Logement des OREILLES : de la face d'appui (x_bulk_in) vers la cavité, sur l'envergure
        # SV_TAB_SPAN. Sans lui, les bouts d'oreille tapaient dans la paroi courbe côté panse.
        x_c = x_bulk_in + d*(SV_FLANGE_T + SV_CLR)
        outils.append(boite('svear', min(x_bulk_in, x_c), max(x_bulk_in, x_c),
                            -SV_W/2 - SV_CLR, SV_W/2 + SV_CLR,
                            z_mid - SV_TAB_SPAN/2 - SV_CLR, z_mid + SV_TAB_SPAN/2 + SV_CLR))
        # avant-trous des oreilles : BORGNES dans la cloison, percés depuis la CAVITÉ (x_bulk_in + d·1.0)
        # vers la paroi, arrêtés 0.4 mm avant elle -> 3.7 mm de prise, jamais de débouché sur la peau.
        # Vis : celles livrées avec le SG90 (autotaraudeuses ≈ Ø1.9 × 6.5) ou M2 × 6 — PAS M2 × 8.
        x_pil0, x_pil1 = x_face + d*0.4, x_bulk_in + d*1.0
        for sz in (-1, 1):
            outils.append(cylindre('svpil', SV_PILOT_D, abs(x_pil1 - x_pil0), 'X', ((x_pil0 + x_pil1)/2, 0.0, z_mid + sz*SV_HOLE_PITCH/2)))
    # ── Interrupteur à glissière 13 × 8 à l'arrière (spine, z ≈ 150)
    outils.append(boite('sw', SPINE_W/2 - 6.5, SPINE_W/2 + 6.5, -DEPTH/2 - 1, y_cav_b + 1, 160, 168))  # z 160-168 : au-dessus du plot screw spine (fin 149.3) → plus de lame non-manifold
    # ── Passe-fils entre panse basse et haute : ouverture dans la cloison à z = Z_MID
    outils.append(boite('pass', SPINE_W + 4, SPINE_W + 16, y_cav_b - 1, y_cav_f + 1, Z_MID - 6, Z_MID + 6))
    soustraire(env, outils)
    return nettoyer(env)

def couper_bisect(ob, garde_plus):
    """Coupe un solide au plan y=0 par bisect bmesh (pas de solveur booléen : robuste).
    `garde_plus=True` conserve y>0. Le bisect referme la face de coupe."""
    bm = bmesh.new(); bm.from_mesh(ob.data)
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    # Convention (testée) : clear_inner=True supprime le côté OPPOSÉ à plane_no ; clear_outer=True supprime le côté de plane_no.
    # → garder y>0 : no=+y, clear_inner=True ; garder y<0 : no=+y, clear_outer=True.
    ci, co = (True, False) if garde_plus else (False, True)
    bmesh.ops.bisect_plane(bm, geom=geom, plane_co=Vector((0, 0, 0)), plane_no=Vector((0, 1, 0)),
                           clear_inner=ci, clear_outer=co, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob.data.clear_geometry(); bm.to_mesh(ob.data); bm.free()
    return ob

def split_body(env):
    """Coupe au plan y = 0 → b_front (y>0) et b_back (y<0) par BISECT bmesh (les booleens de coupe
    EXACT étaient instables sur cette géométrie).

    Les parois ne font que WALL=2.4 : goujons Ø5.8 et vis M3 vivent dans des
    PLOTS Ø9 internes soudés aux murs (pattern v2), pas dans la paroi.
    """
    yf, yb = DEPTH/2, -DEPTH/2
    y_cav_f = yf - WALL - COUNTER          # fond de la cavité côté avant
    y_cav_b = yb + WALL                    # fond de la cavité côté arrière
    # positions des plots : ADOSSÉS aux murs intérieurs (soudés) — spine, et mur courbe droit de chaque panse
    def bowl_geo(b):
        r = (b['zt'] - b['zb'])/2; cz = (b['zt'] + b['zb'])/2; return r, b['xr'] - r, cz
    rL, cxL, czL = bowl_geo(LOW); rH, cxH, czH = bowl_geo(HIGH)
    # CORRECTION 10/09 — le goujon bas du spine était à z = Z0+12 = 38, soit EN PLEIN MILIEU de la
    # baie du servo spine (corps z 36.1…58.9, oreilles z 31.4…63.6) : son plot Ø9 (z 33.5…42.5,
    # x 5.5…14.5) traversait le corps ET les oreilles du servo — c'est le « plot qui bloque ».
    # Descendu à z = 20 : plot z 15.5…24.5, soit 5.9 mm sous l'oreille basse (z 31.4 − 1 de jeu),
    # toujours dans la cavité du spine (x 2.4…17.6, plancher z 14.4) et soudé aux 2 parois Y.
    # Bonus : l'écartement des 2 goujons passe de 141 à 159 mm (meilleur guidage des coques).
    pins = [(SPINE_W/2, 20.0), (SPINE_W/2, Z0 + GH - 12),               # dans la cavité du spine (13.2 large : plot Ø9 soudé aux 2 murs)
            (cxL + rL - WALL - 4.0, czL), (cxH + rH - WALL - 4.0, czH)]  # adossés au mur courbe droit, à mi-hauteur
    screws = [(SPINE_W/2, Z0 + GH*0.30), (SPINE_W/2, Z0 + GH*0.72),
              (70.0, 33.0),  # LOW : cavité basse, loin des servos (x≤25 / x≥82) et du MPU (x≤50) — pilier tenu par les parois Y + vis M3
              (cxH, HIGH['zt'] - WALL - 4.0)]   # HIGH : plafond
    # plots pleins traversant tout l'intérieur (les 2 coques en hériteront chacune sa moitié)
    for k, (px, pz) in enumerate(pins + screws):
        booleen(env, cylindre(f'plot{k}', 9.0, (y_cav_f - y_cav_b) + 2.0, 'Y', (px, (y_cav_f + y_cav_b)/2, pz)), 'UNION')
    # avant-trous M3 percés AVANT la coupe mais BORGNES dans le front (y 0.5 → 16.5) : ils ne traversent PAS le plan
    # de joint y=0 → la coupe ne les recoupe pas → pas d'éventail de faces sur la face de joint (les pil traversants
    # créaient des arêtes >2 faces qui faisaient rejeter le mesh par le slicer). La vis M3×30 (tête à y≈-16.4) va
    # jusqu'à +13.6 : couverte. Le passage Ø3.4 du back (sc) traverse le joint et guide la vis jusqu'au pil.
    for k, (px, pz) in enumerate(screws):
        booleen(env, cylindre(f'pil{k}', 2.6, 16.0, 'Y', (px, 8.5, pz)), 'DIFFERENCE')

    # coupe en 2 par booléen EXACT (la géométrie est assainie : tubes Ø26.5 sans sliver → la coupe redevient fiable et referme les faces)
    front = dupliquer(env, 'b_front'); back = env; back.name = 'b_back'
    booleen(front, boite('cut_f', -60, 300, -100, -0.02, -60, 400), 'DIFFERENCE')   # garde y > 0
    booleen(back,  boite('cut_b', -60, 300, 0.02, 100, -60, 400), 'DIFFERENCE')     # garde y < 0
    for k, (px, pz) in enumerate(pins):
        booleen(back, cylindre(f'pin{k}', 5.8, 8.0, 'Y', (px, 2.0, pz)), 'UNION')         # goujon : y -2 → +6 (dépasse dans le front)
        booleen(front, cylindre(f'hole{k}', 6.0, 8.8, 'Y', (px, 4.1, pz)), 'DIFFERENCE')  # alésage Ø6.0 : traverse la peau (-0.3→8.5), percé APRÈS la coupe (pas d'éventail)
    for k, (px, pz) in enumerate(screws):
        booleen(back, cylindre(f'sc{k}', 3.4, DEPTH + 0.4, 'Y', (px, -DEPTH/4 + 0.2, pz)), 'DIFFERENCE')   # passage M3 (traverse le joint)
        booleen(back, cylindre(f'sch{k}', 6.4, 3.6, 'Y', (px, yb + 1.8 - EPS, pz)), 'DIFFERENCE')  # tête noyée

    return nettoyer(front), nettoyer(back)

# =============================================================================
#  ROUE-PIÈCE ₿ (face externe z=0, interne z=WHEEL_W) + PNEU TPU 360°
# =============================================================================
def bowl_local(z_bot, z_top, x_left, x_right):
    return bowl(z_bot, z_top, x_left, x_right)

def glyph_relief(scale, cx, cz, z0, z1):
    """₿ en relief sur la roue : glyphe réduit (homothétie `scale`), centré (cx,cz), extrudé Z."""
    s = scale
    def T(p): return ((p[0] - GW/2)*s + cx, (p[1] - (Z0 + GH/2))*s + cz)
    parts = [prisme('rs', [T(p) for p in [(0, Z0), (SPINE_W, Z0), (SPINE_W, Z0+GH), (0, Z0+GH)]], 'Z', z0, z1)]
    for k, b in enumerate((LOW, HIGH)):
        parts.append(prisme(f'rb{k}', [T(p) for p in bowl(b['zb'], b['zt'], 0, b['xr'])], 'Z', z0, z1))
    for k, bx in enumerate(BARS_X):
        parts.append(prisme(f'rt{k}', [T(p) for p in [(bx, Z0+GH-1), (bx+BAR_W, Z0+GH-1), (bx+BAR_W, Z0+GH+BAR_H), (bx, Z0+GH+BAR_H)]], 'Z', z0, z1))
        parts.append(prisme(f'rbt{k}', [T(p) for p in [(bx, Z0-BAR_H), (bx+BAR_W, Z0-BAR_H), (bx+BAR_W, Z0+1), (bx, Z0+1)]], 'Z', z0, z1))
    g = fusionner('relief', parts)
    ctr = fusionner('rctr', [prisme(f'rc{k}', [T(p) for p in bowl(b['zb']+STROKE, b['zt']-STROKE, SPINE_W, b['xr']-STROKE)], 'Z', z0-1, z1+1) for k, b in enumerate((LOW, HIGH))])
    booleen(g, ctr, 'DIFFERENCE')
    return g

def build_wheel():
    """Roue-pièce ₿ : disque Ø70 × 10, face externe z=0 (₿ GRAVÉ 1.0 + liseré — face plane → s'imprime face au plateau
    sans support), gorge de bande sur la jante, face interne prolongée par un MOYEU-TUBE Ø HUB_D × HUB_L (tourne dans le
    palier du corps). Au fond du moyeu : alésage axe, lamage bossage, empreinte palonnier en croix + oblongs de vis."""
    disk = cylindre('coin_wheel', WHEEL_D, WHEEL_W, 'Z', (0, 0, WHEEL_W/2), 128)
    ring_out = cylindre('ring_o', WHEEL_D - 3.0, 0.8 + EPS, 'Z', (0, 0, 0.4 - EPS), 128)
    ring_in  = cylindre('ring_i', WHEEL_D - 6.0, 1.0, 'Z', (0, 0, 0.4), 128)
    booleen(ring_out, ring_in, 'DIFFERENCE'); booleen(disk, ring_out, 'DIFFERENCE')
    # ₿ gravé 1.0 mm : pré-tourné de 90° dans le plan pour être DEBOUT une fois la roue montée (rotation ±90° autour de Y)
    relief = glyph_relief(40.0/(GH + 2*BAR_H), 0.0, 0.0, -1.0, 1.0)
    relief.matrix_world = Matrix.Rotation(math.radians(90), 4, 'Z') @ relief.matrix_world
    bpy.context.view_layer.objects.active = relief; relief.select_set(True); bpy.ops.object.transform_apply(rotation=True); relief.select_set(False)
    booleen(disk, relief, 'DIFFERENCE')
    # gorge de bande de roulement (centrée sur la largeur du disque)
    g_out = cylindre('g_o', WHEEL_D + 2.0, GROOVE_W, 'Z', (0, 0, WHEEL_W/2), 128)
    g_in  = cylindre('g_i', WHEEL_D - 2*GROOVE_D, GROOVE_W + 2, 'Z', (0, 0, WHEEL_W/2), 128)
    booleen(g_out, g_in, 'DIFFERENCE'); booleen(disk, g_out, 'DIFFERENCE')
    # moyeu-tube côté interne
    hub = cylindre('hub', HUB_D, HUB_L + EPS, 'Z', (0, 0, WHEEL_W + HUB_L/2), 96)
    booleen(disk, hub, 'UNION')
    zi = WHEEL_W + HUB_L                  # bout du moyeu (côté servo)
    outils = [cylindre('bore', HUB_BORE_D, (WHEEL_W + HUB_L)*3, 'Z', (0, 0, zi/2)),
              cylindre('cb', HUB_CB_D, HUB_CB_H + 3.0, 'Z', (0, 0, zi - (HUB_CB_H + 3.0)/2 + EPS))]   # lamage bossage + jeu axial 3 mm
    z_horn_top = zi - HUB_CB_H - 3.0 + EPS
    for a in (0, 90):
        m = Matrix.Rotation(math.radians(a), 4, 'Z')
        arm = boite(f'horn{a}', -HORN_ARM_L/2, HORN_ARM_L/2, -HORN_ARM_W/2, HORN_ARM_W/2, z_horn_top - HORN_T, zi + 1)
        arm.matrix_world = m @ arm.matrix_world; outils.append(arm)
    for sx in (-1, 1):
        for r in [HORN_SCREW_R0 + (HORN_SCREW_R1-HORN_SCREW_R0)*i/4 for i in range(5)]:
            outils.append(cylindre(f'os{sx}{r:.1f}', 2.4, WHEEL_W*3, 'Z', (sx*r, 0, WHEEL_W/2), 24))   # oblongs (vis palonnier) traversent le disque
    soustraire(disk, outils)
    return nettoyer(disk)

def build_tire():
    """Bande TPU pleine : anneau Ø int. = fond de gorge − interférence, épaisseur TIRE_T, largeur TIRE_W. S'imprime à plat."""
    d_in = (WHEEL_D - 2*GROOVE_D) - TIRE_STRETCH
    t = cylindre('coin_tire', d_in + 2*TIRE_T, TIRE_W, 'Z', (0, 0, TIRE_W/2), 128)
    booleen(t, cylindre('t_core', d_in, TIRE_W + 2, 'Z', (0, 0, TIRE_W/2), 128), 'DIFFERENCE')
    return nettoyer(t)

# =============================================================================
#  RENDU (EEVEE : face + iso), assemblage roues comprises
# =============================================================================
def _mat(nom, rgba, rough=0.45):
    m = bpy.data.materials.new(nom); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']; b.inputs['Base Color'].default_value = rgba; b.inputs['Roughness'].default_value = rough
    return m

def rendu(objets_mats, chemin, vue='face'):
    sc = bpy.context.scene
    try: sc.render.engine = 'BLENDER_EEVEE_NEXT'
    except TypeError: sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = 1100, 1400; sc.render.film_transparent = False
    w = bpy.data.worlds.new('W'); w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.55, 0.57, 0.62, 1); w.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.2
    sc.world = w
    for ob, m in objets_mats:
        ob.data.materials.clear(); ob.data.materials.append(m)
    # lumières (soleil + 2 points)
    S = bpy.data.lights.new('sun', 'SUN'); S.energy = 4.0; S.angle = math.radians(8)
    so = bpy.data.objects.new('sun', S); so.rotation_euler = (math.radians(50), math.radians(-15), math.radians(160)); bpy.context.collection.objects.link(so)
    for k, (loc, e) in enumerate((((150, 250, 300), 30000), ((-200, 200, 150), 12000))):
        L = bpy.data.lights.new(f'L{k}', 'POINT'); L.energy = e; L.shadow_soft_size = 30
        lo = bpy.data.objects.new(f'L{k}', L); lo.location = loc; bpy.context.collection.objects.link(lo)
    cam = bpy.data.cameras.new('cam'); cam.type = 'ORTHO'
    co = bpy.data.objects.new('cam', cam); bpy.context.collection.objects.link(co); sc.camera = co
    cx, cz = GW/2 - 4, (Z0 - LEG_H + Z0 + GH + BAR_H)/2
    if vue == 'face':
        co.location = (cx, 400, cz); co.rotation_euler = (math.radians(90), 0, math.radians(180)); cam.ortho_scale = 250
    elif vue == 'inside':   # coque arrière vue depuis le plan de joint (y>0 → regarde vers -y)
        co.location = (cx, 400, cz); co.rotation_euler = (math.radians(90), 0, math.radians(180)); cam.ortho_scale = 230
    else:
        co.location = (cx + 260, 300, cz + 200); co.rotation_euler = (math.radians(62), 0, math.radians(139)); cam.ortho_scale = 280
    sc.render.filepath = chemin; bpy.ops.render.render(write_still=True)
    print(f"  [PNG] {os.path.basename(chemin)}")

def assemblage_pour_rendu(front, back, wheel, tire):
    """Copies posées à leur place. Après miroir_x : x → GW − x. Plans internes des roues : GW − x_in_R (gauche), GW − x_in_L (droite)."""
    r_low = (LOW['zt'] - LOW['zb'])/2; cz_low = (LOW['zt'] + LOW['zb'])/2
    x_wall_R = (LOW['xr'] - r_low) + math.sqrt(r_low**2 - (AXLE_Z - cz_low)**2)
    TUBE = (GW + WHEEL_GAP) - x_wall_R
    # bout du moyeu = 1 mm DANS l'épaisseur de la paroi latérale (alésée). Après miroir x → GW − x :
    xL, xR = GW - x_wall_R + 1.0, GW - 1.0     # 12 (paroi courbe, gauche) et 89 (spine, droite)
    O = _mat('orange', (0.97, 0.58, 0.10, 1)); D = _mat('dark', (0.10, 0.10, 0.11, 1), 0.6); T = _mat('tpu', (0.16, 0.16, 0.16, 1), 0.9)
    objs = [(front, O), (back, O)]
    for sx, xw in ((-1, xL), (1, xR)):
        w = dupliquer(wheel, f'wheel{sx}'); t = dupliquer(tire, f'tire{sx}')
        # roue locale : axe Z, face externe z=0, disque z∈[0,10], moyeu z∈[10,23]. Le bout du moyeu (z=23) va au plan xw.
        # pneu local : z∈[0, TIRE_W] → centré sur le disque : décalage (WHEEL_W − TIRE_W)/2
        dt = (WHEEL_W - TIRE_W)/2
        if sx < 0:   # +Z local → +X : rot +90° ; z=23 local → x = origine + 23 = xw → origine = xw − 23
            w.matrix_world = Matrix.Translation((xw - (WHEEL_W + HUB_L), 0, AXLE_Z)) @ Matrix.Rotation(math.radians(90), 4, 'Y')
            t.matrix_world = Matrix.Translation((xw - (WHEEL_W + HUB_L) + dt, 0, AXLE_Z)) @ Matrix.Rotation(math.radians(90), 4, 'Y')
        else:        # +Z local → −X : rot −90° ; z=23 local → x = origine − 23 = xw → origine = xw + 23
            w.matrix_world = Matrix.Translation((xw + (WHEEL_W + HUB_L), 0, AXLE_Z)) @ Matrix.Rotation(math.radians(-90), 4, 'Y')
            t.matrix_world = Matrix.Translation((xw + (WHEEL_W + HUB_L) - dt, 0, AXLE_Z)) @ Matrix.Rotation(math.radians(-90), 4, 'Y')
        objs += [(w, D), (t, T)]
    return objs

# =============================================================================
def miroir_x(ob):
    """Le glyphe est construit avec le spine en x=0 (à gauche dans le repère), mais vu de FACE (+Y vers -Y)
    x croît vers la gauche de l'observateur → le ₿ apparaîtrait en miroir. On retourne le corps en X
    (x → GW - x) pour que le ₿ se lise correctement de face. Appliqué aux 2 coques (roues symétriques : inchangées)."""
    bpy.context.view_layer.objects.active = ob; bpy.ops.object.select_all(action='DESELECT'); ob.select_set(True)
    ob.matrix_world = Matrix.Translation((GW, 0, 0)) @ Matrix.Scale(-1, 4, (1, 0, 0)) @ ob.matrix_world
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False); bpy.ops.object.mode_set(mode='OBJECT')
    ob.select_set(False); return ob

def main():
    raz_scene()
    print('== ₿ BalanceBot v3 ==')
    env = build_body()
    front, back = split_body(env)
    miroir_x(front); miroir_x(back)
    exporter(front, os.path.join(OUT, 'b_front.stl'))
    exporter(back, os.path.join(OUT, 'b_back.stl'))
    w = build_wheel(); exporter(w, os.path.join(OUT, 'coin_wheel.stl'))
    t = build_tire(); exporter(t, os.path.join(OUT, 'coin_tire.stl'))
    if '--preview' in sys.argv:
        objs = assemblage_pour_rendu(front, back, w, t)
        # les originaux roue/pneu restent à l'origine : on les cache
        w.hide_render = True; t.hide_render = True
        rendu(objs, os.path.join(OUT, 'preview_front.png'), 'face')
        rendu(objs, os.path.join(OUT, 'preview_iso.png'), 'iso')
        # intérieur : coque arrière seule vue du plan de joint (aménagements), coque avant seule vue de dos
        for o, _ in objs:
            o.hide_render = True
        back.hide_render = False
        rendu([(back, _mat('o2', (0.97, 0.58, 0.10, 1)))], os.path.join(OUT, 'preview_back_inside.png'), 'inside')
        back.hide_render = True; front.hide_render = False
        # coque avant vue de l'intérieur = caméra derrière (y<0) regardant vers +y
        sc = bpy.context.scene; co = sc.camera
        co.location = (GW/2 - 4, -400, (Z0 - LEG_H + Z0 + GH + BAR_H)/2); co.rotation_euler = (math.radians(90), 0, 0)
        sc.render.filepath = os.path.join(OUT, 'preview_front_inside.png'); bpy.ops.render.render(write_still=True)
        print('  [PNG] preview_front_inside.png')
    print('OK')

if __name__ == '__main__':
    main()
