#pragma once
// ═══════════════════════════════════════════════════════════════════
// BalanceBot — module A (équilibre) · en-tête PRIVÉ des roues
// 2× SG90 modifiés rotation continue sur SERVO_WHEEL_L / SERVO_WHEEL_R.
// Utilisé uniquement par balance.cpp — hors contrat public.
// ═══════════════════════════════════════════════════════════════════
#include <Arduino.h>

namespace Wheels {

// Attache les 2 servos et les met au neutre. false si l'attache échoue.
bool begin();

// Commande les roues. Domaine identique au servo standard :
//   0 … 180, WHEEL_NEUTRAL (90) = arrêt
//   > 90 = marche avant, < 90 = marche arrière (POUR LES DEUX ROUES :
//   l'inversion mécanique de la roue gauche est gérée ici).
void drive(int leftPwm, int rightPwm);

// Idem mais en vitesse signée -90…+90 (0 = arrêt) — plus pratique
// depuis le PID, évite un aller-retour autour de WHEEL_NEUTRAL.
void driveSigned(int leftSpeed, int rightSpeed);

// Neutre immédiat sur les deux roues (chute, arrêt d'urgence).
void stop();

bool ready();       // true si les servos sont attachés
int  lastLeftUs();  // dernières impulsions écrites (debug / télémétrie)
int  lastRightUs();

} // namespace Wheels
