// ═══════════════════════════════════════════════════════════════════
// BalanceBot — module A · driver MPU6050 + filtre complémentaire
//
// Registres MPU6050 pilotés directement via Wire (pas de lib externe :
// seules ArduinoJson / ESP32Servo / TFT_eSPI / WebSockets sont
// installées sur cette machine).
//
// Chaîne de mesure :
//   accel  → angle absolu, juste en moyenne mais bruité (vibrations)
//   gyro   → variation d'angle, lisse mais dérive (biais + intégration)
//   fusion → filtre complémentaire  θ = α(θ + ω·dt) + (1-α)·θ_accel
// α = 0.98 à 200 Hz ⇒ constante de temps ≈ α·dt/(1-α) ≈ 0.25 s :
// le gyro pilote le court terme, l'accel recale le long terme.
// ═══════════════════════════════════════════════════════════════════
#include "imu.h"
#include "config.h"

#include <Wire.h>
#include <math.h>

namespace {

// ── Adresse & registres MPU6050 ────────────────────────────────────
constexpr uint8_t kAddrPrimary   = 0x68;  // AD0 = GND
constexpr uint8_t kAddrSecondary = 0x69;  // AD0 = VCC
constexpr uint8_t kRegSmplrtDiv  = 0x19;
constexpr uint8_t kRegConfig     = 0x1A;
constexpr uint8_t kRegGyroConfig = 0x1B;
constexpr uint8_t kRegAccelConfig= 0x1C;
constexpr uint8_t kRegAccelXoutH = 0x3B;  // début du bloc de 14 octets
constexpr uint8_t kRegPwrMgmt1   = 0x6B;
constexpr uint8_t kRegWhoAmI     = 0x75;

// ── Réglages capteur ───────────────────────────────────────────────
constexpr uint32_t kI2cHz      = 400000;  // fast mode : 14 octets ≈ 0.4 ms
constexpr uint8_t  kDlpfCfg    = 0x03;    // filtre interne 44 Hz accel / 42 Hz gyro
constexpr uint8_t  kSmplrtDiv  = 0x04;    // 1 kHz / (1+4) = 200 Hz — cadence boucle
constexpr uint8_t  kGyroFs     = 0x08;    // ±500 °/s  → 65.5 LSB/(°/s)
constexpr uint8_t  kAccelFs    = 0x08;    // ±4 g      → 8192 LSB/g
constexpr float    kGyroLsb    = 65.5f;
constexpr float    kAccelLsb   = 8192.0f;

// ── Fusion ─────────────────────────────────────────────────────────
constexpr float kAlpha = 0.98f;           // poids du gyro (0.95..0.995)

// ── RÉGLAGE MÉCANIQUE — orientation du MPU6050 sur le châssis ──────
// Convention retenue : pitch > 0 = le robot penche vers l'AVANT.
// Hypothèse de montage : carte à plat sur le châssis, Z vers le haut
// quand le robot est vertical, X vers l'avant, Y vers la gauche.
//   angle accel = atan2(ax, az)   (plage ±180° ⇒ détection de chute OK)
//   vitesse     = gyro Y
// Si le capteur est monté autrement, seuls ces 3 réglages changent :
constexpr float kAccelPitchSign = 1.0f;   // -1 pour inverser l'angle accel
constexpr float kGyroPitchSign  = 1.0f;   // -1 si le gyro s'oppose à l'accel
// Décalage de montage / centre de gravité (°) : retranché de l'angle
// mesuré pour que « 0 » corresponde au vrai point d'équilibre.
constexpr float kMountOffsetDeg = 0.0f;

uint8_t s_addr    = kAddrPrimary;
bool    s_ok      = false;
float   s_pitch   = 0.0f;   // angle fusionné (°)
float   s_rate    = 0.0f;   // vitesse gyro débiaisée (°/s)
float   s_accPitch= 0.0f;   // angle accel brut (°)
float   s_tempC   = 0.0f;
float   s_gyroBias= 0.0f;   // biais gyro mesuré au repos (LSB)

bool writeReg(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(s_addr);
  Wire.write(reg);
  Wire.write(val);
  return Wire.endTransmission() == 0;
}

bool readRegs(uint8_t reg, uint8_t* buf, uint8_t len) {
  Wire.beginTransmission(s_addr);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;   // repeated start
  if (Wire.requestFrom((int)s_addr, (int)len, (int)true) != len) return false;
  for (uint8_t i = 0; i < len; i++) buf[i] = Wire.read();
  return true;
}

bool probe(uint8_t addr) {
  Wire.beginTransmission(addr);
  return Wire.endTransmission() == 0;
}

// Lecture brute du bloc accel(6) + temp(2) + gyro(6).
struct Raw { int16_t ax, ay, az, t, gx, gy, gz; };

bool readRaw(Raw& r) {
  uint8_t b[14];
  if (!readRegs(kRegAccelXoutH, b, 14)) return false;
  r.ax = (int16_t)((b[0]  << 8) | b[1]);
  r.ay = (int16_t)((b[2]  << 8) | b[3]);
  r.az = (int16_t)((b[4]  << 8) | b[5]);
  r.t  = (int16_t)((b[6]  << 8) | b[7]);
  r.gx = (int16_t)((b[8]  << 8) | b[9]);
  r.gy = (int16_t)((b[10] << 8) | b[11]);
  r.gz = (int16_t)((b[12] << 8) | b[13]);
  return true;
}

// ── Vivacité du capteur (REVIEW_CLAUDE.md M9) ──────────────────────
// readRaw() ne détecte que l'échec de TRANSACTION. Un MPU6050 qui ACK mais
// renvoie des registres FIGÉS (retombé en veille/reset après un creux
// d'alimentation : trame de zéros, ou dernière valeur gelée) passerait
// pour vivant — et le robot s'asservirait sur un angle mort sans jamais
// lever s_imuLost. Or le bruit propre du capteur (≥ 2 LSB rms par axe,
// 6 axes) rend deux trames VIVANTES strictement identiques sur les 7 mots
// quasi impossibles… sauf quand la boucle relit le MÊME échantillon : la
// cadence par millis() du .ino est quantifiée et une lecture peut tomber
// < 5 ms après la précédente. D'où le seuil : au-delà de kFrozenMax trames
// identiques CONSÉCUTIVES, la trame est traitée comme PERDUE (update()
// renvoie false) et alimente le compteur kImuFailMax de balance.cpp. Une
// trame qui change remet tout à zéro (reprise automatique, cf. M19).
constexpr uint8_t kFrozenMax = 4;             // 4 × 5 ms = 20 ms
Raw     s_prevRaw{};
bool    s_havePrev     = false;
uint8_t s_frozenStreak = 0;

inline bool sameRaw(const Raw& a, const Raw& b) {
  return a.ax == b.ax && a.ay == b.ay && a.az == b.az && a.t == b.t &&
         a.gx == b.gx && a.gy == b.gy && a.gz == b.gz;
}

// Lecture brute + test de vivacité : false si transaction ratée OU trame
// figée depuis kFrozenMax lectures. Partagé par update() et calibrate().
bool readLive(Raw& r) {
  if (!readRaw(r)) return false;
  const bool frozen = s_havePrev && sameRaw(r, s_prevRaw);
  s_prevRaw  = r;
  s_havePrev = true;
  if (!frozen) { s_frozenStreak = 0; return true; }
  if (s_frozenStreak < 255) s_frozenStreak++;
  return s_frozenStreak < kFrozenMax;
}

// Axe gyro utilisé pour le pitch (voir bloc RÉGLAGE MÉCANIQUE).
inline int16_t gyroPitchRaw(const Raw& r) { return r.gy; }

// Angle d'inclinaison depuis l'accéléromètre, en degrés.
inline float accelPitch(const Raw& r) {
  return kAccelPitchSign * atan2f((float)r.ax, (float)r.az) * RAD_TO_DEG;
}

} // namespace

namespace Imu {

bool begin() {
  s_ok = false;
  Wire.begin(PIN_IIC_SDA, PIN_IIC_SCL);   // ESP32-S3 : pins explicites
  Wire.setClock(kI2cHz);
  Wire.setTimeOut(2);                     // ms — 2 ms suffit (les esclaves I2C
                                          // répondent en µs) ; un timeout long
                                          // gèlerait la boucle 200 Hz si un
                                          // contact faiblit en mouvement

  // Chaque adresse est essayée COMPLÈTEMENT (présence ET identité) : un
  // simple ACK sur 0x68 ne suffit pas — un autre esclave à cette adresse
  // (EEPROM, second capteur) répondrait et on piloterait le mauvais.
  bool found = false;
  const uint8_t kAddrs[2] = { kAddrPrimary, kAddrSecondary };
  for (uint8_t i = 0; i < 2 && !found; i++) {
    if (!probe(kAddrs[i])) continue;
    s_addr = kAddrs[i];
    uint8_t who = 0;
    if (!readRegs(kRegWhoAmI, &who, 1)) continue;
    // MPU6050 = 0x68 ; les clones MPU6500/9250 répondent 0x70/0x71/0x73
    // et sont compatibles registre à registre pour ce qu'on utilise ici.
    if (who == 0x68 || who == 0x70 || who == 0x71 || who == 0x73) found = true;
  }
  if (!found) return false;               // pas d'IMU → mode démo UI

  if (!writeReg(kRegPwrMgmt1, 0x80)) return false;  // reset
  delay(100);
  if (!writeReg(kRegPwrMgmt1, 0x01)) return false;  // wake + horloge PLL gyro X
  delay(10);
  if (!writeReg(kRegConfig,      kDlpfCfg))   return false;
  if (!writeReg(kRegSmplrtDiv,   kSmplrtDiv)) return false;
  if (!writeReg(kRegGyroConfig,  kGyroFs))    return false;
  if (!writeReg(kRegAccelConfig, kAccelFs))   return false;
  delay(20);

  Raw r;
  if (!readRaw(r)) return false;
  s_accPitch = accelPitch(r) - kMountOffsetDeg;
  s_pitch    = s_accPitch;                // amorce le filtre sur l'accel
  s_havePrev     = false;                 // vivacité : repart de zéro
  s_frozenStreak = 0;
  s_ok = true;
  return true;
}

bool calibrate(uint16_t samples) {
  if (!s_ok) return false;

  // Le capteur produit un échantillon toutes les 5 ms (kSmplrtDiv = 4) :
  // lire plus vite relit le même registre. L'ancienne boucle à ~1,4 kHz
  // donnait 400 lectures ≈ 60 échantillons distincts lus 7× chacun — biais
  // √7 fois plus bruité qu'annoncé (REVIEW_CLAUDE.md M18). On lit donc à
  // ~200 Hz (delay(5) + ~0,4 ms de transaction > 5 ms : jamais deux fois
  // le même échantillon) pendant ~2 s, et readLive() écarte de toute façon
  // les trames figées (M9), qui ne comptent pas.
  double sumGyro = 0.0, sumPitch = 0.0;
  uint16_t got = 0;
  for (uint16_t i = 0; i < samples; i++) {
    Raw r;
    if (readLive(r)) {
      sumGyro  += gyroPitchRaw(r);
      sumPitch += accelPitch(r);
      got++;
    }
    delay(5);                             // 200 Hz → 400 pts ≈ 2,2 s (setup())
  }
  if (got < samples / 2) return false;    // bus instable / figé : on ne fige rien

  s_gyroBias = (float)(sumGyro / got);
  s_accPitch = (float)(sumPitch / got) - kMountOffsetDeg;
  s_pitch    = s_accPitch;
  return true;
}

bool update(float dtSec) {
  if (!s_ok) return false;

  Raw r;
  if (!readLive(r)) return false;         // trame perdue OU figée → on garde l'état

  s_tempC    = (float)r.t / 340.0f + 36.53f;
  s_rate     = kGyroPitchSign * ((float)gyroPitchRaw(r) - s_gyroBias) / kGyroLsb;
  s_accPitch = accelPitch(r) - kMountOffsetDeg;

  // Le recalage accel n'a de sens que si le vecteur mesuré vaut ~1 g :
  // pendant une accélération franche (démarrage, choc) il pointe faux,
  // on fait alors confiance au seul gyro.
  const float ax = (float)r.ax / kAccelLsb;
  const float ay = (float)r.ay / kAccelLsb;
  const float az = (float)r.az / kAccelLsb;
  const float norm = sqrtf(ax * ax + ay * ay + az * az);
  const bool  trustAccel = (norm > 0.80f && norm < 1.20f);

  const float gyroAngle = s_pitch + s_rate * dtSec;
  s_pitch = trustAccel ? (kAlpha * gyroAngle + (1.0f - kAlpha) * s_accPitch)
                       : gyroAngle;
  return true;
}

float pitchDeg()      { return s_pitch; }
float pitchRateDps()  { return s_rate; }
float accelPitchDeg() { return s_accPitch; }
float tempC()         { return s_tempC; }
bool  ok()            { return s_ok; }

} // namespace Imu
