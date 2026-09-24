# Tello flight controller

Fly a DJI/Ryze Tello with a gamepad or the keyboard. A pygame window shows battery,
height, speed and the live stick values, plus the camera feed if you ask for it.

## Run it

```bash
pip install -r requirements.txt
# Turn the drone on and connect your computer to its Wi-Fi (TELLO-XXXXXX), then:
python flight_controller.py            # telemetry window only
python flight_controller.py --video    # also show the camera feed
python flight_controller.py --speed 30 # start slower (10-100, default 50)
```

Click the window so it has focus before using the keyboard.

## Controls

| Action            | Keyboard   | Gamepad (Xbox layout) |
| ----------------- | ---------- | --------------------- |
| Take off / land   | T / L      | A / B                 |
| Forward, back, left, right | Arrow keys | Right stick  |
| Up / down         | W / S      | Left stick up/down    |
| Rotate            | A / D      | Left stick left/right |
| Flip forward      | F          | Y                     |
| Slower / faster   | - / =      | LB / RB               |
| **Emergency stop** (motors cut, the drone drops) | Backspace | Back / View |
| Land and quit     | Esc        | –                     |

Keyboard and gamepad work together, and you can plug the gamepad in or pull it out
mid-flight. If it disconnects, the drone hovers.

## Safety

- Closing the window, pressing Esc or hitting Ctrl+C lands the drone before exiting.
- The drone refuses to take off at 10% battery or less and lands on its own if the
  battery drops that low in flight. Flips need at least 50% battery.
- Emergency stop cuts the motors mid-air. Only use it if landing is not an option.

## Gamepad mapping

The button and axis numbers at the top of `flight_controller.py` match an Xbox pad on
Windows and macOS. On Linux the right stick is usually axes 3 and 4. PlayStation pads
number their buttons differently too. The **Last input** line in the window shows the
number of each button or stick you move, so you can find the right numbers and edit
`AXIS_*` and `BUTTON_ACTIONS`.
