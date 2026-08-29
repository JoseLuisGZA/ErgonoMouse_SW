#include <Arduino.h>
#include <EEPROM.h>
#include "config.h"
#include "parameterMenu.h"
#include "runtimeSettings.h"

#if NUMHIDKEYS > MAX_RUNTIME_KEYS
#error "Runtime key remapping supports at most eight HID keys"
#endif

namespace {
const uint32_t KEY_ORDER_MAGIC = 0x454D4B59UL; // "EMKY"
const uint8_t KEY_ORDER_VERSION = 1;
const int KEY_ORDER_ADDRESS = BASE_ADDRESS_PAR + sizeof(ParamStorage);

struct RuntimeKeyOrderRecord {
  uint32_t magic;
  uint8_t version;
  uint8_t count;
  uint8_t order[MAX_RUNTIME_KEYS];
  uint8_t checksum;
} __attribute__((packed));

uint8_t runtimeKeyOrder[MAX_RUNTIME_KEYS];
uint8_t pendingKeyOrder[MAX_RUNTIME_KEYS];

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
