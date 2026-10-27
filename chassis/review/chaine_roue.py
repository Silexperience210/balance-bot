#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chaîne servo → palonnier → moyeu → roue, mesurée sur les STL.

Ne fait pas confiance au générateur : chaque cote est un rayon sur le
maillage, comparé à chassis/cotes.py. Blender n'est pas requis (la CI
peut lancer ce script). L'intersection servo × coque, elle, reste dans
servo_fit.py parce qu'elle a besoin du booléen EXACT.

Ce qui n'est PAS mesuré ici, et qu'il ne faut pas inventer :
  · le palonnier réel (20 × 5,2 × 1,8 mm est une enveloppe de conception) ;
  · le capot du servo sous la main (4,0 mm et +2,9 mm viennent du STL
    FreeCAD Servo-SG90.stl, pas d'un pied à coulisse) ;
  · l'engagement des cannelures une fois le palonnier vissé.
"""
import math
import os
import sys

import numpy as np
import trimesh

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, ".."))
import cotes  # noqa: E402

V3 = os.path.join(ICI, "..", "v3")
RACINE = os.path.join(ICI, "..", "..")
ATOL = 0.20          # mm — facettes de cylindre + soudure de sommets

nok = ntot = 0


def report(label, ok, detail):
    global nok, ntot
    ntot += 1
    nok += int(bool(ok))
    print("  %s %-56s %s" % ("OK " if ok else "KO ", label, detail))
    return ok


def charge(nom):
    m = trimesh.load(os.path.join(V3, nom), process=True)
    m.merge_vertices()
    return m


def rayon(m, origine, direction):
    pts = m.ray.intersects_location(np.array([origine], float),
                                    np.array([direction], float),
                                    multiple_hits=True)[0]
    axe = int(np.argmax(np.abs(direction)))
    return sorted(float(p[axe]) for p in pts)


def proche(valeur, attendu, tol=ATOL):
    return abs(valeur - attendu) <= tol


def main():
    f = charge("b_front.stl")
    b = charge("b_back.stl")
    w = charge("coin_wheel.stl")
    t = charge("coin_tire.stl")

    print("=== enveloppe (ne doit pas bouger) ===")
    report("b_front 132,13 × 23,02 × 201",
           np.allclose(f.bounds[1] - f.bounds[0], [132.13, 23.02, 201.0], atol=0.05),
           str(np.round(f.bounds[1] - f.bounds[0], 2)))
    report("b_back 132,13 × 29 × 201",
           np.allclose(b.bounds[1] - b.bounds[0], [132.13, 29.0, 201.0], atol=0.05),
           str(np.round(b.bounds[1] - b.bounds[0], 2)))
    for nom, m in (("b_front", f), ("b_back", b), ("roue", w), ("pneu", t)):
        report("%s watertight" % nom, bool(m.is_watertight),
               "volume %.2f cm3" % (float(m.volume) / 1000.0))

    print("=== pile axiale, sur le maillage ===")
    sh_p, sh_s = cotes.epaulements_apres_miroir()
    bo_p, bo_s = cotes.bouches_tube_apres_miroir()
    # y = 7 : dans l'alésage Ø24,5 (r 12,25), hors du trou d'axe Ø12,4 (r 6,2).
    # Le front seul (y>0) porte la moitié du tube.
    for nom, attendu in (("panse", sh_p), ("spine", sh_s)):
        xs = rayon(f, [-30.0, 7.0, cotes.AXLE_Z], [1, 0, 0])
        hit = min(xs, key=lambda x: abs(x - attendu)) if xs else None
        report("épaulement %s" % nom, hit is not None and proche(hit, attendu),
               "mesuré %s, cotes %.2f, autres %s" % (
                   None if hit is None else round(hit, 2), attendu,
                   [round(x, 2) for x in xs[:6]]))
    y_paroi = cotes.BEAR_D / 2.0 + 0.45
    for nom, attendu in (("panse", bo_p), ("spine", bo_s)):
        xs = rayon(f, [-40.0, y_paroi, cotes.AXLE_Z], [1, 0, 0])
        hit = min(xs, key=lambda x: abs(x - attendu)) if xs else None
        report("bouche du tube %s" % nom, hit is not None and proche(hit, attendu, 0.35),
               "mesuré %s, cotes %.2f" % (None if hit is None else round(hit, 2), attendu))
    # Le moyeu (HUB_L) doit entrer : bouche → épaulement ≥ longueur engagée.
    for nom, sh, bo in (("panse", sh_p, bo_p), ("spine", sh_s, bo_s)):
        # panse : la bouche est à gauche de l'épaulement (x plus petit)
        profondeur = abs(sh - bo)
        engage = cotes.PILE["u_mouth"] - cotes.HUB_TIP_U
        report("alésage %s contient le moyeu" % nom,
               profondeur + 0.15 >= engage and profondeur < engage + 1.2,
               "profondeur %.2f, moyeu engagé %.2f, jeu épaulement %.2f"
               % (profondeur, engage, cotes.HUB_TIP_U - cotes.SHOULDER_U))

    print("=== trou d'axe et capot oblong ===")
    # Axe : le cylindre Ø12,4 est vide. y=0,5 évite le plan de joint.
    xs_axe = rayon(f, [-30.0, 0.5, cotes.AXLE_Z], [1, 0, 0])
    report("axe Ø%.1f débouchant (y=0,5)" % cotes.AXLE_HOLE_D,
           not any(abs(x - sh_p) < 1.0 or abs(x - sh_s) < 1.0 for x in xs_axe),
           "croisements %s" % [round(x, 2) for x in xs_axe[:8]])
    # Capot : au-delà du cylindre, vers le bout long, le rectangle est ouvert.
    z_long = cotes.AXLE_Z + (cotes.CAP_Z_LONG - 0.5)
    xs_long = rayon(f, [-30.0, 0.5, z_long], [1, 0, 0])
    report("fente capot bout long ouverte",
           not any(abs(x - sh_p) < 1.0 or abs(x - sh_s) < 1.0 for x in xs_long),
           "z=%.1f croisements %s" % (z_long, [round(x, 2) for x in xs_long[:8]]))
    # Sous le bout court, hors du rectangle : la paroi est pleine.
    z_sous = cotes.AXLE_Z - (cotes.CAP_Z_SHORT + 1.5)
    xs_sous = rayon(f, [-30.0, 0.5, z_sous], [1, 0, 0])
    report("paroi pleine sous le capot",
           any(abs(x - sh_p) < 0.6 for x in xs_sous),
           "z=%.1f croisements %s" % (z_sous, [round(x, 2) for x in xs_sous[:6]]))

    print("=== semelle (la 4e vis d'oreille n'existe pas) ===")
    z_bas = cotes.AXLE_Z - cotes.SV_SHAFT_OFF + cotes.SV_L / 2 - cotes.SV_HOLE_PITCH / 2
    peau = cotes.x_wall_panse(z_bas)
    x_bulk = (cotes.X_WALL_R - cotes.WALL) - (cotes.SV_H - cotes.SV_FLANGE_Z - cotes.SV_FLANGE_T)
    report("oreille basse panse hors peau",
           peau < x_bulk - 1.0,
           "peau x=%.2f, face d'oreille x=%.2f (avant miroir)" % (peau, x_bulk))
    # Semelle : sous le corps, z de (z_sv0 - 2,6) à (z_sv0 - 0,2).
    z_sv0 = cotes.AXLE_Z - cotes.SV_SHAFT_OFF
    z_haut = z_sv0 - cotes.SHELF_DROP

    def dalle(zs):
        """Une face haute à z_haut, avec au moins 1,5 mm de matière dessous."""
        for i, z in enumerate(zs):
            if proche(z, z_haut, 0.25) and i > 0 and (z - zs[i - 1]) >= 1.5:
                return True
        return False

    # Après miroir, milieu de la semelle (8…14 mm depuis la face, vers l'intérieur).
    x_face_p = cotes.X_WALL_R - cotes.WALL
    x_sem_p = cotes.GW - (x_face_p - 11.0)          # d=−1, 11 mm vers l'intérieur
    zs = rayon(f, [x_sem_p, 2.0, 28.0], [0, 0, 1])
    report("semelle panse sous l'enveloppe servo", dalle(zs),
           "x=%.1f z=%s (dessus attendu %.2f)" % (x_sem_p, [round(z, 2) for z in zs[:8]], z_haut))
    x_sem_s = cotes.GW - (cotes.WALL + 11.0)
    zs = rayon(f, [x_sem_s, 2.0, 28.0], [0, 0, 1])
    report("semelle spine sous l'enveloppe servo", dalle(zs),
           "x=%.1f z=%s" % (x_sem_s, [round(z, 2) for z in zs[:8]]))

    print("=== roue : moyeu, empreinte, allègement ===")
    zi = float(w.bounds[1][2])
    z0 = float(w.bounds[0][2])
    report("longueur de moyeu",
           proche(zi - cotes.WHEEL_W, cotes.HUB_L, 0.12) and abs(z0) < 0.05,
           "bout z=%.2f, HUB_L cotes %.2f" % (zi, cotes.HUB_L))
    # (8, 0) : dans le bras de la croix (demi-longueur 10,35), hors alésage, dans le capot.
    # La croix est plus profonde que le capot : le fond mesuré est celui de l'empreinte.
    zs = rayon(w, [8.0, 0.0, -2.0], [0, 0, 1])
    fond = max((z for z in zs if z < zi - 0.3), default=None)
    report("fond d'empreinte en croix",
           fond is not None and proche(zi - fond, cotes.PILE["pocket_depth"], 0.2),
           "z=%s, profondeur %s (cotes %.2f)" % (
               [round(z, 2) for z in zs], None if fond is None else round(zi - fond, 2),
               cotes.PILE["pocket_depth"]))
    # (4, 4) : hors de la croix (largeur 2,95), dans la cavité ronde du capot.
    zs = rayon(w, [4.0, 4.0, -2.0], [0, 0, 1])
    fond = max((z for z in zs if z < zi - 0.2), default=None)
    report("cavité ronde du capot",
           fond is not None and proche(zi - fond, cotes.PILE["cap_cavity_depth"], 0.2),
           "z=%s, profondeur %s (cotes %.2f)" % (
               [round(z, 2) for z in zs], None if fond is None else round(zi - fond, 2),
               cotes.PILE["cap_cavity_depth"]))
    # (0, 0) : alésage borgne. La gravure ₿ enlève le premier millimètre au centre.
    zs = rayon(w, [0.0, 0.0, -2.0], [0, 0, 1])
    plein = [z for z in zs if 0.5 < z < zi - 0.2]
    report("alésage d'arbre borgne",
           len(plein) >= 2 and proche(zi - max(plein), cotes.PILE["shaft_bore_depth"], 0.25)
           and min(plein) > 0.4,
           "matière z=%s (la face ₿ ne doit pas être percée)" % [round(z, 2) for z in zs])
    # Bras à angle 0, poche à 30°.
    zs = rayon(w, [28.0, 0.0, -2.0], [0, 0, 1])
    report("bras plein (angle 0, r=28)",
           zs and zs[-1] >= cotes.WHEEL_W - 0.4 and zs[0] < 0.4,
           "z=%s" % [round(z, 2) for z in zs])
    # 20° est dans le bras si celui-ci fait 44° (ancienne inversion) et dans
    # la poche si le bras fait bien 16° (±8°).
    a = math.radians(20.0)
    zs = rayon(w, [25.0 * math.cos(a), 25.0 * math.sin(a), -2.0], [0, 0, 1])
    report("poche large (20°, bras de 16°)",
           zs and proche(max(z for z in zs if z < 4), cotes.SPOKE_Z0, 0.25)
           and max(zs) <= cotes.SPOKE_Z0 + 0.3,
           "z=%s" % [round(z, 2) for z in zs])
    a = math.radians(30.0)
    zs = rayon(w, [25.0 * math.cos(a), 25.0 * math.sin(a), -2.0], [0, 0, 1])
    report("poche entre les bras (30°, r=25)",
           zs and proche(max(z for z in zs if z < 4), cotes.SPOKE_Z0, 0.25)
           and max(zs) <= cotes.SPOKE_Z0 + 0.3,
           "z=%s (peau à %.1f)" % ([round(z, 2) for z in zs], cotes.SPOKE_Z0))
    # Jante : le fond de gorge est à r = 39,5. Juste au-dessus, deux flasques.
    zs = rayon(w, [0.0, 39.65, -2.0], [0, 0, 1])
    report("gorge de pneu (deux flasques)",
           len(zs) >= 4 and zs[1] < 1.2 and zs[-2] > cotes.WHEEL_W - 1.2,
           "z=%s" % [round(z, 2) for z in zs])

    vol = float(w.volume) / 1000.0
    w.density = cotes.PETG_G_PER_CM3 * 1e-3          # g/mm³
    izz = float(w.moment_inertia[2, 2]) * 1e-9       # g·mm² → kg·m²
    masse = vol * cotes.PETG_G_PER_CM3
    # Un disque plein faisait ~42,6 cm³ / ~54 g. On exige un allègement réel
    # sans vider la jante (plancher : 20 cm³).
    report("roue allégée (plus un disque plein)",
           20.0 < vol < 40.0, "%.2f cm3, %.1f g PETG, Izz %.3e kg·m²" % (vol, masse, izz))
    report("inertie d'axe imprimée", izz > 0.0, "%.3e kg·m² (le sim ignore cette masse)" % izz)

    print("=== pneu ===")
    report("pneu Ø83 × 7",
           np.allclose(t.bounds[1] - t.bounds[0], [83.0, 83.0, 7.0], atol=0.05),
           str(np.round(t.bounds[1] - t.bounds[0], 2)))

    print("=== simulateur : physique figée, géométrie à part ===")
    eng = open(os.path.join(RACINE, "sim", "web", "engine.js"), encoding="utf-8").read()
    sim = open(os.path.join(RACINE, "sim", "balancebot_sim.py"), encoding="utf-8").read()
    report("engine.js R = 0,0415 (références selfcheck)",
           "R = 0.0415" in eng and "TRACK = 0.13887" in eng, "littéraux inchangés")
    report("balancebot_sim.py TRACK = 0,13887",
           "TRACK = 0.13887" in sim and "0.0415" in sim, "littéraux inchangés")
    report("axe géométrique 42,0 mm", abs(cotes.AXLE_Z - 42.0) < 1e-9,
           "cotes.AXLE_Z = %.3f" % cotes.AXLE_Z)
    pieds = open(os.path.join(RACINE, "balance-bot", "feet.cpp"), encoding="utf-8").read()
    report("sens des roues inchangé (miroir)",
           "kDirL = -1.0f" in pieds and "kDirR = +1.0f" in pieds,
           "kDirL −1, kDirR +1")

    print()
    print("RESULTAT CHAINE : %d/%d" % (nok, ntot))
    return 0 if nok == ntot else 1


if __name__ == "__main__":
    sys.exit(main())
