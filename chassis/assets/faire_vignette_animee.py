#!/usr/bin/env python3
"""Fabrique la vignette ANIMÉE du README depuis la vidéo de rendu du projet.

Un README GitHub ne sait pas lire un mp4 en ligne : une image animée (GIF) s'affiche
directement, c'est ce qui donne l'aperçu « vidéo » sans que le lecteur ait à cliquer.

Usage : python3 faire_vignette_animee.py [largeur] [pas] [duree_ms] [couleurs]
Sortie : docs/apercu-anime.gif  (et affiche le poids obtenu)
"""
import sys
from pathlib import Path

import av
from PIL import Image

RACINE = Path("/home/silex/balance-bot")
SOURCE = RACINE / "chassis/render/cinematique.mp4"
SORTIE = RACINE / "docs/apercu-anime.gif"

largeur = int(sys.argv[1]) if len(sys.argv) > 1 else 640
pas = int(sys.argv[2]) if len(sys.argv) > 2 else 6
duree = int(sys.argv[3]) if len(sys.argv) > 3 else 200
couleurs = int(sys.argv[4]) if len(sys.argv) > 4 else 96

SORTIE.parent.mkdir(parents=True, exist_ok=True)

conteneur = av.open(str(SOURCE))
flux = conteneur.streams.video[0]
hauteur = int(round(largeur * flux.height / flux.width))

images = []
for i, trame in enumerate(conteneur.decode(flux)):
    if i % pas:
        continue
    vue = trame.to_image().convert("RGB").resize((largeur, hauteur), Image.Resampling.LANCZOS)
    images.append(vue.quantize(colors=couleurs, method=Image.Quantize.MEDIANCUT))
conteneur.close()

images[0].save(
    SORTIE,
    save_all=True,
    append_images=images[1:],
    duration=duree,
    loop=0,
    optimize=True,
)

poids = SORTIE.stat().st_size / 1048576
print(f"  {len(images)} images · {largeur}x{hauteur} · {1000/duree:.1f} i/s")
print(f"  {SORTIE}  →  {poids:.2f} Mo")
print("  " + ("TOUT BON pour un README (< 5 Mo)" if poids < 5 else "TROP LOURD : réduis largeur/pas/couleurs"))
