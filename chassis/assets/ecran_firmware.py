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


def style(expr, blink):
    """faceStyle() : (w, h, angle) par expression."""
    st = {"calme": (EYE_W, EYE_H, 6.0), "penche": (EYE_W, 57, 13.0),
          "content": (95, 55, 4.0), "surprise": (100, 76, 3.0)}[expr]
    w, h, ang = st
    return (w, 8, ang) if blink else (w, h, ang)


def ecran_visage(expr="calme", blink=False, gaze=0.0, rouge=False):
    im = Image.new("RGB", (W, H), NOIR)
    d = ImageDraw.Draw(im)
    w, h, ang = style(expr, blink)
    col = ROUGE if rouge else ORANGE
    hb = int(h * (1.0 - LID_TOP))
    r = int(hb * IRIS_R)
    for cx, inn in ((FACE_CX_L, +1), (FACE_CX_R, -1)):
        pts = points_amande(cx, FACE_CY, w, h, ang, inn)
        d.polygon(pts, fill=col)
        if blink:
            continue
        ix = cx + int(max(-18, min(18, gaze)))
        iy = FACE_CY + int(hb * 0.30)
        if expr == "content":
            d.arc([cx - w // 2 + 8, FACE_CY - w // 2 + 18, cx + w // 2 - 8, FACE_CY + w // 2 - 6],
                  90, 270, fill=NOIR, width=6)
            continue
        d.ellipse([ix - r, iy - r, ix + r, iy + r], fill=NOIR)
        d.ellipse([ix - r + 3, iy - r + 1, ix - r + 8, iy - r + 6], fill=BLANC)
    return im


# ── chronologie ───────────────────────────────────────────────────────────
def image(n):
    """n : numéro d'image (1..780)."""
    if n < F_BASCULE:
        # doigt sur le bouton EQUIL. vers l'image 300, puis armé (vert → STOP)
        t = (n - 1) / 30.0
        presse = 1 if 290 <= n <= 302 else -1
        arme = n > 300
        pitch = 1.2 * math.sin(t * 0.7) + (0.25 if arme else 0.0)
        return ecran_manuel(arme, pitch, 7.98 - 0.0004 * n, None, presse,
                            "AUTO" if arme else "MANUEL")
    # bascule rapide (effacement en 4 bandes, comme le firmware)
    reste = F_BASCULE + 4 - n
    if reste > 0:
        im = ecran_manuel(True, 0.3, 7.9, None, -1, "AUTO")
        d = ImageDraw.Draw(im)
        bande = W / 4
        efface = (4 - reste) * bande
        if efface > 0:
            d.rectangle([0, 0, efface, H], fill=NOIR)
        return im
    # visage : regard qui suit le tangage, deux clignements, puis yeux rieurs
    t = (n - F_BASCULE) / 30.0
    blink = (0 < (n % 78) < 3) or (62 < (n % 78) < 65)
    gaze = 9.0 * math.sin(t * 1.1)
    expr = "content" if n > F_BASCULE + 150 else "calme"
    return ecran_visage(expr, blink, gaze)


def main():
    os.makedirs(OUT, exist_ok=True)
    for n in range(1, N_IMAGES + 1):
        image(n).save(os.path.join(OUT, f"ecran_{n:04d}.png"))
    print(f"{N_IMAGES} images d'écran → {OUT}")


if __name__ == "__main__":
    main()
