#ifndef RUNTIMESETTINGS_H
#define RUNTIMESETTINGS_H

#include <Arduino.h>

#define MAX_RUNTIME_KEYS 8
#define RUNTIME_AXIS_COUNT 6

void loadRuntimeKeyOrder();
bool saveRuntimeKeyOrder();
void resetRuntimeKeyOrder();
bool setRuntimeKeyOrder(uint8_t physicalIndex, uint8_t logicalIndex);
uint8_t getRuntimeKeyOrder(uint8_t physicalIndex);
uint8_t getRuntimeButtonCode(uint8_t physicalIndex);
void printRuntimeKeyOrder();
void setSetupTelemetryEnabled(bool enabled);
bool isSetupTelemetryEnabled();
void loadRuntimeAxisMapping();
void resetRuntimeAxisMapping();
bool setRuntimeAxisMapping(uint8_t flags);
bool saveRuntimeAxisMapping();
uint8_t getRuntimeAxisMapping();
void printRuntimeAxisMapping();
void applyRuntimeAxisMapping(int16_t *velocity);

#endif
