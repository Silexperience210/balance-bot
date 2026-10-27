#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cohérence cotes ↔ notes ↔ firmware ↔ simulateur.

Ce n'est pas une mesure de maillage (c'est chaine_roue.py). Ici on
vérifie que les textes qui prétendent décrire le robot disent la même
chose que chassis/cotes.py, et que le recentrage des roues n'a pas été
appliqué en douce.

Deux rayons coexistent exprès :
  · 42,0 mm — axe géométrique, WHEEL_RADIUS_MM, viewer ;
  · 41,5 mm — rayon dynamique figé, engine.js et balancebot_sim.py.
"""
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "chassis"))
import cotes  # noqa: E402

echecs = []


def ok(label, cond, detail):
    print("  %s %-52s %s" % ("OK " if cond else "KO ", label, detail))
    if not cond:
        echecs.append(label)


def lit(rel):
    return (RACINE / rel).read_text(encoding="utf-8")


def define_float(texte, nom):
    m = re.search(r"#define\s+" + nom + r"\s+([0-9.]+)f?", texte)
    return float(m.group(1)) if m else None


def main():
    print("COTES — les textes disent-ils la même chose que cotes.py ?\n")
    cfg = lit("balance-bot/config.h")
    pieds = lit("balance-bot/feet.cpp")
    notes = lit("chassis/NOTES_v3.md")
    readme = lit("README.md")
    eng = lit("sim/web/engine.js")
    sim = lit("sim/balancebot_sim.py")
    gen = lit("chassis/gen_bitcoin_bot.py")

    print("— géométrie —")
    rayon = define_float(cfg, "WHEEL_RADIUS_MM")
    ok("WHEEL_RADIUS_MM = AXLE_Z",
       rayon is not None and abs(rayon - cotes.AXLE_Z) < 1e-6,
       "config %s, cotes %.3f" % (rayon, cotes.AXLE_Z))
    ok("axe géométrique 42 mm", abs(cotes.AXLE_Z - 42.0) < 1e-9, "%.3f" % cotes.AXLE_Z)
    ok("générateur lit cotes.AXLE_Z", "AXLE_Z = cotes.AXLE_Z" in gen, "affectation")
    ok("NOTES citent 42,0 mm", "42,0" in notes, "NOTES_v3.md")
    ok("README cite 42,0 mm", "42,0" in readme or "42.0" in readme, "README.md")

    print("— physique figée (selfcheck) —")
    ok("engine.js R = 0,0415", "R = 0.0415" in eng, "littéral")
    ok("engine.js TRACK = 0,13887", "TRACK = 0.13887" in eng, "littéral")
    ok("balancebot_sim.py 0,0415", "0.0415" in sim and "TRACK = 0.13887" in sim, "littéral")
    ok("NOTES citent les deux rayons", "41,5" in notes and "42,0" in notes, "NOTES_v3.md")

    print("— sens des roues (non mesuré au sol, invariant du miroir) —")
    ok("kDirL = −1", "kDirL = -1.0f" in pieds, "feet.cpp")
    ok("kDirR = +1", "kDirR = +1.0f" in pieds, "feet.cpp")

    print("— visserie et recentrage —")
    ok("NOTES : M2 × 6 (pas la cote courante M2 × 8)",
       "M2 × 6" in notes and "Pas M2 × 8" in notes, "NOTES_v3.md")
    mil, dec = cotes.milieu_axes()
    ok("roues NON recentrées (écart < −5 mm)",
       dec < -5.0, "milieu %.2f, écart %+.2f" % (mil, dec))
    prop = cotes.proposition_recentrage()
    ok("proposition de recentrage inactive",
       prop["applique"] is False and "proposition_recentrage" not in gen,
       "delta %+.2f mm, générateur ne la lit pas" % prop["delta_mm"])
    ok("moyeu spine de la proposition encore positif",
       prop["moyeu_spine_mm"] > cotes.PILE["pocket_depth"],
       "moyeu %.2f > empreinte %.2f" % (prop["moyeu_spine_mm"], cotes.PILE["pocket_depth"]))

    print()
    if echecs:
        print("ÉCHEC — %d point(s) : %s" % (len(echecs), ", ".join(echecs)))
        return 1
    print("OK — cotes, notes, firmware et simulateur d'accord.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
