#!/usr/bin/env python3
"""Simulateur 1D BalanceBot v2 — pendule inversé sur pieds en arc.

Reproduit À L'IDENTIQUE le contrôleur de balance.cpp (PID anti-windup
conditionnel, deadband, soft clamp de butée, recentrage) couplé à un modèle
physique du robot : pendule inversé dont la base roule (x = R·φ), servo
SG90 1er ordre (τ=50 ms, 250°/s max), bruit IMU + retard du filtre.

Usage : python3 balancebot_sim.py [kp ki kd]   (défaut : 25 500 0.5)
Sortie : test en escalier (θ0, bruit, tapes) + profil PNG.

Résultats clés (commit ea68b1b) :
- Ki > g/R ≈ 300 est REQUIS (condition de stabilité) — Ki=20 hérité du
  design « roues » ne peut pas tenir le robot.
- Kp=25 Ki=500 Kd=0.5 : tient debout, robuste au bruit, tapes modérées.
- Recentrage par trim d'angle ±1° : fragile (balancebot penché = accélère,
  pas vitesse constante) → adouci dans le firmware (max ±0.4°, 0.10°/s).
"""
import math, random, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ── Paramètres physiques ─────────────────────────────────────────────
G, R, H = 9.81, 0.0325, 0.080      # gravité, rayon arc (m), hauteur CoM (m)
TAU_SERVO, VMAX_SERVO = 0.05, 250.0  # servo : 1er ordre (s), vitesse max (°/s)
MU_ROLL = 0.03                        # friction de roulement PLA
DT = 1.0 / 200                        # pas de contrôle = 200 Hz (comme le code)

# ── Contrôleur (copie de balance.cpp / feet.cpp) ─────────────────────
INTEGRAL_MAX, OUT_MAX = 25.0, 90.0
DEADBAND, FOOT_HARD, FOOT_MARGIN, FOOT_TAPER, FALL_ANGLE = 0.25, 45.0, 9.0, 10.0, 45.0


class Sim:
    def __init__(self, kp, ki, kd):
        self.kp, self.ki, self.kd = kp, ki, kd
        self.reset()

    def reset(self):
        self.theta = self.dtheta = self.phi = self.phi_cmd = 0.0
        self.integ = self.t = self.prev_dphi = 0.0
        self.fallen = False
        self.pitch_f = self.rate_f = 0.0
        self.vbase = 0.0

    def ctrl(self, noise):
        """Copie de la boucle PID de balance.cpp (signe = câblage stabilisant)."""
        tau_f = 0.025  # retard du filtre complémentaire
        pt, rt = self.theta * 180 / math.pi, self.dtheta * 180 / math.pi
        self.pitch_f += ((pt + random.gauss(0, noise * 0.15)) - self.pitch_f) * (DT / tau_f)
        self.rate_f  += ((rt + random.gauss(0, noise * 1.5))  - self.rate_f)  * (DT / tau_f)
        err = -self.pitch_f
        if abs(err) < DEADBAND:
            err = 0.0
        p = self.kp * err
        d = -self.kd * self.rate_f
        cand = max(-INTEGRAL_MAX, min(INTEGRAL_MAX, self.integ + self.ki * err * DT))
        raw = p + cand + d
        if abs(raw) < OUT_MAX or raw * err < 0:
            self.integ = cand
        out = max(-OUT_MAX, min(OUT_MAX, p + self.integ + d))
        if out * self.phi > 0:  # soft clamp de butée
            lim = min(FOOT_HARD, 90.0 - abs(self.pitch_f) - FOOT_MARGIN)
            out *= max(0.0, min(1.0, (lim - abs(self.phi)) / FOOT_TAPER))
        return out

    def run(self, theta0, tmax, noise, push=None, dt_sim=DT):
        self.reset()
        self.theta = theta0 * math.pi / 180
        push_t, push_v = push or (0, 0)
        for k in range(int(tmax / dt_sim)):
            t = k * dt_sim
            u = -self.ctrl(noise)  # câblage stabilisant (convention sim)
            self.phi_cmd = max(-FOOT_HARD, min(FOOT_HARD, self.phi_cmd + u * dt_sim))
            dphi = (self.phi_cmd - self.phi) / TAU_SERVO
            dphi = max(-VMAX_SERVO, min(VMAX_SERVO, dphi))
            a = R * (dphi - self.prev_dphi) / dt_sim
            self.prev_dphi = dphi
            self.phi += dphi * dt_sim
            self.vbase = R * dphi * math.pi / 180
            if abs(self.vbase) > 1e-4:
                a -= math.copysign(MU_ROLL * G * 0.3, self.vbase)
            thdd = (G / H) * math.sin(self.theta) - (a / H) * math.cos(self.theta) - 0.5 * self.dtheta
            if push_t and abs(t - push_t) < 0.02:
                self.dtheta += push_v
            self.dtheta += thdd * dt_sim
            self.theta += self.dtheta * dt_sim
            self.t = t
            if abs(self.theta * 180 / math.pi) > FALL_ANGLE:
                return False, "chute θ"
            if abs(self.phi) > FOOT_HARD:
                return False, "butée φ"
        return True, "ok"


if __name__ == "__main__":
    kp, ki, kd = (float(x) for x in sys.argv[1:4]) if len(sys.argv) > 3 else (25, 500, 0.5)
    random.seed(42)
    print(f"Gains Kp={kp} Ki={ki} Kd={kd} — test en escalier :")
    s = Sim(kp, ki, kd)
    for label, kw in [
        ("θ0=2° propre",  dict(theta0=2, tmax=6,  noise=0)),
        ("θ0=2° bruit",   dict(theta0=2, tmax=6,  noise=1)),
        ("θ0=5° bruit",   dict(theta0=5, tmax=6,  noise=1)),
        ("tape 0.4 rad/s",dict(theta0=3, tmax=8,  noise=1, push=(3, 0.4))),
        ("tape 0.8 rad/s",dict(theta0=3, tmax=8,  noise=1, push=(3, 0.8))),
        ("tape 1.2 rad/s",dict(theta0=3, tmax=8,  noise=1, push=(3, 1.2))),
    ]:
        ok, why = s.run(**kw)
        print(f"  {label:18s}: {'✅' if ok else '❌ ' + why}  "
              f"θfin={s.theta * 57.3:+6.1f}° φfin={s.phi:+5.1f}°")
