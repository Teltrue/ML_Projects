"""Tello flight controller: fly a DJI/Ryze Tello with a gamepad or the keyboard.

Connect your computer to the drone's Wi-Fi (TELLO-XXXXXX), then run:

    python flight_controller.py            # telemetry window only
    python flight_controller.py --video    # also show the camera feed

Keyboard (click the window first so it has focus):
    T / L            take off / land
    Arrow keys       forward, back, left, right
    W / S            up / down
    A / D            rotate left / right
    F                flip forward (needs 50%+ battery)
    - / =            slower / faster
    Backspace        EMERGENCY: cuts the motors, the drone drops
    Esc              land and quit

Gamepad (Xbox layout, "Mode 2" sticks):
    Left stick       up/down and rotate
    Right stick      forward/back and left/right
    A / B            take off / land
    Y                flip forward
    LB / RB          slower / faster
    Back / View      EMERGENCY

Closing the window, pressing Esc or Ctrl+C in the terminal all land the drone
before the program exits.
"""

import argparse
import math
import sys

import pygame
from djitellopy import Tello

FPS = 30                # control loop rate; one RC command is sent per loop
DEADZONE = 0.15         # ignore small stick drift
DEFAULT_SPEED = 50      # RC command scale in % of the Tello's max speed
MIN_SPEED, MAX_SPEED, SPEED_STEP = 10, 100, 10
LOW_BATTERY = 20        # % where the HUD turns red
CRITICAL_BATTERY = 10   # % where the drone lands on its own
FLIP_MIN_BATTERY = 50   # the Tello refuses to flip below this

# Gamepad layout. These match an Xbox pad on Windows and macOS. Other pads and
# Linux can number them differently; the "Last input" line in the window shows
# the number of the button or axis you just moved, so you can fix them here.
AXIS_YAW = 0            # left stick X
AXIS_UP_DOWN = 1        # left stick Y
AXIS_LEFT_RIGHT = 2     # right stick X (3 on Linux)
AXIS_FORWARD_BACK = 3   # right stick Y (4 on Linux)

BUTTON_ACTIONS = {
    0: "takeoff",       # A
    1: "land",          # B
    3: "flip",          # Y
    4: "slower",        # LB
    5: "faster",        # RB
    6: "emergency",     # Back / View
}

KEY_ACTIONS = {
    pygame.K_t: "takeoff",
    pygame.K_l: "land",
    pygame.K_f: "flip",
    pygame.K_MINUS: "slower",
    pygame.K_KP_MINUS: "slower",
    pygame.K_EQUALS: "faster",
    pygame.K_KP_PLUS: "faster",
    pygame.K_BACKSPACE: "emergency",
}

WHITE = (240, 240, 240)
GREEN = (90, 220, 120)
YELLOW = (250, 210, 80)
RED = (255, 90, 90)
BACKGROUND = (20, 24, 30)


def parse_args():
    parser = argparse.ArgumentParser(description="Fly a Tello with a gamepad or keyboard.")
    parser.add_argument("--video", action="store_true", help="show the drone's camera feed")
    parser.add_argument("--speed", type=int, default=DEFAULT_SPEED,
                        help=f"starting speed, {MIN_SPEED}-{MAX_SPEED} (default {DEFAULT_SPEED})")
    return parser.parse_args()


def read_axis(joystick, index):
    """Stick position in -1..1, zero inside the deadzone and rescaled outside it."""
    if index >= joystick.get_numaxes():
        return 0.0
    value = joystick.get_axis(index)
    if abs(value) < DEADZONE:
        return 0.0
    return (value - math.copysign(DEADZONE, value)) / (1 - DEADZONE)


def read_controls(joystick, speed):
    """Combine keyboard and gamepad input into Tello RC values (-100..100)."""
    keys = pygame.key.get_pressed()
    left_right = (keys[pygame.K_RIGHT] - keys[pygame.K_LEFT]) * speed
    forward_back = (keys[pygame.K_UP] - keys[pygame.K_DOWN]) * speed
    up_down = (keys[pygame.K_w] - keys[pygame.K_s]) * speed
    yaw = (keys[pygame.K_d] - keys[pygame.K_a]) * speed

    if joystick is not None:
        # Pushing a stick up gives a negative value, so the Y axes are flipped.
        left_right += read_axis(joystick, AXIS_LEFT_RIGHT) * speed
        forward_back -= read_axis(joystick, AXIS_FORWARD_BACK) * speed
        up_down -= read_axis(joystick, AXIS_UP_DOWN) * speed
        yaw += read_axis(joystick, AXIS_YAW) * speed

    return tuple(max(-100, min(100, round(v))) for v in (left_right, forward_back, up_down, yaw))


def run_action(drone, action):
    """Run a one-shot command and return a status message for the HUD."""
    if action == "emergency":
        drone.emergency()
        return "EMERGENCY STOP: motors cut"

    battery = drone.get_battery()
    if action == "takeoff":
        if drone.is_flying:
            return "Already flying"
        if battery <= CRITICAL_BATTERY:
            return f"Battery too low to take off ({battery}%)"
        drone.takeoff()
        return "Airborne"
    if action == "land":
        if not drone.is_flying:
            return "Already on the ground"
        drone.land()
        return "Landed"
    if action == "flip":
        if not drone.is_flying:
            return "Take off before flipping"
        if battery < FLIP_MIN_BATTERY:
            return f"Flips need {FLIP_MIN_BATTERY}%+ battery (now {battery}%)"
        drone.flip_forward()
        return "Flip!"
    return ""


def draw(screen, font, frame, lines, help_text):
    if frame is not None:
        height, width = frame.shape[:2]
        image = pygame.image.frombuffer(frame.tobytes(), (width, height), "RGB")
        screen.blit(pygame.transform.scale(image, screen.get_size()), (0, 0))
    else:
        screen.fill(BACKGROUND)

    line_height = font.get_linesize()
    panel = pygame.Surface((screen.get_width(), line_height * len(lines) + 16), pygame.SRCALPHA)
    panel.fill((0, 0, 0, 150))
    screen.blit(panel, (0, 0))
    for i, (text, color) in enumerate(lines):
        screen.blit(font.render(text, True, color), (10, 8 + i * line_height))

    y = screen.get_height() - line_height * len(help_text) - 8
    panel = pygame.Surface((screen.get_width(), screen.get_height() - y), pygame.SRCALPHA)
    panel.fill((0, 0, 0, 150))
    screen.blit(panel, (0, y))
    for i, text in enumerate(help_text):
        screen.blit(font.render(text, True, WHITE), (10, y + 4 + i * line_height))

    pygame.display.flip()


def main():
    args = parse_args()
    speed = max(MIN_SPEED, min(MAX_SPEED, args.speed))

    pygame.init()
    pygame.joystick.init()

    joystick = None

    if pygame.joystick.get_count() > 0:
        joystick = pygame.joystick.Joystick(0)
        joystick.init()
        print(f"Controller detected: {joystick.get_name()}")
    else:
        print("No controller found. Keyboard fallback enabled.")

    drone = Tello()
    try:
        drone.connect()
    except Exception as exc:
        print(f"Could not connect to the Tello: {exc}")
        print("Turn the drone on and connect this computer to its Wi-Fi (TELLO-XXXXXX).")
        pygame.quit()
        sys.exit(1)

    print(f"Battery Life: {drone.get_battery()}%")

    screen = pygame.display.set_mode((960, 720) if args.video else (720, 420))
    pygame.display.set_caption("Tello Flight Controller")
    font = pygame.font.Font(None, 28)
    clock = pygame.time.Clock()

    frame_read = None
    if args.video:
        try:
            drone.streamon()
            frame_read = drone.get_frame_read()
        except Exception as exc:
            print(f"Video unavailable, flying without it: {exc}")

    help_text = [
        "T/L takeoff/land   Arrows move   W/S up/down   A/D rotate   F flip",
        "-/= speed   Backspace EMERGENCY   Esc land & quit",
    ]
    message = "Ready. Press T (or A on the gamepad) to take off."
    last_input = "-"
    running = True

    try:
        while running:
            actions = []
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key in KEY_ACTIONS:
                        actions.append(KEY_ACTIONS[event.key])
                elif event.type == pygame.JOYBUTTONDOWN:
                    last_input = f"button {event.button}"
                    if event.button in BUTTON_ACTIONS:
                        actions.append(BUTTON_ACTIONS[event.button])
                elif event.type == pygame.JOYAXISMOTION and abs(event.value) > 0.5:
                    last_input = f"axis {event.axis}"
                elif event.type == pygame.JOYDEVICEADDED and joystick is None:
                    joystick = pygame.joystick.Joystick(event.device_index)
                    message = f"Controller connected: {joystick.get_name()}"
                elif (event.type == pygame.JOYDEVICEREMOVED and joystick is not None
                        and event.instance_id == joystick.get_instance_id()):
                    # Drop the pad so its last stick position isn't replayed forever.
                    joystick = None
                    message = "Controller disconnected - hovering. Use the keyboard."

            for action in actions:
                if action == "slower":
                    speed = max(MIN_SPEED, speed - SPEED_STEP)
                elif action == "faster":
                    speed = min(MAX_SPEED, speed + SPEED_STEP)
                else:
                    try:
                        message = run_action(drone, action)
                    except Exception as exc:
                        message = f"{action} failed: {exc}"

            battery = drone.get_battery()
            if drone.is_flying and battery <= CRITICAL_BATTERY:
                message = f"Battery critical ({battery}%) - landing"
                try:
                    drone.land()
                except Exception as exc:
                    message = f"Auto-land failed: {exc}"

            rc = read_controls(joystick, speed)
            if drone.is_flying:
                # Sent every loop, even when all zero: this holds the hover and
                # stops the Tello's 15 s no-command auto-land.
                drone.send_rc_control(*rc)

            lines = [
                ("FLYING" if drone.is_flying else "LANDED", GREEN if drone.is_flying else YELLOW),
                (f"Battery: {battery}%", RED if battery < LOW_BATTERY else WHITE),
                (f"Height: {drone.get_height()} cm   Flight time: {drone.get_flight_time()} s", WHITE),
                (f"Speed: {speed}%   RC (lr fb ud yaw): {rc[0]} {rc[1]} {rc[2]} {rc[3]}", WHITE),
                (f"Controller: {joystick.get_name() if joystick else 'keyboard only'}"
                 f"   Last input: {last_input}", WHITE),
                (message, YELLOW),
            ]
            frame = frame_read.frame if frame_read is not None else None
            draw(screen, font, frame, lines, help_text)
            clock.tick(FPS)
    finally:
        # Also runs on Ctrl+C or a crash, so the drone never flies off unattended.
        if drone.is_flying:
            print("Landing...")
            try:
                drone.land()
            except Exception as exc:
                print(f"Landing failed ({exc}). The Tello lands by itself after 15 s without commands.")
        drone.end()
        pygame.quit()
        print("Goodbye!")


if __name__ == "__main__":
    main()
