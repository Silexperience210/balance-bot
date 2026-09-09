#!/usr/bin/env python3
"""Banc de test matériel BalanceBot — vérifie la cadence de la boucle 200 Hz.

Utilisation (la carte doit être flashée et l'AP « BalanceBot-Tune » disponible) :

    python3 tools/hw_test.py            # les 3 phases
    python3 tools/hw_test.py --duree 30 # fenêtre plus longue

Phases :
  1. CONTRÔLE   : 20 s sans visage (écran de commande), poll HTTP 1 Hz
  2. VISAGE     : 20 s d'aperçu avec balayage du regard (charge maxi)
  3. VISAGE IDLE: 10 s d'aperçu statique (vérifie que rien ne bouffe la boucle)

Critères (le watchdog du firmware coupe sous 120 Hz) :
  - aucune seconde sous 150 Hz  → OK
  - aucune seconde sous 120 Hz  → OK mais marge faible
  - une seconde sous 120 Hz     → ÉCHEC (le robot s'arrêterait en équilibre)

Le WiFi de la machine est restauré à la fin (bloc finally).
"""
import argparse
import json
import subprocess
import sys
import time

AP_SSID = "BalanceBot-Tune"
AP_URL = "http://192.168.4.1"
HOME_SSID = "Freebox-66E1B2"
POLL_S = 1.0


def sh(cmd, timeout=40):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    return ((r.stdout or "") + (r.stderr or "")).strip()


def connect_ap():
    sh("nmcli dev wifi rescan", 45)
    time.sleep(4)
    out = sh(f"nmcli --wait 25 dev wifi connect {AP_SSID}", 50)
    time.sleep(3)
    return out


def restore_wifi():
    sh(f"nmcli --wait 30 con up {HOME_SSID}", 60)
    for _ in range(8):
        time.sleep(2)
        code = sh("curl -s -o /dev/null -w '%{http_code}' -m 5 https://api.telegram.org", 10)
        if code[:1] in "23":
            return True
    return False


def state():
    raw = sh(f"curl -s -m 6 {AP_URL}/api/state", 15)
    return json.loads(raw)


def phase(name, seconds, face=None):
    """Poll la télémétrie pendant `seconds`. face=None → pas d'aperçu."""
    if face is not None:
        sh(f"curl -s -m 6 '{AP_URL}/api/face?state={face}&t={seconds + 2}&sweep'", 15)
    hz, ui, rows = [], [], []
    prev_s = None
    for i in range(seconds):
        time.sleep(POLL_S)
        try:
            st = state()
        except Exception:
            rows.append((i + 1, None, None, "pas de réponse"))
            continue
        hz.append(st["hz"])
        ui.append(st["ui"])
        note = ""
        if prev_s is not None:
            if st["s"] < prev_s:
                note = "REBOOT"
            elif st["s"] - prev_s > 3:
                note = f"BLOCAGE ({st['s'] - prev_s}s sautés)"
        prev_s = st["s"]
        rows.append((i + 1, st["hz"], st["ui"], note))
    for t, h, u, note in rows:
        print(f"  t+{t:3d}s  hz={h if h is not None else '  --':>5}  ui={u if u is not None else '--':>3} ms  {note}")
    if not hz:
        return name, None
    return name, {
        "hz_min": min(hz), "hz_moy": sum(hz) / len(hz), "hz_max": max(hz),
        "sous_150": sum(1 for h in hz if h < 150),
        "sous_120": sum(1 for h in hz if h < 120),
        "ui_max": max(ui),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duree", type=int, default=20, help="durée des phases (s)")
    ap.add_argument("--court", action="store_true", help="phases courtes (10 s)")
    args = ap.parse_args()
    d = 10 if args.court else args.duree

    resultats = []
    try:
        print(f"=== connexion à {AP_SSID} ===")
        print(connect_ap()[:120])
        st = state()
        print(f"état initial : hz={st['hz']} uptime={st['s']}s\n")

        print(f"=== 1/3 CONTRÔLE ({d} s, sans visage) ===")
        resultats.append(phase("controle", d, face=None))

        print(f"\n=== 2/3 VISAGE + sweep ({d} s, charge maxi) ===")
        resultats.append(phase("visage_sweep", d, face=0))

        print("\n=== 3/3 VISAGE statique (10 s) ===")
        resultats.append(phase("visage_idle", 10, face=4))
    finally:
        print("\n=== restauration WiFi ===")
        print("internet restauré" if restore_wifi() else "!! internet NON restauré !!")

    print("\n" + "=" * 52)
    print("BILAN")
    print("=" * 52)
    verdict = "OK"
    for name, r in resultats:
        if r is None:
            print(f"{name:14s} : AUCUNE DONNÉE")
            verdict = "ÉCHEC"
            continue
        etat = "OK"
        if r["sous_120"]:
            etat = f"ÉCHEC ({r['sous_120']} s < 120 Hz)"
            verdict = "ÉCHEC"
        elif r["sous_150"]:
            etat = f"limite ({r['sous_150']} s < 150 Hz)"
            if verdict == "OK":
                verdict = "LIMITE"
        print(f"{name:14s} : hz min={r['hz_min']:.0f} moy={r['hz_moy']:.0f} max={r['hz_max']:.0f} "
              f"| ui_max={r['ui_max']} ms | {etat}")
    print(f"\nVERDICT : {verdict}")
    return 0 if verdict == "OK" else 1


if __name__ == "__main__":
    sys.exit(main())
