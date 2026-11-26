// UNO + IBT-2 timed tray cycle. Serial Monitor: 9600 baud.
// r = forward, pause, return; x = stop and cancel.
// PawLog: s = identify firmware, c = fresh camera clearance, a = auto cycle.
// Start from a manually checked level tray. Calibrate both durations.
const byte RPWM_PIN = 5;
const byte LPWM_PIN = 6;
const byte ENABLE_PIN = 7;  // Both R_EN and L_EN.
const byte MOTOR_PWM = 255;
const bool FORWARD_USES_RPWM = true;
const unsigned long FORWARD_MS = 1000;
const unsigned long RETURN_MS = 200;
const unsigned long HOLD_MS = 1000;
const unsigned long RESTART_DELAY_MS = 1000;
const unsigned long CAMERA_TIMEOUT_MS = 1500;

enum Phase { IDLE, MOVING_OUT, HOLDING, RETURNING };
Phase phase = IDLE;
unsigned long phaseStartedAt = 0;
unsigned long stoppedAt = 0;
unsigned long lastCameraClear = 0;
bool automaticCycle = false;
bool positionUnknown = false;
bool cameraClear = false;

void stopMotor() {
  digitalWrite(ENABLE_PIN, LOW);
  analogWrite(RPWM_PIN, 0);
  analogWrite(LPWM_PIN, 0);
  stoppedAt = millis();
}

void startMotor(bool forward) {
  stopMotor();
  const byte activePin = (forward == FORWARD_USES_RPWM) ? RPWM_PIN : LPWM_PIN;
  analogWrite(activePin, MOTOR_PWM);
  digitalWrite(ENABLE_PIN, HIGH);
  phaseStartedAt = millis();
}

void setup() {
  digitalWrite(ENABLE_PIN, LOW);
  pinMode(ENABLE_PIN, OUTPUT);
  pinMode(RPWM_PIN, OUTPUT);
  pinMode(LPWM_PIN, OUTPUT);
  stopMotor();
  Serial.begin(9600);
  Serial.println(F("Ready: r = timed cycle, x = stop"));
  Serial.println(F("Check tray is level before starting."));
}

void loop() {
  bool runRequested = false;
  bool stopRequested = false;
  bool automaticRequested = false;
  while (Serial.available()) {
    const int command = Serial.read();
    if (command == 'x') stopRequested = true;
    if (command == 'r') runRequested = true;
    if (command == 'a') automaticRequested = true;
    if (command == 'c') {
      lastCameraClear = millis();
      cameraClear = true;
    }
    if (command == 's') Serial.println(F("pawlog-motortest-v1"));
  }
  // Stop takes priority over any run command in the same input batch.
  if (stopRequested) {
    cameraClear = false;
    if (phase != IDLE) positionUnknown = true;
    stopMotor();
    phase = IDLE;
    Serial.println(F("Cancelled. Check tray position before restarting."));
    return;
  }
  if (phase != IDLE && automaticCycle && millis() - lastCameraClear >= CAMERA_TIMEOUT_MS) {
    cameraClear = false;
    stopMotor();
    phase = IDLE;
    positionUnknown = true;
    Serial.println(F("Camera timeout. Inspect tray and reset Uno."));
    return;
  }
  if (runRequested || automaticRequested) {
    if (automaticRequested && (positionUnknown || !cameraClear || millis() - lastCameraClear >= CAMERA_TIMEOUT_MS)) {
      Serial.println(F("Automatic start blocked. Inspect tray and reset Uno."));
      return;
    }
    if (phase == IDLE && millis() - stoppedAt >= RESTART_DELAY_MS) {
      automaticCycle = automaticRequested;
      phase = MOVING_OUT;
      startMotor(true);
      Serial.println(F("Tilting"));
    } else {
      Serial.println(F("Busy or settling. Run command ignored."));
    }
  }

  const unsigned long elapsed = millis() - phaseStartedAt;
  if (phase == MOVING_OUT && elapsed >= FORWARD_MS) {
    stopMotor();
    phase = HOLDING;
    phaseStartedAt = millis();
    Serial.println(F("Pause"));
  } else if (phase == HOLDING && elapsed >= HOLD_MS) {
    phase = RETURNING;
    startMotor(false);
    Serial.println(F("Returning"));
  } else if (phase == RETURNING && elapsed >= RETURN_MS) {
    stopMotor();
    phase = IDLE;
    Serial.println(F("Cycle finished. Verify tray is level."));
  }
}
