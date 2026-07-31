// Include the Adafruit DHT library
#include <DHT.h>
// DHT11 Signal is connected to digital pin D2
#define DHTPIN 2
// Tell the library that the sensor is a DHT11
#define DHTTYPE DHT11
// Create the DHT sensor object
DHT dht(DHTPIN, DHTTYPE);
void setup() {
// Start communication with the PC
Serial.begin(9600);
// Start the DHT11 sensor
dht.begin();
// Print the CSV column names
Serial.println("temperature_c,humidity_percent");
}
void loop() {
// Wait 2 seconds between readings
delay(2000);
// Read humidity and temperature
float humidity = dht.readHumidity();
float temperature = dht.readTemperature();
// Check whether the sensor reading failed
if (isnan(humidity) || isnan(temperature)) {
Serial.println("ERROR,DHT11_READ_FAILED");
return;
}
// Send temperature,humidity to the PC
Serial.print(temperature, 1);
Serial.print(",");
Serial.println(humidity, 1);
