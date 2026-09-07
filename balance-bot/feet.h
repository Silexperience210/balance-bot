#pragma once
// ═══════════════════════════════════════════════════════════════════
// BalanceBot — module A (équilibre) · en-tête PRIVÉ des pieds en arc
//
// Remplace wheels.h : la mécanique v2 n'a plus de roues. Deux arcs de
// cercle (foot_arc.stl, rayon 32.5 mm) entraînés par des servos taille
// SG90 roulent sur le sol.
//
// L'API est la MÊME pour les deux matériels supportés (sélecteur
// FEET_MODE_CONTINUOUS dans config.h) : on commande toujours une VITESSE
// de pied, et angleL/R/Avg renvoient toujours la course consommée sur
// l'arc. Seule change la façon d'écrire sur le servo — position intégrée
// (SG90 standard) ou vitesse directe (servo 360°).
//
// Utilisé uniquement par balance.cpp — hors contrat public.
// ═══════════════════════════════════════════════════════════════════
#include <Arduino.h>

namespace Feet {

// Attache les 2 servos et les met au repos (position : pied à 0° =
// servo 90° ; continu : neutre 1500 µs). false si l'attache échoue.
bool begin();

// Commande la VITESSE ANGULAIRE de chaque pied, en °/s signés
// (+ = le pied pousse le robot vers l'AVANT). La course φ est intégrée
// en interne à partir du dt réel dans les deux modes ; l'inversion
// mécanique du servo gauche (monté en miroir) est gérée ici.
void driveFootSpeed(int leftDegS, int rightDegS);

// Frein immédiat. Position : on RÉÉCRIT la position courante, on ne
// revient PAS au neutre — un retour brutal à 0° ferait basculer le
// robot. Continu : on écrit l'arrêt (1500 µs), seule commande d'arrêt
// possible sur un servo sans position.
void stop();

// Remise à zéro de la course des pieds. Position : les servos reviennent
// physiquement au neutre. Continu : seul le compteur φ est remis à 0, sans
// rien écrire (rien à rejoindre — le servo n'a pas de position). À
// n'appeler QUE robot couché / tenu à la main (chute, avant ré-armement) :
// en mode position, sur un robot debout, c'est une mise à terre garantie.
void recenterNow();

// Course courante des pieds, en degrés (0 = repos, + = avant).
float angleL();
float angleR();
float angleAvg();      // moyenne des deux — grandeur utile au recentrage

bool ready();          // true si les servos sont attachés

} // namespace Feet
