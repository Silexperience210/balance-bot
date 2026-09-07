# BalanceBot — robot auto-équilibré sur pieds en arc

ESP32-S3 (LilyGo T-Display S3 Touch 3,5") + MPU6050 + 4× SG90 + HC-SR04.
Firmware Arduino (200 Hz, PID + réglage web à chaud), châssis 3D PLA (P1S).

```
balance-bot/            ← FIRMWARE (le code qui tourne sur la carte)
  balance-bot.ino       assemblage + cadences (Balance 200 Hz, UI 60, Head 50)
  config.h              pins (immuable)
  interfaces.h          BotState partagé (contrat inter-modules)
  imu.cpp/h             MPU6050 (I2C 400 kHz, filtre complémentaire)
  balance.cpp           PID d'équilibre + recentrage (module A)
  feet.cpp/h            actionneur POSITION : pieds en arc (ex-roues)
  head.cpp              tête pan/tilt + ultrason (adaptatif)
  battery.cpp/h         ADC batterie (−1 = USB seul, seuil 3,5 V)
  ui.cpp                écran 320×170 paysage (CST816) + boutons
  tuner.cpp/h           banc de réglage web à chaud (AP BalanceBot-Tune)
  build.sh              compile + flash (defines 170×320, /dev/ttyACM0)
chassis/                châssis v2 : gen_chassis.py + STL + FIT_NOTES
sim/                    simulateur 1D (pendule inversé, contrôleur identique)
TEST_PROTOCOL.md        protocole du premier essai debout (à lire avant)
BACKLOG.md              suivi du marathon d'amélioration
```

## Points clés hardware (douloureusement appris)
- Écran réel : **ST7789 170×320** (offset 35 px, CGRAM_OFFSET) — PAS 240×320.
  Rotation paysage : `setRotation(3)` + touch `setRotation(1)`, init ST7789V.
- Touch : **CST816 self** sur cartes récentes (`TOUCH_MODULES_CST_SELF`).
- Servos : **jamais sur le 3V3/5V de la carte** (brownout → reboot) — rail 5-6V
  séparé + GND commun obligatoire. GPIO 1/2 pieds, 3 pan, 10 tilt.
- MPU6050 : SDA 18 / SCL 17, 0x68. US : GPIO 11/12 (diviseur ECHO requis).
- Upload : `/dev/ttyACM0` (USB JTAG), jamais sketch.yaml (casse les libs).

## Réglage d'équilibre
Gains validés par simulation (`sim/balancebot_sim.py`) : **Kp 25, Ki 500,
Kd 0.5** — condition de stabilité : Ki > g/R ≈ 300. Réglage à chaud sans
recompiler : se connecter au WiFi **BalanceBot-Tune** → http://192.168.4.1/
(sliders Kp/Ki/Kd + télémétrie). Signe du câblage : `kAccelPitchSign`
(imu.cpp).

## Méthode de développement
Délégation à Claude Opus par lots (brief → implémentation → vérification
indépendante par Hermes : compile + contrôle du code → flash → commit).
Le simulateur 1D a évité de tester en réel des gains qui ne pouvaient pas
tenir le robot (Ki 20 au lieu de 300+).
