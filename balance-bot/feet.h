#pragma once
// ═══════════════════════════════════════════════════════════════════
// BalanceBot — module A (équilibre) · en-tête PRIVÉ des pieds en arc
//
// Remplace wheels.h : la mécanique v2 n'a plus de roues. Deux arcs de
// cercle (foot_arc.stl, rayon 32.5 mm) entraînés par des SG90 STANDARD
// 180° roulent sur le sol. Le servo ne prend qu'une POSITION : ce
// module intègre la vitesse demandée par le PID en position de pied.
//
// Utilisé uniquement par balance.cpp — hors contrat public.
// ═══════════════════════════════════════════════════════════════════
#include <Arduino.h>

namespace Feet {

// Attache les 2 servos et les met au repos (pied à 0° = servo 90°).
// false si l'attache échoue.
bool begin();

// Commande la VITESSE ANGULAIRE de chaque pied, en °/s signés
// (+ = le pied pousse le robot vers l'AVANT). La position est intégrée
// en interne à partir du dt réel ; l'inversion mécanique du servo
// gauche (monté en miroir) est gérée ici.
void driveFootSpeed(int leftDegS, int rightDegS);

// Frein immédiat : on RÉÉCRIT la position courante, on ne revient PAS
// au neutre — un retour brutal à 0° ferait basculer le robot.
void stop();

// Retour à la position neutre (pieds à 0°). À n'appeler QUE robot
// couché / tenu à la main (chute, avant ré-armement) : sur un robot
// debout c'est une mise à terre garantie.
void recenterNow();

// Position courante des pieds, en degrés (0 = repos, + = avant).
float angleL();
float angleR();
float angleAvg();      // moyenne des deux — grandeur utile au recentrage

bool ready();          // true si les servos sont attachés

} // namespace Feet
