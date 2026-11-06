#include <Arduino.h>
#include <WiFi.h>

// Isolate Wi-Fi driver startup from camera initialization and provisioning.
// Does not erase, save, or connect to any Wi-Fi network.
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n[TEST] WiFi startup only; no camera or portal");
  Serial.flush();
  delay(2000);

  Serial.println("[TEST] Starting WiFi station mode...");
  Serial.flush();
  if (!WiFi.mode(WIFI_STA)) {
    Serial.println("[TEST] WiFi.mode failed; no restart requested.");
    return;
  }
  WiFi.setAutoReconnect(false);
  Serial.println("[TEST] WiFi driver started. No WiFi.begin() was called.");
}

void loop() {
  delay(5000);
  Serial.printf("[TEST] Alive: %lu seconds\n", millis() / 1000UL);
}
