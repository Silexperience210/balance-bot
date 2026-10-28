#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cotes de la chaîne d'entraînement du B-bot — source unique.

Le générateur (``gen_bitcoin_bot.py``), l'export du simulateur et
``chassis/review/chaine_roue.py`` lisent ce module. Les longueurs
dérivées sont calculées ici ; on ne les recopie pas dans les commentaires.

Repère ``u`` : origine sur la face de sortie du servo (face interne de
la paroi latérale), ``u`` croît vers l'extérieur, vers la roue.

Deux descriptions du servo coexistent et sont toutes les deux dégagées :

* datasheet TowerPro déjà codé dans le dépôt : bossage Ø11,8 × 1,5 mm,
  arbre qui dépasse le bossage de 4,5 mm (pointe à 6,0 mm de la face) ;
* capot oblong mesuré sur ``chassis/assets/servo/Servo-SG90.stl``
  (bibliothèque FreeCAD, pas un pied à coulisse) : 4,0 mm de haut,
  largeur 11,8 mm, débord de 2,9 mm vers le bout long du corps.

Le palonnier en croix n'est PAS dans cette CAO. Ses cotes nominales sont
celles déjà choisies par le générateur (20 × 5,2 × 1,8 mm). Ce ne sont
pas des mesures : elles se contrôlent au pied à coulisse (voir NOTES).
"""
import math

# ── Glyphe (repris du générateur : l'enveloppe extérieure n'est pas touchée)
GW, GH = 118.0, 165.0
Z0 = 26.0
SPINE_W = 20.0
STROKE = 19.0
WALL = 2.4
Z_MID = Z0 + GH * 0.50
LOW_ZB = Z0
LOW_ZT = Z_MID + STROKE * 0.50          # 118
AXLE_DZ_CENTER = (LOW_ZT + LOW_ZB) / 2  # 72
AXLE_R_BOWL = (LOW_ZT - LOW_ZB) / 2     # 46

# ── Servo 9 g (datasheet TowerPro SG90 / même boîtier que le FS90R)
SV_L, SV_W, SV_H = 22.8, 12.2, 22.5
SV_FLANGE_Z, SV_FLANGE_T, SV_TAB_SPAN = 15.9, 2.5, 32.2
SV_HOLE_PITCH, SV_SHAFT_OFF = 27.8, 5.9
SV_SHAFT_D, SV_SHAFT_PROJ = 4.8, 4.5
SV_BOSS_D, SV_BOSS_H = 11.8, 1.5
SV_CLR = 1.0
# Capot oblong — MESURÉ sur Servo-SG90.stl (tranches z = 22,5 et z = 26,5).
# Hauteur 4,0 mm au-dessus de la face, largeur ±5,9 mm, du centre d'arbre
# vers le bout court sur un rayon (5,9) et vers le bout long sur 8,8 mm
# (rayon + 2,9). Ce n'est PAS le datasheet : un SG90 ou un FS90R réel peut
# différer. Le trou d'axe dégage cette enveloppe ; le contrôle physique
# reste obligatoire.
CAP_H = 4.0
CAP_OVER = 2.9
CAP_FIT = 0.40                  # jeu autour du capot mesuré (mm)

# ── Roue / pneu
WHEEL_D, WHEEL_W = 80.0, 8.0
GROOVE_D, GROOVE_W = 0.5, 7.0
TIRE_T, TIRE_W = 2.5, 7.0
TIRE_STRETCH = 1.0              # interférence diamétrale (mm), pneu TPU sur la gorge
# Rayon MONTÉ : le fond de gorge plus l'épaisseur du pneu. Le brut non
# étiré fait Ø 83 (rayon 41,5) ; une fois en place le rayon extérieur vaut
# 42,0 si l'épaisseur ne change pas. L'axe du châssis est à cette cote.
WHEEL_R = WHEEL_D / 2 - GROOVE_D + TIRE_T     # 42.0
AXLE_Z = WHEEL_R

# ── Palonnier en croix (cotes de CONCEPTION, à contrôler au pied à coulisse)
HORN_ARM_L = 20.0               # bout à bout
HORN_ARM_W = 5.2
HORN_T = 1.8
HORN_FIT = 0.35                 # jeu par face, largeur et longueur
HORN_AXIAL = 0.40               # jeu axial au-delà des bras

# ── Jeux de la pile axiale (mm, repère u)
# Le palonnier peut s'asseoir sur le bossage datasheet (1,5) OU sur le
# capot de la CAO de référence (4,0). L'empreinte du moyeu couvre les deux
# stations ; la vis centrale du palonnier le plaque sur l'arbre.
HORN_ON_BOSS = SV_BOSS_H + 0.30             # 1.80 dos du palonnier, cas datasheet
HORN_ON_CAP = CAP_H + 0.30                  # 4.30 dos du palonnier, cas capot CAO
SHOULDER_CLEAR = 0.50                       # dos du palonnier (cas bas) / épaulement
HUB_END_CLEAR = 0.40                        # bout du moyeu / épaulement
# Épaulement du lamage Ø palier : enfoncé dans la paroi, assez loin pour
# qu'un palonnier posé sur le bossage de 1,5 mm ne frotte pas.
SHOULDER_U = HORN_ON_BOSS - SHOULDER_CLEAR  # 1.30
HUB_TIP_U = SHOULDER_U + HUB_END_CLEAR      # 1.70
# Fond de l'empreinte en croix : au-delà du palonnier le plus à l'extérieur.
POCKET_FLOOR_U = HORN_ON_CAP + HORN_T + HORN_AXIAL   # 6.50
# Cavité ronde qui admet le capot (rayon maxi mesuré 8,8 mm) quelle que
# soit la rotation de la roue. Le capot ne tourne pas avec la roue.
CAP_REACH = SV_BOSS_D / 2 + CAP_OVER        # 8.80
CAP_CAVITY_D = 2 * (CAP_REACH + CAP_FIT)    # 18.40
CAP_CAVITY_U = HORN_ON_CAP                  # le capot s'arrête sous le palonnier
# Alésage d'arbre borgne (la face ₿ reste fermée : le palonnier est vissé
# sur le servo avant d'enfiler la roue).
SHAFT_TIP_U = SV_BOSS_H + SV_SHAFT_PROJ     # 6.00 datasheet, pire cas (arbre court)
HUB_BORE_D = SV_SHAFT_D + 0.60              # Ø 5,4 — jeu diamétral 0,6
SHAFT_BORE_U = SHAFT_TIP_U + 1.2            # un peu au-delà de la pointe datasheet

# Trou d'axe dans la paroi. Le cylindre centre le bossage rond ; le
# rectangle dégage le capot oblong. Jeu diamétral 0,6 mm sur Ø 11,8 :
# trou horizontal à l'impression (coque couchée), donc pas un alésage
# d'outillage. Le centrage fin du servo, c'est les vis d'oreille + la
# semelle, pas ce trou.
AXLE_HOLE_D = SV_BOSS_D + 0.60              # Ø 12,4
CAP_HALF_Y = SV_BOSS_D / 2 + CAP_FIT        # ±6,3 selon Y (largeur)
CAP_Z_SHORT = SV_BOSS_D / 2 + CAP_FIT       # 6,3 vers le bout court (vers le bas)
CAP_Z_LONG = SV_BOSS_D / 2 + CAP_OVER + CAP_FIT  # 9,2 vers le bout long (vers le haut)

# ── Palier et moyeu
HUB_D = 24.0
BEAR_CLEAR = 0.50               # jeu diamétral moyeu / alésage
BEAR_D = HUB_D + BEAR_CLEAR     # Ø 24,5
BEAR_WALL = 1.0
WHEEL_GAP = 1.0                 # face interne du disque / bout réel du tube
TUBE_OVER = 0.50                # le solide du tube dépasse le plan nominal (booléen)
BORE_OVER = 2.0                 # l'alésage dépasse le bout du tube (pas de voile)

# Allègement : 6 bras, peau externe conservée (gravure ₿ intacte).
SPOKE_N = 6
SPOKE_DEG = 16.0                # largeur angulaire d'un bras (la poche fait 60° − 16°)
SPOKE_R0 = 14.0                 # les poches commencent hors du moyeu
SPOKE_R1 = 36.0                 # et s'arrêtent avant le fond de gorge (r = 39,5)
SPOKE_Z0 = 1.8                  # peau sous la gravure (1,0 mm) : il reste 0,8 mm

# Vis M3 des coques : avant-trou d'autotaraudage. Ø 2,5 = ~83 % du Ø nominal,
# valeur usuelle PETG (l'ancien Ø 2,6 reste montable ; 2,5 mord mieux).
M3_PILOT_D = 2.5

# Semelle sous le servo. sg90_model.SG_TAB = 0,5 mm étend le fond du corps
# dans le test d'intersection : ce 0,5 n'est PAS une cote au pied à coulisse,
# c'est une saillie d'ingénierie pour la bavure de moulage. On passe 0,2 mm
# sous cette enveloppe, donc 0,7 mm sous le corps nominal du datasheet.
# Les vis d'oreille restent le centrage ; la semelle empêche la chute dans
# le jeu de baie (SV_CLR = 1 mm) quand l'oreille basse de la panse, hors
# peau, ne peut pas être vissée.
SHELF_DROP = 0.70

PETG_G_PER_CM3 = 1.27
TPU_G_PER_CM3 = 1.20


def x_wall_panse(z=AXLE_Z):
    """Abscisse de la peau externe de la panse basse, avant le miroir x → GW−x."""
    dz = z - AXLE_DZ_CENTER
    return (GW - AXLE_R_BOWL) + math.sqrt(AXLE_R_BOWL ** 2 - dz ** 2)


X_WALL_R = x_wall_panse()
# Longueur de tube AU-DELÀ de la peau si les deux côtés étaient égaux.
# C'est la référence qui figeait le débord panse à x = GW + WHEEL_GAP, et
# donc la largeur de la boîte du corps. On ne la réécrit pas : le
# recentrage ajoute et retire la même longueur, la somme (et la boîte)
# reste celle-ci.
TUBE_LEN_SYM = (GW + WHEEL_GAP) - X_WALL_R


def _delta_recentrage():
    """Décalage des peaux vers le spine, à compenser par les tubes.

    Les peaux ne bougent pas (panse ronde). Le milieu des peaux, avant
    miroir, est à ``X_WALL_R / 2``. Le centre du glyphe est ``GW / 2``.
    Allonger la panse de ``delta`` et raccourcir le spine de ``delta``
    déplace le milieu des roues de ``delta`` sans changer leur écart.
    """
    dec = X_WALL_R / 2.0 - GW / 2.0
    return -dec


DELTA_RECENTRAGE = _delta_recentrage()
# APPLIQUÉ. Deux STL : le moyeu suit le tube, l'empreinte (repère u depuis
# la face servo) ne change pas.
TUBE_PANSE = TUBE_LEN_SYM + DELTA_RECENTRAGE
TUBE_SPINE = TUBE_LEN_SYM - DELTA_RECENTRAGE


def pile(tube_len):
    """Cotes dérivées d'un côté. ``u`` depuis la face servo."""
    u_skin = WALL
    u_mouth = u_skin + tube_len + TUBE_OVER          # bout RÉEL du tube
    u_disk = u_mouth + WHEEL_GAP                     # face interne du disque
    hub_l = u_disk - HUB_TIP_U
    bore_depth = u_mouth - SHOULDER_U                # du bout du tube à l'épaulement
    engagement = u_mouth - HUB_TIP_U                 # longueur de moyeu dans le palier
    return dict(
        tube_len=tube_len,
        u_skin=u_skin, u_mouth=u_mouth, u_disk=u_disk,
        hub_l=hub_l, bore_depth=bore_depth, engagement=engagement,
        pocket_depth=POCKET_FLOOR_U - HUB_TIP_U,
        cap_cavity_depth=CAP_CAVITY_U - HUB_TIP_U,
        shaft_bore_depth=SHAFT_BORE_U - HUB_TIP_U,
    )


PILE_PANSE = pile(TUBE_PANSE)
PILE_SPINE = pile(TUBE_SPINE)
HUB_PANSE = PILE_PANSE["hub_l"]
HUB_SPINE = PILE_SPINE["hub_l"]


def _verifier_pile():
    """Échoue tout de suite si une cote dérivée se contredit."""
    erreurs = []
    if not (0.8 < SHOULDER_U < WALL):
        erreurs.append("épaulement hors de la paroi (u=%.2f, paroi %.2f)" % (SHOULDER_U, WALL))
    jeu = HUB_TIP_U - SHOULDER_U
    if jeu < 0.30:
        erreurs.append("jeu bout de moyeu / épaulement < 0,30 mm")
    if abs(jeu - HUB_END_CLEAR) > 1e-9:
        erreurs.append("jeu d'épaulement n'est plus %.2f mm" % HUB_END_CLEAR)
    if HORN_ON_BOSS - SHOULDER_U < 0.40:
        erreurs.append("palonnier datasheet trop près de l'épaulement")
    if HUB_TIP_U > CAP_H + 0.15:
        erreurs.append("le moyeu rencontre le capot de 4 mm")
    if CAP_REACH + 0.2 > BEAR_D / 2:
        erreurs.append("le capot ne passe pas dans l'alésage Ø%.1f" % BEAR_D)
    if POCKET_FLOOR_U < HORN_ON_CAP + HORN_T:
        erreurs.append("empreinte trop courte pour le palonnier sur capot")
    if HORN_ON_BOSS + 0.2 < HUB_TIP_U:
        erreurs.append("palonnier datasheet sort du moyeu")
    if SHAFT_TIP_U - HORN_ON_CAP < 1.5:
        erreurs.append("engagement d'arbre < 1,5 mm dans le cas capot")
    rayon_coin = math.hypot(CAP_Z_LONG, CAP_HALF_Y)
    if rayon_coin > BEAR_D / 2 - 0.4:
        erreurs.append("coin du capot hors de l'alésage (r=%.2f)" % rayon_coin)
    if TUBE_SPINE < 5.0 or TUBE_PANSE < TUBE_SPINE:
        erreurs.append("tube spine trop court ou plus long que la panse")
    # La somme des tubes est celle du montage symétrique : la voie et la
    # largeur de boîte des coques ne bougent pas.
    if abs((TUBE_PANSE + TUBE_SPINE) - 2 * TUBE_LEN_SYM) > 1e-9:
        erreurs.append("la somme des tubes a changé")
    for nom, p in (("panse", PILE_PANSE), ("spine", PILE_SPINE)):
        if p["hub_l"] <= p["pocket_depth"] + 2.5:
            erreurs.append("%s : le moyeu ne couvre pas l'empreinte (%.2f ≤ %.2f)"
                           % (nom, p["hub_l"], p["pocket_depth"]))
        if p["hub_l"] <= p["shaft_bore_depth"] + 2.0:
            erreurs.append("%s : l'alésage d'arbre mange le disque" % nom)
        if p["engagement"] <= p["pocket_depth"] + 2.0:
            erreurs.append("%s : l'empreinte dépasse la bouche du tube" % nom)
        if p["bore_depth"] < p["engagement"] + HUB_END_CLEAR - 1e-6:
            erreurs.append("%s : alésage plus court que le moyeu" % nom)
        if p["engagement"] > p["bore_depth"] - 0.2:
            erreurs.append("%s : le moyeu talonne l'épaulement" % nom)
        if abs(p["pocket_depth"] - (POCKET_FLOOR_U - HUB_TIP_U)) > 1e-9:
            erreurs.append("%s : empreinte dérivée" % nom)
    if abs(PILE_PANSE["pocket_depth"] - PILE_SPINE["pocket_depth"]) > 1e-9:
        erreurs.append("les deux empreintes ne font plus la même profondeur")
    if erreurs:
        raise SystemExit("cotes.py incohérent :\n  - " + "\n  - ".join(erreurs))


def _faces(tube_panse, tube_spine):
    """Faces externes après miroir pour deux longueurs de tube."""
    def hub(tube):
        return pile(tube)["hub_l"]
    long_p = WHEEL_W + hub(tube_panse)
    long_s = WHEEL_W + hub(tube_spine)
    tip_panse = (X_WALL_R - WALL) + HUB_TIP_U
    tip_spine = WALL - HUB_TIP_U
    tip_g = GW - tip_panse
    tip_d = GW - tip_spine
    face_g = tip_g - long_p
    face_d = tip_d + long_s
    return face_g, face_d, (face_g + face_d) / 2.0, face_d - face_g


# Entraxe des faces externes du montage symétrique (avant recentrage).
# Le recentrage doit le reproduire au nanomètre : c'est la voie des pneus.
_g0, _d0, _m0, ENTRAXE_SYM_MM = _faces(TUBE_LEN_SYM, TUBE_LEN_SYM)

_verifier_pile()


def roues_apres_miroir():
    """Faces externes des roues après le miroir ``x → GW − x``.

    Gauche (x petit) = panse, moyeu long. Droite (x grand) = spine, moyeu
    court. ₿ lu de face. Retourne ``(x_gauche, x_droite, x_milieu, entraxe)``.
    """
    return _faces(TUBE_PANSE, TUBE_SPINE)


def epaulements_apres_miroir():
    """x de l'épaulement (fond de l'alésage Ø palier) après miroir.

    Retourne ``(panse, spine)``. La panse est à gauche (x petit).
    Les épaulements ne bougent pas avec le recentrage : ils sont dans la paroi.
    """
    sh_panse = (X_WALL_R - WALL) + SHOULDER_U
    sh_spine = WALL - SHOULDER_U
    return GW - sh_panse, GW - sh_spine


def bouches_tube_apres_miroir():
    """x du bout réel du tube (TUBE_OVER compris) après miroir. ``(panse, spine)``."""
    bouche_panse = X_WALL_R + TUBE_PANSE + TUBE_OVER
    bouche_spine = -(TUBE_SPINE + TUBE_OVER)
    return GW - bouche_panse, GW - bouche_spine


def milieu_axes():
    """Milieu des deux PEAUX à hauteur d'axe, avant miroir, et l'écart au
    centre du glyphe (GW/2). Négatif = décalé vers le spine.

    Les peaux ne bougent pas quand on recentre : ce n'est pas le milieu
    des roues. Voir ``milieu_roues``.
    """
    milieu = X_WALL_R / 2.0
    return milieu, milieu - GW / 2.0


def milieu_roues():
    """Milieu des faces externes après miroir, et l'écart à GW/2.

    Après recentrage l'écart est nul. L'entraxe, lui, reste
    ``ENTRAXE_SYM_MM``.
    """
    _g, _d, milieu, _e = roues_apres_miroir()
    return milieu, milieu - GW / 2.0


def ecran_viewer():
    """Centre de la dalle dans le repère Three.js (m), origine = axe des roues.

    Même conversion que ``exporter_parts_web.py`` : (y, z−axe, x−milieu).
    """
    lcx = (SPINE_W + GW - STROKE) / 2.0     # 59,5
    lcz = (LOW_ZB + LOW_ZT) / 2.0           # 72
    y_dalle = 18.0                          # plan de la dalle dans le viewer (historique)
    _g, _d, milieu, _e = roues_apres_miroir()
    return (y_dalle / 1000.0,
            (lcz - AXLE_Z) / 1000.0,
            (lcx - milieu) / 1000.0)


def proposition_recentrage():
    """Recentrage APPLIQUÉ : milieu des roues sur le centre du glyphe.

    Les peaux ne bougent pas. Le tube et le moyeu de la panse sont plus
    longs de ``delta``, ceux du spine plus courts de la même quantité.
    ``applique`` est True : ``gen_bitcoin_bot.py`` lit ``TUBE_PANSE`` et
    ``TUBE_SPINE``. Deux STL, ``coin_wheel_panse.stl`` et
    ``coin_wheel_spine.stl``.
    """
    _mil, dec_peaux = milieu_axes()
    _mr, dec_roues = milieu_roues()
    _g, _d, _m, ent = roues_apres_miroir()
    return dict(
        applique=True,
        delta_mm=DELTA_RECENTRAGE,
        tube_panse_mm=TUBE_PANSE,
        tube_spine_mm=TUBE_SPINE,
        moyeu_panse_mm=HUB_PANSE,
        moyeu_spine_mm=HUB_SPINE,
        engagement_panse_mm=PILE_PANSE["engagement"],
        engagement_spine_mm=PILE_SPINE["engagement"],
        jeu_epaulement_mm=HUB_TIP_U - SHOULDER_U,
        empreinte_mm=PILE_PANSE["pocket_depth"],
        entraxe_faces_mm=ent,
        entraxe_symetrique_mm=ENTRAXE_SYM_MM,
        ecart_peaux_mm=dec_peaux,
        ecart_roues_mm=dec_roues,
    )


def _verifier_recentrage():
    p = proposition_recentrage()
    erreurs = []
    if not p["applique"]:
        erreurs.append("le recentrage doit être appliqué")
    if abs(p["ecart_roues_mm"]) > 1e-6:
        erreurs.append("milieu des roues encore décalé de %+.4f mm" % p["ecart_roues_mm"])
    if abs(p["entraxe_faces_mm"] - p["entraxe_symetrique_mm"]) > 1e-6:
        erreurs.append("la voie des faces a bougé (%.4f → %.4f)"
                       % (p["entraxe_symetrique_mm"], p["entraxe_faces_mm"]))
    if abs(p["entraxe_faces_mm"] - 150.1288) > 0.02:
        # 150,13 mm : entraxe mesuré avant recentrage (tubes égaux).
        # La tolérance est celle de l'arrondi d'affichage, pas un jeu.
        erreurs.append("entraxe %.4f s'éloigne des 150,13 mm d'avant recentrage"
                       % p["entraxe_faces_mm"])
    if p["ecart_peaux_mm"] > -5.0:
        erreurs.append("les peaux ont bougé (écart %+.2f)" % p["ecart_peaux_mm"])
    if erreurs:
        raise SystemExit("recentrage incohérent :\n  - " + "\n  - ".join(erreurs))


_verifier_recentrage()


def resume():
    """Texte court pour les journaux de génération."""
    g, d, mid, ent = roues_apres_miroir()
    _mil, dec_roues = milieu_roues()
    return (
        "axe z=%.2f  tubes panse/spine %.2f/%.2f  moyeux %.2f/%.2f  "
        "jeu épaulement=%.2f  empreinte=%.2f  "
        "engagement panse/spine %.2f/%.2f  "
        "faces x=%.2f..%.2f milieu=%.2f (écart glyphe %+.3f) entraxe=%.2f"
        % (AXLE_Z, TUBE_PANSE, TUBE_SPINE, HUB_PANSE, HUB_SPINE,
           HUB_TIP_U - SHOULDER_U, PILE_PANSE["pocket_depth"],
           PILE_PANSE["engagement"], PILE_SPINE["engagement"],
           g, d, mid, dec_roues, ent)
    )


if __name__ == "__main__":
    print(resume())
    for nom, p in (("panse", PILE_PANSE), ("spine", PILE_SPINE)):
        print("  -- %s" % nom)
        for k, v in sorted(p.items()):
            print("    %-20s %8.3f" % (k, v))
    print("  épaulement u       %8.3f" % SHOULDER_U)
    print("  bout moyeu u       %8.3f" % HUB_TIP_U)
    print("  palonnier boss u   %8.3f" % HORN_ON_BOSS)
    print("  palonnier capot u  %8.3f" % HORN_ON_CAP)
    print("  fond empreinte u   %8.3f" % POCKET_FLOOR_U)
    print("  engagement arbre   %8.3f (cas capot, datasheet 6,0 mm)" % (SHAFT_TIP_U - HORN_ON_CAP))
    print("  dalle viewer       %s" % (tuple(round(x, 6) for x in ecran_viewer()),))
    print("  entraxe symétrique %8.4f mm (doit égaler l'entraxe appliqué)" % ENTRAXE_SYM_MM)
    p = proposition_recentrage()
    print("  recentrage         APPLIQUÉ  delta=%+.2f mm" % p["delta_mm"])
