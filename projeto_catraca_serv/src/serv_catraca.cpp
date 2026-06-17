#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <uri/UriBraces.h>
#include <LittleFS.h>
#include <Preferences.h>

#include <WiFiClient.h> 
#include "certificados.h" 
#include <MQTT.h>

WiFiClient conexao; 
MQTTClient mqtt(1000);

Preferences preferencias;

WebServer servidor(80);

void reconectarMQTT() {
  int tentativas = 0;

  while (!mqtt.connected() && tentativas < 5) {
    Serial.print("Conectando MQTT..."); 

    String id = preferencias.getString("mqttID", "");
    String login = preferencias.getString("mqttLogin", "");
    String senha = preferencias.getString("mqttSenha", "");

    mqtt.connect(id.c_str(), login.c_str(), senha.c_str());

    Serial.print(".");
    delay(1000);
    tentativas++;
  }

  if (mqtt.connected()){
    Serial.println(" conectado!");
    String topic = preferencias.getString("mqttTopic", "");
    if (!topic.isEmpty()) {
      mqtt.subscribe(topic.c_str());
    }
  }
  else {
    Serial.println(" falhou!");
  }
}


void reconectarWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  String ssid = preferencias.getString("wifi", "");
  String senha = preferencias.getString("senha", "");

  if (ssid.isEmpty()) {
    Serial.println("SSID nao configurado.");
    return;
  }

  WiFi.begin(ssid.c_str(), senha.c_str());

  int tentativas = 0;
  while (WiFi.status() != WL_CONNECTED && tentativas < 20) {
    delay(500);
    Serial.print(".");
    tentativas++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nConectado!");
    Serial.println(WiFi.localIP());
  }
  else {
    Serial.println("\nFalha ao conectar.");
    WiFi.softAP("ESP32-Config");
    Serial.print("IP AP: ");
    Serial.println(WiFi.softAPIP());
  }
}

void login() {
  File arquivo = LittleFS.open("/login.html", "r");
  if (!arquivo) {
    servidor.send(500, "text/html", "Erro no HTML");
    return;
  }
 
  String html = arquivo.readString();
  arquivo.close();
 
  html.replace("{{erro}}", ""); // mensagem de erro inicial vazia
 
  servidor.send(200, "text/html", html);
}

void validarLogin() {
  String usuario = servidor.arg("usuario");
  String senha = servidor.arg("senha");

  if (usuario == "admin" && senha == "1234") {
    servidor.send(200, "text/html", "Login OK!");
  } 
  else {
    File arquivo = LittleFS.open("/login.html", "r");
    if (!arquivo) {
      servidor.send(500, "text/html", "Erro no HTML");
      return;
    }

    String html = arquivo.readString();
    arquivo.close();

    html.replace("{{erro}}", "Usuario ou senha invalidos");

    servidor.send(200, "text/html", html);
  }
}

void inicio() {
  File arq = LittleFS.open("/inicio.html", "r");
  if (!arq) {
    servidor.send(404, "text/plain", "Arquivo nao encontrado");
    return;
  }

  String html = arq.readString();
  arq.close();

  html.replace("{{wifi}}", preferencias.getString("wifi", ""));
  html.replace("{{senha}}", preferencias.getString("senha", ""));
  html.replace("{{mqttHost}}", preferencias.getString("mqttHost", ""));
  html.replace("{{mqttPort}}", String(preferencias.getInt("mqttPort", 1883)));
  html.replace("{{mqttTopic}}", preferencias.getString("mqttTopic", ""));
  html.replace("{{mqttID}}", preferencias.getString("mqttID", ""));
  html.replace("{{mqttLogin}}", preferencias.getString("mqttLogin", ""));
  html.replace("{{mqttSenha}}", preferencias.getString("mqttSenha", ""));

  servidor.send(200, "text/html", html);
}

void salvarConfiguracao() {
  String wifi = servidor.arg("wifi");
  String senha = servidor.arg("senha");

  String mqttHost = servidor.arg("mqttHost");
  int mqttPort = servidor.arg("mqttPort").toInt();
  String mqttTopic = servidor.arg("mqttTopic");

  String mqttID = servidor.arg("mqttID");
  String mqttLogin = servidor.arg("mqttLogin");
  String mqttSenha = servidor.arg("mqttSenha");

  preferencias.putString("wifi", wifi);
  preferencias.putString("senha", senha);

  preferencias.putString("mqttHost", mqttHost);
  preferencias.putInt("mqttPort", mqttPort); //verificar int/long possivel string...
  preferencias.putString("mqttTopic", mqttTopic);

  preferencias.putString("mqttLogin", mqttLogin);
  preferencias.putString("mqttID", mqttID);
  preferencias.putString("mqttSenha", mqttSenha);

  Serial.println("Configurações salvas.");
  servidor.send(200, "text/plain", "Configuracao salva. Reiniciando...");
  delay(1000);
  ESP.restart();
}

void recebeuMensagem(String topico, String conteudo) { 
  Serial.println(topico + ": " + conteudo); 
}

void setup() {
  Serial.begin(115200);
  delay(500);

  preferencias.begin("ajustesUsuario", false);

  if (!LittleFS.begin()) {
    Serial.println("LittleFS falhou!");
    while (true);
  }

  reconectarWiFi();

  String mqttHost = preferencias.getString("mqttHost", "");
  int mqttPort = preferencias.getInt("mqttPort", 1883);

  mqtt.begin(mqttHost.c_str(), mqttPort, conexao);
  mqtt.onMessage(recebeuMensagem); 

  servidor.on("/login", HTTP_GET, login);
  servidor.on("/auth", HTTP_POST, validarLogin);
  servidor.on("/", HTTP_GET, inicio);
  servidor.on("/salvar", HTTP_POST, salvarConfiguracao);

  servidor.begin();
}


void loop() {
  reconectarWiFi();
  servidor.handleClient();

  if (WiFi.status() != WL_CONNECTED) return;

  reconectarMQTT(); 
  mqtt.loop();
}