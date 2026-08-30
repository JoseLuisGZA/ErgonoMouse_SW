#include <Arduino.h>
#include <EEPROM.h>
#include "config.h"
#include "parameterMenu.h"
#include "runtimeSettings.h"
#include "kinematics.h"

#if NUMHIDKEYS > MAX_RUNTIME_KEYS
#error "Runtime key remapping supports at most eight HID keys"
#endif

namespace {
const uint32_t KEY_ORDER_MAGIC = 0x454D4B59UL; // "EMKY"
const uint8_t KEY_ORDER_VERSION = 1;
const int KEY_ORDER_ADDRESS = BASE_ADDRESS_PAR + sizeof(ParamStorage);
const uint32_t AXIS_MAP_MAGIC = 0x454D4158UL; // "EMAX"
// Version 2 makes saved bits user overrides only; the corrected hardware signs
// are part of the firmware baseline and therefore do not appear selected in Tune.
const uint8_t AXIS_MAP_VERSION = 2;
const uint8_t AXIS_SWAP_GROUPS_FLAG = 1U << 6;
const uint8_t AXIS_MAP_ALLOWED_FLAGS = 0x7F;
const uint8_t BASELINE_AXIS_INVERT_FLAGS =
    (1U << TRANSX) | (1U << TRANSY) | (1U << ROTZ);
const uint8_t DEFAULT_AXIS_MAP_FLAGS = 0;

struct RuntimeKeyOrderRecord {
  uint32_t magic;
  uint8_t version;
  uint8_t count;
  uint8_t order[MAX_RUNTIME_KEYS];
  uint8_t checksum;
} __attribute__((packed));

const int AXIS_MAP_ADDRESS = KEY_ORDER_ADDRESS + sizeof(RuntimeKeyOrderRecord);

struct RuntimeAxisMapRecord {
  uint32_t magic;
  uint8_t version;
  uint8_t flags;
  uint8_t checksum;
} __attribute__((packed));

uint8_t runtimeKeyOrder[MAX_RUNTIME_KEYS];
uint8_t pendingKeyOrder[MAX_RUNTIME_KEYS];
bool setupTelemetryEnabled = false;
uint8_t runtimeAxisFlags = DEFAULT_AXIS_MAP_FLAGS;
uint8_t pendingAxisFlags = DEFAULT_AXIS_MAP_FLAGS;

#if NUMHIDKEYS > 0
const uint8_t defaultButtonCodes[NUMHIDKEYS] = BUTTONLIST;
#endif

uint8_t checksumFor(const RuntimeKeyOrderRecord &record) {
  uint8_t checksum = record.version ^ record.count;
  for (uint8_t i = 0; i < MAX_RUNTIME_KEYS; i++) {
    checksum ^= record.order[i];
  }
  return checksum;
}

bool recordIsValid(const RuntimeKeyOrderRecord &record) {
  if (record.magic != KEY_ORDER_MAGIC || record.version != KEY_ORDER_VERSION ||
      record.count != NUMHIDKEYS || record.checksum != checksumFor(record)) {
    return false;
  }
  bool used[MAX_RUNTIME_KEYS] = {false};
  for (uint8_t i = 0; i < NUMHIDKEYS; i++) {
    if (record.order[i] >= NUMHIDKEYS || used[record.order[i]]) {
      return false;
    }
    used[record.order[i]] = true;
  }
  return true;
}

bool orderIsValid(const uint8_t *order) {
  bool used[MAX_RUNTIME_KEYS] = {false};
  for (uint8_t i = 0; i < NUMHIDKEYS; i++) {
    if (order[i] >= NUMHIDKEYS || used[order[i]]) return false;
    used[order[i]] = true;
  }
  return true;
}

uint8_t axisChecksumFor(const RuntimeAxisMapRecord &record) {
  return record.version ^ record.flags ^ 0xA5;
}

bool axisRecordIsValid(const RuntimeAxisMapRecord &record) {
  return record.magic == AXIS_MAP_MAGIC && record.version == AXIS_MAP_VERSION &&
         (record.flags & ~AXIS_MAP_ALLOWED_FLAGS) == 0 &&
         record.checksum == axisChecksumFor(record);
}
}

void resetRuntimeKeyOrder() {
  for (uint8_t i = 0; i < MAX_RUNTIME_KEYS; i++) {
    runtimeKeyOrder[i] = i;
    pendingKeyOrder[i] = i;
  }
}

void loadRuntimeKeyOrder() {
  resetRuntimeKeyOrder();
  RuntimeKeyOrderRecord record;
  EEPROM.get(KEY_ORDER_ADDRESS, record);
  if (recordIsValid(record)) {
    for (uint8_t i = 0; i < NUMHIDKEYS; i++) {
      runtimeKeyOrder[i] = record.order[i];
      pendingKeyOrder[i] = record.order[i];
    }
  }
}

bool saveRuntimeKeyOrder() {
  if (!orderIsValid(pendingKeyOrder)) return false;
  RuntimeKeyOrderRecord record;
  record.magic = KEY_ORDER_MAGIC;
  record.version = KEY_ORDER_VERSION;
  record.count = NUMHIDKEYS;
  for (uint8_t i = 0; i < MAX_RUNTIME_KEYS; i++) {
    runtimeKeyOrder[i] = pendingKeyOrder[i];
    record.order[i] = runtimeKeyOrder[i];
  }
  record.checksum = checksumFor(record);
  EEPROM.put(KEY_ORDER_ADDRESS, record);
  return true;
}

bool setRuntimeKeyOrder(uint8_t physicalIndex, uint8_t logicalIndex) {
  if (physicalIndex >= NUMHIDKEYS || logicalIndex >= NUMHIDKEYS) {
    return false;
  }
  pendingKeyOrder[physicalIndex] = logicalIndex;
  return true;
}

uint8_t getRuntimeKeyOrder(uint8_t physicalIndex) {
  return physicalIndex < NUMHIDKEYS ? runtimeKeyOrder[physicalIndex] : physicalIndex;
}

uint8_t getRuntimeButtonCode(uint8_t physicalIndex) {
#if NUMHIDKEYS > 0
  if (physicalIndex < NUMHIDKEYS) {
    return defaultButtonCodes[getRuntimeKeyOrder(physicalIndex)];
  }
#endif
  return 0;
}

void printRuntimeKeyOrder() {
  Serial.print(F("<b"));
  for (uint8_t i = 0; i < NUMHIDKEYS; i++) {
    if (i > 0) Serial.print(',');
    Serial.print(runtimeKeyOrder[i] + 1);
  }
  Serial.println();
}

void setSetupTelemetryEnabled(bool enabled) {
  setupTelemetryEnabled = enabled;
}

bool isSetupTelemetryEnabled() {
  return setupTelemetryEnabled;
}

void resetRuntimeAxisMapping() {
  runtimeAxisFlags = DEFAULT_AXIS_MAP_FLAGS;
  pendingAxisFlags = DEFAULT_AXIS_MAP_FLAGS;
}

void loadRuntimeAxisMapping() {
  resetRuntimeAxisMapping();
  RuntimeAxisMapRecord record;
  EEPROM.get(AXIS_MAP_ADDRESS, record);
  if (axisRecordIsValid(record)) {
    runtimeAxisFlags = record.flags;
    pendingAxisFlags = record.flags;
  }
}

bool setRuntimeAxisMapping(uint8_t flags) {
  if ((flags & ~AXIS_MAP_ALLOWED_FLAGS) != 0) return false;
  runtimeAxisFlags = flags;
  pendingAxisFlags = flags;
  return true;
}

bool saveRuntimeAxisMapping() {
  RuntimeAxisMapRecord record;
  record.magic = AXIS_MAP_MAGIC;
  record.version = AXIS_MAP_VERSION;
  record.flags = pendingAxisFlags;
  record.checksum = axisChecksumFor(record);
  EEPROM.put(AXIS_MAP_ADDRESS, record);
  runtimeAxisFlags = pendingAxisFlags;
  return true;
}

uint8_t getRuntimeAxisMapping() {
  return runtimeAxisFlags;
}

void printRuntimeAxisMapping() {
  Serial.print(F("<g"));
  Serial.println(runtimeAxisFlags);
}

void applyRuntimeAxisMapping(int16_t *velocity) {
  for (uint8_t axis = 0; axis < RUNTIME_AXIS_COUNT; axis++) {
    if (BASELINE_AXIS_INVERT_FLAGS & (1U << axis)) velocity[axis] = -velocity[axis];
  }
  if (runtimeAxisFlags & AXIS_SWAP_GROUPS_FLAG) {
    for (uint8_t axis = 0; axis < 3; axis++) {
      int16_t value = velocity[axis];
      velocity[axis] = velocity[axis + 3];
      velocity[axis + 3] = value;
    }
  }
  for (uint8_t axis = 0; axis < RUNTIME_AXIS_COUNT; axis++) {
    if (runtimeAxisFlags & (1U << axis)) velocity[axis] = -velocity[axis];
  }
}
