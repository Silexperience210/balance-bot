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

// Commande les roues en vitesse signée -90…+90 (0 = arrêt) — domaine du
// PID, l'inversion mécanique de la roue gauche est gérée ici.
// (Une variante drive() en domaine servo 0…180 a existé : jamais appelée,
// supprimée.)
void driveSigned(int leftSpeed, int rightSpeed);

// Neutre immédiat sur les deux roues (chute, arrêt d'urgence).
void stop();

bool ready();       // true si les servos sont attachés

} // namespace Wheels
