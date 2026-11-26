// UNO + IBT-2, SPDT HOME and TILT switches, HC-SR04.
const byte HOME = 2, TILT = 3, RPWM = 5, LPWM = 6, ENABLE = 7;
const byte HOME_NO = 4, TILT_NO = 8;
const byte TRIG = 9, ECHO = 10, PWM = 100;
const unsigned long LEASE_MS = 3500, TRAVEL_MS = 5000;
enum Phase { IDLE, OUTBOUND, HOLD, INBOUND, FAULT };
Phase phase = IDLE;
unsigned long phaseAt = 0, clearAt = 0, sampleAt = 0, sensorAt = 0;
bool visionClear = false, sensorClear = false;
int lowCm = 0, highCm = 0;
char line[24];
byte length = 0;
bool overflow = false;

bool active(byte nc, byte no) {
  return digitalRead(nc) == HIGH && digitalRead(no) == LOW;
}

bool validSwitches() {
  return digitalRead(HOME) != digitalRead(HOME_NO) &&
         digitalRead(TILT) != digitalRead(TILT_NO);
}

void stopMotor() {
  digitalWrite(ENABLE, LOW);
  analogWrite(RPWM, 0);
  analogWrite(LPWM, 0);
}

void fault() {
  stopMotor();
  phase = FAULT;
  Serial.println(F("fault"));
}

bool safe(unsigned long now) {
  return visionClear && now - clearAt < LEASE_MS &&
         sensorClear && now - sensorAt >= 500;
}

void moveTo(Phase next) {
  stopMotor();
  phase = next;
  phaseAt = millis();
  analogWrite(next == OUTBOUND ? RPWM : LPWM, PWM);
  digitalWrite(ENABLE, HIGH);
}

void command() {
  if (!strcmp(line, "x")) {
    visionClear = false;
    if (phase != IDLE && phase != FAULT) fault();
  } else if (!strcmp(line, "c")) {
    clearAt = millis();
    visionClear = true;
  } else if (!strcmp(line, "r")) {
    if (phase == IDLE && safe(millis()) && validSwitches() &&
        active(HOME, HOME_NO) && !active(TILT, TILT_NO)) {
      moveTo(OUTBOUND);
      Serial.println(F("running"));
    } else {
      Serial.println(F("rejected"));
    }
  } else if (!strcmp(line, "s")) {
    if (phase == FAULT) Serial.println(F("fault"));
    else if (phase != IDLE) Serial.println(F("running"));
    else if (safe(millis()) && validSwitches() && active(HOME, HOME_NO) &&
             !active(TILT, TILT_NO)) Serial.println(F("ready"));
    else Serial.println(F("blocked"));
  } else if (line[0] == 'w' && phase == IDLE) {
    int minimum, maximum;
    char extra;
    if (sscanf(line + 1, "%d %d %c", &minimum, &maximum, &extra) == 2 &&
        minimum >= 2 && maximum <= 400 && minimum < maximum) {
      lowCm = minimum;
      highCm = maximum;
      sensorClear = visionClear = false;
      Serial.println(F("pawlog-controller-v1"));
    }
  }
}

void setup() {
  digitalWrite(ENABLE, LOW);
  pinMode(ENABLE, OUTPUT);
  pinMode(RPWM, OUTPUT);
  pinMode(LPWM, OUTPUT);
  stopMotor();
  pinMode(HOME, INPUT_PULLUP);
  pinMode(TILT, INPUT_PULLUP);
  pinMode(HOME_NO, INPUT_PULLUP);
  pinMode(TILT_NO, INPUT_PULLUP);
  pinMode(TRIG, OUTPUT);
  pinMode(ECHO, INPUT);
  Serial.begin(9600);
}

void loop() {
  if (millis() - sampleAt >= 60) {
    sampleAt = millis();
    digitalWrite(TRIG, HIGH);
    delayMicroseconds(10);
    digitalWrite(TRIG, LOW);
    const unsigned long echo = pulseIn(ECHO, HIGH, 30000UL);
    const bool clear = lowCm > 0 && echo >= lowCm * 58UL && echo <= highCm * 58UL;
    if (clear && !sensorClear) sensorAt = millis();
    sensorClear = clear;
  }
  for (byte count = 0; count < 32 && Serial.available(); count++) {
    const char ch = Serial.read();
    if (ch == '\n') {
      line[length] = '\0';
      if (!overflow) command();
      overflow = false;
      length = 0;
    } else if (ch != '\r') {
      if (length < sizeof(line) - 1) line[length++] = ch;
      else overflow = true;
    }
  }
  if (phase == IDLE || phase == FAULT) return;
  const unsigned long now = millis();
  const unsigned long elapsed = now - phaseAt;
  const bool home = active(HOME, HOME_NO), tilt = active(TILT, TILT_NO);
  if (!safe(now) || !validSwitches() || (home && tilt)) {
    fault();
  } else if (phase == OUTBOUND) {
    if (tilt) {
      stopMotor();
      phase = HOLD;
      phaseAt = now;
    } else if (elapsed >= TRAVEL_MS || (elapsed >= 600 && home)) {
      fault();
    }
  } else if (phase == HOLD) {
    if (!tilt) fault();
    else if (elapsed >= 1000) moveTo(INBOUND);
  } else if (phase == INBOUND) {
    if (home) {
      stopMotor();
      phase = IDLE;
      Serial.println(F("returned"));
    } else if (elapsed >= TRAVEL_MS || (elapsed >= 600 && tilt)) {
      fault();
    }
  }
}
