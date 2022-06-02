"""
CircuitPython script for a raspberry pi pico to handle the input
from the output of a bbc micro keyboard and handle as a normal
HID keyboard.
"""

import time

import digitalio
import board
import pwmio
from adafruit_debouncer import Debouncer
import usb_hid
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS
from adafruit_hid.keycode import Keycode


class Shifted:
    """
    A base key pretends to be a shifted key
    """

    def __init__(self, key: Keycode):
        self.key = key


class AltShift:
    """
    the alternative key is non-standard,
    pretend to be another key when it comes up
    """

    def __init__(self, key, alt_key):
        self.key = key
        self.alt_key = alt_key


keys = {x: {} for x in range(8)}
keys[2][0] = Keycode.F1
keys[7][1] = Keycode.F2
keys[7][2] = Keycode.F3
keys[7][3] = Keycode.F4
keys[1][4] = Keycode.F5
keys[7][4] = Keycode.F6
keys[7][5] = Keycode.F7
keys[1][6] = Keycode.F8
keys[7][6] = Keycode.F9
keys[7][7] = Keycode.F10

keys[7][0] = Keycode.ESCAPE
keys[3][0] = Keycode.ONE
keys[3][1] = Keycode.TWO
keys[1][1] = AltShift(Keycode.THREE, Keycode.POUND)
keys[1][2] = Keycode.FOUR
keys[1][3] = Keycode.FIVE
keys[3][4] = AltShift(Keycode.SIX, Shifted(Keycode.SEVEN))
keys[2][4] = AltShift(Keycode.SEVEN, Keycode.QUOTE)
keys[1][5] = AltShift(Keycode.EIGHT, Shifted(Keycode.NINE))
keys[2][6] = AltShift(Keycode.NINE, Shifted(Keycode.ZERO))
keys[2][7] = Keycode.ZERO
keys[1][7] = AltShift(Keycode.MINUS, Keycode.EQUALS)
keys[1][8] = AltShift(Shifted(Keycode.SIX), Shifted(Keycode.POUND))
keys[7][8] = Keycode.BACKSLASH
keys[1][9] = Keycode.LEFT_ARROW
keys[7][9] = Keycode.RIGHT_ARROW

keys[6][0] = Keycode.TAB
keys[1][0] = Keycode.Q
keys[2][1] = Keycode.W
keys[2][2] = Keycode.E
keys[3][3] = Keycode.R
keys[2][3] = Keycode.T
keys[4][4] = Keycode.Y
keys[3][5] = Keycode.U
keys[2][5] = Keycode.I
keys[3][6] = Keycode.O
keys[3][7] = Keycode.P
keys[4][7] = Shifted(Keycode.QUOTE)  # @
keys[3][8] = Keycode.LEFT_BRACKET
keys[2][8] = AltShift(Shifted(Keycode.MINUS), Shifted(Keycode.THREE))  # _ £
keys[3][9] = Keycode.UP_ARROW
keys[2][9] = Keycode.DOWN_ARROW
keys[4][0] = Keycode.CAPS_LOCK
keys[0][1] = Keycode.LEFT_CONTROL
keys[4][1] = Keycode.A

keys[5][1] = Keycode.S
keys[3][2] = Keycode.D
keys[4][3] = Keycode.F
keys[5][3] = Keycode.G
keys[5][4] = Keycode.H
keys[4][5] = Keycode.J
keys[4][6] = Keycode.K
keys[5][6] = Keycode.L
keys[5][7] = AltShift(Keycode.SEMICOLON, Shifted(Keycode.EQUALS))
keys[4][8] = AltShift(Keycode.KEYPAD_ASTERISK, Shifted(Keycode.SEMICOLON))
keys[5][8] = Keycode.RIGHT_BRACKET
keys[4][9] = Keycode.RETURN

keys[5][0] = Keycode.ALT
keys[0][0] = Keycode.SHIFT
keys[6][1] = Keycode.Z
keys[4][2] = Keycode.X
keys[5][2] = Keycode.C
keys[6][3] = Keycode.V
keys[6][4] = Keycode.B
keys[5][5] = Keycode.N
keys[6][5] = Keycode.M
keys[6][6] = Keycode.COMMA
keys[6][7] = Keycode.PERIOD
keys[6][8] = Keycode.FORWARD_SLASH
keys[5][9] = Keycode.DELETE
keys[6][9] = Keycode.WINDOWS

keys[6][2] = Keycode.SPACEBAR


def int_to_bin(v: int, max: int):
    """
    Convert integer to sequence of boolean values
    """
    s = "{:0{0}b}".replace("{0}", str(max))
    return [True if int(x) else False for x in s.format(v)]


def megahertz_clock(func: function, delay_factor: int = 1):
    """
    Run the passed in function at 1 megahertz
    """
    previous = 0
    while True:
        current_time = time.monotonic_ns()
        if (previous + (100 * delay_factor)) < current_time:
            previous = current_time
            func()


class HIDKeyboard:
  """
  Quick wrapper for HID interface
  """
    def __init__(self):
        self.keyboard = Keyboard(usb_hid.devices)
        self.keyboard_layout = KeyboardLayoutUS(self.keyboard)
        self.shift_down = False

    def key_press(self, value):
        if isinstance(value, str):
            self.keyboard_layout.write(value)
        else:
            self.keyboard.press(value)
        if value == Keycode.SHIFT:
            self.shift_down = True

    def key_release(self, value):
        self.keyboard.release(value)
        if value == Keycode.SHIFT:
            self.shift_down = False

    def align_leds(self):
        LED.caps_lock.set(self.keyboard.led_on(Keyboard.LED_CAPS_LOCK))


bbc_keyboard = HIDKeyboard()


class DebounceInput:
    """
    Modern keyboards seem to have a varying bounce
    Long for the first time, but then lesser after that    
    """

    def __init__(self, delay=0.15, short_delay=0.09):
        self.queue = {}
        self.short_queue = {}
        self.recent_release = None
        self.delay = delay
        self.short_delay = short_delay
        self.no_input_registered = False

    def input(self, value, shift=False):
        now = time.monotonic()
        shift_escape = False
        self.no_input_registered = False
        if isinstance(value, AltShift):
            if bbc_keyboard.shift_down:
                value = value.alt_key
                shift_escape = True
            else:
                value = value.key
        if shift and value == Keycode.BACKSPACE:
            # process shift + break here
            print("SHIFT + BREAK")

        if value not in self.queue:
            self.key_down(value, shift_escape)
            self.queue[value] = now

    def check(self):
        """
        see if any keypresses should be said to have expired
        """

        current_time = time.monotonic()
        for k, v in self.queue.items():
            if self.no_input_registered:
                delay = self.delay / 2
            else:
                delay = self.delay
            if k == self.recent_release:
                delay = self.short_delay
            if v + delay < current_time:
                self.key_up(k)
                self.recent_release = k
                del self.queue[k]

    def no_input(self):
        self.no_input_registered = True

    def key_down(self, value, shift_escape=False):
        # this should interface with hid keyboard
        if shift_escape:
            bbc_keyboard.key_release(Keycode.SHIFT)
        if isinstance(value, Shifted):
            bbc_keyboard.key_press(Keycode.SHIFT)
            bbc_keyboard.key_press(value.key)
            bbc_keyboard.key_release(Keycode.SHIFT)
        else:
            bbc_keyboard.key_press(value)
        if shift_escape:
            bbc_keyboard.key_press(Keycode.SHIFT)

    def key_up(self, value):
        # this should interface with hid keyboard
        if isinstance(value, Shifted):
            bbc_keyboard.key_release(Keycode.SHIFT)
            bbc_keyboard.key_release(value.key)
        else:
            bbc_keyboard.key_release(value)


input_processor = DebounceInput()


class Input:
    def __init__(self, pin: board.PIN, pull=digitalio.Pull.UP):
        self.input = digitalio.DigitalInOut(pin)
        self.input.direction = digitalio.Direction.INPUT
        self.input.pull = pull

    def tripped(self) -> bool:
        return self.input.value is True


class BreakButtonProcessor:
    def __init__(self, pin: board.PIN, label: str):
        self.input = Input(pin)
        self.switch = Debouncer(self.input.input)
        self.label = label

    def check(self):
        self.switch.update()
        if not self.input.tripped():
            shift = bbc.ss.check_shift()
            input_processor.input(self.label, shift=shift)


class Output:
    """
    Wrapper around DigitalInOut that handles some reversed outputs
    """

    def __init__(self, pin: board.PIN, reverse: bool = False):
        self.output = digitalio.DigitalInOut(pin)
        self.output.direction = digitalio.Direction.OUTPUT
        self.reverse = reverse

    def toggle(self):
        self.output.value = not self.output.value

    def set(self, value: bool):
        if value:
            self.output.value = not self.reverse
        else:
            self.output.value = self.reverse

    def set_on(self):
        self.set(True)

    def set_off(self):
        self.set(False)


class HardwareScan:
    """
    Control the built-in hardware scan
    This detects a keypress on anything other than a few modifier keys
    Originally this would have alerted the CPU, which then scans for the actual key
    Can technically be dumped, given as CPU resources aren't a problem
    But it's nice to use the way designed
    """

    clock = Output(board.GP1)
    interrupt = Input(pin=board.GP12)  # ca2

    def __init__(self):
        SoftwareScan.kb_en.value = True
        self.absence_count = 0

    def check(self, trigger_func: function, absence_func: function):
        if HardwareScan.interrupt.tripped():
            HardwareScan.clock.set_off()
            # oh boy a keypress, here we go here we go
            trigger_func()
            self.absence_count = 0
        else:
            self.absence_count += 1
            if self.absence_count > 100:
                absence_func()
                self.absence_count = 0
        # send the clock pulse
        HardwareScan.clock.set_off()
        HardwareScan.clock.set_on()
        bbc_keyboard.align_leds()


class SoftwareScan:
    """
    Implimentation of the software scan function
    Three row pins that indicate which of 8 rows to use.
    Four column pins that indicate which of 16 column to use.
    w_line is high if the row/column combo is currently pressed
    kb_en needs to be set off for the software scan to work.
    """

    row_pins = list(map(Output, [board.GP5, board.GP4, board.GP3]))
    col_pins = list(map(Output, [board.GP9, board.GP8, board.GP7, board.GP6]))
    w_line = Input(pin=board.GP10, pull=digitalio.Pull.DOWN)
    kb_en = Output(board.GP2)
    max_rows = 2 ** len(row_pins)
    max_columns = 2 ** len(col_pins)

    def __init__(self):

        col_pin_count = len(SoftwareScan.col_pins)
        row_pin_count = len(SoftwareScan.row_pins)

        self.r_opts = [int_to_bin(x, row_pin_count) for x in range(2 ** row_pin_count)]
        self.c_opts = [int_to_bin(x, col_pin_count) for x in range(2 ** col_pin_count)]

        def part_zip(pins, options):
            for o in options:
                yield list(zip(pins, o))

        self.col_with_options = list(
            enumerate(list(part_zip(SoftwareScan.col_pins, self.c_opts)))
        )

        self.row_with_options = list(
            enumerate(list(part_zip(SoftwareScan.row_pins, self.r_opts)))
        )

    def no_input(self):
        input_processor.no_input()

    def process(self, row: int, column: int):
        # add more processing here
        try:
            keycode = keys[row][column]
        except Exception:
            keycode = None

        print(f"row: {row}, column: {column}, keycode: {keycode}")
        if keycode:
            input_processor.input(keycode)

    def check_shift(self):
        """
        just check if the shift key is pressed
        # shift is at 0 cols and 0 rows
        """

        SoftwareScan.kb_en.output.value = False
        for pin in SoftwareScan.col_pins:
            pin.output.value = False
        for pin in SoftwareScan.row_pins:
            pin.output.value = False

        HardwareScan.clock.output.value = False
        HardwareScan.clock.output.value = True

        value = bool(SoftwareScan.w_line.input.value)
        SoftwareScan.kb_en.output.value = True
        return value

    def check(self):
        """
        check all row and column combos for an active keypress
        """
        SoftwareScan.kb_en.output.value = False

        for cx, pin_opts in self.col_with_options:
            # set column pin values
            for column, value in pin_opts:
                column.output.value = value
            for rx, pin_opts in self.row_with_options:
                # set row in values
                for row, value in pin_opts:
                    row.output.value = value

                # seem to need to pulse the clock to latch the columns
                HardwareScan.clock.output.value = False
                HardwareScan.clock.output.value = True

                # see if we have a return value
                if SoftwareScan.w_line.input.value is True:
                    self.process(rx, cx)

        SoftwareScan.kb_en.output.value = True


class LED:
    """
    Manage case LEDs
    """

    internal_led = Output(board.GP25)
    caps_lock = Output(board.GP15, reverse=True)
    shift_lock = Output(board.GP14, reverse=True)
    cassette_motor = Output(board.GP13, reverse=True)

    leds = [internal_led, caps_lock, shift_lock, cassette_motor]

    @classmethod
    def set_off(cls):
        for l in cls.leds:
            l.set_off()


class BlinkLed:
    """
    Blink selected LED lights once a second
    """

    leds = [LED.internal_led]
    # leds = LED.leds

    def __init__(self):
        self.pace = 1000
        self.increment = 0
        for l in BlinkLed.leds:
            l.set_off()

    def try_toggle(self):
        self.increment += 1
        if self.increment == self.pace:
            for l in BlinkLed.leds:
                l.toggle()
                self.increment = 0


class BBCKeyboardInterface:
    """ """

    def __init__(self, hardware_scan: bool = True):

        # are we using the hardware scan features or just the software scan?
        self.hardware_scan = hardware_scan

        self.blink = BlinkLed()

        self.hs = HardwareScan()
        self.ss = SoftwareScan()

        if self.hardware_scan is True:
            # if not using the hardware scan this needs to be off
            SoftwareScan.kb_en.set_on()

        # Case LEDs are flipped, enforce off to stop them being on by default
        LED.set_off()

    def check(self):
        """
        this is the main loop function
        """

        # this comes out
        self.blink.try_toggle()
        if self.hardware_scan is True:
            self.hs.check(self.ss.check, self.ss.no_input)
        else:
            self.ss.check()
        break_button.check()
        input_processor.check()

    def loop(self):
        # run the main function at 1MHZ
        megahertz_clock(self.check, delay_factor=1)


bbc = BBCKeyboardInterface(hardware_scan=True)

# the break button is a seperate button, this ties it back into the main input processor
break_button = BreakButtonProcessor(pin=board.GP0, label=Keycode.BACKSPACE)

if __name__ == "__main__":

    bbc.loop()