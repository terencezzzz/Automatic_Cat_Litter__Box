// Arduino UNO + HC-SR04 distance-only bench test. No motor control.
// VCC -> 5V, GND -> GND, Trig -> D9, Echo -> D10.
const byte TRIG_PIN = 9;
const byte ECHO_PIN = 10;

void setup() {
  Serial.begin(9600);
  pinMode(TRIG_PIN, OUTPUT);
  digitalWrite(TRIG_PIN, LOW);
  pinMode(ECHO_PIN, INPUT);
  Serial.println(F("HC-SR04 distance test ready"));
}

void loop() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  const unsigned long duration = pulseIn(ECHO_PIN, HIGH, 30000UL);
  const float distanceCm = duration / 58.0f;
  if (duration == 0) {
    Serial.println(F("UNKNOWN: no echo (check wiring/target)"));
  } else if (distanceCm < 2.0f || distanceCm > 400.0f) {
    Serial.println(F("UNKNOWN: outside 2-400 cm range"));
  } else {
    Serial.print(F("Distance: "));
    Serial.print(distanceCm, 1);
    Serial.println(F(" cm"));
  }
  delay(500);
}
