// Minimal host-side stand-in for the Arduino core, used only to compile-check and unit-test
// generated sketches with g++. Time advances when the sketch calls delay().
#pragma once
#include <ctype.h>
#include <math.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

#define HIGH 1
#define LOW 0
#define INPUT 0
#define OUTPUT 1

class __FlashStringHelper;
#define F(s) (reinterpret_cast<const __FlashStringHelper *>(s))

extern unsigned long stub_now_us;
extern int stub_pin_value[64];
extern int stub_pwm_value[64];
inline unsigned long millis() { return stub_now_us / 1000UL; }
inline unsigned long micros() { return stub_now_us; }
inline void delay(unsigned long ms) { stub_now_us += ms * 1000UL; }
inline void delayMicroseconds(unsigned int us) { stub_now_us += us; }
inline void pinMode(int, int) {}
inline void digitalWrite(int pin, int v) { stub_pin_value[pin] = v; }
inline int digitalRead(int pin) { return stub_pin_value[pin]; }
inline void analogWrite(int pin, int v) { stub_pwm_value[pin] = v; }
inline unsigned long pulseIn(int, int, unsigned long timeout = 1000000UL) { (void)timeout; return 0; }

class HardwareSerialStub {
 public:
  void begin(long) {}
  int available() { return 0; }
  int read() { return -1; }
  float parseFloat() { return 0.0f; }
  long parseInt() { return 0; }
  size_t print(const __FlashStringHelper *s) { return printf("%s", reinterpret_cast<const char *>(s)); }
  size_t print(const char *s) { return printf("%s", s); }
  size_t print(double v, int digits = 2) { return printf("%.*f", digits, v); }
  size_t print(int v) { return printf("%d", v); }
  size_t println(const __FlashStringHelper *s) { return printf("%s\n", reinterpret_cast<const char *>(s)); }
  size_t println(const char *s) { return printf("%s\n", s); }
  size_t println(double v, int digits = 2) { return printf("%.*f\n", digits, v); }
  size_t println() { return printf("\n"); }
};
extern HardwareSerialStub Serial;
