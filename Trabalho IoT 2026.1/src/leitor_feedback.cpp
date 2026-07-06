#include <Arduino.h>
#include <GxEPD2_BW.h>
#include <U8g2_for_Adafruit_GFX.h>
#include <SPI.h>
#include <MFRC522.h>
#include <WiFi.h>
#include <time.h>
#include <WiFiClient.h>
#include <WiFiClientSecure.h>
#include "certificados.h"
#include <MQTT.h>
#include <ArduinoJson.h>
#include <WebServer.h>
#include <LittleFS.h>
#include "AS5600.h"
#include "Wire.h"

// Constantes Globais
String msg = "";
String placeholder_Uid = "";
long lastPosition = 0;
const int relay = 4; // Valor arbitrário
unsigned long last_instance = 0;
bool showing_home = true;
bool showing_welcome = false;
bool showing_denied = false;
bool setup_mode = false;
bool showing_waiting = false;
bool showing_setup = false;
bool passage = false;


// AS5600 (entrada/saída)
AS5600 as5600;

// Servidor Web (cadastro de funcionários)
WebServer servidor(80);
String pending_uid = "";

// Tela e-paper
U8G2_FOR_ADAFRUIT_GFX fonts;
GxEPD2_290_T94_V2 modeloTela(10, 14, 15, 16);
GxEPD2_BW<GxEPD2_290_T94_V2, GxEPD2_290_T94_V2::HEIGHT> screen(modeloTela);

// RFiD
MFRC522 rfid(46, 17);
MFRC522::MIFARE_Key chaveA = {{0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF}};

// MQTT
WiFiClientSecure conexaoSegura;
MQTTClient mqtt(1000);

// Funções auxiliares
String doubleDigit(int num) {
  return (num < 10 ? "0" : "") + String(num);
}

// Funções da Tela
void home_screen() {
  showing_home = true;
  screen.fillScreen(GxEPD_WHITE);

  fonts.setFont( u8g2_font_helvB24_te );
  fonts.setFontMode(1);
  fonts.setCursor(35, 65);
  fonts.print("Aproxime o Cartão.");

  // Horário na Tela
  fonts.setFont( u8g2_font_helvR14_te  );
  fonts.setFontMode(1);

  struct tm timeinfo;
  getLocalTime(&timeinfo);
  String current_time_str = doubleDigit(timeinfo.tm_hour) + ":"
    + doubleDigit(timeinfo.tm_min);
  String current_date_str = doubleDigit(timeinfo.tm_mday) + "/"
    + doubleDigit(timeinfo.tm_mon + 1) + "/"
    + String(timeinfo.tm_year + 1900);

  String now_str = current_date_str + " - " + current_time_str;
  fonts.setCursor(75, 110);
  fonts.print(now_str);

  screen.display(true);
}

void welcome_screen(String worker_name) {
  showing_welcome = true;
  showing_home = false;
  screen.fillScreen(GxEPD_WHITE);

  fonts.setFont( u8g2_font_helvB24_te );
  fonts.setFontMode(1);
  fonts.setCursor(60, 50);
  fonts.print("Bem-Vinda(o)!");

  fonts.setFont( u8g2_font_helvR18_te  );
  fonts.setFontMode(1);
  fonts.setCursor(20, 75);
  fonts.print(worker_name);

  digitalWrite(relay, LOW);
  screen.display(true);
}

void access_denied_screen() {
  showing_denied = true;
  showing_home = false;
  screen.fillScreen(GxEPD_WHITE);

  fonts.setFont( u8g2_font_helvB24_te );
  fonts.setFontMode(1);
  fonts.setCursor(60, 50);
  fonts.print("Acesso Negado");

  screen.display(true);
}

void awaiting_screen() {
  showing_waiting = true;
  showing_home = false;
  screen.fillScreen(GxEPD_WHITE);

  fonts.setFont( u8g2_font_helvB10_te );
  fonts.setFontMode(1);
  fonts.setCursor(25, 60);
  fonts.print("Aguardando leitura do novo cartão...");

  screen.display(true);
}

// Exibe confirmação no display e disponibiliza o UID na página de cadastro
void setup_screen_adminControl(String Uid) {
  showing_setup = true;
  showing_home = false;
  pending_uid = Uid;
  screen.fillScreen(GxEPD_WHITE);
  
  fonts.setFont( u8g2_font_helvB24_te );
  fonts.setFontMode(1);
  fonts.setCursor(53, 70);
  fonts.print("Cartão lido!");
  fonts.setFont(u8g2_font_helvR10_te);
  fonts.setFontMode(1);
  fonts.setCursor(43, 95);
  fonts.print("Complete o cadastro no sistema.");
}

// Funções MMQTT
void reconectarMQTT() {
  if (!mqtt.connected()) {
    Serial.print("Conectando MQTT...");
    while(!mqtt.connected()) {
      mqtt.connect("esp32_teste", "aula", "zowmad-tavQez");
      Serial.print(".");
      delay(1000);
    }
    Serial.println(" conectado!");

    mqtt.subscribe("A3/catraca/resposta");
  }
}

void recebeuMensagem(String topic, String content) {
  Serial.println(topic + ": " + content);

  if (topic == "A3/catraca/resposta") {
    JsonDocument access_answer;
    deserializeJson(access_answer, content);
    String worker_permission = access_answer["acesso"];
    String worker_admin = access_answer["cargo"];
    String worker_name = access_answer["nome"];

    if (worker_permission) {
      // Desativa solenoid
      welcome_screen(worker_name);
      passage = true;
      lastPosition = as5600.getCumulativePosition();
    }
    else {
      access_denied_screen();
    }
    if (worker_admin == "administrador") {
      awaiting_screen();
      setup_mode = true;
    }
  }
}

// Funções RFid
String lerUID() {
  String id = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    if (i > 0) {
      id += " "; // espaço depois do byte anterior
    }
    if (rfid.uid.uidByte[i] < 0x10) {
      id += "0"; // para ficar "07" em vez de "7", por exemplo
    }
    id += String(rfid.uid.uidByte[i], HEX);
  }
  id.toUpperCase();
  return id;
}

// Funções Wi-Fi
void reconectarWiFi() {
  if (WiFi.status() != WL_CONNECTED) {
    WiFi.begin("LabIoT", "4n1m4l5@))!!");
    Serial.print("Conectando ao WiFi...");
    while (WiFi.status() != WL_CONNECTED) {
      Serial.print(".");
      delay(1000);
    }
    Serial.print("conectado!\nEndereço IP: ");
    Serial.println(WiFi.localIP());
  }
}

// Configura as rotas do servidor web
void iniciarWebServer() {
  // Serve a página de cadastro (arquivo em /data/cadastro_funcionario.html)
  servidor.on("/cadastro", HTTP_GET, []() {
    File f = LittleFS.open("/cadastro_funcionario.html", "r");
    if (!f) {
      servidor.send(404, "text/plain", "Arquivo nao encontrado");
      return;
    }
    servidor.streamFile(f, "text/html");
    f.close();
  });

  // A página faz polling neste endpoint para receber o UID do cartão escaneado.
  // Retorna o UID pendente e limpa após a primeira leitura.
  servidor.on("/uid", HTTP_GET, []() {
    String json = "{\"uid\":\"" + pending_uid + "\"}";
    pending_uid = "";
    servidor.send(200, "application/json", json);
  });

  // Endpoints de simulação — úteis para testar sem hardware RFID
  servidor.on("/modo-admin", HTTP_GET, []() {
    setup_mode = true;
    servidor.send(200, "text/plain", "setup_mode ativado. Chame /simular?uid=XX agora.");
    Serial.println("[SIM] setup_mode = true (via web)");
  });

  servidor.on("/simular", HTTP_GET, []() {
    String uid = servidor.hasArg("uid") ? servidor.arg("uid") : "AA BB CC DD";
    uid.toUpperCase();
    pending_uid = uid;
    servidor.send(200, "text/plain", "UID simulado: " + uid);
    Serial.println("[SIM] pending_uid = " + uid);
  });

  servidor.begin();
  Serial.print("Servidor HTTP em http://");
  Serial.print(WiFi.localIP());
  Serial.println("/cadastro");
}

// Setup e Loop
void setup() {
  Serial.begin(115200); delay(500);
  reconectarWiFi();
  conexaoSegura.setCACert(certificado1);
  Wire.begin();

  // LittleFS
  if (!LittleFS.begin()) {
    Serial.println("LittleFS falhou!");
    while (true) {};
  }

  iniciarWebServer();

  // Calibração do Horário
  configTime(-3 * 3600, 0, "pool.ntp.org"); // Horário de Brasília
  struct tm timeinfo;
  while (!getLocalTime(&timeinfo)) delay(500); // aguarda sincronização

  // Inicialização da leitura do RFid
  SPI.begin();
  rfid.PCD_Init();

  // Inicialização da Tela e das Fontes
  screen.init();
  screen.setRotation(3);
  screen.fillScreen(GxEPD_WHITE);

  fonts.begin(screen);
  fonts.setForegroundColor(GxEPD_BLACK);

  // Inicializando componentes no esp32
  pinMode(relay, OUTPUT);

  // Inicialização do AS5600
  as5600.begin(); // Pino default do I2C GPIO 21 e 22
  Serial.println("as5600 conectada:" + String(as5600.isConnected()));
  as5600.resetCumulativePosition();
}

void loop() {
  reconectarWiFi();
  reconectarMQTT();
  servidor.handleClient();

  // Verificação e limitação do tempo telas diferentes
  if (showing_home && (millis() - last_instance >= 60000)) {
    home_screen();
  }

  if (showing_welcome && (millis() - last_instance >= 7000)) {
    showing_welcome = false;
    if (passage){ passage = false; }
    home_screen();
    digitalWrite(relay, HIGH);
  }

  if (showing_denied && (millis() - last_instance >= 3000)) {
    showing_denied = false;
    home_screen();
  }

  if (showing_waiting && (millis() - last_instance >= 7000)) {
    showing_waiting = false;
    home_screen();
  }

  if (showing_setup && (millis() - last_instance >= 30000)) {
    showing_setup = false;
    home_screen();
  }

  // Simulação via serial: 1ª linha ativa setup_mode, 2ª define o UID pendente
  if (Serial.available()) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    input.toUpperCase();
    if (!input.isEmpty()) {
      if (!setup_mode) {
        setup_mode = true;
        Serial.println("[SIM] setup_mode ativado. Digite o UID do novo cartao:");
      } else {
        setup_screen_adminControl(input);
        Serial.println("[SIM] pending_uid = " + input + " | Acesse /cadastro no browser");
      }
    }
  }

  // Leitura do RFid apenas se está na 'Home Screen'
  if (rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial() && showing_home) {
    String id = lerUID();
    placeholder_Uid = id;
    Serial.println("UID da tag: " + id);
    mqtt.publish("A3/catraca/acesso", id);
    last_instance = millis();

    if (setup_mode) {
      setup_screen_adminControl(id);
      setup_mode = false;
    }

    rfid.PICC_HaltA(); // interrompe leitura (não fica repetindo)
    rfid.PCD_StopCrypto1();
  }

  // Cálculo para ver se a catraca girou no sentido horário ou ante-horário
  // Entrada ou saída
  if (passage) {
    long current_position = as5600.getCumulativePosition();
    long delta = current_position - lastPosition;
    if (delta > 0) { // Entrada
      mqtt.publish("A3/catraca/entrada", placeholder_Uid);
    }
    if (delta < 0) { // Saída
      mqtt.publish("A3/catraca/saída", placeholder_Uid);
    }
    // Se delta == 0, não houve nenhuma mudança na posição da catraca
    // Mas isso não é possível a não ser que alguém leu o cartão
    // e não entrou em menos de 7 segundos.
    lastPosition = current_position;
    passage = false;
    placeholder_Uid = "";
  }
  mqtt.loop();
}