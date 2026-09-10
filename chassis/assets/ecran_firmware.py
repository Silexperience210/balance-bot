#!/usr/bin/env python3
"""Écran du LilyGo T-Display S3 pour le rendu : 320 × 170, fidèle au firmware.

Reproduit ui.cpp :
  • écran de COMMANDE (manuel) : en-tête BALANCEBOT, bandeau télémétrie
    (PITCH / BAT / OBS / MODE / PIED), croix directionnelle 2×2 + gros bouton
    EQUIL./STOP — zones tactiles et couleurs TFT_eSPI d'origine (g_zones,
    C_BG/C_TEXT/C_ORANGE/C_GREEN/C_RED/C_DARK) ;
  • écran AUTO : le VISAGE — amandes par faceEyePoints() (LID_TOP, EXP_TOP,
    EXP_BOT, IRIS_R, kEyeN=16, miroir x → 319−x pour l'œil droit), iris + reflet,
    expression CONTENT (yeux rieurs) et clignement (h = 8).

Séquence produite : l'écran manuel (le doigt arme l'équilibre → le bouton passe
au vert puis à STOP), bascule, puis le visage qui regarde et cligne.

    python3 chassis/assets/ecran_firmware.py
"""
import math
import os

from PIL import Image, ImageDraw, ImageFont

import demo_timeline as TL

W, H = 320, 170
ICI = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(ICI, "..", "render", "ecran"))
N_IMAGES = 780          # 26 s à 30 fps, comme la cinématique
F_BASCULE = 556         # bascule manuel → visage

# ── couleurs TFT_eSPI (RGB565 → RGB888) ───────────────────────────────────
def c565(v):
    return (((v >> 11) & 0x1F) * 255 // 31, ((v >> 5) & 0x3F) * 255 // 63, (v & 0x1F) * 255 // 31)

NOIR   = c565(0x0000)
BLANC  = c565(0xFFFF)
ORANGE = c565(0xFDA0)      # TFT_ORANGE
VERT   = c565(0x07E0)      # TFT_GREEN
ROUGE  = c565(0xF800)      # TFT_RED
GRIS   = c565(0x7BEF)      # TFT_DARKGREY (verdâtre, comme sur la vraie dalle)

# ── zones tactiles réelles (ui.cpp, g_zones) ──────────────────────────────
ZONES = [(12, 66, 88, 46), (108, 66, 88, 46), (12, 116, 88, 46),
         (108, 116, 88, 46), (208, 66, 100, 96)]

# ── géométrie du visage (ui.cpp) ──────────────────────────────────────────
FACE_CY, EYE_W, EYE_H, EYE_GAP = 84, 104, 68, 118
FACE_CX_L = (W - EYE_GAP - 1) // 2       # 100
FACE_CX_R = W - 1 - FACE_CX_L            # 219
LID_TOP, EXP_TOP, EXP_BOT, IRIS_R = 0.28, 1.00, 0.62, 0.52
KEyeN = 16


def police(taille, gras=False):
    for nom in (("DejaVuSansMono-Bold.ttf" if gras else "DejaVuSansMono.ttf"),
                "DejaVuSans.ttf"):
        for base in ("/usr/share/fonts/truetype/dejavu/", "/usr/share/fonts/TTF/"):
            chemin = os.path.join(base, nom)
            if os.path.exists(chemin):
                return ImageFont.truetype(chemin, taille)
    return ImageFont.load_default()


F1 = police(9)            # ≈ setTextSize(1) : 6×8 px
F2 = police(14, True)     # ≈ setTextSize(2) : 12×16 px
FD = police(11, True)     # chiffres du bandeau
FM = police(13, True)     # EQUIL. / STOP


def texte(d, x, y, s, couleur, f=F1):
    """TFT_eSPI dessine le coin haut-gauche du texte au (x, y) donné."""
    d.text((x, y - 1), s, font=f, fill=couleur)


# ── écran MANUEL ──────────────────────────────────────────────────────────
def ecran_manuel(armé, pitch, batt, obs, bouton_presse, mode="MANUEL"):
    im = Image.new("RGB", (W, H), NOIR)
    d = ImageDraw.Draw(im)

    # en-tête
    texte(d, 6, 2, "BALANCEBOT", ORANGE, F2)
    texte(d, 240, 8, "IDLE" if not armé else "ACTIF", GRIS)
    d.line([(6, 22), (W - 6, 22)], fill=GRIS)

    # télémétrie (positions de drawStatic())
    texte(d, 6, 32, "PITCH", GRIS);   texte(d, 48, 32, f"{pitch:+.1f} deg".replace("+", "+"), BLANC, FD)
    texte(d, 6, 44, "BAT", GRIS);     texte(d, 48, 44, f"{batt:.2f} V", BLANC, FD)
    texte(d, 166, 32, "OBS", GRIS);   texte(d, 206, 32, "--" if obs is None else str(obs), BLANC, FD)
    texte(d, 166, 44, "MODE", GRIS);  texte(d, 206, 44, mode, BLANC, FD)
    texte(d, 166, 54, "PIED", GRIS);  texte(d, 206, 54, "P:+0 deg", BLANC, FD)

    # boutons (drawButton)
    for i, (x, y, w, h) in enumerate(ZONES):
        actif = (i == bouton_presse)
        if i == 4:
            fond = ORANGE if actif else (VERT if armé else GRIS)
        else:
            fond = ORANGE if actif else GRIS
        d.rounded_rectangle([x, y, x + w, y + h], radius=8, fill=fond, outline=BLANC)
        cx, cy = x + w // 2, y + h // 2
        glyphe = BLANC if actif else ORANGE
        if i == 0:
            d.polygon([(cx - 12, cy + 8), (cx + 12, cy + 8), (cx, cy - 12)], fill=glyphe)
        elif i == 1:
            d.polygon([(cx - 12, cy - 8), (cx + 12, cy - 8), (cx, cy + 12)], fill=glyphe)
        elif i == 2:
            d.polygon([(cx + 8, cy - 12), (cx + 8, cy + 12), (cx - 12, cy)], fill=glyphe)
        elif i == 3:
            d.polygon([(cx - 8, cy - 12), (cx - 8, cy + 12), (cx + 12, cy)], fill=glyphe)
        else:
            texte(d, cx - 34, cy - 8, "STOP" if armé else "EQUIL.", BLANC, FM)
    return im


# ── écran AUTO (le visage) ────────────────────────────────────────────────
def points_amande(cx, cy, w, h, ang_deg, inn):
    """Portage de faceEyePoints() — miroir x → 319−x pour l'œil droit."""
    if inn < 0:
        pts = points_amande(W - 1 - cx, cy, w, h, ang_deg, +1)
        return [(W - 1 - x, y) for (x, y) in pts]
    ht, hb = h * LID_TOP, h * (1.0 - LID_TOP)
    a = math.radians(ang_deg)
    ca, sa = math.cos(a), math.sin(a)
    pts = []
    for i in range(KEyeN + 1):                       # paupière haute
        t = -1.0 + 2.0 * i / KEyeN
        x, y = t * w * 0.5, -ht * max(0.0, 1.0 - t * t) ** EXP_TOP
        pts.append((cx + inn * (x * ca - y * sa), cy + (x * sa + y * ca)))
    for i in range(KEyeN + 1):                       # paupière basse
        t = 1.0 - 2.0 * i / KEyeN
        x, y = t * w * 0.5, hb * max(0.0, 1.0 - t * t) ** EXP_BOT
        pts.append((cx + inn * (x * ca - y * sa), cy + (x * sa + y * ca)))
    return pts


def style(expr, blink, clin=False):
    """faceStyle() de ui.cpp : (w, h, angle, fente, débattement du regard)."""
    st = {
        "calme":    (EYE_W, EYE_H, 6.0,  False, 18),
        "penche":   (EYE_W, 57,    13.0, False, 16),
        "mefiant":  (EYE_W, 44,    15.0, True,  6),
        "enerve":   (EYE_W, 27,    26.0, True,  6),
        "surprise": (100,   76,    3.0,  False, 10),
        "content":  (95,    55,    4.0,  False, 0),
        "clin":     (100,   73,    4.0,  False, 10),
    }[expr]
    w, h, ang, slit, gmax = st
    if clin:
        # LE CLIN D'ŒIL : l'œil gauche reste OUVERT (h = 73) et c'est son IRIS
        # qu'on omet (cf. ecran_visage) — sinon les deux yeux se ferment et ça
        # ne ressemble plus à un clin d'œil.
        w, h, ang, slit, gmax = 100, 73, 4.0, False, 10
    elif blink:
        h = 8
    return w, h, ang, slit, gmax


def ecran_visage(expr="calme", blink=False, gaze=0.0, clin=False, rouge=False):
    """Le visage : amandes + iris (fendu si l'expression le demande) + reflet.

    clin=True ferme l'œil GAUCHE (le droit reste ouvert) : c'est le clin d'œil
    final. Le regard est borné par le débattement propre à l'expression, comme
    dans faceIrisGeom().
    """
    im = Image.new("RGB", (W, H), NOIR)
    d = ImageDraw.Draw(im)
    w, h, ang, slit, gmax = style(expr, blink, clin)
    col = ROUGE if rouge else ORANGE
    hb = int(h * (1.0 - LID_TOP))
    r = int(hb * IRIS_R)
    for cx, inn in ((FACE_CX_L, +1), (FACE_CX_R, -1)):
        if expr == "content":
            # YEUX RIEURS : l'amande pleine ne suffit pas (elle donne un arc
            # cassé sur le côté). Un trait épais en ∩ se lit immédiatement
            # comme une joie — c'est le seul cas où on ne remplit pas l'œil.
            # SAUF l'œil du clin d'œil, qui se ferme : sans ça le clin est
            # invisible puisque « content » prime sur l'expression « clin ».
            if clin and inn == +1:
                d.polygon(points_amande(cx, FACE_CY, w, 14, 4.0, inn), fill=col)
                continue
            d.arc([cx - w // 2, FACE_CY - h // 2 - 10, cx + w // 2, FACE_CY + h // 2 + 10],
                  180, 360, fill=col, width=15)
            continue
        pts = points_amande(cx, FACE_CY, w, h, ang, inn)
        d.polygon(pts, fill=col)
        if blink or (clin and inn == +1):     # œil fermé (ou clin d'œil)
            continue
        ix = cx + int(max(-gmax, min(gmax, gaze)))
        iy = FACE_CY + int(hb * 0.30)
        if slit:
            # pupille FENDUE (méfiant, énervé) : étroite et haute
            bw = max(3, r // 4)
            d.ellipse([ix - bw, iy - r, ix + bw, iy + r], fill=NOIR)
        else:
            d.ellipse([ix - r, iy - r, ix + r, iy + r], fill=NOIR)
        d.ellipse([ix - r + 3, iy - r + 1, ix - r + 8, iy - r + 6], fill=BLANC)
    return im


# ── chronologie ───────────────────────────────────────────────────────────
def batterie(n):
    """Tension qui descend lentement (7,98 → 7,66 V sur la démo)."""
    return 7.98 - 0.00041 * n


def image(n):
    """UNE seule scène : la DÉMONSTRATION, visage à l'écran.

    Ce qu'affiche la dalle — expression, clignement, regard, clin d'œil — sort
    de demo_timeline.py, le MÊME fichier qui fait bouger le robot dans le rendu
    3D : les yeux et le mouvement ne peuvent donc pas se désynchroniser.
    """
    expr, blink, gaze, clin = TL.visage(n)
    return ecran_visage(expr, blink, gaze, clin)


def main():
    os.makedirs(OUT, exist_ok=True)
    for n in range(1, N_IMAGES + 1):
        image(n).save(os.path.join(OUT, f"ecran_{n:04d}.png"))
    print(f"{N_IMAGES} images d'écran → {OUT}")


if __name__ == "__main__":
    main()
