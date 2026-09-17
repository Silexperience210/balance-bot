#pragma once
// ═══════════════════════════════════════════════════════════════════
// BalanceBot — configuration centralisée (pins + constantes)
// Carte : LilyGo T-Display-S3-Touch (ESP32-S3R8, 16MB, 8MB OPI PSRAM)
// Référence pinout : repo officiel Xinyuan-LilyGO/T-Display-S3
// Ce fichier est la SOURCE UNIQUE des affectations. Les modules le
// lisent ; aucun agent ne doit le modifier sans validation Hermes.
// ═══════════════════════════════════════════════════════════════════

// ── Écran / Touch (occupés — ne pas réutiliser) ────────────────────
#define PIN_LCD_BL      38
#define PIN_LCD_D0      39
#define PIN_LCD_D1      40
#define PIN_LCD_D2      41
#define PIN_LCD_D3      42
#define PIN_LCD_D4      45
#define PIN_LCD_D5      46
#define PIN_LCD_D6      47
#define PIN_LCD_D7      48
#define PIN_POWER_ON    15     // DOIT être HIGH avant usage écran
#define PIN_LCD_RES     5
#define PIN_LCD_CS      6
#define PIN_LCD_DC      7
#define PIN_LCD_WR      8
#define PIN_LCD_RD      9
#define PIN_BUTTON_1    0      // BOOT
#define PIN_BUTTON_2    14
#define PIN_BAT_VOLT    4      // ADC batterie (USB débranché)
#define PIN_TOUCH_INT   16
#define PIN_TOUCH_RES   21

// ── I2C (IMU MPU6050 — bus Qwiic/STEMMA) ───────────────────────────
#define PIN_IIC_SCL     17
#define PIN_IIC_SDA     18

// ── Servos (GPIO libres) ───────────────────────────────────────────
// Mécanique v3 RÉELLE (chassis/NOTES_v3.md, docs/photos/robot-reel.jpg) :
// deux ROUES entraînées par des servos 9 g à ROTATION CONTINUE 360°
// (taille SG90/FS90R). Les GPIO 1 et 2 pilotent ces deux roues. Le nom
// « FOOT » est conservé dans le code (feet.cpp) : l'API commande une
// VITESSE de roue et intègre la course φ, ce qui vaut pour les deux
// matériels — voir FEET_MODE_CONTINUOUS ci-dessous.
#define SERVO_FOOT_L    1      // roue gauche — servo continu (cf. FEET_MODE_CONTINUOUS)
#define SERVO_FOOT_R    2      // roue droite — servo continu (cf. FEET_MODE_CONTINUOUS)
#define SERVO_HEAD_PAN  3      // tête : rotation horizontale (SG90 standard)
#define SERVO_HEAD_TILT 10     // tête : inclinaison (SG90 standard)

// ── TYPE des servos de ROUES — sélecteur de mode (compile-time) ─────
// Deux matériels possibles sur les mêmes broches, même boîtier 23×12.2×29 :
//   0 = SG90 STANDARD 180° (ancienne mécanique v3.1 « pieds en arc ») : le
//       servo ne connaît que la POSITION. feet.cpp intègre la vitesse du
//       PID (°/s) en position (°) et écrit l'angle. Débattement FINI.
//   1 = servo à ROTATION CONTINUE 360° (ROBOT RÉEL) : le servo ne connaît
//       que la VITESSE (1500 µs = arrêt, ±500 µs = pleine vitesse). La
//       sortie du PID part DIRECTEMENT au servo, sans intégration position.
//
// POURQUOI 1 EST LE BON MODE POUR CE MATÉRIEL : un servo continu n'a pas
// d'asservissement de position interne — lui envoyer un « angle » n'a
// aucun sens, l'impulsion est lue comme une vitesse. Avec le mode 0 sur
// des servos continus, l'écriture d'une position croissante (ex. 1600 µs)
// ferait TOURNER la roue en continu au lieu de la déplacer de quelques
// degrés : le robot partirait à pleine vitesse au premier écart de pitch.
// C'est aussi ce que simulent sim/balancebot_sim.py et le simulateur web
// (MODE = "roue") — la règle d'or (scripts/verifier-regle-or.py) exige que
// firmware et simulateurs disent la même chose.
//
// Le mode continu conserve malgré tout l'intégration interne de φ : le
// soft clamp de balance.cpp (Feet::angleAvg()) et la butée dure lisent
// cette course « conventionnelle ». Voir feet.cpp pour la calibration
// µs/(°/s) et le trim du neutre.
//
// Revenir au mode POSITION : compiler avec -DFEET_MODE_CONTINUOUS=0 ou
// changer la valeur ci-dessous — un seul #define, rien d'autre à toucher.
#ifndef FEET_MODE_CONTINUOUS
#define FEET_MODE_CONTINUOUS 1
#endif
// COURSE FINIE (arc) ou LIBRE (roue). Une roue tourne sans fin : la butée
// dure ±FOOT_HARD_DEG de feet.cpp, le soft clamp de butée et le « panic »
// à kFootPanicDeg de balance.cpp n'ont plus d'objet — et le simulateur en
// MODE = "roue" ne les modélise pas (règle d'or). Ils restent VITAUX en
// mode position (arc) : dérivé du mode, surchargeable par -D si un jour
// un servo continu entraînait un arc à course finie.
#ifndef FOOT_TRAVEL_LIMITED
#define FOOT_TRAVEL_LIMITED (!FEET_MODE_CONTINUOUS)
#endif

// ── Ultrason HC-SR04 ───────────────────────────────────────────────
#define PIN_US_TRIG     11
#define PIN_US_ECHO     12

// ── Constantes robot ───────────────────────────────────────────────
#define BALANCE_LOOP_HZ 200    // fréquence de la boucle d'équilibre
// Butée DURE du pied en arc (°) — SOURCE UNIQUE, active seulement si
// FOOT_TRAVEL_LIMITED. feet.cpp l'applique (clamp de φ + coupure explicite
// de la commande) et balance.cpp s'en sert pour le soft clamp qui s'ouvre
// AVANT elle. Deux littéraux 45 recopiés dans deux fichiers finissent
// toujours par diverger.
#define FOOT_HARD_DEG   45.0f
#define HEAD_PAN_MIN    0      // degrés
#define HEAD_PAN_MAX    180
#define HEAD_TILT_MIN   20     // éviter de viser le sol
#define HEAD_TILT_MAX   90
#define US_MAX_CM       150    // portée utile du HC-SR04
#define US_STOP_CM      25     // distance d'arrêt : ne plus avancer, reculer doucement
#define US_SLOW_CM      60     // sous cette distance (et > US_STOP_CM) : ralentir
// Seuil « batterie faible » d'une cellule LiPo 1S : sous 3.5 V la cellule
// n'a plus qu'environ 10-15 % de charge et sa tension s'effondre vite sous
// l'appel de courant des servos. À distinguer de « pas de batterie » (USB
// seul), signalé par batteryV = -1 (cf. battery.cpp).
#define BAT_LOW_V       3.5f

// ── Répartition sur les deux cœurs ─────────────────────────────────
// 1 = la boucle d'équilibre tourne dans SA tâche FreeRTOS, épinglée sur le
//     cœur BALANCE_TASK_CORE à priorité haute ; loop() (cœur 1, Arduino)
//     garde l'écran, la tête + ultrason, la batterie et la surveillance.
//     Le pulseIn() de l'ultrason (jusqu'à 9,5 ms) ne peut plus décaler un
//     pas d'équilibre de 5 ms.
// 0 = compilation de REPLI : tout dans loop() sur le cœur 1, exactement
//     comme avant (à utiliser si la version deux cœurs se comporte mal).
// Le cadencement (BALANCE_LOOP_HZ) et la loi de commande sont IDENTIQUES
// dans les deux cas : seul l'appelant de Balance::loop() change.
#ifndef BALANCE_SPLIT_CORES
#define BALANCE_SPLIT_CORES 1
#endif
#define BALANCE_TASK_CORE   0      // cœur 0 = PRO_CPU (WiFi y vit aussi, à priorité 23)
#define BALANCE_TASK_PRIO   (configMAX_PRIORITIES - 1)   // 24 : au-dessus du WiFi
#define BALANCE_TASK_STACK  8192   // octets (Wire + ESP32Servo + flottants)
#define TUNER_TASK_CORE     (BALANCE_SPLIT_CORES ? 1 : 0)  // le serveur HTTP cède le cœur 0

// ── Arrêt sûr ──────────────────────────────────────────────────────
// Boucle d'équilibre FIGÉE : si aucun pas n'a démarré depuis ce délai
// (tâche bloquée sur un verrou, plantage partiel), la surveillance de
// loop() coupe les roues (PWM détaché). 200 ms = 40 pas manqués, bien
// au-delà de la gigue normale, et en deçà d'une roue qui « part » sur la
// dernière consigne pendant qu'un robot tombé glisse au sol.
#define BALANCE_STALL_MS    200
// Arrêt d'urgence matériel : appui long sur PIN_ESTOP → roues coupées,
// écran « ARRÊT », verrouillé jusqu'au RESET. BOOT (GPIO 0) est une
// broche de strapping SEULEMENT au reset : à l'exécution c'est une entrée
// ordinaire avec pull-up et bouton câblés sur la carte — utilisable.
// Conséquence : relâcher BOOT AVANT d'appuyer sur RESET, sinon le S3
// démarre en mode téléversement (BOOT bas au reset) au lieu du firmware.
#define PIN_ESTOP           PIN_BUTTON_1   // BOOT (GPIO 0)
#define ESTOP_HOLD_MS       1000
// Le banc web (ouvrir/fermer l'AP) passait par un appui long sur BOOT :
// deux appuis longs sur le même bouton sont ambigus, l'arrêt d'urgence
// doit être sans équivoque. Le toggle migre sur KEY (GPIO 14, second
// bouton de la T-Display-S3, non-strapping, libre).
#define PIN_TUNER_TOGGLE    PIN_BUTTON_2   // KEY (GPIO 14)
#define TUNER_TOGGLE_HOLD_MS 1500

// ── Évitement d'obstacle (head.cpp → BotState → balance.cpp) ────────
// Le robot est un ÉQUILIBREUR d'abord : l'évitement n'agit QUE sur les
// consignes de déplacement (cmdForward / cmdTurn, avant le lissage), jamais
// sur le PID ni sur les roues. Valeurs en unités de consigne UI (-100..100).
#define AVOID_SLOW_CMD      40     // < US_SLOW_CM : marche avant plafonnée à 40 %
#define AVOID_BACK_CMD      20     // < US_STOP_CM : recul doux à 20 % (≈ 1,2° de consigne)
#define AVOID_BACK_MAX_MS   1500   // recul borné dans le temps (capteur masqué → on ne recule pas à l'infini)
#define AVOID_TURN_CMD      40     // pivot vers le côté libre pendant le recul
#define AVOID_TURN_SIGN     (+1)   // -1 si le robot pivote VERS l'obstacle au premier essai
#define AVOID_SIDE_DEAD_DEG 10     // |pan − 90| sous ce seuil : obstacle « en face », côté par défaut
#define AVOID_DEFAULT_SIDE  (+1)   // côté choisi quand l'obstacle est en face
#define US_CLEAR_CM         35     // hystérésis : fin d'évitement seulement au-delà (> US_STOP_CM)
// En équilibre, la tête balaie ±HEAD_BALANCE_SWEEP_DEG autour du centre
// (0 = tête fixe comme avant) : c'est ce qui donne un sens à « l'angle où
// l'obstacle a été vu ». Tête légère (SG90 + HC-SR04 ≈ 20 g) à 30 °/s :
// perturbation négligeable devant les corrections de roues.
#define HEAD_BALANCE_SWEEP_DEG 30
