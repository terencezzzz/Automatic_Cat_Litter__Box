#include <Arduino.h>
#include "esp_camera.h"
#include <WiFi.h>
#include <WiFiMulti.h>
#include <Preferences.h>
#include "src/WiFiManager/WiFiManager.h"

// ===========================
// Select camera model in board_config.h
// ===========================
#include "board_config.h"

// ===========================
// Phone Wi-Fi setup (home/router credentials are saved in ESP32 flash)
// ===========================
const char *SETUP_AP_NAME = "Camera-Setup";
const char *SETUP_AP_PASSWORD = "camera123";

bool cameraReady = false;
bool serverStartRequested = false;

bool startCameraServer();
void setupLedFlash();

// Newest configured network first. Keep up to five networks across power loss.
const uint8_t MAX_SAVED_NETWORKS = 5;
struct SavedNetwork {
  String ssid;
  String password;
};
SavedNetwork savedNetworks[MAX_SAVED_NETWORKS];
uint8_t savedNetworkCount = 0;

void loadSavedNetworks() {
  savedNetworkCount = 0;
  Preferences preferences;
  if (!preferences.begin("camera-wifi", false)) {
    Serial.println("Could not open saved WiFi storage.");
    return;
  }
  for (uint8_t i = 0; i < MAX_SAVED_NETWORKS; ++i) {
    String ssid = preferences.getString(("s" + String(i)).c_str(), "");
    if (ssid.isEmpty()) continue;
    savedNetworks[savedNetworkCount++] = {
      ssid, preferences.getString(("p" + String(i)).c_str(), "")
    };
  }
  preferences.end();
}

void rememberNetwork(const String &ssid, const String &password) {
  if (ssid.isEmpty()) return;
  uint8_t index = 0;
  while (index < savedNetworkCount && savedNetworks[index].ssid != ssid) ++index;
  if (index < savedNetworkCount && savedNetworks[index].password == password) return;
  if (index == savedNetworkCount) {
    if (savedNetworkCount < MAX_SAVED_NETWORKS) ++savedNetworkCount;
    index = savedNetworkCount - 1;
  }
  for (uint8_t i = index; i > 0; --i) savedNetworks[i] = savedNetworks[i - 1];
  savedNetworks[0] = {ssid, password};

  Preferences preferences;
  if (!preferences.begin("camera-wifi", false)) {
    Serial.println("Could not save WiFi network. Configure again after restart.");
    return;
  }
  bool saved = true;
  for (uint8_t i = 0; i < savedNetworkCount; ++i) {
    saved &= preferences.putString(("s" + String(i)).c_str(), savedNetworks[i].ssid) > 0;
    // An empty password is valid for a deliberately configured open network.
    preferences.putString(("p" + String(i)).c_str(), savedNetworks[i].password);
    saved &= preferences.getString(("p" + String(i)).c_str(), "") == savedNetworks[i].password;
  }
  preferences.end();
  Serial.println(saved ? "WiFi network saved for future visits." : "WiFi storage failed. Configure again after restart.");
}

void setup() {
  Serial.begin(115200);
  Serial.setDebugOutput(true);
  Serial.println();
  Serial.println("[BOOT] CameraWebServer WiFi-first v3");
  Serial.printf("[BOOT] Build: %s %s; PSRAM: %s; free heap: %u\n",
                __DATE__, __TIME__, psramFound() ? "available" : "unavailable", ESP.getFreeHeap());
  Serial.printf("[CAMERA] PWDN=%d RESET=%d XCLK=%d SDA=%d SCL=%d\n",
                PWDN_GPIO_NUM, RESET_GPIO_NUM, XCLK_GPIO_NUM, SIOD_GPIO_NUM, SIOC_GPIO_NUM);

  // Keep the camera powered down while starting/configuring Wi-Fi. The
  // camera driver releases PWDN during esp_camera_init() below.
  if (PWDN_GPIO_NUM >= 0) {
    pinMode(PWDN_GPIO_NUM, OUTPUT);
    digitalWrite(PWDN_GPIO_NUM, HIGH);
  }
#if defined(LED_GPIO_NUM)
  pinMode(LED_GPIO_NUM, OUTPUT);
  digitalWrite(LED_GPIO_NUM, LOW);
#endif
  delay(100);
  Serial.println("[WIFI] Starting before camera initialization...");
  Serial.flush();
  if (!WiFi.mode(WIFI_STA)) {
    Serial.println("[STOP] WiFi driver could not start. No automatic restart requested.");
    return;
  }
  // Let WiFiMulti/portal own connection attempts during setup; enable
  // automatic reconnect only after they have finished.
  WiFi.setAutoReconnect(false);
  // Keep the portal local to setup: it must release port 80 before the
  // camera HTTP server starts. Do not resetSettings() on normal startup.
  {
    WiFiManager wifiManager;
    wifiManager.setDebugOutput(false); // Keep network credentials out of library logs.
    loadSavedNetworks();
    // Import the one network retained by the previous firmware on first use.
    if (savedNetworkCount == 0) {
      rememberNetwork(wifiManager.getWiFiSSID(), wifiManager.getWiFiPass());
    }
    bool connected = false;
    if (savedNetworkCount > 0) {
      WiFiMulti wifiMulti;
      for (uint8_t i = 0; i < savedNetworkCount; ++i) {
        wifiMulti.addAP(savedNetworks[i].ssid.c_str(), savedNetworks[i].password.c_str());
      }
      Serial.printf("Trying %u saved WiFi network(s)...\n", savedNetworkCount);
      // WiFiMulti tries one candidate per run. Continue so a wrong password
      // on the strongest network cannot hide another working saved network.
      for (uint8_t attempt = 0; attempt < savedNetworkCount && !connected; ++attempt) {
        connected = wifiMulti.run(20000) == WL_CONNECTED;
      }
    }
    wifiManager.setConnectTimeout(20);
    wifiManager.setConfigPortalTimeout(0); // Wait until the user configures Wi-Fi.
    wifiManager.setAPCallback([](WiFiManager *manager) {
      Serial.println("WiFi setup: connect phone to Camera-Setup (password: camera123).");
      Serial.print("Open http://");
      Serial.println(WiFi.softAPIP());
    });
    if (!connected && !wifiManager.startConfigPortal(SETUP_AP_NAME, SETUP_AP_PASSWORD)) {
      Serial.println("WiFi setup ended without a connection. Restarting...");
      delay(1000);
      ESP.restart();
      return;
    }
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("[WIFI] Setup returned without a connection. Restarting...");
      Serial.flush();
      delay(1000);
      ESP.restart();
      return;
    }
    // Save only working credentials; a failed password must not replace a
    // previously working entry. Updating an SSID replaces its old password.
    rememberNetwork(WiFi.SSID(), WiFi.psk());
  }
  WiFi.setAutoReconnect(true);
  WiFi.setSleep(false);
  Serial.println("WiFi connected");

  camera_config_t config = {};  // Zero-initialize optional fields too.
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.frame_size = FRAMESIZE_UXGA;
  config.pixel_format = PIXFORMAT_JPEG;  // for streaming
  //config.pixel_format = PIXFORMAT_RGB565; // for face detection/recognition
  config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.jpeg_quality = 12;
  config.fb_count = 1;

  // if PSRAM IC present, init with UXGA resolution and higher JPEG quality
  //                      for larger pre-allocated frame buffer.
  if (config.pixel_format == PIXFORMAT_JPEG) {
    if (psramFound()) {
      config.jpeg_quality = 10;
      config.fb_count = 2;
      config.grab_mode = CAMERA_GRAB_LATEST;
    } else {
      // Limit the frame size when PSRAM is not available
      config.frame_size = FRAMESIZE_SVGA;
      config.fb_location = CAMERA_FB_IN_DRAM;
    }
  } else {
    // Best option for face detection/recognition
    config.frame_size = FRAMESIZE_240X240;
#if CONFIG_IDF_TARGET_ESP32S3
    config.fb_count = 2;
#endif
  }

#if defined(CAMERA_MODEL_ESP_EYE)
  pinMode(13, INPUT_PULLUP);
  pinMode(14, INPUT_PULLUP);
#endif

  // camera init
  Serial.println("[CAMERA] Initializing sensor after WiFi connection...");
  Serial.flush();
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("[CAMERA] Init failed: 0x%x (%s)\n", err, esp_err_to_name(err));
    Serial.println("[STOP] WiFi is connected, but camera initialization failed. Camera webpage is unavailable.");
    Serial.flush();
    return;
  }
  Serial.println("[CAMERA] Sensor initialized successfully.");

  sensor_t *s = esp_camera_sensor_get();
  if (s == nullptr) {
    Serial.println("Camera sensor unavailable. Restart after checking configuration.");
    esp_camera_deinit();
    return;
  }
  // initial sensors are flipped vertically and colors are a bit saturated
  if (s->id.PID == OV3660_PID) {
    s->set_vflip(s, 1);        // flip it back
    s->set_brightness(s, 1);   // up the brightness just a bit
    s->set_saturation(s, -2);  // lower the saturation
  }
  // Capture at 640x480 so small waste retains detail without UXGA transfer cost.
  if (config.pixel_format == PIXFORMAT_JPEG) {
    s->set_framesize(s, FRAMESIZE_VGA);
  }

#if defined(CAMERA_MODEL_M5STACK_WIDE) || defined(CAMERA_MODEL_M5STACK_ESP32CAM)
  s->set_vflip(s, 1);
  s->set_hmirror(s, 1);
#endif

#if defined(CAMERA_MODEL_ESP32S3_EYE)
  s->set_vflip(s, 1);
#endif

// Setup LED FLash if LED pin is defined in camera_pins.h
#if defined(LED_GPIO_NUM)
  setupLedFlash();
#endif

  cameraReady = true;


  serverStartRequested = true;
  if (startCameraServer()) {
    Serial.print("Camera Ready! Use 'http://");
    Serial.print(WiFi.localIP());
    Serial.println("' to connect");
  } else {
    Serial.println("[SERVER] Startup failed. Camera webpage is not ready; check the preceding error.");
  }
}

void loop() {
  static bool disconnected = false;
  static uint32_t disconnectedAt = 0;
  // Camera failure requires checking configuration and restarting.
  if (!cameraReady) {
    delay(100);
    return;
  }

  if (WiFi.status() == WL_CONNECTED) {
    disconnected = false;
    if (!serverStartRequested) {
      serverStartRequested = true;
      if (startCameraServer()) {
        Serial.print("Camera Ready! Use http://");
        Serial.println(WiFi.localIP());
      } else {
        Serial.println("[SERVER] Startup failed; restart after checking the error.");
      }
    }
  } else {
    if (!disconnected) {
      disconnected = true;
      disconnectedAt = millis();
      Serial.println("WiFi lost. Trying automatic reconnect for 60 seconds...");
    }
    // Restart before opening the portal so the camera server cannot conflict
    // with WiFiManager on port 80. Saved credentials survive this restart.
    if ((uint32_t)(millis() - disconnectedAt) >= 60000U) {
      Serial.println("WiFi unavailable. Restarting for phone WiFi setup...");
      delay(100);
      ESP.restart();
    }
  }
  // Suitable for the camera demo only; add non-blocking control separately later.
  delay(20);
}

