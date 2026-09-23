#include "Arduino.h"
unsigned long stub_now_us = 0;
int stub_pin_value[64] = {0};
int stub_pwm_value[64] = {0};
HardwareSerialStub Serial;
