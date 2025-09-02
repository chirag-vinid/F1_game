// Define the pin connected to the touch sensor's signal pin.
// Change this to match your wiring if needed.
const int TOUCH_SENSOR_PIN = 2;

void setup() {
  // Start serial communication at 9600 baud rate.
  Serial.begin(9600);
  pinMode(TOUCH_SENSOR_PIN, INPUT);
}

void loop() {
  // Check if there is data available from the serial port.
  if (Serial.available() > 0) {
    char command = Serial.read();

    // The 'S' command from the Python script tells the Arduino to start the game.
    if (command == 'S') {
      
      // Start the countdown. The Python script will display this.
      Serial.println("3");
      delay(1000); 

      Serial.println("2");
      delay(1000); 

      Serial.println("1");
      delay(1000); 

      // Start the timer immediately after the countdown.
      unsigned long startTime = micros();
      
      // Wait for the touch sensor to be released to prevent immediate re-triggering.
      while (digitalRead(TOUCH_SENSOR_PIN) == HIGH) {
        // Wait until the touch is released.
      }
      
      // Wait for the player's single touch to stop the timer.
      while (digitalRead(TOUCH_SENSOR_PIN) == LOW) {
        // Wait for the player's touch.
      }

      // Stop the timer and calculate the reaction time.
      unsigned long reactionTime = micros() - startTime;
      
      // Format the time as a JSON string and send it to your Python script.
      Serial.print("{\"time_us\":");
      Serial.print(reactionTime);
      Serial.println("}");
    }
  }
}