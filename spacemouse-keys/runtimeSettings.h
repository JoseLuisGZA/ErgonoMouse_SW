#ifndef RUNTIMESETTINGS_H
#define RUNTIMESETTINGS_H

#include <Arduino.h>

#define MAX_RUNTIME_KEYS 8

void loadRuntimeKeyOrder();
bool saveRuntimeKeyOrder();
void resetRuntimeKeyOrder();
bool setRuntimeKeyOrder(uint8_t physicalIndex, uint8_t logicalIndex);
uint8_t getRuntimeKeyOrder(uint8_t physicalIndex);
uint8_t getRuntimeButtonCode(uint8_t physicalIndex);
void printRuntimeKeyOrder();
void setSetupTelemetryEnabled(bool enabled);
bool isSetupTelemetryEnabled();

#endif
