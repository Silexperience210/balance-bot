#!/usr/bin/env python3
"""Simulateur 1D BalanceBot — pendule inversé sur pieds en arc.

Modélise le contrôleur RÉEL de balance.cpp : PID d'équilibre **+ cascade de
recentrage** (lot 2c), pieds en arc sur servos de position, physique du
roulement par les équations de Lagrange (masse ponctuelle, arc sans masse,
angle de servo imposé).

RÈGLE D'OR : mêmes boucles, mêmes constantes, mêmes SIGNES que balance.cpp.
Deux écarts de signe (boucle interne de la cascade, soft clamp) ont vécu ici
8 jours sans être vus (REVIEW_CLAUDE.md M1, M2) : toute modification de
balance.cpp se porte ici le même jour, et réciproquement.

Usage :
  python3 balancebot_sim.py                 # jeux de gains par défaut, PID+cascade
  python3 balancebot_sim.py 25 500 0.5      # Kp Ki Kd
  python3 balancebot_sim.py 25 500 0.5 3    # Kp Ki Kd k_out (= kOutToFootDegS)
  python3 balancebot_sim.py --no-cascade    # comparaison sans la cascade
  python3 balancebot_sim.py --sweep         # balayage Kp/Ki/Kd/k_out (tient les 6 scénarios ?)

── Physique (modèle) ────────────────────────────────────────────────────────
MÉCANIQUE RÉELLE = ROUES Ø80 + pneus Ø83 entraînées par des servos **360°
continus** (FS90R) : la roue tourne LIBREMENT (pas de butée). Pendule inversé :
masse ponctuelle m à la hauteur h au-dessus de l'axe, ROUE de rayon R (rayon de
roulage avec le pneu = 41,5 mm) centrée sur l'axe, qui roule sans glisser. La
position est l'angle φ (relatif au corps), IMPOSÉ par le servo ; la rotation
ABSOLUE de la roue vaut (θ + φ), donc x_axe = R·(θ + φ). Lagrange avec
T = ½·m·(ẋ² + ẏ²) du CoM et V = m·g·(R + h·cosθ), φ(t) donné :

    θ̈ · (R² + 2·R·h·cosθ + h²) = g·h·sinθ − φ̈ · R·(R + h·cosθ) + R·h·sinθ · θ̇²

Aux petits angles : θ̈ = g·h/(R+h)²·θ − R/(R+h)·φ̈, pôle instable
√(g·h)/(R+h) = 7,87 rad/s. L'ancienne équation « chariot-pendule »
θ̈ = [(g/h)·sinθ − (R/h)·φ̈·cosθ]/(1 + (R/h)·cosθ) oubliait le couple de
réaction du servo sur le corps (le servo est vissé sur le corps) et le terme
centrifuge : même autorité de commande, mais gravité g/(R+h) = 87,2 s⁻² au
lieu de 62,0 (pôle 9,34 rad/s), ~19 % trop pessimiste (REVIEW_CLAUDE.md M5).

Servo : suivi de la consigne de position en 1er ordre (τ = 50 ms) borné à
250 °/s. Course de pied bornée à ±45° (butée dure de feet.cpp).

── Ce que le modèle NE contient PAS (et qui dominera le réel) ───────────────
· la trame PWM 50 Hz du SG90 : la consigne n'est prise qu'une fois toutes les
  20 ms (échantillonneur-bloqueur, 0-20 ms de latence) — ici le servo suit
  une consigne rafraîchie à 200 Hz ;
· la mort-zone du SG90 (~5-10 µs ≈ 0,5-1° ≈ 0,3-0,6 mm de base) : elle
  produira un cycle limite de quelques degrés que ce sim ne peut pas prédire ;
· aucune borne d'ACCÉLÉRATION du servo (φ̈ impulsionnel au premier pas,
  +800 °/s² dans les traces) — seule sa vitesse est bornée ;
· ni la friction (conservateur), ni la 3D, ni la masse des pieds ;
· le retard de mesure tau_f = 25 ms (ctrl()) est un forfait « retard total de
  boucle » NON justifié finement — le verdict sur les gains embarqués en
  dépend (REVIEW_CLAUDE.md §2 #9).
Le réglage réel reste indispensable.

​── État de validation (mesuré, 17/09/2026 — MÉCANIQUE ROUE, R = 41,5 mm) ───
MODE = "roue" (le robot réel) : ni butée ±45°, ni soft clamp, ni panic.
Le jeu embarqué Kp25/Ki500/Kd0.5 (k_out = 1, cascade Kv = 3) tient toujours
**0/6** — chute θ en 0,42-0,55 s : la cascade à Kv = 3 reste un passif.
En revanche, avec Kv = 0 le robot TIENT dès k_out = 1 : le jeu
Kp25/Ki350/Kd1/k_out=3/Kv=0 tient **5/6** (seule la tape 1,2 rad/s le fait
tomber, à 3,6 s) — les roues libres changent tout par rapport à l'arc.
MODE = "arc" (ancienne mécanique R = 32,5 mm, butée ±45°) reste disponible
pour comparaison : c'est lui qui donnait 2/6 et des « panic φ ».
Historique : la validation d'origine (09/09) reposait sur un modèle 57× trop
optimiste (facteur °/rad) et SANS cascade (commit 19535f7). Utiliser ce script
pour CHERCHER des gains, pas pour certifier ceux qui sont embarqués.
"""
import math, random, sys

# ── Paramètres physiques ─────────────────────────────────────────────
G, R, H = 9.81, 0.0415, 0.080       # gravité, rayon de ROULAGE (pneu Ø83 → 41,5 mm), hauteur CoM (m)
TAU_SERVO, VMAX_SERVO = 0.05, 250.0  # servo : 1er ordre (s), vitesse max (°/s)
DT = 1.0 / 200                       # pas de contrôle = 200 Hz (comme le code)

# ── Constantes du contrôleur (copiées de balance.cpp) ────────────────
OUT_MAX = 90.0
INTEGRAL_MAX = OUT_MAX               # kIntegralMax = kOutMax (M10 : I est la raideur)
DEADBAND = 0.0                       # kErrDeadbandDeg = 0 (M3 : la bande + I = cliquet)
FOOT_HARD, FOOT_MARGIN, FOOT_TAPER, FALL_ANGLE = 45.0, 9.0, 10.0, 45.0
# ── MÉCANIQUE ─────────────────────────────────────────────────────────
# Le robot RÉEL = ROUES Ø80 + pneus Ø83 entraînées par des servos **360°
# continus** (FS90R) : la roue tourne LIBREMENT — il n'y a donc NI butée ±45°,
# NI soft clamp de butée, NI « panic ». Ces garde-fous modélisaient l'ARC
# (ancienne mécanique, R = 32,5 mm) ; ils restent disponibles pour comparaison.
MODE = "roue"            # "roue" = le robot réel | "arc" = ancienne mécanique
# kOutToFootDegS n'est plus une constante : paramètre k_out de Sim (M11),
# réglable au banc web (1-3) et balayé par --sweep.
RECENTER_PERIOD = 0.100              # 10 Hz
RECENTER_VEL_MAX, RECENTER_REF_MAX, RECENTER_SLEW = 20.0, 6.0, 3.0
FOOT_VEL_TAU, FOOT_PANIC = 0.08, 35.0
# ── Consignes de DÉPLACEMENT (balance.cpp l.178-183, l.673-692, l.751-758) ──
# Avancer = incliner la consigne d'angle (kTiltPerCmd) ; tourner = différentiel
# de vitesse entre les deux roues (kTurnPerCmd). Les deux consignes UI
# (cmdForward / cmdTurn, −100..100) sont LISSÉES à kCmdSlewPerS. L'évitement
# d'obstacle (head.cpp → g_state.avoidFwdMax / avoidTurn) n'entre QUE par ici,
# AVANT le lissage : un plafond sur la marche avant (négatif = recul imposé) et
# un pivot imposé si l'UI ne tourne pas. Jamais sur le PID ni sur les roues.
SETPOINT_DEG = 0.0                   # kSetpointDeg
TILT_PER_CMD = 0.06                  # kTiltPerCmd  : ° de consigne par unité de cmdForward
TURN_PER_CMD = 0.30                  # kTurnPerCmd  : unités de sortie par unité de cmdTurn
CMD_SLEW_PER_S = 200.0               # kCmdSlewPerS : lissage des consignes (unités/s)
# Voie des roues (m), plans médians des pneus : faces externes des roues à
# 146,87 mm (chassis/assets/exporter_parts_web.py TRACK), pneu centré 4 mm en
# dedans → 138,87 mm. Sert UNIQUEMENT à la cinématique du lacet ci-dessous —
# le firmware n'a ni cap ni odométrie (head.cpp l.10-15), le lacet est une
# grandeur du SIMULATEUR (pour voir le pivot), pas une grandeur du robot.
TRACK = 0.13887


def slew(current, target, max_step):
    """balance.cpp slew() : rampe bornée vers la cible."""
    delta = target - current
    if delta > max_step:
        return current + max_step
    if delta < -max_step:
        return current - max_step
    return target


class Sim:
    def __init__(self, kp, ki, kd, cascade=True, kp_phi=0.8, kv=3.0, k_out=1.0):
        self.kp, self.ki, self.kd = kp, ki, kd
        self.cascade, self.kp_phi, self.kv = cascade, kp_phi, kv
        self.k_out = k_out               # kOutToFootDegS : °/s de pied par unité de sortie
        # ENTRÉES de déplacement (ce que g_state porte dans le firmware) — posées
        # de l'extérieur (UI, tête), conservées par reset() comme les gains :
        self.cmd_forward = 0             # g_state.cmdForward (−100..100)
        self.cmd_turn = 0                # g_state.cmdTurn    (−100..100)
        self.avoid_fwd_max = 100         # g_state.avoidFwdMax (100 libre · 40 ralenti · 0 stop · <0 recul)
        self.avoid_turn = 0              # g_state.avoidTurn   (pivot imposé si l'UI ne tourne pas)
        self.obstacle_warn = False       # g_state.obstacleWarn (< US_STOP_CM)
        self.reset()

    def reset(self):
        self.theta = self.dtheta = self.phi = self.phi_cmd = 0.0
        self.integ = self.prev_dphi = self.t = 0.0
        self.pitch_f = self.rate_f = 0.0
        self.recenter_vel = self.foot_vel_filt = 0.0
        self.recenter_last = 0.0
        self.panicked = False
        # couche déplacement : consignes lissées (halt() les vide aussi), voie
        # différentielle et pose au sol
        self.fwd_smooth = self.turn_smooth = 0.0   # s_fwdSmooth / s_turnSmooth
        self.phi_diff = self.phi_diff_cmd = 0.0    # (φ_G − φ_D)/2 : réel / commandé (°)
        self.psi = 0.0                             # lacet (rad, + = vers la droite)
        self.pos_x = self.pos_z = 0.0              # axe des roues au sol (m)

    # ── PID + cascade, à l'identique de balance.cpp ──────────────────
    def ctrl(self, noise, t):
        # Retard TOTAL de boucle forfaitaire (DLPF 42 Hz ≈ 5 ms + échantillonnage
        # 2,5 ms + trame servo 50 Hz 0-20 ms), appliqué au pitch ET au gyro. Le
        # filtre complémentaire, lui, n'a AUCUN retard sur le signal vrai (les
        # voies gyro et accel se somment à 1 ; 0,25 s est sa fréquence de
        # croisement, pas un lag). Valeur non justifiée finement : avec 25 ms les
        # gains embarqués sont linéairement instables, sans ils sont marginaux
        # (REVIEW_CLAUDE.md §2 #9) — le verdict du sim en dépend.
        tau_f = 0.025
        pt, rt = self.theta * 180 / math.pi, self.dtheta * 180 / math.pi
        self.pitch_f += ((pt + random.gauss(0, noise * 0.15)) - self.pitch_f) * (DT / tau_f)
        self.rate_f += ((rt + random.gauss(0, noise * 1.5)) - self.rate_f) * (DT / tau_f)

        # ── Consignes UI + évitement (balance.cpp l.673-692), AVANT le lissage ──
        cmd_fwd = max(-100, min(100, self.cmd_forward))
        cmd_turn = max(-100, min(100, self.cmd_turn))
        if self.obstacle_warn and cmd_fwd > 0:          # l.678 : plus de marche avant
            cmd_fwd = 0
        if cmd_fwd > self.avoid_fwd_max:                # l.687 : plafond / recul imposé (min)
            cmd_fwd = self.avoid_fwd_max
        if cmd_turn == 0 and self.avoid_turn != 0:      # l.688 : pivot si l'UI ne tourne pas
            cmd_turn = max(-100, min(100, self.avoid_turn))
        max_step = CMD_SLEW_PER_S * DT                  # l.690-692 (dt = DT ici)
        self.fwd_smooth = slew(self.fwd_smooth, float(cmd_fwd), max_step)
        self.turn_smooth = slew(self.turn_smooth, float(cmd_turn), max_step)

        # boucle EXTERNE de la cascade (10 Hz), sur φ = phi_cmd (ce que lit feet.cpp)
        if self.cascade:
            if t - self.recenter_last >= RECENTER_PERIOD:
                dt_rec = min(max(t - self.recenter_last, 0.0), 1.0)
                self.recenter_last = t
                if MODE == "arc" and abs(self.phi_cmd) > FOOT_PANIC:
                    self.panicked = True
                else:
                    target = max(-RECENTER_VEL_MAX, min(RECENTER_VEL_MAX, self.kp_phi * (0.0 - self.phi_cmd)))
                    step = RECENTER_SLEW * dt_rec
                    if target > self.recenter_vel + step:
                        self.recenter_vel += step
                    elif target < self.recenter_vel - step:
                        self.recenter_vel -= step
                    else:
                        self.recenter_vel = target

        # boucle INTERNE (200 Hz) : contribution à θ_ref.
        # SIGNE NON TRANCHÉ — à décider en réel, commencer kv = 0 au banc web
        # (REVIEW_CLAUDE.md M1). Aligné sur balance.cpp recenterSetpoint() :
        # −kRecenterKv·(v_cible − φ̇). De 6aabd3c à ce jour, ce sim portait le
        # signe (+) pendant que le firmware avait (−) — règle d'or violée. La
        # « preuve » par simulation du signe (−) est caduque (le sim ne tenait
        # pas le PID seul) ; ici, les deux signes se testent en changeant cette
        # seule ligne ET celle du firmware, jamais l'une sans l'autre.
        ref = 0.0
        if self.cascade:
            ref = max(-RECENTER_REF_MAX, min(RECENTER_REF_MAX,
                                             -self.kv * (self.recenter_vel - self.foot_vel_filt)))

        # balance.cpp l.724-725 : kSetpointDeg + s_fwdSmooth·kTiltPerCmd + recenterSetpoint()
        setpoint = SETPOINT_DEG + self.fwd_smooth * TILT_PER_CMD + ref
        err = setpoint - self.pitch_f
        if abs(err) < DEADBAND:
            err = 0.0
        p = self.kp * err
        d = -self.kd * self.rate_f
        cand = max(-INTEGRAL_MAX, min(INTEGRAL_MAX, self.integ + self.ki * err * DT))
        raw = p + cand + d
        if abs(raw) < OUT_MAX or raw * err < 0:
            self.integ = cand
        out = max(-OUT_MAX, min(OUT_MAX, p + self.integ + d))
        # soft clamp de butée (feet.cpp fournit φ intégré = phi_cmd).
        # ATTENTION AU SIGNE (REVIEW_CLAUDE.md M2) : `out` est la sortie PID NON
        # inversée ; la vitesse de pied réelle est u = −out (run()). Le pied
        # pousse vers la butée quand u·φ > 0 ⇔ (−out)·φ > 0 — c'est ce que teste
        # balance.cpp (limitTowardStop après l'inversion : out·footAvg ≤ 0 →
        # libre). L'ancien test `out * phi_cmd > 0` atténuait le RETOUR vers le
        # centre et laissait la poussée vers la butée à pleine autorité.
        if MODE == "arc" and (-out) * self.phi_cmd > 0:
            lim = min(FOOT_HARD, 90.0 - abs(self.pitch_f) - FOOT_MARGIN)
            out *= max(0.0, min(1.0, (lim - abs(self.phi_cmd)) / FOOT_TAPER))
        # estimateur φ̇ : filtre 1er ordre de la commande APRÈS clamp, AVANT différentiel.
        # Même signe que ci-dessus : la commande réellement envoyée à feet.cpp est
        # −out·k_out (l'inversion stabilisante se fait chez l'appelant, comme dans
        # balance.cpp : updateFootVel(out · kOutToFootDegS)).
        alpha = DT / (FOOT_VEL_TAU + DT)
        cmd_vel = -out * self.k_out
        self.foot_vel_filt += alpha * (cmd_vel - self.foot_vel_filt)
        return out

    def run(self, theta0, tmax, noise, push=None, pilote=None):
        """pilote(sim, t), facultatif : appelé au DÉBUT de chaque pas, avant le
        correcteur — c'est là que le firmware lit g_state (cmdForward, cmdTurn,
        avoidFwdMax, avoidTurn, obstacleWarn écrits par l'UI et la tête). Sert
        à scénariser un déplacement ou un évitement (selfcheck.js §6)."""
        self.reset()
        self.theta = theta0 * math.pi / 180
        push_t, push_v = push or (0, 0)
        for k in range(int(tmax / DT)):
            t = k * DT
            if pilote:
                pilote(self, t)
            # câblage stabilisant (comme le firmware) : `out` de balance.cpp
            # est la sortie PID INVERSÉE (l.741).
            out = -self.ctrl(noise, t)
            # Différentiel de rotation (balance.cpp l.751-758) : roue G = out +
            # turn, roue D = out − turn, chacune bornée, puis °/s de pied via
            # k_out (Feet::driveFootSpeed(left · kOutToFootDegS, right · …)).
            # La MOYENNE des deux roues pilote θ (le pendule ne voit que
            # l'axe) ; la DIFFÉRENCE ne fait que pivoter le robot (lacet).
            # À cmdTurn = 0 : left = right = out, u = out·k_out exactement.
            turn = self.turn_smooth * TURN_PER_CMD
            left = max(-OUT_MAX, min(OUT_MAX, out + turn))
            right = max(-OUT_MAX, min(OUT_MAX, out - turn))
            u = (left + right) / 2 * self.k_out
            u_diff = (left - right) / 2 * self.k_out
            # roue (servo 360°) : pas de butée, la roue tourne sans fin ;
            # arc : butée dure ±FOOT_HARD (ancienne mécanique).
            if MODE == "arc":
                self.phi_cmd = max(-FOOT_HARD, min(FOOT_HARD, self.phi_cmd + u * DT))
            else:
                self.phi_cmd += u * DT
            dphi = max(-VMAX_SERVO, min(VMAX_SERVO, (self.phi_cmd - self.phi) / TAU_SERVO))
            dphidd = (dphi - self.prev_dphi) / DT * (math.pi / 180.0)   # rad/s²
            self.prev_dphi = dphi
            self.phi += dphi * DT
            # Voie différentielle : même servo du 1er ordre que la moyenne
            # (la loi est linéaire, la décomposition somme/différence est
            # exacte hors saturation VMAX_SERVO). Lacet ψ = (φ_G − φ_D)·R/TRACK.
            self.phi_diff_cmd += u_diff * DT
            dphi_diff = max(-VMAX_SERVO, min(VMAX_SERVO, (self.phi_diff_cmd - self.phi_diff) / TAU_SERVO))
            self.phi_diff += dphi_diff * DT
            self.psi = 2.0 * self.phi_diff * (math.pi / 180.0) * R / TRACK
            # Lagrange (voir docstring) : θ̈·(R² + 2Rh cosθ + h²)
            #   = g·h·sinθ − φ̈·R·(R + h·cosθ) + R·h·sinθ·θ̇²
            cos_t, sin_t = math.cos(self.theta), math.sin(self.theta)
            inertia = R * R + 2.0 * R * H * cos_t + H * H
            thdd = (G * H * sin_t - dphidd * R * (R + H * cos_t)
                    + R * H * sin_t * self.dtheta * self.dtheta) / inertia
            if push_t and abs(t - push_t) < DT / 2:
                self.dtheta += push_v
            self.dtheta += thdd * DT
            self.theta += self.dtheta * DT
            # Pose au sol : roulement sans glissement le long du cap, l'axe
            # avance de R·(Δθ + Δφ) (x_axe = R·(θ + φ) à ψ = 0).
            ds = R * (self.dtheta * DT + dphi * DT * (math.pi / 180.0))
            self.pos_x += ds * math.cos(self.psi)
            self.pos_z += ds * math.sin(self.psi)
            self.t = t
            if abs(self.theta * 180 / math.pi) > FALL_ANGLE:
                return False, "chute θ"
            if self.panicked:
                return False, "panic φ"
        return True, "ok"


SCENARIOS = [
    ("θ0=2° propre",   dict(theta0=2, tmax=6, noise=0)),
    ("θ0=2° bruit",    dict(theta0=2, tmax=6, noise=1)),
    ("θ0=5° bruit",    dict(theta0=5, tmax=6, noise=1)),
    ("tape 0.4 rad/s", dict(theta0=3, tmax=8, noise=1, push=(3, 0.4))),
    ("tape 0.8 rad/s", dict(theta0=3, tmax=8, noise=1, push=(3, 0.8))),
    ("tape 1.2 rad/s", dict(theta0=3, tmax=8, noise=1, push=(3, 1.2))),
]


def score(kp, ki, kd, cascade=True, k_out=1.0):
    random.seed(42)
    s = Sim(kp, ki, kd, cascade=cascade, k_out=k_out)
    return sum(1 for _, kw in SCENARIOS if s.run(**kw)[0])


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    cascade = "--no-cascade" not in sys.argv
    if "--sweep" in sys.argv:
        # k_out (kOutToFootDegS) fait partie du balayage (M11) : c'est « le
        # PREMIER bouton à monter » selon balance.cpp, il n'était jamais varié.
        print(f"Balayage (cascade={cascade}) — jeux tenant les {len(SCENARIOS)} scénarios :")
        found = 0
        for k_out in (1.0, 2.0, 3.0):
            found_k = 0
            for kp in (0.5, 1, 2, 5, 10, 25, 50, 100):
                for ki in (350, 500, 800, 1200, 2000):
                    for kd in (0.2, 0.5, 1, 2, 5, 10, 20):
                        if score(kp, ki, kd, cascade, k_out) == len(SCENARIOS):
                            print(f"  k_out={k_out:<3} Kp={kp:<4} Ki={ki:<5} Kd={kd}")
                            found_k += 1
            print(f"  (k_out={k_out} : {found_k} jeu(x))")
            found += found_k
        print(f"→ {found} jeu(x) de gains")
    else:
        kp, ki, kd = (float(x) for x in args[:3]) if len(args) >= 3 else (25, 500, 0.5)
        k_out = float(args[3]) if len(args) >= 4 else 1.0
        print(f"Gains Kp={kp} Ki={ki} Kd={kd} k_out={k_out} — cascade={'ON' if cascade else 'OFF'}")
        random.seed(42)
        s = Sim(kp, ki, kd, cascade=cascade, k_out=k_out)
        ok_n = 0
        for label, kw in SCENARIOS:
            ok, why = s.run(**kw)
            ok_n += ok
            print(f"  {label:16s}: {'OK ' if ok else '❌ ' + why:8s}  "
                  f"θfin={math.degrees(s.theta):+6.1f}° φfin={s.phi_cmd:+5.1f}°")
        print(f"→ {ok_n}/{len(SCENARIOS)} scénarios tenus")
