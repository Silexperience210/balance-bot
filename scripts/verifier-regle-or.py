#!/usr/bin/env python3
"""Vérifie la RÈGLE D'OR du projet : le simulateur et le firmware doivent dire la même chose.

Le projet tient sur une seule loi : toute divergence entre le simulateur et le firmware est
un bug des deux côtés à la fois. Ce script la fait respecter automatiquement : il lit les
constantes du firmware (`balance-bot/config.h` ET les `static const` de `head.cpp`) et celles
des deux simulateurs (`sim/web/`, `sim/balancebot_sim.py`), et échoue si elles divergent.

Usage : python3 scripts/verifier-regle-or.py     (code de sortie 1 si divergence)
"""
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CONFIG_H = RACINE / "balance-bot/config.h"
HEAD_CPP = RACINE / "balance-bot/head.cpp"
ULTRASON_JS = RACINE / "sim/web/ultrason.js"
ENGINE_JS = RACINE / "sim/web/engine.js"
SIM_PY = RACINE / "sim/balancebot_sim.py"

# Constantes qui décident du comportement : comparées des deux côtés, échec si elles diffèrent.
STRICTES = [
    "US_MAX_CM",
    "US_STOP_CM",
    "HEAD_PAN_MIN",
    "HEAD_PAN_MAX",
    "HEAD_TILT_MIN",
    "HEAD_TILT_MAX",
    "US_SMOOTH_COUNT",
    "PAN_SPEED_DEG",
    "TILT_SPEED_DEG",
]

# Le mode d'actionneur : firmware en 0/1, simulateurs en "arc"/"roue".
MODE_ATTENDU = {0: "arc", 1: "roue"}


def normalise(brut):
    v = brut.strip().rstrip(";").strip()
    if re.fullmatch(r"-?[\d.]+\s*[fF]", v):
        v = v.rstrip("fF")
    v = v.strip('"').strip("'")
    # Une expression arithmétique simple (« 1.0 / 200 ») doit être évaluée : un pas de temps
    # écrit sous forme de calcul vaut autant qu'un littéral.
    if re.fullmatch(r"[\d\s.+\-*/()]+", v) and any(c in v for c in "+-*/"):
        try:
            return str(eval(v, {"__builtins__": {}}, {}))  # noqa: S307 — expression filtrée
        except Exception:
            pass
    for conv in (int, float):
        try:
            return str(conv(v))
        except ValueError:
            continue
    return v


def lit_defines(chemin):
    """#define NAME valeur → {NAME: valeur}"""
    trouves = {}
    if not chemin.exists():
        return trouves
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*#define\s+([A-Z_][A-Z0-9_]*)\s+([^/\s]+)", ligne)
        if m:
            trouves[m.group(1)] = normalise(m.group(2))
    return trouves


def lit_statics_cpp(chemin):
    """static const <type> NAME = valeur ;  → {NAME: valeur}  (constantes locales au module)"""
    trouves = {}
    if not chemin.exists():
        return trouves
    texte = re.sub(r"//[^\n]*", "", chemin.read_text(encoding="utf-8"))
    for m in re.finditer(
            r"static\s+const(?:expr)?\s+\w+\s+([A-Z_][A-Z0-9_]*)\s*=\s*([^;]+);", texte):
        trouves[m.group(1)] = normalise(m.group(2))
    return trouves


def lit_js(chemin):
    """Déclarations JS : var NAME = valeur ; (y compris dans un groupe « var A = 1, B = 2 ; »).

    On NE retient que la PREMIÈRE occurrence : une comparaison comme `MODE == "arc"` plus
    loin dans le code ne doit pas être confondue avec la déclaration `var MODE = "roue"`.
    """
    trouves = {}
    if not chemin.exists():
        return trouves
    texte = re.sub(r"//[^\n]*", "", chemin.read_text(encoding="utf-8"))
    for m in re.finditer(r"(?:var|let|const|,)\s*([A-Z_][A-Z0-9_]*)\s*=\s*([^,;\n]+)", texte):
        trouves.setdefault(m.group(1), normalise(m.group(2)))
    return trouves


def lit_mode_python(chemin):
    if not chemin.exists():
        return None
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        m = re.match(r'\s*MODE\s*=\s*"(\w+)"', ligne)
        if m:
            return m.group(1)
    return None


def main():
    print("RÈGLE D'OR — le simulateur et le firmware disent-ils la même chose ?\n")
    echecs = []

    firmware = lit_defines(CONFIG_H)
    firmware.update(lit_statics_cpp(HEAD_CPP))
    sim = lit_js(ULTRASON_JS)
    sim.update(lit_js(ENGINE_JS))

    print("— constantes partagées —")
    for nom in STRICTES:
        fw, js = firmware.get(nom), sim.get(nom)
        if fw is None:
            print(f"  ~ {nom:16s} (pas dans le firmware)")
        elif js is None:
            print(f"  ~ {nom:16s} firmware={fw} (pas reprise dans le simulateur)")
        elif fw == js:
            print(f"  ✔ {nom:16s} {fw}")
        else:
            print(f"  ✘ {nom:16s} firmware={fw}   simulateur={js}   ← DIVERGENCE")
            echecs.append(nom)

    # Cadence de la boucle d'équilibre : le firmware la nomme, le simulateur la déduit du
    # pas de temps. On compare la cadence réelle, pas le nom.
    hz_fw = firmware.get("BALANCE_LOOP_HZ")
    dt_js = sim.get("DT")
    print()
    print("— cadence de la boucle d'équilibre —")
    if hz_fw and dt_js:
        try:
            hz_sim = round(1.0 / float(dt_js))
        except (ValueError, ZeroDivisionError):
            hz_sim = None
        if hz_sim == int(float(hz_fw)):
            print(f"  ✔ firmware {hz_fw} Hz  ↔  simulateur {hz_sim} Hz (pas de {dt_js} s)")
        else:
            print(f"  ✘ firmware {hz_fw} Hz  ↔  simulateur {hz_sim} Hz   ← DIVERGENCE")
            echecs.append("BALANCE_LOOP_HZ")
    else:
        print(f"  ~ firmware={hz_fw} Hz · pas de temps du simulateur={dt_js} (non comparable)")

    # Mode d'actionneur : trois acteurs (firmware, simulateur web, simulateur Python).
    print()
    print("— mode d'actionneur —")
    mode_fw = firmware.get("FEET_MODE_CONTINUOUS")
    mode_js = sim.get("MODE")
    mode_py = lit_mode_python(SIM_PY)
    attendu = MODE_ATTENDU.get(int(mode_fw)) if mode_fw and mode_fw.isdigit() else None
    print(f"  firmware FEET_MODE_CONTINUOUS={mode_fw}  ↔  web MODE={mode_js!r}"
          f"  ↔  python MODE={mode_py!r}")
    if attendu is None:
        print("  ~ drapeau du firmware illisible : comparaison impossible")
    else:
        if mode_js != attendu:
            print(f"  ✘ DIVERGENCE : firmware en « {attendu} », simulateur web en « {mode_js} »")
            echecs.append("MODE_firmware_web")
        if mode_py != attendu:
            print(f"  ✘ DIVERGENCE : firmware en « {attendu} », simulateur Python en « {mode_py} »")
            echecs.append("MODE_firmware_python")
        if mode_js == attendu == mode_py:
            print(f"  ✔ les trois disent « {attendu} »")

    print()
    if echecs:
        print(f"ÉCHEC — {len(echecs)} divergence(s) : {', '.join(echecs)}")
        print("Corrige la constante des DEUX côtés, jamais d'un seul.")
        return 1
    print("OK — simulateur et firmware d'accord sur tout ce qui est comparable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
