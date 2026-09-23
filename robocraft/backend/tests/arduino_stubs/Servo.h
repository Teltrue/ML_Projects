#pragma once
#include "Arduino.h"
class Servo {
 public:
  int pin = -1;
  int us = 0;
  void attach(int p, int = 544, int = 2400) { pin = p; }
  void writeMicroseconds(int v) { us = v; }
  void write(int angle) { us = 544 + angle * 10; }
  void setPeriodHertz(int) {}
};
