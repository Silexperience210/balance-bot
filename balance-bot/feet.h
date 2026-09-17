#pragma once
// ═══════════════════════════════════════════════════════════════════
// BalanceBot — module A (équilibre) · en-tête PRIVÉ des pieds en arc
//
// Le nom « Feet » date de la mécanique v3.1 (pieds en arc sur SG90 de
// position). Le robot RÉEL (v3, chassis/NOTES_v3.md) a deux ROUES sur
// servos à rotation continue : même API, sélecteur FEET_MODE_CONTINUOUS
// dans config.h.
//
// L'API est la MÊME pour les deux matériels supportés : on commande
// toujours une VITESSE de roue/pied, et angleL/R/Avg renvoient toujours
// la course φ intégrée. Seule change la façon d'écrire sur le servo —
// vitesse directe (servo 360°, robot réel) ou position intégrée (SG90
// standard).
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

bool ready();          // true si les servos sont attachés (même coupés, cf. cut)

// ── Coupure de sécurité ────────────────────────────────────────────
// cut() DÉTACHE le PWM des deux servos et force la broche à l'état bas :
// plus aucune impulsion → un servo continu s'arrête quel que soit son
// trim (le « neutre » 1500 µs, lui, peut ramper) ; un servo de position
// devient libre. Appelée par balance.cpp (chute, arrêt d'urgence) et par
// la surveillance de loop() sur un AUTRE cœur (boucle figée) — c'est la
// seule écriture servo autorisée hors de la boucle d'équilibre, protégée
// par une section critique. Tant que isCut(), driveFootSpeed()/stop()
// sont des no-op. rearm() ré-attache et écrit le neutre — à n'appeler
// que depuis la boucle d'équilibre.
void cut();
void rearm();
bool isCut();

} // namespace Feet
