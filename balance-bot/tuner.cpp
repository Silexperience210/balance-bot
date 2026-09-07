// ═══════════════════════════════════════════════════════════════════
// BalanceBot — module D · banc de réglage web à chaud (mode AP)
//
// BUT : régler Kp/Ki/Kd et lire la télémétrie depuis un téléphone,
// SANS recompiler ni reflasher, pendant que la main tient le robot.
//
// La carte ouvre un point d'accès « BalanceBot-Tune », on s'y connecte
// et on ouvre http://192.168.4.1/.
//
// SÉCURITÉ : le réseau est OUVERT (sans mot de passe). C'est délibéré —
// c'est un réseau de réglage d'atelier, éphémère, sans passerelle vers
// Internet, et taper une clé WPA sur un téléphone d'une seule main
// pendant qu'on rattrape un robot qui tombe est le contraire du but
// recherché. Quiconque est à portée radio peut piloter les gains : ne
// pas laisser tourner ce firmware hors de l'atelier.
//
// NON-INTRUSIF : ce module est complètement inerte tant qu'aucun client
// ne le sollicite. Si softAP() échoue, begin() retourne false et loop()
// devient un no-op — le robot se comporte exactement comme avant.
// ═══════════════════════════════════════════════════════════════════

#include "tuner.h"
#include <WiFi.h>
#include <WebServer.h>

namespace {

constexpr char kSsid[] = "BalanceBot-Tune";

// Un client est considéré « présent » tant qu'il a dialogué il y a
// moins de ça (le navigateur interroge /api/state toutes les 150 ms).
constexpr unsigned long kActiveWindowMs = 2000;

// Au-delà, une requête a mordu sur le temps de la boucle d'équilibre :
// on le signale sur le port série (diagnostic, pas une erreur fatale).
constexpr unsigned long kSlowRequestUs = 5000;

WebServer      s_server(80);
bool           s_up          = false;   // AP + serveur démarrés
unsigned long  s_lastReqMs   = 0;
bool           s_stationSeen = false;   // ≥1 station associée (cache 20 Hz)

// ── Page embarquée ─────────────────────────────────────────────────
// Mobile-first, sombre, zéro dépendance externe (aucun CDN : l'AP n'a
// pas d'accès Internet, un <script src> distant ne chargerait jamais).
const char kPage[] PROGMEM = R"HTML(<!DOCTYPE html><html lang="fr"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>BalanceBot</title><style>
*{box-sizing:border-box}
body{margin:0;padding:10px;background:#0d0f12;color:#e8e8e8;font:15px system-ui,sans-serif}
h1{font-size:14px;margin:0 0 8px;color:#ff9d2e;letter-spacing:.12em}
.c{background:#181b20;border-radius:10px;padding:10px;margin-bottom:10px}
#p{font-size:46px;font-weight:600;text-align:center;line-height:1.1;font-variant-numeric:tabular-nums}
#p.up{color:#3ddc6b}
.t{display:flex;justify-content:space-between;font-size:12px;color:#8b94a0;margin-top:6px}
.t b{display:block;color:#e8e8e8;font-size:16px;font-variant-numeric:tabular-nums}
label{display:flex;justify-content:space-between;font-size:14px;margin-bottom:2px}
label b{color:#ff9d2e;font-variant-numeric:tabular-nums}
input{width:100%;height:36px;accent-color:#ff9d2e}
.r{margin-bottom:10px}.r:last-child{margin-bottom:0}
button{width:100%;height:64px;font-size:22px;font-weight:700;border:0;border-radius:10px;background:#2a2f38;color:#e8e8e8}
button.on{background:#c0392b}
#s{text-align:center;font-size:12px;color:#667;margin-top:8px}
</style></head><body>
<h1>BALANCEBOT &middot; R&Eacute;GLAGE</h1>
<div class="c"><div id="p">--</div><div class="t">
<div>vitesse<b id="r">--</b></div><div>pied G<b id="fl">--</b></div>
<div>pied D<b id="fr">--</b></div><div>boucle<b id="hz">--</b></div></div></div>
<div class="c">
<div class="r"><label>Kp<b id="vkp">--</b></label><input type="range" id="kp" min="0" max="100" step="0.5"></div>
<div class="r"><label>Ki<b id="vki">--</b></label><input type="range" id="ki" min="0" max="2000" step="10"></div>
<div class="r"><label>Kd<b id="vkd">--</b></label><input type="range" id="kd" min="0" max="10" step="0.1"></div>
</div>
<button id="b">&Eacute;QUILIBRE</button>
<div id="s">connexion&hellip;</div>
<script>
var E=function(i){return document.getElementById(i)},K=['kp','ki','kd'];
var drag=0,tmr=0,bal=0,first=1;
var FORM={method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'}};
function post(u,b){var o={};for(var k in FORM)o[k]=FORM[k];o.body=b;return fetch(u,o)}
K.forEach(function(k){var s=E(k);
 // pendant le glissement : affichage seul, on n'inonde pas la carte
 s.oninput=function(){drag=1;E('v'+k).textContent=s.value};
 // au relacher du doigt : un seul POST, 300 ms apres le dernier geste
 s.onchange=function(){drag=0;clearTimeout(tmr);tmr=setTimeout(send,300)};
});
function send(){tmr=0;post('/api/gains','kp='+E('kp').value+'&ki='+E('ki').value+'&kd='+E('kd').value)}
E('b').onclick=function(){post('/api/bal','on='+(bal?0:1))};
function tick(){fetch('/api/state').then(function(r){return r.json()}).then(function(d){
 E('p').textContent=d.pitch.toFixed(1)+'°';
 E('p').className=d.up?'up':'';
 E('r').textContent=Math.round(d.rate)+'°/s';
 E('fl').textContent=d.footL+'°';E('fr').textContent=d.footR+'°';
 E('hz').textContent=Math.round(d.hz)+' Hz';
 bal=d.balancing;
 E('b').textContent=bal?'ARRÊTER':'ÉQUILIBRE';
 E('b').className=bal?'on':'';
 // on ne recale les sliders que hors geste : la carte fait autorite
 // (valeurs bornees), mais elle ne doit pas bouger le doigt de l'user
 if(!drag&&!tmr){K.forEach(function(k){E(k).value=d[k];E('v'+k).textContent=d[k]});first=0}
 E('s').textContent='192.168.4.1 — en ligne';
}).catch(function(){E('s').textContent='hors ligne…'})}
setInterval(tick,150);tick();
</script></body></html>)HTML";

// ── Routes ─────────────────────────────────────────────────────────

void touchReq() { s_lastReqMs = millis(); }

void handleRoot() {
  touchReq();
  s_server.send_P(200, "text/html", kPage);
}

// Télémétrie compacte. « balancing » = ARMÉ (miroir du bouton EQUIL. de
// l'écran, c'est ce que le bouton de la page bascule) ; « up » = le
// robot tient effectivement debout (g_state.balancing).
void handleState() {
  touchReq();
  float kp, ki, kd;
  Balance::getGains(kp, ki, kd);
  char buf[256];
  snprintf(buf, sizeof(buf),
           "{\"pitch\":%.1f,\"rate\":%.0f,\"footL\":%d,\"footR\":%d,"
           "\"hz\":%.0f,\"kp\":%.1f,\"ki\":%.0f,\"kd\":%.2f,"
           "\"balancing\":%d,\"up\":%d}",
           g_state.pitchDeg, Balance::pitchRateDps(),
           g_state.footLDeg, g_state.footRDeg, g_state.balanceHz,
           kp, ki, kd,
           Balance::isEnabled() ? 1 : 0, g_state.balancing ? 1 : 0);
  s_server.send(200, "application/json", buf);
}

// Un argument absent laisse le gain inchangé (NaN → ignoré par setGains).
float argOrNan(const char* name) {
  if (!s_server.hasArg(name)) return NAN;
  return s_server.arg(name).toFloat();
}

void handleGains() {
  touchReq();
  Balance::setGains(argOrNan("kp"), argOrNan("ki"), argOrNan("kd"));
  float kp, ki, kd;
  Balance::getGains(kp, ki, kd);
  Serial.printf("TUNER : gains → Kp=%.1f Ki=%.0f Kd=%.2f\n", kp, ki, kd);
  s_server.send(200, "text/plain", "ok");
}

// Même chemin que le bouton EQUIL. de l'écran : Balance::setEnabled().
void handleBal() {
  touchReq();
  const bool on = s_server.hasArg("on") && s_server.arg("on").toInt() != 0;
  Balance::setEnabled(on);
  Serial.printf("TUNER : équilibre %s\n", on ? "ON" : "OFF");
  s_server.send(200, "text/plain", "ok");
}

} // namespace

namespace Tuner {

bool begin() {
  WiFi.mode(WIFI_AP);
  // Réseau ouvert (cf. bandeau en tête de fichier), canal 1, 4 clients max.
  if (!WiFi.softAP(kSsid, nullptr, 1, 0, 4)) {
    Serial.println("BANC WEB  : ÉCHEC softAP — tuner désactivé");
    WiFi.mode(WIFI_OFF);                 // pas de radio qui traîne pour rien
    return false;
  }
  s_server.on("/",           HTTP_GET,  handleRoot);
  s_server.on("/api/state",  HTTP_GET,  handleState);
  s_server.on("/api/gains",  HTTP_POST, handleGains);
  s_server.on("/api/bal",    HTTP_POST, handleBal);
  s_server.onNotFound([]() { s_server.send(404, "text/plain", "404"); });
  s_server.begin();
  s_up = true;
  Serial.print("BANC WEB  : OK — SSID « " );
  Serial.print(kSsid);
  Serial.print(" » (ouvert) → http://");
  Serial.println(WiFi.softAPIP());
  return true;
}

void loop() {
  if (!s_up) return;                     // no-op total si l'AP n'a pas démarré

  // Cadence : 20 Hz max. Le .ino gère en plus l'exclusion avec la boucle
  // d'équilibre ; ce garde-fou reste local pour que loop() soit sûr à
  // appeler aussi souvent qu'on veut.
  static unsigned long tLast = 0;
  const unsigned long now = millis();
  if (now - tLast < 50) return;
  tLast = now;

  s_stationSeen = (WiFi.softAPgetStationNum() > 0);

  const unsigned long t0 = micros();
  s_server.handleClient();
  const unsigned long dt = micros() - t0;
  if (dt > kSlowRequestUs) {
    Serial.printf("TUNER : requête lente %lu us\n", dt);
  }
}

// « Un client est là » : une station associée ET un échange récent. Les
// deux, sinon un téléphone qui reste connecté écran éteint garderait le
// voyant allumé indéfiniment.
bool active() {
  return s_up && s_stationSeen &&
         (millis() - s_lastReqMs) < kActiveWindowMs && s_lastReqMs != 0;
}

unsigned long lastRequestMs() { return s_lastReqMs; }

} // namespace Tuner
