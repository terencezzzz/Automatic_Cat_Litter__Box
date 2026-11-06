// Bench test with the motor secured and disconnected from the mechanism.
// HC-SR04: VCC -> 5V, GND -> GND, Trig -> D9, Echo -> D10.
// Serial 9600: c = fresh camera clear, r = run request, x = occupied/unknown/stop.
const byte RPWM_PIN = 5;
const byte LPWM_PIN = 6;
const byte ENABLE_PIN = 7;  // Connect both R_EN and L_EN here.
const byte TEST_PWM = 100;
const unsigned long MAX_RUN_MS = 1000;

void stopMotor() {
  digitalWrite(ENABLE_PIN, LOW);
  analogWrite(RPWM_PIN, 0);
  analogWrite(LPWM_PIN, 0);
}

void startMotor() {
  analogWrite(RPWM_PIN, TEST_PWM);
  digitalWrite(ENABLE_PIN, HIGH);
}

void setupMotor() {
  digitalWrite(ENABLE_PIN, LOW);
  pinMode(ENABLE_PIN, OUTPUT);
  pinMode(RPWM_PIN, OUTPUT);
  pinMode(LPWM_PIN, OUTPUT);
  stopMotor();
}

const byte TRIG_PIN = 9;
const byte ECHO_PIN = 10;
const unsigned long SAMPLE_MS = 60;
const unsigned long CAMERA_TIMEOUT_MS = 3000;
const unsigned long CLEAR_STABLE_MS = 500;
// Bench example: place a fixed backdrop roughly 40 cm away.
const float CLEAR_MIN_CM = 35;
const float CLEAR_MAX_CM = 45;

bool cameraClear = false;
bool sensorClear = false;
bool runRequested = false;
unsigned long cameraClearAt = 0;
unsigned long sensorClearSince = 0;
unsigned long sampledAt = 0;
unsigned long startedAt = 0;

void setup() {
  setupMotor();
  pinMode(TRIG_PIN, OUTPUT);
  digitalWrite(TRIG_PIN, LOW);
  pinMode(ECHO_PIN, INPUT);
  Serial.begin(9600);
}

void loop() {
  const unsigned long sampleStart = millis();
  if (sampleStart - sampledAt >= SAMPLE_MS) {
    sampledAt = sampleStart;
    digitalWrite(TRIG_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(TRIG_PIN, LOW);
    const unsigned long echoUs = pulseIn(ECHO_PIN, HIGH, 30000UL);
    const float distanceCm = echoUs / 58.0f;
    const bool clearReading = distanceCm >= CLEAR_MIN_CM && distanceCm <= CLEAR_MAX_CM;
    if (clearReading && !sensorClear) {
      sensorClearSince = millis();
    }
    sensorClear = clearReading;
  }

  const unsigned long now = millis();
  if (now - cameraClearAt >= CAMERA_TIMEOUT_MS) {
    cameraClear = false;
    runRequested = false;
  }
  const bool sensorReady = sensorClear && now - sensorClearSince >= CLEAR_STABLE_MS;
  if (!sensorReady || (runRequested && now - startedAt >= MAX_RUN_MS)) {
    runRequested = false;
  }

  if (Serial.available()) {
    const int command = Serial.read();
    if (command == 'c') {
      cameraClearAt = now;
      cameraClear = true;
    } else if (command == 'r') {
      if (!runRequested && cameraClear && sensorReady) {
        startedAt = now;
        runRequested = true;
      }
    } else if (command != '\r' && command != '\n') {
      cameraClear = false;
      runRequested = false;
    }
  }
  if (runRequested) {
    startMotor();
  } else {
    stopMotor();
  }
}
