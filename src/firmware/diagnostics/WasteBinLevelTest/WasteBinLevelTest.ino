// UNO bench test: VCC->5V, GND->GND, Trig->D9, Echo->D10.
// Serial Monitor: 9600 baud. Send e at empty, f at chosen full limit.
// Calibration is RAM-only; reset/power loss requires calibration again.
// Local surface-height estimate only. No motor control.
const byte TRIG_PIN = 9;
const byte ECHO_PIN = 10;
float emptyCm = 0;
float fullCm = 0;

void setup() {
  Serial.begin(9600);
  pinMode(TRIG_PIN, OUTPUT);
  digitalWrite(TRIG_PIN, LOW);
  pinMode(ECHO_PIN, INPUT);
  Serial.println(F("Send e for EMPTY; then f for FULL limit. Reset clears calibration."));
}

void loop() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  unsigned long duration = pulseIn(ECHO_PIN, HIGH, 30000UL);
  float cm = duration / 58.0f;
  bool valid = duration != 0 && cm >= 2 && cm <= 400;

  while (Serial.available()) {
    char command = Serial.read();
    if (command != 'e' && command != 'f') continue;
    if (!valid) {
      Serial.println(F("Calibration rejected: invalid distance"));
    } else if (command == 'e') {
      emptyCm = cm;
      fullCm = 0;
      Serial.println(F("EMPTY saved; FULL cleared. Place target at full limit, send f."));
    } else if (emptyCm == 0 || cm >= emptyCm - 2.0f) {
      Serial.println(F("FULL rejected: set EMPTY first; need at least 2 cm span."));
    } else {
      fullCm = cm;
      Serial.println(F("FULL saved. Calibration ready."));
    }
  }

  if (!valid) {
    Serial.println(F("UNKNOWN: no valid echo; fullness unavailable"));
  } else {
    Serial.print(F("Distance: "));
    Serial.print(cm, 1);
    Serial.print(F(" cm"));
    if (emptyCm > fullCm && fullCm > 0) {
      float percent = 100.0f * (emptyCm - cm) / (emptyCm - fullCm);
      percent = constrain(percent, 0.0f, 100.0f);
      Serial.print(F(" | Estimated level: "));
      Serial.print(percent, 0);
      Serial.println(F("%"));
    } else {
      Serial.println(F(" | NOT CALIBRATED"));
    }
  }
  delay(500);
}
