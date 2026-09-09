#!/usr/bin/env python3
"""Vérification tactile en 4 touches — mesure le repère du CST816 sans ambiguïté.

Protocole : la carte en mode MANUEL (écran de commande). On affiche en continu
les champs tactiles publiés par /api/state (bruts et transformés), et l'opérateur
tape un coin de l'écran à la fois, dans cet ordre :
    1. coin HAUT-GAUCHE   2. HAUT-DROIT   3. BAS-GAUCHE   4. BAS-DROIT
Le script conserve la dernière valeur stable de chaque touche pour bâtir la table.

    python3 tools/touch_check.py --duree 60

Le WiFi de la machine est restauré à la fin (bloc finally).
"""
import argparse
import json
import re
import subprocess
import sys
import time

AP_SSID = "BalanceBot-Tune"
AP_URL = "http://192.168.4.1"
HOME_SSID = "Freebox-66E1B2"

# champs tactiles acceptés (l'instrumentation peut en publier plusieurs)
CLE_RE = re.compile(r"(touch|touchX|touchY|raw|tx|ty|px|py)", re.I)


def sh(cmd, timeout=40):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    return ((r.stdout or "") + (r.stderr or "")).strip()


def connect_ap():
    sh("nmcli dev wifi rescan", 45)
    time.sleep(4)
    sh(f"nmcli --wait 25 dev wifi connect {AP_SSID}", 50)
    time.sleep(3)


def restore_wifi():
    sh(f"nmcli --wait 30 con up {HOME_SSID}", 60)
    for _ in range(8):
        time.sleep(2)
        c = sh("curl -s -o /dev/null -w '%{http_code}' -m 5 https://api.telegram.org", 10)
        if c[:1] in "23":
            return True
    return False


def state():
    return json.loads(sh(f"curl -s -m 6 {AP_URL}/api/state", 15))


def champs_tactiles(st):
    return {k: v for k, v in st.items() if CLE_RE.search(k)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duree", type=int, default=60)
    args = ap.parse_args()

    touches = []          # (instant, dict)
    try:
        print(f"=== connexion à {AP_SSID} ===")
        connect_ap()
        st = state()
        print("champs disponibles :", list(st.keys()))
        t = champs_tactiles(st)
        if not t:
            print("\n!! aucun champ tactile dans /api/state — l'instrumentation n'est pas encore flashée.")
            print("   Champs présents :", ", ".join(st.keys()))
            return 2
        print("champs tactiles :", t)
        print(f"\nTape un coin puis reste immobile 2 s. Ordre : HAUT-GAUCHE, HAUT-DROIT, BAS-GAUCHE, BAS-DROIT.")
        print(f"Écoute {args.duree} s...\n")
        dernier = None
        t0 = time.time()
        while time.time() - t0 < args.duree:
            try:
                st = state()
            except Exception:
                time.sleep(0.4)
                continue
            t = champs_tactiles(st)
            if t and t != dernier:
                touches.append((round(time.time() - t0, 1), t))
                print(f"  t+{touches[-1][0]:5.1f}s  {t}")
                dernier = t
            time.sleep(0.25)
    finally:
        print("\n=== restauration WiFi ===")
        print("internet restauré" if restore_wifi() else "!! internet NON restauré !!")

    print("\n" + "=" * 56)
    print("SÉQUENCE DES TOUCHES (à confronter aux 4 coins tapés)")
    print("=" * 56)
    for t, vals in touches:
        print(f"  t+{t:5.1f}s  {vals}")
    print(f"\n{len(touches)} valeurs distinctes relevées.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
