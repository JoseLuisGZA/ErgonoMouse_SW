// The user specific settings, like pin mappings or special configuration variables and
// sensitivities are stored in config.h. Please open config_sample.h, adjust your settings and save
// it as config.h
#include "config.h"
#include <Arduino.h>
#include "kinematics.h"
// check config.h if this functions and variables are needed
#if NUMKEYS > 0

// array with the pin definition of all keys
int keyList[NUMKEYS] = KEYLIST;

// Function to setup up all keys in keyList
void setupKeys() {
  for (int i = 0; i < NUMKEYS; i++) {
    pinMode(keyList[i], INPUT_PULLUP);
  }
}

// Function to read and store the digital states for each of the keys
void readAllFromKeys(int *keyVals) {
  for (int i = 0; i < NUMKEYS; i++) {
    keyVals[i] = digitalRead(keyList[i]);
  }
}

// Evaluate and debounce all keys from the raw keyVals into the debounced keyOut event or the
// debounced keyState. The keyOut is only 1 for one iteration of the loop.
void evalKeys(int *keyVals, uint8_t *keyOut, uint8_t *keyState) {
  static unsigned long timestamp[NUMKEYS]; // needed for key evaluation

  // Button Evaluation
  for (int i = 0; i < NUMKEYS; i++) {
    // The keys are configured with pull_up, see setupKeys() and are pulled to ground, when pressed.
    // Therefore, the pressed key is false, which is an inverted logic
    if (!keyVals[i]) { // the key is pressed
      // Making sure button cannot trigger multiple times which would result in overloading HID.
      if (keyState[i] == 0) { // if the button has not been pressed lately:
        keyOut[i] = 1;   // this is the variable telling the outside world only one iteration, that
                         // the key was pressed
        keyState[i] = 1; // remember, that we already told the outside world about this key
        timestamp[i] = millis(); // remember the time, the button was pressed
#ifdef DEBUG_KEYS
        Serial.println("");
        Serial.print("Key: "); // this is always sent over the serial console, and not only in debug
        Serial.println(i);
#endif
      } else { // the button was already pressed and is still pressed (and the event sent in the
               // last loop), don't send the keyOut event again.
        keyOut[i] = 0;
      }
    } else {                  // the button is not pressed
      if (keyState[i] == 1) { // has it been pressed lately?
        // debouncing:
        if (millis() - timestamp[i] >
            DEBOUNCE_KEYS_MS) { // check if the last button press is long enough in the past
          keyState[i] = 0;      // reset this marker and allow a new button press
        }
      }
    }
  }
}

#if NUMKILLKEYS == 2
namespace {
constexpr unsigned long KILL_BUTTON_DEBOUNCE_MS = 25;
constexpr unsigned long KILL_BUTTON_DOUBLE_CLICK_MS = 500;

struct KillButtonState {
  bool rawPressed = false;
  bool stablePressed = false;
  bool dominantOnly = false;
  unsigned long rawChangedAt = 0;
  unsigned long lastPressAt = 0;
};

KillButtonState killButtonStates[2];

bool updateKillButton(uint8_t slot, bool rawPressed) {
  KillButtonState &button = killButtonStates[slot];
  const unsigned long now = millis();
  if (rawPressed != button.rawPressed) {
    button.rawPressed = rawPressed;
    button.rawChangedAt = now;
  }
  if (button.stablePressed != button.rawPressed &&
      now - button.rawChangedAt >= KILL_BUTTON_DEBOUNCE_MS) {
    button.stablePressed = button.rawPressed;
    if (button.stablePressed) {
      if (button.lastPressAt != 0 && now - button.lastPressAt <= KILL_BUTTON_DOUBLE_CLICK_MS) {
        button.dominantOnly = !button.dominantOnly;
        button.lastPressAt = 0;
      } else {
        button.lastPressAt = now;
      }
    }
  }
  return button.stablePressed;
}

void keepDominantAxis(int16_t *velocity, uint8_t firstAxis) {
  uint8_t dominantAxis = firstAxis;
  int16_t dominantMagnitude = abs(velocity[firstAxis]);
  for (uint8_t axis = firstAxis + 1; axis < firstAxis + 3; axis++) {
    const int16_t magnitude = abs(velocity[axis]);
    if (magnitude > dominantMagnitude) {
      dominantAxis = axis;
      dominantMagnitude = magnitude;
    }
  }
  for (uint8_t axis = firstAxis; axis < firstAxis + 3; axis++) {
    if (axis != dominantAxis) velocity[axis] = 0;
  }
}
} // namespace

void applyKillButtons(int16_t *velocity, int *keyVals) {
  const bool rotationKilled = updateKillButton(0, keyVals[KILLROT] == LOW);
  const bool translationKilled = updateKillButton(1, keyVals[KILLTRANS] == LOW);

  if (rotationKilled) {
    velocity[ROTX] = 0;
    velocity[ROTY] = 0;
    velocity[ROTZ] = 0;
    if (killButtonStates[0].dominantOnly) keepDominantAxis(velocity, TRANSX);
  }
  if (translationKilled) {
    velocity[TRANSX] = 0;
    velocity[TRANSY] = 0;
    velocity[TRANSZ] = 0;
    if (killButtonStates[1].dominantOnly) keepDominantAxis(velocity, ROTX);
  }
}
#else
void applyKillButtons(int16_t *, int *) {}
#endif
#endif
