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
#include <QRCodeGFX.h> 


// Contantes Globais
String msg = "";
const int relay = 4; // Valor arbitrário 
unsigned long last_instance = 0;
bool showing_welcome = false;
bool showing_home = true;
bool showing_denied = false;
bool setup_mode = false;
bool showing_waiting = false;
bool showing_setup = false;

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

// QR Code
QRCodeGFX qrcode(screen); 

// Funções auxiliares
String doubleDigit(int num) {
    return (num < 10 ? "0" : "") + String(num);
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
    }
    if (worker_admin == "administrador") {
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

// Funções da Tela 
void welcome_screen(String worker_name) {
  showing_welcome = true;
  showing_home = false;
  screen.fillScreen(GxEPD_WHITE);

  fonts.setFont( u8g2_font_helvB24_te );
  fonts.setFontMode(1);
  fonts.setCursor(60, 50);
  fonts.print("Bem Vindo!");

  fonts.setFont( u8g2_font_helvR18_te  );
  fonts.setFontMode(1);
  fonts.setCursor(20, 75);
  fonts.print(worker_name);
  
  digitalWrite(relay, LOW);  
  screen.display(true);
}

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

void awaiting_scan() {
  showing_waiting = true;
  showing_home = false;
  screen.fillScreen(GxEPD_WHITE);

  fonts.setFont( u8g2_font_helvB10_te );
  fonts.setFontMode(1);
  fonts.setCursor(25, 60);
  fonts.print("Aguardando leitura do novo cartão...");
  
  screen.display(true);
}

void setup_screen(String Uid) {
  showing_setup = true;
  showing_home = false;
  screen.fillScreen(GxEPD_WHITE);

  fonts.setFont( u8g2_font_helvB10_te );
  fonts.setFontMode(1);
  fonts.setCursor(30, 60);
  fonts.print("Abra o código QR no celular");

  // Desenhando QR code
  qrcode.setScale(2);
  qrcode.draw("https://app.example.org/dashboard" + Uid, 110, 50);

  screen.display(true);
}

// Setuo e Loop
void setup() {
  Serial.begin(115200); delay(500);
  reconectarWiFi();
  conexaoSegura.setCACert(certificado1);

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
}

void loop() {
  reconectarWiFi();
  reconectarMQTT();
''
  // Verificação e limitação do tempo telas diferentes
  if (showing_home && (millis() - last_instance >= 1000)) {
    home_screen();
  }

  if (showing_welcome && (millis() - last_instance >= 7000)) {
    showing_welcome = false;
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

  // Leitura do RFid apenas se está na 'Home Screen'
  if (rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial() && showing_home) { 
    String id = lerUID(); 
    Serial.println("UID da tag: " + id); 
    mqtt.publish("A3/catraca/acesso", "id"); // Envia o Uid para o mqtt para busca no banco de dados
    last_instance = millis();

    if (setup_mode) {
      setup_screen(id);
      setup_mode = false;
    }

    rfid.PICC_HaltA(); // interrompe leitura (não fica repetindo) 
    rfid.PCD_StopCrypto1();   
  }
  mqtt.loop(); 
}