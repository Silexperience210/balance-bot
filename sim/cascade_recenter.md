"""Exploration : cascade de recentrage en vitesse (validée le 07/09).

Problème : le recentrage par trim d'angle (±0.4° sur θ_ref) est trop faible.
Après une tape qui laisse le pied à φ=36°, le robot reste collé près de la
butée (±45°) et la tape suivante le fait tomber.

Solution validée dans ce modèle 1D : boucle externe de POSITION du pied
(v_cible = KP_PHI·(0−φ)) → boucle interne de VITESSE (θ_ref += KV·(v_cible
− φ̇_estimé)) → PID d'équilibre inchangé. La vitesse φ̇ est estimée SANS
encodeur par la commande filtrée (τ≈80 ms) — feet.cpp intègre φ, sa dérivée
commandée approxime le servo réel.

Résultats (KP_PHI=0.8, KV=3.0, bruit IMU inclus) :
- tape 0.5 rad/s : φ revient de ~36° à ~1° en ~10 s, robot ~à sa place
- tape 0.8 rad/s : tient (φ fin ~15°) — le trim actuel laissait 36°+ 
- LIMITE GÉOMÉTRIQUE confirmée : la MARCHE est impossible avec les arcs
  (50 cm exigeraient φ=88°, butée à 45°). La cascade sert au recentrage
  et à encaisser les perturbations en série, pas à se déplacer.

Intégration firmware : lot 2c (balance.cpp). Gains exposés en constantes
pour réglage réel via le tuner.
"""
