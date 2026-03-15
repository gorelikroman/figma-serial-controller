/*
 * FIGMA SERIAL CONTROLLER
 * Arduino Micro (ATmega32U4) — чистый Serial (без HID)
 * 
 * Отправляет сырые события по Serial в формате:
 *   E1:+1\n  E1:-1\n      — энкодер вращение
 *   E1:sw\n               — кнопка энкодера
 *   JX:tl\n JX:tc\n ...   — джойстик направления (tl/tc/tr/cl/cc/cr/bl/bc/br)
 *   JX:sw\n               — кнопка джойстика
 *   M1:down\n M1:up\n     — матрица кнопки (M1..M16)
 *
 * Никакого HID. Всё идёт через Python Agent → WebSocket → Figma Plugin.
 *
 * Железо:
 *   MCP23017 @ 0x20 (I2C SDA=D2, SCL=D3)
 *   Энкодеры 1-5: MCP (CLK/DT/SW на портах A/B)
 *   Энкодер 6: MCU D4/D5, SW на MCP B7
 *   Джойстик: VRX=A3, VRY=A2, SW=A1
 *   Матрица 4×4: Rows D15,D14,D16,D10 / Cols D6,D7,D8,D9
 */

#include <Wire.h>

// ─── MCP23017 ───
const uint8_t MCP_ADDR    = 0x20;
const uint8_t MCP_IODIRA  = 0x00;
const uint8_t MCP_IODIRB  = 0x01;
const uint8_t MCP_GPPUA   = 0x0C;
const uint8_t MCP_GPPUB   = 0x0D;
const uint8_t MCP_GPIOA   = 0x12;
const uint8_t MCP_GPIOB   = 0x13;

bool mcpOk = false;

// ─── MCP Encoders (5 шт) ───
const uint8_t ENC_COUNT = 5;
const uint8_t ENC_CLK[ENC_COUNT] = {0, 3, 6,  9, 12};  // MCP bit positions
const uint8_t ENC_DT[ENC_COUNT]  = {1, 4, 7, 10, 13};
uint8_t encLast[ENC_COUNT];

// ─── MCP SW buttons (E1..E5) ───
const uint8_t SW_PINS[ENC_COUNT] = {2, 5, 8, 11, 14};   // A2,A5,B0,B3,B6
uint8_t swLast[ENC_COUNT];
uint16_t swLastT[ENC_COUNT];

// ─── MCU Encoder 6 (D4/D5) ───
const uint8_t E6_CLK = 4;
const uint8_t E6_DT  = 5;
uint8_t e6Last = 0;

// ─── E6 SW on MCP B7 ───
const uint8_t E6_SW_BIT = 15;
uint8_t e6SwLast = 0;
uint16_t e6SwLastT = 0;

// ─── Joystick ───
const uint8_t JOY_X   = A3;
const uint8_t JOY_Y   = A2;
const uint8_t JOY_BTN = A1;
int centerX, centerY;
bool joyOk = false;
uint8_t lastDir = 0;           // 0=center, 1-8 directions
bool lastJoyBtn = false;
unsigned long lastDirT = 0;
unsigned long lastJoyBtnT = 0;
const int DEAD_ZONE  = 100;
const int THRESHOLD  = 250;
const unsigned long DPAD_DB = 200;
const unsigned long BTN_DB  = 50;

// ─── Matrix 4×4 ───
const uint8_t MROWS = 4;
const uint8_t MCOLS = 4;
const uint8_t ROW_PINS[MROWS] = {15, 14, 16, 10};
const uint8_t COL_PINS[MCOLS] = {6, 7, 8, 9};
uint8_t matState[MROWS][MCOLS];
uint16_t matLastT[MROWS][MCOLS];
const uint16_t MAT_DB = 10;

// Direction codes: index 0=center(unused), 1..8
// tl=1 tc=2 tr=3 cl=4 cr=5 bl=6 bc=7 br=8
const char* const DIR_CODES[] = {
  "", "tl", "tc", "tr", "cl", "cr", "bl", "bc", "br"
};

// ═══════════════════════════════════════════════════
void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 3000) {}  // ждём USB до 3 сек
  Wire.begin();
  
  // LED
  pinMode(LED_BUILTIN, OUTPUT);
  flashLed(3);
  
  // MCP setup
  Wire.beginTransmission(MCP_ADDR);
  mcpOk = (Wire.endTransmission() == 0);
  if (mcpOk) {
    mcpWrite(MCP_IODIRA, 0xFF);
    mcpWrite(MCP_IODIRB, 0xFF);
    mcpWrite(MCP_GPPUA,  0xFF);
    mcpWrite(MCP_GPPUB,  0xFF);
    delay(100);
  }
  
  // MCU Encoder 6 pins
  pinMode(E6_CLK, INPUT_PULLUP);
  pinMode(E6_DT,  INPUT_PULLUP);
  
  // Matrix
  for (uint8_t r = 0; r < MROWS; r++) {
    pinMode(ROW_PINS[r], OUTPUT);
    digitalWrite(ROW_PINS[r], HIGH);
  }
  for (uint8_t c = 0; c < MCOLS; c++) {
    pinMode(COL_PINS[c], INPUT_PULLUP);
  }
  memset(matState, 0, sizeof(matState));
  memset(matLastT, 0, sizeof(matLastT));
  
  // Joystick
  pinMode(JOY_BTN, INPUT_PULLUP);
  int testX = analogRead(JOY_X);
  joyOk = (testX > 100 && testX < 900);
  if (joyOk) {
    long sx = 0, sy = 0;
    for (int i = 0; i < 10; i++) {
      sx += analogRead(JOY_X);
      sy += analogRead(JOY_Y);
      delay(30);
    }
    centerX = sx / 10;
    centerY = sy / 10;
  }
  
  // Init encoder states
  if (mcpOk) {
    uint16_t pins = mcpReadAll();
    for (uint8_t i = 0; i < ENC_COUNT; i++) {
      encLast[i] = ((pins >> ENC_CLK[i]) & 1) << 1 | ((pins >> ENC_DT[i]) & 1);
      swLast[i] = !((pins >> SW_PINS[i]) & 1);
      swLastT[i] = 0;
    }
    e6SwLast = !((pins >> E6_SW_BIT) & 1);
    e6SwLastT = 0;
  }
  e6Last = (digitalRead(E6_CLK) << 1) | digitalRead(E6_DT);
  
  // Ready
  Serial.println(F("READY"));
  Serial.print(F("MCP:")); Serial.println(mcpOk ? F("OK") : F("FAIL"));
  Serial.print(F("JOY:")); Serial.println(joyOk ? F("OK") : F("FAIL"));
}

// ═══════════════════════════════════════════════════
void loop() {
  if (mcpOk) {
    uint16_t pins = mcpReadAll();
    scanEncoders(pins);
    scanSwButtons(pins);
  }
  scanE6();
  scanMatrix();
  if (joyOk) scanJoystick();
  delay(2);
}

// ─── MCP helpers ───
void mcpWrite(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(MCP_ADDR);
  Wire.write(reg);
  Wire.write(val);
  Wire.endTransmission();
}

uint8_t mcpRead(uint8_t reg) {
  Wire.beginTransmission(MCP_ADDR);
  Wire.write(reg);
  Wire.endTransmission();
  Wire.requestFrom((uint8_t)MCP_ADDR, (uint8_t)1);
  return Wire.available() ? Wire.read() : 0;
}

uint16_t mcpReadAll() {
  uint8_t a = mcpRead(MCP_GPIOA);
  uint8_t b = mcpRead(MCP_GPIOB);
  return ((uint16_t)b << 8) | a;
}

// ─── MCP Encoders 1-5 ───
void scanEncoders(uint16_t pins) {
  for (uint8_t i = 0; i < ENC_COUNT; i++) {
    uint8_t clk = (pins >> ENC_CLK[i]) & 1;
    uint8_t dt  = (pins >> ENC_DT[i]) & 1;
    uint8_t cur = (clk << 1) | dt;
    uint8_t prev = encLast[i];
    
    if (cur != prev) {
      // Detect direction on stable states (00 or 11)
      if (cur == 0b00 || cur == 0b11) {
        if ((prev == 0b01 && cur == 0b00) || (prev == 0b10 && cur == 0b11)) {
          // CCW
          Serial.print(F("E")); Serial.print(i + 1); Serial.println(F(":-1"));
          flashLed(1);
        } else if ((prev == 0b10 && cur == 0b00) || (prev == 0b01 && cur == 0b11)) {
          // CW
          Serial.print(F("E")); Serial.print(i + 1); Serial.println(F(":+1"));
          flashLed(1);
        }
      }
      encLast[i] = cur;
    }
  }
}

// ─── MCU Encoder 6 ───
void scanE6() {
  uint8_t clk = digitalRead(E6_CLK);
  uint8_t dt  = digitalRead(E6_DT);
  uint8_t cur = (clk << 1) | dt;
  uint8_t prev = e6Last;
  
  if (cur != prev) {
    if (cur == 0b00 || cur == 0b11) {
      if ((prev == 0b01 && cur == 0b00) || (prev == 0b10 && cur == 0b11)) {
        Serial.println(F("E6:-1"));
        flashLed(1);
      } else if ((prev == 0b10 && cur == 0b00) || (prev == 0b01 && cur == 0b11)) {
        Serial.println(F("E6:+1"));
        flashLed(1);
      }
    }
    e6Last = cur;
  }
}

// ─── SW buttons (E1-E5 + E6) ───
void scanSwButtons(uint16_t pins) {
  uint16_t now16 = (uint16_t)millis();
  
  // Double-read for stability
  delay(2);
  uint16_t pins2 = mcpReadAll();
  if (pins != pins2) return;
  
  for (uint8_t i = 0; i < ENC_COUNT; i++) {
    bool pressed = !((pins >> SW_PINS[i]) & 1);
    if (pressed != swLast[i]) {
      if ((uint16_t)(now16 - swLastT[i]) >= 100) {
        swLast[i] = pressed;
        swLastT[i] = now16;
        if (pressed) {
          Serial.print(F("E")); Serial.print(i + 1); Serial.println(F(":sw"));
          flashLed(1);
        }
      }
    }
  }
  
  // E6 SW on B7
  bool e6p = !((pins >> E6_SW_BIT) & 1);
  if (e6p != e6SwLast) {
    if ((uint16_t)(now16 - e6SwLastT) >= 100) {
      e6SwLast = e6p;
      e6SwLastT = now16;
      if (e6p) {
        Serial.println(F("E6:sw"));
        flashLed(1);
      }
    }
  }
}

// ─── Matrix 4×4 ───
void scanMatrix() {
  uint16_t now16 = (uint16_t)millis();
  for (uint8_t r = 0; r < MROWS; r++) {
    digitalWrite(ROW_PINS[r], LOW);
    delayMicroseconds(50);
    for (uint8_t c = 0; c < MCOLS; c++) {
      bool pressed = (digitalRead(COL_PINS[c]) == LOW);
      if (pressed != matState[r][c]) {
        if ((uint16_t)(now16 - matLastT[r][c]) >= MAT_DB) {
          matState[r][c] = pressed;
          matLastT[r][c] = now16;
          uint8_t idx = r * MCOLS + c + 1; // M1..M16
          Serial.print(F("M"));
          Serial.print(idx);
          Serial.println(pressed ? F(":down") : F(":up"));
          if (pressed) flashLed(1);
        }
      }
    }
    digitalWrite(ROW_PINS[r], HIGH);
  }
}

// ─── Joystick D-pad ───
void scanJoystick() {
  unsigned long now = millis();
  
  int x = analogRead(JOY_X);
  int y = analogRead(JOY_Y);
  int dx = x - centerX;
  int dy = y - centerY;
  
  uint8_t dir = 0; // center
  if (abs(dx) > DEAD_ZONE || abs(dy) > DEAD_ZONE) {
    bool up    = (dy < -THRESHOLD);
    bool down  = (dy >  THRESHOLD);
    bool left  = (dx < -THRESHOLD);
    bool right = (dx >  THRESHOLD);
    bool midX  = (abs(dx) < THRESHOLD);
    bool midY  = (abs(dy) < THRESHOLD);
    
    if (up && left)       dir = 1; // tl
    else if (up && midX)  dir = 2; // tc
    else if (up && right) dir = 3; // tr
    else if (midY && left)  dir = 4; // cl
    else if (midY && right) dir = 5; // cr
    else if (down && left)  dir = 6; // bl
    else if (down && midX)  dir = 7; // bc
    else if (down && right) dir = 8; // br
  }
  
  if (dir != lastDir && (now - lastDirT) >= DPAD_DB) {
    lastDir = dir;
    lastDirT = now;
    if (dir > 0) {
      Serial.print(F("JX:")); Serial.println(DIR_CODES[dir]);
      flashLed(1);
    }
  }
  
  // Joystick button
  bool btn = (digitalRead(JOY_BTN) == LOW);
  if (btn != lastJoyBtn && (now - lastJoyBtnT) >= BTN_DB) {
    lastJoyBtn = btn;
    lastJoyBtnT = now;
    if (btn) {
      Serial.println(F("JX:sw"));
      flashLed(1);
    }
  }
}

void flashLed(int n) {
  for (int i = 0; i < n; i++) {
    digitalWrite(LED_BUILTIN, HIGH);
    delay(30);
    digitalWrite(LED_BUILTIN, LOW);
    if (i < n - 1) delay(30);
  }
}
