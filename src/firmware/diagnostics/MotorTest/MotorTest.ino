// Bench test with the motor secured and disconnected from the mechanism.
// Serial 9600: r = one short forward pulse, x = stop.
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

bool running = false;
unsigned long startedAt = 0;

void setup() {
  setupMotor();
  Serial.begin(9600);
  Serial.println(F("Motor-only test. Send r to run, x to stop."));
}

void loop() {
  if (running && millis() - startedAt >= MAX_RUN_MS) {
    stopMotor();
    running = false;
  }

  if (Serial.available()) {
    const int command = Serial.read();
    if (command == 'x') {
      stopMotor();
      running = false;
    } else if (command == 'r' && !running) {
      startedAt = millis();
      startMotor();
      running = true;
    }
  }
}
