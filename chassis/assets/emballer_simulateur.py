#!/usr/bin/env python3
"""Génère une version MONO-FICHIER du simulateur web BalanceBot : tout est
embarqué (Three.js, OrbitControls, moteur, pièces STL, viewer) → un seul .html
ouvrable partout (téléphone, double-clic, sans serveur, sans réseau).

Usage : python3 chassis/assets/emballer_simulateur.py
Sortie : sim/web/simulateur-balancebot.html
"""
import os
import re

D = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "sim", "web")
OUT = os.path.join(D, "simulateur-balancebot.html")

ORDRE = ["lib/three.min.js", "lib/OrbitControls.js",
         "engine.js", "ultrason.js", "parts.js", "ui.js"]

with open(os.path.join(D, "index.html"), encoding="utf-8") as fh:
    html = fh.read()

total = 0
for src in ORDRE:
    with open(os.path.join(D, src), encoding="utf-8") as fh:
        code = fh.read()
    total += len(code)
    # Un </script> littéral dans le code casserait la balise : on l'échappe.
    code = code.replace("</script>", "<\\/script>")
    motif = re.compile(r'<script\s+src="' + re.escape(src) + r'"\s*>\s*</script>')
    html, n = motif.subn(
        lambda m, c=code: "<script>\n" + c + "\n</script>", html)
    print(f"  {src:28s} {len(code):>9,} car.  {'inliné' if n else 'NON TROUVÉ !'}")

with open(OUT, "w", encoding="utf-8") as fh:
    fh.write(html)

print(f"\nÉCRIT → {OUT}  ({os.path.getsize(OUT):,} octets, {total:,} car. de JS embarqués)")
