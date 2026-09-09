#!/usr/bin/env python3
"""Simulateur 1D BalanceBot — pendule inversé sur pieds en arc.

Modélise le contrôleur RÉEL de balance.cpp : PID d'équilibre **+ cascade de
recentrage** (lot 2c), pieds en arc sur servos de position, avec le modèle
physique du roulement EXACT.

Usage :
  python3 balancebot_sim.py                 # jeux de gains par défaut, PID+cascade
  python3 balancebot_sim.py 25 500 0.5      # Kp Ki Kd
  python3 balancebot_sim.py --no-cascade    # comparaison sans la cascade
  python3 balancebot_sim.py --sweep         # balayage de gains (tient les 6 scénarios ?)

── Physique (modèle) ────────────────────────────────────────────────────────
Pendule inversé de hauteur de CoM h, base roulante de rayon R. La position du
pied est l'angle de servo φ (relatif au corps) ; le pied est un arc de rayon R
qui roule sans glisser, donc son rotation ABSOLUE vaut (θ + φ) et :

    x = R·(θ + φ)          ⇒     ẍ = R·(θ̈ + φ̈)

    θ̈ = [ (g/h)·sinθ − (R/h)·φ̈·cosθ ] / ( 1 + (R/h)·cosθ )

Servo : suivi de la consigne de position en 1er ordre (τ = 50 ms) borné à
250 °/s. Course de pied bornée à ±45° (butée dure de feet.cpp).

Ce modèle N'EST PAS : ni la friction (conservateur), ni la borne d'accélération
du servo, ni la 3D. Le réglage réel reste indispensable.

── État de validation (mesuré, 09/09/2026) ──────────────────────────────────
Les gains Kp25/Ki500/Kd0.5 livrés dans balance.cpp NE tiennent PAS dans ce
modèle corrigé (0/6 scénarios, avec ou sans cascade) : le pied consomme ses
±45° de course et le robot tombe. C'est cohérent avec le constat du commit
19535f7 (« gains validés non fiables, réglage réel indispensable ») : la
validation d'origine avait été faite avec un modèle 57× trop optimiste
(facteur °/rad) et SANS cascade. Utiliser ce script pour CHERCHER des gains,
pas pour certifier ceux qui sont embarqués.
"""
import math, random, sys

# ── Paramètres physiques ─────────────────────────────────────────────
G, R, H = 9.81, 0.0325, 0.080       # gravité, rayon arc (m), hauteur CoM (m)
TAU_SERVO, VMAX_SERVO = 0.05, 250.0  # servo : 1er ordre (s), vitesse max (°/s)
DT = 1.0 / 200                       # pas de contrôle = 200 Hz (comme le code)

# ── Constantes du contrôleur (copiées de balance.cpp) ────────────────
INTEGRAL_MAX, OUT_MAX = 25.0, 90.0
DEADBAND, FOOT_HARD, FOOT_MARGIN, FOOT_TAPER, FALL_ANGLE = 0.25, 45.0, 9.0, 10.0, 45.0
OUT_TO_FOOT_DEGS = 1.0               # kOutToFootDegS
RECENTER_PERIOD = 0.100              # 10 Hz
RECENTER_VEL_MAX, RECENTER_REF_MAX, RECENTER_SLEW = 20.0, 6.0, 3.0
FOOT_VEL_TAU, FOOT_PANIC = 0.08, 35.0


class Sim:
    def __init__(self, kp, ki, kd, cascade=True, kp_phi=0.8, kv=3.0):
        self.kp, self.ki, self.kd = kp, ki, kd
        self.cascade, self.kp_phi, self.kv = cascade, kp_phi, kv
        self.reset()

    def reset(self):
        self.theta = self.dtheta = self.phi = self.phi_cmd = 0.0
        self.integ = self.prev_dphi = self.t = 0.0
        self.pitch_f = self.rate_f = 0.0
        self.recenter_vel = self.foot_vel_filt = 0.0
        self.recenter_last = 0.0
        self.panicked = False

    # ── PID + cascade, à l'identique de balance.cpp ──────────────────
    def ctrl(self, noise, t):
        tau_f = 0.025   # retard du filtre complémentaire (0,25 s ≈ α 0,98 à 200 Hz)
        pt, rt = self.theta * 180 / math.pi, self.dtheta * 180 / math.pi
        self.pitch_f += ((pt + random.gauss(0, noise * 0.15)) - self.pitch_f) * (DT / tau_f)
        self.rate_f += ((rt + random.gauss(0, noise * 1.5)) - self.rate_f) * (DT / tau_f)

        # boucle EXTERNE de la cascade (10 Hz), sur φ = phi_cmd (ce que lit feet.cpp)
        if self.cascade:
            if t - self.recenter_last >= RECENTER_PERIOD:
                dt_rec = min(max(t - self.recenter_last, 0.0), 1.0)
                self.recenter_last = t
                if abs(self.phi_cmd) > FOOT_PANIC:
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

        # boucle INTERNE (200 Hz) : contribution à θ_ref
        ref = 0.0
        if self.cascade:
            ref = max(-RECENTER_REF_MAX, min(RECENTER_REF_MAX,
                                             self.kv * (self.recenter_vel - self.foot_vel_filt)))

        setpoint = ref
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
        # soft clamp de butée (feet.cpp fournit φ intégré = phi_cmd)
        if out * self.phi_cmd > 0:
            lim = min(FOOT_HARD, 90.0 - abs(self.pitch_f) - FOOT_MARGIN)
            out *= max(0.0, min(1.0, (lim - abs(self.phi_cmd)) / FOOT_TAPER))
        # estimateur φ̇ : filtre 1er ordre de la commande APRÈS clamp, AVANT différentiel.
        # ATTENTION AU SIGNE : la commande réellement envoyée à feet.cpp est -out
        # (l'inversion stabilisante se fait chez l'appelant, comme dans balance.cpp).
        alpha = DT / (FOOT_VEL_TAU + DT)
        cmd_vel = -out * OUT_TO_FOOT_DEGS
        self.foot_vel_filt += alpha * (cmd_vel - self.foot_vel_filt)
        return out

    def run(self, theta0, tmax, noise, push=None):
        self.reset()
        self.theta = theta0 * math.pi / 180
        push_t, push_v = push or (0, 0)
        for k in range(int(tmax / DT)):
            t = k * DT
            u = -self.ctrl(noise, t)          # câblage stabilisant (comme le firmware)
            self.phi_cmd = max(-FOOT_HARD, min(FOOT_HARD, self.phi_cmd + u * DT))
            dphi = max(-VMAX_SERVO, min(VMAX_SERVO, (self.phi_cmd - self.phi) / TAU_SERVO))
            dphidd = (dphi - self.prev_dphi) / DT * (math.pi / 180.0)   # rad/s²
            self.prev_dphi = dphi
            self.phi += dphi * DT
            cos_t = math.cos(self.theta)
            thdd = ((G / H) * math.sin(self.theta) - (R * dphidd / H) * cos_t) / (1.0 + (R / H) * cos_t)
            if push_t and abs(t - push_t) < 0.02:
                self.dtheta += push_v
            self.dtheta += thdd * DT
            self.theta += self.dtheta * DT
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


def score(kp, ki, kd, cascade=True):
    random.seed(42)
    s = Sim(kp, ki, kd, cascade=cascade)
    return sum(1 for _, kw in SCENARIOS if s.run(**kw)[0])


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    cascade = "--no-cascade" not in sys.argv
    if "--sweep" in sys.argv:
        print(f"Balayage (cascade={cascade}) — jeux tenant les {len(SCENARIOS)} scénarios :")
        found = 0
        for kp in (0.5, 1, 2, 5, 10, 25, 50, 100):
            for ki in (350, 500, 800, 1200, 2000):
                for kd in (0.2, 0.5, 1, 2, 5, 10, 20):
                    if score(kp, ki, kd, cascade) == len(SCENARIOS):
                        print(f"  Kp={kp:<4} Ki={ki:<5} Kd={kd}")
                        found += 1
        print(f"→ {found} jeu(x) de gains")
    else:
        kp, ki, kd = (float(x) for x in args[:3]) if len(args) >= 3 else (25, 500, 0.5)
        print(f"Gains Kp={kp} Ki={ki} Kd={kd} — cascade={'ON' if cascade else 'OFF'}")
        random.seed(42)
        s = Sim(kp, ki, kd, cascade=cascade)
        ok_n = 0
        for label, kw in SCENARIOS:
            ok, why = s.run(**kw)
            ok_n += ok
            print(f"  {label:16s}: {'OK ' if ok else '❌ ' + why:8s}  "
                  f"θfin={math.degrees(s.theta):+6.1f}° φfin={s.phi_cmd:+5.1f}°")
        print(f"→ {ok_n}/{len(SCENARIOS)} scénarios tenus")
