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
// #include "AS5600.h"
#include "Wire.h"

// Constantes Globais
String msg = "";
long lastPosition = 0;
const int relay = 38; // Valor arbitrário
unsigned long last_instance = 0;
enum state_E { 
  showing_home,
  checking_bank,
  setup_mode, // Aviso para castro no sistema
  awaiting_RFid2, // Aguarda leitura do RFid a ser registrado
  showing_access,
  MQTT_process,
  awaiting_MQTT,
  enter,
  leave
};
enum state_E state = showing_home;

// AS5600 (entrada/saída)
// AS5600 as5600;

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
  screen.fillScreen(GxEPD_WHITE);

  fonts.setFont( u8g2_font_helvB18_te );
  fonts.setFontMode(1);
  fonts.setCursor(35, 65);
  fonts.print("Aproxime o Cartão");

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
  screen.fillScreen(GxEPD_WHITE);

  fonts.setFont( u8g2_font_helvB24_te );
  fonts.setFontMode(1);
  fonts.setCursor(40, 60);
  fonts.print("Bem-Vinda(o)!");

  fonts.setFont( u8g2_font_helvR18_te  );
  fonts.setFontMode(1);
  fonts.setCursor(70, 95);
  fonts.print(worker_name);

  digitalWrite(relay, HIGH);
  screen.display(true);
}

void access_denied_screen() {
  screen.fillScreen(GxEPD_WHITE);

  fonts.setFont( u8g2_font_helvB24_te );
  fonts.setFontMode(1);
  fonts.setCursor(28, 70);
  fonts.print("Acesso Negado");

  screen.display(true);
}

void awaiting_screen() {
  screen.fillScreen(GxEPD_WHITE);

  fonts.setFont( u8g2_font_helvB10_te );
  fonts.setFontMode(1);
  fonts.setCursor(25, 60);
  fonts.print("Aguardando leitura do novo cartão...");

  screen.display(true);
}

void MQTT_screen() {
  screen.fillScreen(GxEPD_WHITE);

  fonts.setFont( u8g2_font_helvB18_te );
  fonts.setFontMode(1);
  fonts.setCursor(20, 60);
  fonts.print("Aguardando resposta");
  fonts.setCursor(80, 95);
  fonts.print("do sistema");
  
  screen.display(true);
}

// Exibe confirmação no display e disponibiliza o UID na página de cadastro
void setup_screen_adminControl(String Uid) {
  JsonDocument idMessage;
  String jsonString;
  idMessage["uid"] = Uid;
  serializeJson(idMessage, jsonString);
  mqtt.publish("a3/cadastros", jsonString);

  screen.fillScreen(GxEPD_WHITE);
  
  fonts.setFont( u8g2_font_helvB24_te );
  fonts.setFontMode(1);
  fonts.setCursor(53, 70);
  fonts.print("Cartão lido!");
  fonts.setFont(u8g2_font_helvR10_te);
  fonts.setFontMode(1);
  fonts.setCursor(43, 95);
  fonts.print("Complete o cadastro no sistema.");

  screen.display(true);
}

// Funções MMQTT
void reconectarMQTT() {
  if (!mqtt.connected()) {
    Serial.print("Conectando MQTT...");
    while(!mqtt.connected()) {
      Serial.println("Não conectado ainda");
      mqtt.connect("esp32_teste", "aula", "zowmad-tavQez");
      Serial.print(".");
      delay(1000);
    }
    Serial.println(" conectado!");

    mqtt.subscribe("a3/catraca/resposta");
  }
}

void recebeuMensagem(String topic, String content) {
  Serial.println(topic + ": " + content);

  if (topic == "a3/catraca/resposta") {
    JsonDocument access_answer;
    deserializeJson(access_answer, content);
    bool worker_permission = access_answer["autorizado"];
    bool worker_admin = access_answer["isAdmin"];
    String worker_name = access_answer["nome"];

    if (worker_admin) {
      awaiting_screen();
      state = awaiting_RFid2; // Para ler segundo RFid
      last_instance = millis();
    }
    else {
      if (worker_permission) {
        welcome_screen(worker_name);
        state = showing_access;
        // passage = true;
        // lastPosition = as5600.getCumulativePosition();
        last_instance = millis();
      }
      else {
        access_denied_screen();
        state = showing_access;
        last_instance = millis();
      }
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
    WiFi.begin("LabIoT", "4n1m4l5@))!!"); // WiFi IoT    
    Serial.print("Conectando ao WiFi...");
    while (WiFi.status() != WL_CONNECTED) {
      Serial.print(".");
      delay(1000);
    }
    Serial.print("conectado!\nEndereço IP: ");
    // rgbLedWrite(RGB_BUILTIN, 0, 255, 0);
    Serial.println(WiFi.localIP());
  }
} 

// Setup e Loop
void setup() {
  Serial.begin(115200); delay(500);
  reconectarWiFi();
  conexaoSegura.setCACert(certificado1);
  mqtt.begin("mqtt.janks.dev.br", 8883, conexaoSegura); 

  // conexaoSegura.setInsecure();
  // mqtt.begin("mqtt.janks.dev.br", 1883, conexaoSegura); 
  mqtt.setTimeout(2000);
  mqtt.onMessage(recebeuMensagem); 
  reconectarMQTT();
  
  // Inicialização da Tela e das Fontes
  screen.init();
  screen.setRotation(1);
  screen.fillScreen(GxEPD_WHITE);

  fonts.begin(screen);
  fonts.setForegroundColor(GxEPD_BLACK);

  state = showing_home;
  last_instance = millis() + 60000;

  // iniciarWebServer();

  // Calibração do Horário
  configTime(-3 * 3600, 0, "pool.ntp.org"); // Horário de Brasília
  struct tm timeinfo;
  while (!getLocalTime(&timeinfo)) delay(500); // aguarda sincronização

  // Inicialização da leitura do RFid
  SPI.begin();
  rfid.PCD_Init();

  // Inicializando componentes no esp32
  pinMode(relay, OUTPUT);
  pinMode(10, OUTPUT);
  pinMode(14, OUTPUT);
  pinMode(15, OUTPUT);

  // // Inicialização do AS5600
  // Wire.begin(21, 47);
  // as5600.begin(); // Pino default do I2C GPIO 21 e 22
  // Serial.println("as5600 conectada:" + String(as5600.isConnected()));
  // as5600.resetCumulativePosition();
}

void loop() {
  reconectarWiFi();
  reconectarMQTT();
  servidor.handleClient();

  // Leitura do RFid apenas se está na 'Home Screen'
  if (state == showing_home || state == awaiting_RFid2) {
    if (rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial()) {
      String id = lerUID();
      Serial.println("UID da tag: " + id);
      JsonDocument idMessage;
      String jsonString;
      idMessage["uid"] = id;
      serializeJson(idMessage, jsonString);
      last_instance = millis();
    
      if (state == showing_home) {
        MQTT_screen();
        mqtt.publish("a3/catraca/entrada", jsonString);
        state = awaiting_MQTT;
      }
      else {
        setup_screen_adminControl(id);
        state = setup_mode;
      }
      

      rfid.PICC_HaltA(); // interrompe leitura (não fica repetindo)
      rfid.PCD_StopCrypto1();
    }
  }


  // Verificação e limitação do tempo telas diferentes
  if (state == showing_home) {
    // Atualiza a tela a cada minuto
    if (millis() - last_instance >= 60000) {
      home_screen();
      last_instance = millis();
    }
  }
  else if (state == awaiting_MQTT) {
    // Deu timeout no mqtt espera de 30s
    if (millis() - last_instance >= 15000) {
      home_screen();
      state = showing_home;
      last_instance = millis(); 
    }
  }
  else if (state == showing_access) {
    // Tela de acesso Permitido/Negado mostra 5s e volta para home
    if (millis() - last_instance >= 5000) {
      digitalWrite(relay, LOW);
      home_screen();
      state = showing_home;
      last_instance = millis(); 
    }      
  }
  else if (state == awaiting_RFid2) {
    if (millis() - last_instance >= 5000) {
      home_screen();
      state = showing_home;
      last_instance = millis(); 
    }      
  }
  else if (state == setup_mode) {
    if (millis() - last_instance >= 5000) {
      home_screen();
      state = showing_home;
      last_instance = millis(); 
    }      
  }

  // Cálculo para ver se a catraca girou no sentido horário ou ante-horário
  // Entrada ou saída
  // if (passage) {
  //   long current_position = as5600.getCumulativePosition();
  //   long delta = current_position - lastPosition;
  //   if (delta > 0) { // Entrada
  //     mqtt.publish("a3/catraca/entrada", placeholder_Uid);
  //   }
  //   if (delta < 0) { // Saída
  //     mqtt.publish("a3/catraca/saída", placeholder_Uid);
  //   }
  //   // Se delta == 0, não houve nenhuma mudança na posição da catraca
  //   // Mas isso não é possível a não ser que alguém leu o cartão
  //   // e não entrou em menos de 7 segundos.
  //   lastPosition = current_position;
  //   passage = false;
  //   placeholder_Uid = "";
  // }
  mqtt.loop();
}