# Contexto do Projeto IoT — ENG4051 (PUC-Rio)

> **Curso:** ENG4051 – Projeto Internet das Coisas  
> **Professor:** Jan K. S. (janks@puc-rio.br)  
> **Ambiente de desenvolvimento:** VS Code + PlatformIO  
> **Microcontrolador principal:** ESP32-S3 CAM  

---

## 1. Visão Geral do Projeto Final

**Tema:** Controle de cadastro e acesso de funcionários via RFID com catraca.

### Funcionalidades principais
- Leitura de cartão RFID (MFRC522) na catraca
- Display E-Paper de feedback visual ao funcionário
- Solenoide (JF-0530B) acionada por relé (SRD-05VDC) para liberar/bloquear a catraca
- Sensor de ângulo magnético AS5600 + encoder KY-040 para simular/monitorar giro da catraca
- Servidor interno no ESP32 (configuração local de permissões via WiFi AP)
- Servidor em nuvem no Raspberry Pi (banco de dados, MQTT broker, Node-RED, Grafana)
- Interface de administrador para cadastro, edição e controle de funcionários
- Registro de entrada/saída com contagem de tempo e visualização em Grafana
- Comunicação entre ESPs via MQTT
- Múltiplos ESPs (um por ponto de acesso)

### Stack tecnológica
- **Firmware:** C++ (Arduino framework via PlatformIO)
- **Protocolo IoT:** MQTT com TLS (porta 8883)
- **Banco de dados:** TimescaleDB (PostgreSQL com hipertabelas para séries temporais)
- **Orquestração de fluxos:** Node-RED
- **Visualização:** Grafana
- **Servidor:** Raspberry Pi (self-hosted)
- **PCB:** EasyEDA
- **Caixa/enclosure:** Onshape (modelagem 3D, impressão 3D)

---

## 2. Hardware e Pinagem

### ESP32-S3 CAM — Especificações Relevantes
| Parâmetro | Valor |
|---|---|
| CPU | 2 núcleos, 240MHz |
| RAM | 512KB SRAM + 8MB PSRAM |
| Flash | 16MB + SD (até 32GB) |
| Pinos digitais | 34 pinos (3.3V) |
| Pinos analógicos | 20 pinos (12 bits) |
| WiFi | 2.4GHz |
| Bluetooth | 5.0 |
| Consumo ativo | ~160mA–260mA |
| Deep sleep | ~20µA–2.5mA |

### Conexão do Leitor RFID MFRC522 (SPI)
| Pino MFRC522 | Pino ESP32-S3 CAM |
|---|---|
| 3.3V | 3.3V |
| GND | GND |
| MISO | 13 |
| MOSI | 11 |
| SCK (Clock) | 12 |
| SDA (Chip Select) | 46 |
| RST (Reset) | 17 |
| IRQ | -- (não usado) |

> **Atenção:** Os pinos 11, 12 e 13 são os pinos padrão de SPI do ESP32-S3 CAM.

### Conexão do Display E-Paper WeAct 2.9" (SPI)
| Pino Display | Pino ESP32-S3 CAM |
|---|---|
| VCC | 3.3V |
| GND | GND |
| SDA (MOSI) | 11 |
| SCL (Clock) | 12 |
| CS (Chip Select) | 10 |
| D/C (Data/Command) | 14 |
| RES (Reset) | 15 |
| BUSY | 16 |

> **Atenção:** Os fios SCL e SDA de componentes I2C devem ser **trançados** para reduzir interferência.

### Outros componentes de hardware
- **Solenoide JF-0530B:** acionada pelo relé SRD-05VDC-SL-C (nunca diretamente pelo ESP)
- **Relé SRD-05VDC-SL-C:** acionado por pino digital do ESP, aciona a solenoide
- **Sensor AS5600:** sensor de ângulo magnético (I2C) — simula posição da catraca
- **Encoder KY-040:** sensor rotativo — leitura de giro da catraca
- **Capacitores de desacoplamento:** 10µF e 1µF nos componentes I2C/SPI para estabilidade

---

## 3. Conceitos do Curso por Aula

### Teoria 01 — Coisas Configuráveis
**Tópicos:** Hardware ESP32 vs Raspberry Pi vs Arduino; LED simples e LED RGB Neopixel; WiFi + servidor HTTP no ESP32; JSON + LittleFS; HTTPS e certificados; NTP (sincronização de data/hora); integração com Telegram.

**Padrão de WiFi (reconexão):**
```cpp
#include <WiFi.h>
void reconectarWiFi() {
  if (WiFi.status() != WL_CONNECTED) {
    WiFi.begin("NOME_REDE", "SENHA");
    while (WiFi.status() != WL_CONNECTED) { delay(1000); }
  }
}
```

**Servidor HTTP simples:**
```cpp
#include <WebServer.h>
WebServer servidor(80);
void paginaInicial() { servidor.send(200, "text/html", "Bem-vindo!"); }
void setup() {
  reconectarWiFi();
  servidor.on("/inicio", HTTP_GET, paginaInicial);
  servidor.begin();
}
void loop() { reconectarWiFi(); servidor.handleClient(); }
```

**Rota com parâmetros na URL:**
```cpp
#include <uri/UriBraces.h>
servidor.on(UriBraces("/soma/{}/{}"), HTTP_GET, paginaComParametros);
// acesso: servidor.pathArg(0), servidor.pathArg(1)
```

**Submissão de formulário (POST):**
```cpp
servidor.on("/formulario", HTTP_GET, paginaComArquivoHTML);
servidor.on("/formulario", HTTP_POST, tratarDadosSubmetidos);
// acesso: servidor.arg("usuario"), servidor.arg("senha")
```

**LittleFS (sistema de arquivos no Flash):**
```cpp
// Leitura de JSON
File arquivo = LittleFS.open("/dados.json", "r");
JsonDocument dados;
deserializeJson(dados, arquivo);
arquivo.close();

// Escrita de JSON
JsonDocument dados2;
dados2["nome"] = "Jan K. S.";
File arquivo2 = LittleFS.open("/dados2.json", "w");
serializeJson(dados2, arquivo2);
arquivo2.close();
```

**Sincronização NTP:**
```cpp
#include <time.h>
configTzTime("<-03>3", "a.ntp.br", "pool.ntp.org");
struct tm tempo;
getLocalTime(&tempo);
int ano = tempo.tm_year + 1900;
int diaDaSemana = tempo.tm_wday; // 0=domingo
```

**LED RGB embutido (pino 48):**
```cpp
rgbLedWrite(RGB_BUILTIN, vermelho, verde, azul);
```

---

### Teoria 02 — Coisas Replicadas
**Tópicos:** Display E-Paper E-Ink; protocolo SPI vs UART; biblioteca GxEPD2; biblioteca Adafruit_GFX; MQTT.

**Atualização do display E-Paper:**
- **Parcial:** rápida, deixa vestígios
- **Total:** lenta, pisca a tela, limpa tudo

**Biblioteca GxEPD2 (E-Paper):**
```cpp
#include <GxEPD2_BW.h>
GxEPD2_290_T94_V2 modeloTela(10, 14, 15, 16); // CS, DC, RST, BUSY
GxEPD2_BW<GxEPD2_290_T94_V2, GxEPD2_290_T94_V2::HEIGHT> tela(modeloTela);
// rotação
tela.setRotation(0); // vertical normal
tela.setRotation(2); // vertical invertido
tela.setRotation(3); // paisagem
```

**Funções de desenho (Adafruit_GFX):**
```cpp
tela.drawLine(x1, y1, x2, y2, cor);
tela.fillCircle(x, y, raio, cor);
tela.drawCircle(x, y, raio, cor);
tela.fillRect(x, y, comprimento, altura, cor);
tela.drawRect(x, y, comprimento, altura, cor);
tela.fillTriangle(x1, y1, x2, y2, x3, y3, cor);
```

**MQTT — Conexão e inscrição (biblioteca MQTT.h):**
```cpp
#include <MQTT.h>
WiFiClientSecure conexaoSegura;
MQTTClient mqtt(1000); // tamanho máximo da mensagem em bytes

void reconectarMQTT() {
  if (!mqtt.connected()) {
    while (!mqtt.connected()) {
      mqtt.connect("IDENTIFICADOR_UNICO", "LOGIN", "SENHA");
      delay(1000);
    }
    mqtt.subscribe("topico1");                       // QoS 0
    mqtt.subscribe("topico2/+/parametro", 1);        // QoS 1
  }
}

void recebeuMensagem(String topico, String conteudo) {
  Serial.println(topico + ": " + conteudo);
}

void setup() {
  reconectarWiFi();
  conexaoSegura.setCACert(certificado1);
  mqtt.begin("ENDERECO_MQTT.COM", 8883, conexaoSegura);
  mqtt.onMessage(recebeuMensagem);
  mqtt.setKeepAlive(10);
  mqtt.setWill("topico/despedida", "offline"); // testamento (last will)
  reconectarMQTT();
}

void loop() {
  reconectarWiFi();
  reconectarMQTT();
  mqtt.loop();
}
```

**MQTT — Publicação:**
```cpp
mqtt.publish("topico1", "conteudo");             // retain=false, QoS 0
mqtt.publish("topico2/123/abc", "conteudo", false, 1); // QoS 1
```

**MQTT — Wildcards em tópicos:**
- `+` → substitui um nível: `topico/+/parametro`
- `#` → substitui todos os níveis à frente: `topico/#`

---

### Teoria 03 — Coisas Monitoradas
**Tópicos:** Leitor SD Card (SD_MMC); câmera OV2640 (ESP32-S3 CAM); PSRAM; iBeacon e BLE para triangulação de localização.

**SD Card (SD_MMC):**
```cpp
#include <SD_MMC.h>
SD_MMC.setPins(39, 38, 40); // ATENÇÃO À ORDEM EXATA!
SD_MMC.begin("/sdcard", true);

// Leitura
File arquivo = SD_MMC.open("/arquivo.txt", FILE_READ);
String texto = arquivo.readString();
arquivo.close();

// Escrita
File arquivo2 = SD_MMC.open("/arquivo.txt", FILE_WRITE);
arquivo2.println("Olá!");
arquivo2.close();
```

> **Atenção:** Câmera, PSRAM e SD Card compartilham pinos — não é possível conectar outros dispositivos nesses pinos quando todos estão ativos.

---

### Teoria 04 — Coisas à Venda
**Tópicos:** Código de barras EAN-13; biblioteca BarcodeGFX para desenhar código de barras no display E-Paper.

**BarcodeGFX:**
```cpp
#include <BarcodeGFX.h>
BarcodeGFX codigoBarras(tela);
codigoBarras.setScale(2);               // escala de 1 a 20
codigoBarras.draw("7896065880069", 0, 60, 65); // x, y, altura
```

---

### Teoria 05 — Coisas Consumíveis (RFID — foco do projeto)
**Tópicos:** Leitor RFID MFRC522; cartões MIFARE Classic; estrutura de setores/blocos; TimescaleDB; Grafana.

**Funcionamento do RFID:**
- O leitor gera campo magnético, acorda o cartão e lê o UID
- Cartões MIFARE Classic têm 16 setores, cada um com 4 blocos de 16 bytes
- O bloco trailer de cada setor guarda chave A, condições de acesso e chave B
- A chave padrão de fábrica é `FF FF FF FF FF FF`
- **Não guardar dados sensíveis no RFID** — há falha de segurança conhecida no protocolo
- O UID é suficiente para controle de acesso (sem necessidade de ler blocos de dados)

**Biblioteca MFRC522:**
```cpp
#include <SPI.h>
#include <MFRC522.h>
MFRC522 rfid(46, 17); // pinos: SDA (CS), RST
MFRC522::MIFARE_Key chaveA = {{0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF}};

// Leitura de UID
String lerUID() {
  String id = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    if (i > 0) id += " ";
    if (rfid.uid.uidByte[i] < 0x10) id += "0";
    id += String(rfid.uid.uidByte[i], HEX);
  }
  id.toUpperCase();
  return id;
}

// Leitura de bloco de dados
String lerTextoDoBloco(byte bloco) {
  byte tamanhoDados = 18;
  char dados[tamanhoDados];
  MFRC522::StatusCode status = rfid.PCD_Authenticate(
    MFRC522::PICC_CMD_MF_AUTH_KEY_A, bloco, &chaveA, &(rfid.uid)
  );
  if (status != MFRC522::STATUS_OK) return "";
  status = rfid.MIFARE_Read(bloco, (byte*)dados, &tamanhoDados);
  if (status != MFRC522::STATUS_OK) return "";
  dados[tamanhoDados - 2] = '\0';
  return String(dados);
}

void setup() {
  SPI.begin();
  rfid.PCD_Init();
}

void loop() {
  if (rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial()) {
    String id = lerUID();
    Serial.println("UID: " + id);
    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();
  }
}
```

**TimescaleDB (PostgreSQL para séries temporais):**
```sql
-- Criação de hipertabela
CREATE TABLE acessos (
  data_hora TIMESTAMP WITH TIME ZONE DEFAULT now(),
  uid_cartao VARCHAR(20),
  nome_funcionario VARCHAR(100),
  tipo VARCHAR(10), -- 'entrada' ou 'saida'
  autorizado BOOLEAN,
  PRIMARY KEY (data_hora)
);
SELECT create_hypertable('acessos', 'data_hora');

-- Consulta com janelamento temporal (time_bucket)
SELECT
  time_bucket('1 hour', data_hora) AS time,
  COUNT(*) AS total_acessos,
  SUM(CASE WHEN tipo = 'entrada' THEN 1 ELSE 0 END) AS entradas,
  SUM(CASE WHEN tipo = 'saida' THEN 1 ELSE 0 END) AS saidas
FROM acessos
WHERE $__timeFilter(data_hora)
GROUP BY time
ORDER BY time ASC;
```

**Grafana — integração com TimescaleDB:**
- Variável `$__timeFilter(data_hora)` substitui o filtro de tempo do painel automaticamente
- Suporta gráficos de linha, barras, status e tabelas
- É possível criar variáveis interativas para filtrar por funcionário, setor, etc.

---

### Teoria 07 — Coisas Remotas
**Tópicos:** Bases numéricas (hex, base64); LoRaWAN (Radioenge); comandos AT; BME680; modo deep sleep.

**Deep Sleep (economia de energia):**
```cpp
// Acorda por timer
esp_sleep_enable_timer_wakeup(10e6); // 10 segundos em µs
esp_deep_sleep_start();

// Acorda por interrupção em pino
esp_sleep_enable_ext0_wakeup((gpio_num_t) pinoParaAcordar, HIGH);

// Variável que persiste no deep sleep
RTC_DATA_ATTR int contador = 0;
```

> Consumo: ~160–260mA em modo ativo; ~0.01mA em deep sleep.

---

### Teoria 08 — Coisas da Casa
**Tópicos:** Preferences (NVS); WiFi AP (Access Point); OTA (atualização Over The Air); protocolo Matter.

**Preferences (armazenamento persistente no Flash NVS):**
```cpp
#include <Preferences.h>
Preferences preferencias;
preferencias.begin("ajustesUsuario"); // namespace (máx. 15 chars)

// Salvar
preferencias.putString("nome", "Jan K. S.");
preferencias.putInt("contagem", 37);
preferencias.putFloat("preco", 10.99);
preferencias.putBool("somAtivado", true);

// Carregar (2º parâmetro = valor padrão)
String nome = preferencias.getString("nome", "");
int contagem = preferencias.getInt("contagem", 0);
```

> Namespace e chaves têm limite de **15 caracteres**.

**WiFi Access Point (AP) — servidor sem roteador externo:**
```cpp
#include <WiFi.h>
#include <WebServer.h>
WiFi.softAP("NOME_DA_REDE", "SENHA_8_CHARS");
Serial.println("IP: " + WiFi.softAPIP().toString()); // 192.168.4.1
int conexoes = WiFi.softAPgetStationNum();
```

**OTA (atualização de firmware pelo ar):**
```cpp
#include <HTTPUpdate.h>
// verifica versão atual no servidor
// se diferente, baixa novo .bin e reinicia
t_httpUpdate_return resultado = httpUpdate.update(conexaoSegura, enderecoFirmware);
```

---

### Teoria 09 — Coisas Bonitinhas (PCB e impressão 3D)
**Tópicos:** EasyEDA (desenho de PCB); Onshape (modelagem 3D); impressão 3D.

**Etapas do PCB no EasyEDA:**
1. Esquemático dos componentes
2. Passagem para o desenho da placa
3. Desenho das trilhas (camada superior e inferior)
4. Configuração da camada de cobre como terra (GND plane)
5. Adição de modelos 3D
6. Visualização 3D final

**Etapas da modelagem 3D no Onshape (caixa do protótipo):**
1. Esboço (Sketch) num plano
2. Definição exata das dimensões e restrições
3. Extrusão para 3D
4. Casca (Shell) para criar a caixa
5. Esboço + Extrusão numa face para encaixes
6. Encaixe da tampa com Offset + saliências espelhadas
7. Arredondamento das quinas com Filetes

---

## 4. Padrões e Boas Práticas do Curso

### Estrutura padrão de código (firmware)
```cpp
// 1. Includes
// 2. Constantes e variáveis globais
// 3. Funções auxiliares (reconectarWiFi, reconectarMQTT, lerRFID, etc.)
// 4. setup() — inicializa Serial, SPI, WiFi, MQTT, periféricos
// 5. loop() — reconexões + mqtt.loop() + lógica de negócio
```

### Reconexão WiFi e MQTT
Sempre chamar `reconectarWiFi()` e `reconectarMQTT()` **tanto no `setup()` quanto no `loop()`**.

### Tratamento de erros
```cpp
if (!SD_MMC.begin("/sdcard", true)) {
  Serial.println("Falha na inicialização do SD");
  while (true) {}; // trava o programa em caso de erro crítico
}
```

### HTTPS e certificados
Sempre usar `WiFiClientSecure` com certificados de autoridade raiz para conexões seguras ao servidor e ao broker MQTT.

---

## 5. Arquitetura do Sistema (Projeto Final)

```
[Cartão RFID]
      |
[ESP32 - Catraca]
  ├── Leitor MFRC522 (SPI)
  ├── Display E-Paper WeAct 2.9" (SPI)
  ├── Relé → Solenoide JF-0530B
  ├── AS5600 (I2C) + KY-040 (encoder)
  ├── Servidor WiFi AP local (config de permissões)
  └── MQTT client (publica eventos de acesso)
        |
     [MQTT Broker]  ←→  [Node-RED]  ←→  [TimescaleDB]
         (Raspberry Pi)                       |
                                          [Grafana]
                                    (painel de entrada/saída)

[Interface Admin (Web)]
  ├── Cadastro de funcionários
  ├── Edição de permissões
  └── Visualização de logs
```

### Tópicos MQTT sugeridos
```
catraca/acesso          → ESP publica: { "uid": "E7 45 D6 19", "tipo": "entrada", "autorizado": true }
catraca/status          → ESP publica status da catraca (online/offline)
admin/permissoes        → Servidor publica atualizações de permissões
admin/cadastro          → Servidor publica novos cadastros
```

---

## 6. Referências de Bibliotecas

| Biblioteca | Uso |
|---|---|
| `WiFi.h` | Conexão WiFi |
| `WebServer.h` | Servidor HTTP no ESP32 |
| `MQTT.h` | Comunicação MQTT |
| `WiFiClientSecure.h` | Conexão TLS/HTTPS |
| `ArduinoJson.h` | Parse e serialização de JSON |
| `Preferences.h` | Armazenamento persistente (NVS) |
| `LittleFS.h` | Sistema de arquivos no Flash |
| `SPI.h` | Protocolo SPI |
| `MFRC522.h` | Leitor RFID |
| `GxEPD2_BW.h` | Display E-Paper |
| `Adafruit_GFX.h` | Primitivas gráficas |
| `SD_MMC.h` | Cartão SD |
| `time.h` | NTP e data/hora |
| `HTTPUpdate.h` | OTA updates |
