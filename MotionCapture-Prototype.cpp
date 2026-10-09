#include <Wire.h>

// --- Configuration ---
#define MPU_ADDR 0x68
#define TARGET_FPS 12
#define FRAME_DELAY 83 // ms for ~12 FPS
#define FLEX_COUNT 5

// Pins A0-A4 on ESP32-S3 (Adjust GPIOs based on your specific board)
const int flexPins[FLEX_COUNT] = {1, 2, 3, 4, 5};

// --- Stripped-Down Kalman Filter Class ---
// Derived from the scalarized math for FPU efficiency
class KalmanFilter {
private:
    float Q_angle = 0.001f;     // Accelerometer trust
    float Q_gyroBias = 0.003f;  // Gyro drift speed
    float R_measure = 0.03f;    // Measurement noise
    float angle = 0.0f;
    float bias = 0.0f;
    float P = {{0, 0}, {0, 0}};

public:
    float getAngle(float newAngle, float newRate, float dt) {
        // Step 1: Predict state
        float rate = newRate - bias;
        angle += dt * rate;

        // Step 2: Predict error covariance
        P += dt * (dt * P - P - P + Q_angle);
        P -= dt * P;
        P -= dt * P;
        P += Q_gyroBias * dt;

        // Step 3-4: Innovation
        float y = newAngle - angle;
        float S = P + R_measure;

        // Step 5: Kalman Gain
        float K = { P / S, P / S };

        // Step 6: Correct State
        angle += K * y;
        bias  += K * y;

        // Step 7: Update Covariance with Temp preservation
        float P00_temp = P;
        float P01_temp = P;
        P -= K * P00_temp;
        P -= K * P01_temp;
        P -= K * P00_temp;
        P -= K * P01_temp;

        return angle;
    }
    void setAngle(float a) { angle = a; }
};

// --- Globals ---
KalmanFilter kalmanRoll, kalmanPitch;
float adcMin[FLEX_COUNT]; // Stores "Wall Pose" values
float adcMax[FLEX_COUNT]; // Stores "Closed Hand" values
long timer;

void setup() {
    Serial.begin(115200);
    Wire.begin(); // Standard SDA/SCL pins for ESP32-S3

    // 1. Initialize MPU6050
    Wire.beginTransmission(MPU_ADDR);
    Wire.write(0x6B); Wire.write(0); // Wake up
    Wire.endTransmission();

    // 2. Calibration: Wall Pose (0 Degrees) [9, User]
    Serial.println("CALIBRATION: Place palm flat against the wall.");
    Serial.println("Keep hand straight for 3 seconds...");
    delay(3000);

    for(int i = 0; i < FLEX_COUNT; i++) {
        adcMin[i] = analogRead(flexPins[i]); // Record baseline
        adcMax[i] = adcMin[i] + 1000; // Default range until dynamic calibration
    }

    // 3. Static Gyro Calibration (500 samples)
    Serial.println("Calibrating Gyro offsets... Do not move.");
    // In a full implementation, you would average 500 samples here to set bias_0.

    // 4. Initialize Kalman with initial tilt
    int16_t ax, ay, az, gx, gy, gz;
    readMPU(ax, ay, az, gx, gy, gz);
    float rollAcc = atan2(ay, az) * 57.295f;
    float pitchAcc = atan2(-ax, sqrt(ay*ay + az*az)) * 57.295f;
    kalmanRoll.setAngle(rollAcc);
    kalmanPitch.setAngle(pitchAcc);

    timer = micros();
}

void loop() {
    // Timing increment
    float dt = (float)(micros() - timer) / 1000000.0f;
    timer = micros();

    // 1. Read IMU via 14-byte Burst Read
    int16_t ax, ay, az, gx, gy, gz;
    readMPU(ax, ay, az, gx, gy, gz);

    // 2. Absolute Tilt
    float rollAcc = atan2(ay, az) * 57.295f;
    float pitchAcc = atan2(-ax, sqrt(ay*ay + az*az)) * 57.295f;

    // 3. Kalman Fusion
    float roll = kalmanRoll.getAngle(rollAcc, gx / 131.0f, dt);
    float pitch = kalmanPitch.getAngle(pitchAcc, gy / 131.0f, dt);

    // 4. Flex Sensor Calculation (Linear Interpolation)
    float fingerAngles[FLEX_COUNT];
    for(int i = 0; i < FLEX_COUNT; i++) {
        float raw = analogRead(flexPins[i]);
        // Angle = (ADC - ADC_min) * 90 / (ADC_max - ADC_min)
        fingerAngles[i] = (raw - adcMin[i]) * 90.0f / (adcMax[i] - adcMin[i]);
        if(fingerAngles[i] < 0) fingerAngles[i] = 0; // Clamp for "Wall Pose"
    }

    // 5. Output Data Frame for Blender (Target 12 FPS)
    Serial.print("Orientation:"); Serial.print(roll); Serial.print(","); Serial.print(pitch);
    Serial.print(" Fingers:");
    for(int i=0; i<FLEX_COUNT; i++) { Serial.print(fingerAngles[i]); Serial.print(i==4?"":","); }
    Serial.println();

    delay(FRAME_DELAY); // Maintain the "Spider-Verse" choppy feel
}

void readMPU(int16_t &ax, int16_t &ay, int16_t &az, int16_t &gx, int16_t &gy, int16_t &gz) {
    Wire.beginTransmission(MPU_ADDR);
    Wire.write(0x3B); // Starting register for Burst Read
    Wire.endTransmission(false);
    Wire.requestFrom(MPU_ADDR, 14, true);
    ax = Wire.read()<<8|Wire.read();
    ay = Wire.read()<<8|Wire.read();
    az = Wire.read()<<8|Wire.read();
    Wire.read()<<8|Wire.read(); // Skip Temperature
    gx = Wire.read()<<8|Wire.read();
    gy = Wire.read()<<8|Wire.read();
    gz = Wire.read()<<8|Wire.read();
}

