#!/usr/bin/env python3
"""Collecte les taps de l'écran pour vérifier le repère tactile (4 coins).

Usage : python3 tools/touch_check.py [durée_s]     (défaut 180 s)

Bascule le WiFi sur l'AP de la carte, interroge /api/touch 4×/s et enregistre
chaque NOUVEAU tap (compteur n) : point brut du CST816 et point transformé.
Écrit tools/touch_log.json au fur et à mesure, restaure le WiFi à la fin.

Protocole : taper les 4 coins dans l'ordre HAUT-GAUCHE, HAUT-DROIT,
BAS-GAUCHE, BAS-DROIT, en levant le doigt entre chaque.
"""
import json
import subprocess
import sys
import time

AP_SSID = "BalanceBot-Tune"
HOME_SSID = "Freebox-66E1B2"
URL = "http://192.168.4.1/api/touch"
SORTIE = "/home/silex/balance-bot/tools/touch_log.json"


def sh(cmd, timeout=40):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    return ((r.stdout or "") + (r.stderr or "")).strip()


def main():
    duree = int(sys.argv[1]) if len(sys.argv) > 1 else 180
    taps = []
    try:
        sh("nmcli dev wifi rescan", 45)
        time.sleep(4)
        sh(f"nmcli --wait 25 dev wifi connect {AP_SSID}", 50)
        time.sleep(3)
        print(f"connecté à {AP_SSID} — écoute {duree} s", flush=True)
        dernier_n = None
        t0 = time.time()
        while time.time() - t0 < duree:
            try:
                d = json.loads(sh(f"curl -s -m 5 {URL}", 12))
            except Exception:
                time.sleep(0.3)
                continue
            if d.get("n") != dernier_n:
                dernier_n = d.get("n")
                if dernier_n:
                    rec = {"t": round(time.time() - t0, 2), "n": dernier_n,
                           "brut": d.get("brut"), "ecran": d.get("ecran"),
                           "mirrorX": d.get("mirrorX"), "mirrorY": d.get("mirrorY")}
                    taps.append(rec)
                    print(f"  tap n={rec['n']:3d}  brut={rec['brut']}  ecran={rec['ecran']}", flush=True)
                    with open(SORTIE, "w") as f:
                        json.dump(taps, f, indent=1)
            time.sleep(0.25)
    finally:
        sh(f"nmcli --wait 30 con up {HOME_SSID}", 60)
        for _ in range(10):
            time.sleep(2)
            c = sh("curl -s -o /dev/null -w '%{http_code}' -m 5 https://api.telegram.org", 10)
            if c[:1] in "23":
                print("WiFi restauré, internet OK", flush=True)
                break
    with open(SORTIE, "w") as f:
        json.dump(taps, f, indent=1)
    print(f"{len(taps)} tap(s) enregistré(s) dans {SORTIE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
