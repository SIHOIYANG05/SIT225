#include <Arduino.h>
#include <Wire.h>
#include <DHT.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <SensirionI2cScd4x.h>

#define DHT_TYPE DHT22
#define INDOOR_DHT_PIN 2
#define OUTDOOR_DHT_PIN 3
#define DS18B20_PIN 4

DHT indoorDht(INDOOR_DHT_PIN, DHT_TYPE);
DHT outdoorDht(OUTDOOR_DHT_PIN, DHT_TYPE);

OneWire oneWire(DS18B20_PIN);
DallasTemperature exhaustSensor(&oneWire);

SensirionI2cScd4x scd40;

const unsigned long SAMPLE_INTERVAL_MS = 10000;
unsigned long sessionStartMs = 0;
unsigned long lastSampleMs = 0;
bool sessionRunning = false;

void printFloatOrBlank(float value) {
  if (isnan(value) || value <= -126.0) {
    Serial.print("");
  } else {
    Serial.print(value, 2);
  }
}

void takeSample() {
  exhaustSensor.requestTemperatures();

  float indoorTemp = indoorDht.readTemperature();
  float indoorRh = indoorDht.readHumidity();
  float outdoorTemp = outdoorDht.readTemperature();
  float outdoorRh = outdoorDht.readHumidity();
  float exhaustTemp = exhaustSensor.getTempCByIndex(0);

  bool dataReady = false;
  uint16_t co2 = 0;
  float scdTemperature = 0.0;
  float scdHumidity = 0.0;
  bool co2Valid = false;

  int16_t error = scd40.getDataReadyStatus(dataReady);
  if (error == 0 && dataReady) {
    error = scd40.readMeasurement(co2, scdTemperature, scdHumidity);
    co2Valid = (error == 0 && co2 > 0);
  }

  unsigned long elapsedSeconds = (millis() - sessionStartMs) / 1000;

  Serial.print(elapsedSeconds);
  Serial.print(",");
  printFloatOrBlank(indoorTemp);
  Serial.print(",");
  printFloatOrBlank(indoorRh);
  Serial.print(",");
  printFloatOrBlank(outdoorTemp);
  Serial.print(",");
  printFloatOrBlank(outdoorRh);
  Serial.print(",");
  printFloatOrBlank(exhaustTemp);
  Serial.print(",");

  if (co2Valid) {
    Serial.print(co2);
  }
  Serial.println();
}

void setup() {
  Serial.begin(115200);

  indoorDht.begin();
  outdoorDht.begin();
  exhaustSensor.begin();

  Wire.begin();
  scd40.begin(Wire, 0x62);

  delay(30);
  scd40.wakeUp();
  delay(30);
  scd40.stopPeriodicMeasurement();
  delay(500);
  scd40.reinit();
  delay(30);

  int16_t error = scd40.startPeriodicMeasurement();
  if (error != 0) {
    Serial.println("SCD40_START_ERROR");
  }

  Serial.println("READY");
}

void loop() {
  if (!sessionRunning && Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();

    if (command == "START") {
      sessionRunning = true;
      sessionStartMs = millis();
      lastSampleMs = sessionStartMs;

      Serial.println(
          "elapsed_seconds,indoor_temp_c,indoor_rh,outdoor_temp_c,"
          "outdoor_rh,pc_exhaust_temp_c,co2_ppm");
      takeSample();
    }
  }

  if (sessionRunning &&
      millis() - lastSampleMs >= SAMPLE_INTERVAL_MS) {
    lastSampleMs += SAMPLE_INTERVAL_MS;
    takeSample();
  }
}
