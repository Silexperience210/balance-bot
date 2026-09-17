#pragma once
// ═══════════════════════════════════════════════════════════════════
// BalanceBot — module A (équilibre) · en-tête PRIVÉ du driver IMU
// MPU6050 en I2C brut (Wire.h) — aucune dépendance externe.
// Utilisé uniquement par balance.cpp. Ne fait pas partie du contrat
// public (interfaces.h) : ne pas inclure depuis les autres modules.
// ═══════════════════════════════════════════════════════════════════
#include <Arduino.h>

namespace Imu {

// Init du bus I2C + du MPU6050. false si le capteur ne répond pas
// (le robot doit alors booter quand même, en mode démo UI).
bool begin();

// Mesure le biais gyro au repos (robot posé, immobile) et fige l'angle
// de départ à partir de l'accéléromètre. Lit à 200 Hz (la cadence du
// capteur) : 400 échantillons DISTINCTS ≈ 2 s bloquantes, appelé
// uniquement depuis Balance::begin(). false si moins de la moitié des
// lectures sont valides (bus instable, capteur figé) — l'appelant loggue.
bool calibrate(uint16_t samples = 400);

// Un échantillon : lecture accel+gyro, filtre complémentaire.
// dtSec = temps écoulé depuis l'appel précédent (secondes).
// false si la lecture I2C a échoué OU si le capteur renvoie des trames
// figées (kFrozenMax identiques consécutives) — l'angle précédent est
// conservé, l'appelant compte la trame comme perdue.
bool update(float dtSec);

float pitchDeg();     // angle filtré, 0 = vertical (robot en équilibre)
float pitchRateDps(); // vitesse angulaire gyro (°/s), déjà débiaisée
float accelPitchDeg();// angle brut accéléromètre (debug / réglage)
float tempC();        // température interne du MPU6050 (diagnostic)
bool  ok();           // true si le capteur a répondu au démarrage

} // namespace Imu
