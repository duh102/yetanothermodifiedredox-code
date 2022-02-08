import board, neopixel_write, digitalio, time, usb_hid, busio
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keycode import Keycode
from adafruit_bus_device.i2c_device import I2CDevice

SCL = board.GP1
SDA = board.GP0

io_addr = 0x20
IOE_PORTSEL_ADDR = 0x18
IOE_PORT_0_INPUT_ADDR = 0x00
IOE_PORT_1_OUPUT_ADDR = 0x09

ns_in_ms = 1000000
ns_in_s = 1000 * ns_in_ms
target_ns = 1
led_on = False

pin = digitalio.DigitalInOut(board.NEOPIXEL)
pin.direction = digitalio.Direction.OUTPUT
pixel_off = bytearray([0, 0, 0])
pixel_on = bytearray([10, 0, 10])
neopixel_write.neopixel_write(pin, pixel_off)
kbd = Keyboard(usb_hid.devices)

columnPins = [board.GP7,board.GP8,board.GP9,board.GP10,board.GP11,board.GP12,board.GP13]
rowPins = [board.GP2,board.GP3,board.GP4,board.GP5,board.GP6]
statusLedPins = {
    kbd.LED_CAPS_LOCK: board.GP15,
    kbd.LED_NUM_LOCK: board.GP14,
    kbd.LED_SCROLL_LOCK: board.GP16
}

statusLeds = {key: digitalio.DigitalInOut(pin) for key, pin in statusLedPins.items()}
columns = [digitalio.DigitalInOut(pin) for pin in columnPins]
rows = [digitalio.DigitalInOut(pin) for pin in rowPins]
for columnPin in columns:
    columnPin.switch_to_output(value=True)
for rowPin in rows:
    rowPin.switch_to_input(pull=digitalio.Pull.DOWN)
for key, ledPin in statusLeds.items():
    ledPin.switch_to_output(value=False)

i2c = busio.I2C(SCL, SDA)
ioe = I2CDevice(i2c, io_addr)

# configure the IO expander's pins; GP0 0-4 are our rows, GP1 0-6 our columns
# we're using the columns as outputs and rows as inputs (due to the diode direction)
# set port 0 as inputs on 0-4
# the registers are, in order, the port select (0), the interrupt mask (all masked, 0xff), pwm output (all off, 0), inversion selection (all off, 0), input/output selection (1 for the first 5 io, inputs), pullup selection (all off, 0), pulldown selection (1 for the first 5 io, pulldowns)
commbuf = bytearray([IOE_PORTSEL_ADDR, 0, 0xff, 0x00, 0x00, 0b11111, 0, 0xff])
with ioe:
    ioe.write(commbuf)
# port 1 should be set as all outputs by default on startup, but let's make it explicit
commbuf = bytearray([IOE_PORTSEL_ADDR, 1, 0xff, 0x00, 0x00, 0])
with ioe:
    ioe.write(commbuf)

class KeyState(object):
    def __init__(self, x, y):
        self.state = False
        self.x = x
        self.y = y

class KeyDef(object):
    def __init__(self, contents):
        self.contents = contents

    def isModifier(self):
        return False

class Layer(KeyDef):
    def __init__(self, layerId, transformed):
        self.layerId = layerId
        self.transformed = transformed

    def isModifier(self):
        return True

    def keyAt(self, colId, rowId):
        if len(self.transformed) <= colId:
            return None
        col = self.transformed[colId]
        if len(col) <= rowId:
            return None
        return col[rowId]

layerFn = Layer('Function', [[], [KeyDef(Keycode.F1)], [KeyDef(Keycode.F2)], [KeyDef(Keycode.F3)], [KeyDef(Keycode.F4)], [KeyDef(Keycode.F5)],
                             [KeyDef(Keycode.F6)], [KeyDef(Keycode.F7)], [KeyDef(Keycode.F8)], [KeyDef(Keycode.F9)], [KeyDef(Keycode.F10), KeyDef(Keycode.F11), KeyDef(Keycode.F12)]])
layerNav = Layer('Navigation', [[], [None, None, KeyDef(Keycode.LEFT_ARROW)], [None, KeyDef(Keycode.UP_ARROW), KeyDef(Keycode.DOWN_ARROW)], [None, None, KeyDef(Keycode.RIGHT_ARROW)]])
layerNumPad = Layer('Numpad', [[], [], [], [], [], [], [], [], [],
                               [KeyDef(Keycode.KEYPAD_NUMLOCK), KeyDef(Keycode.KEYPAD_SEVEN), KeyDef(Keycode.KEYPAD_FOUR), KeyDef(Keycode.KEYPAD_ONE), KeyDef(Keycode.KEYPAD_ZERO)],
                               [KeyDef(Keycode.KEYPAD_FORWARD_SLASH), KeyDef(Keycode.KEYPAD_EIGHT), KeyDef(Keycode.KEYPAD_FIVE), KeyDef(Keycode.KEYPAD_TWO), KeyDef(Keycode.KEYPAD_ZERO)],
                               [KeyDef(Keycode.KEYPAD_ASTERISK), KeyDef(Keycode.KEYPAD_NINE), KeyDef(Keycode.KEYPAD_SIX), KeyDef(Keycode.KEYPAD_THREE), KeyDef(Keycode.KEYPAD_PERIOD)],
                               [KeyDef(Keycode.KEYPAD_MINUS), KeyDef(Keycode.KEYPAD_PLUS), KeyDef(Keycode.KEYPAD_PLUS), KeyDef(Keycode.KEYPAD_ENTER), KeyDef(Keycode.KEYPAD_ENTER)]])

# default map, without any modifiers applied
keycodeMap = [
    # left half
    # matrix is columns from 0 to 13, 0-6 are left half, 7-13 right half
    # keys are indexed from top to bottom, 0 to 4
    [KeyDef(Keycode.ESCAPE), KeyDef(Keycode.TAB), KeyDef(Keycode.CAPS_LOCK), KeyDef(Keycode.LEFT_SHIFT), KeyDef(Keycode.LEFT_CONTROL)],
    [KeyDef(Keycode.ONE), KeyDef(Keycode.Q), KeyDef(Keycode.A), KeyDef(Keycode.Z), KeyDef(Keycode.GUI)],
    [KeyDef(Keycode.TWO), KeyDef(Keycode.W), KeyDef(Keycode.S), KeyDef(Keycode.X), layerFn],
    [KeyDef(Keycode.THREE), KeyDef(Keycode.E), KeyDef(Keycode.D), KeyDef(Keycode.C), KeyDef(Keycode.MINUS)],
    [KeyDef(Keycode.FOUR), KeyDef(Keycode.R), KeyDef(Keycode.F), KeyDef(Keycode.V), KeyDef(Keycode.LEFT_ALT)],
    [KeyDef(Keycode.FIVE), KeyDef(Keycode.T), KeyDef(Keycode.G), KeyDef(Keycode.B), KeyDef(Keycode.SPACEBAR)],
    [KeyDef(Keycode.GRAVE_ACCENT), KeyDef(Keycode.HOME), KeyDef(Keycode.END), KeyDef(Keycode.LEFT_BRACKET), layerNumPad],
    # right half
    [KeyDef(Keycode.INSERT), KeyDef(Keycode.BACKSPACE), KeyDef(Keycode.ENTER), KeyDef(Keycode.RIGHT_BRACKET), layerNav],
    [KeyDef(Keycode.SIX), KeyDef(Keycode.Y), KeyDef(Keycode.H), KeyDef(Keycode.N), KeyDef(Keycode.SPACEBAR)],
    [KeyDef(Keycode.SEVEN), KeyDef(Keycode.U), KeyDef(Keycode.J), KeyDef(Keycode.M), KeyDef(Keycode.RIGHT_ALT)],
    [KeyDef(Keycode.EIGHT), KeyDef(Keycode.I), KeyDef(Keycode.K), KeyDef(Keycode.COMMA), KeyDef(Keycode.BACKSLASH)],
    [KeyDef(Keycode.NINE), KeyDef(Keycode.O), KeyDef(Keycode.L), KeyDef(Keycode.PERIOD), KeyDef(Keycode.EQUALS)],
    [KeyDef(Keycode.ZERO), KeyDef(Keycode.P), KeyDef(Keycode.SEMICOLON), KeyDef(Keycode.FORWARD_SLASH), KeyDef(Keycode.RIGHT_GUI)],
    [KeyDef(Keycode.PAGE_UP), KeyDef(Keycode.PAGE_DOWN), KeyDef(Keycode.QUOTE), KeyDef(Keycode.RIGHT_SHIFT), KeyDef(Keycode.RIGHT_CONTROL)],
]

matrix = {
  colIdx: {
    rowIdx: KeyState(colIdx, rowIdx) for rowIdx in range(5)
  } for colIdx in range(14)
}

reverseMatrix = {}
pressedKeys = []
modifiers = []

def enable_modifier(layer):
  modifiers.append(layer)

def disable_modifier(layer):
    try:
        modifiers.remove(layer)
    except ValueError:
        pass

def scan_rh_column(colNum):
    # if colNum is >=7, we're using left-indexed and should modulo 7
    # else we're using right-indexed, and can leave it alone
    colNum = colNum % 7

    commbuf = bytearray([IOE_PORT_1_OUPUT_ADDR, 1<<colNum])
    with ioe:
        ioe.write(commbuf)
    commbuf = bytearray([IOE_PORT_0_INPUT_ADDR])
    inbuf = bytearray(1)
    with ioe:
        ioe.write_then_readinto(commbuf, inbuf)
    rowScan = []
    for i in range(5):
        rowScan.append(inbuf[0] & 1<<i)
    return rowScan

def checkKey(colIdx, rowIdx, keyDown, pressedKeys, releasedKeys):
    keyState = matrix.get(colIdx, {}).get(rowIdx, None)
    if keyState is None:
        return
    if keyDown == keyState.state:
        return
    keydef = getKeydef(colIdx, rowIdx)
    keyState.state = keyDown
    if keyDown:
        if keydef.isModifier():
          enable_modifier(keydef)
        else:
          pressedKeys.append(keyState)
    else:
        if keydef.isModifier():
          disable_modifier(keydef)
        else:
          try:
            pressedKeys.remove(keyState)
          except ValueError:
            pass
          releasedKeys.append(keyState)

def getKeydef(colIdx, rowIdx):
    if len(modifiers) > 0:
        for layer in modifiers[::-1]:
            keyDef = layer.keyAt(colIdx, rowIdx)
            if keyDef is not None:
                return keyDef
    return keycodeMap[colIdx][rowIdx]

def getKeycode(colIdx, rowIdx):
    keyDef = getKeydef(colIdx, rowIdx)
    if keyDef.isModifier():
        return None
    return keyDef.contents

def doKeyboard(pressedKeys):
    releasedKeys = []
    # scan all the keys on the left half
    for cidx, columnPin in enumerate(columns):
        try:
            columnPin.value = True
            for ridx, rowPin in enumerate(rows):
                # keyState is True when pressed, False when released
                # rowPin, on the other hand, is pulled down when pressed, hence it will be False
                keyDown = rowPin.value
                checkKey(cidx, ridx, keyDown, pressedKeys, releasedKeys)
        finally:
            columnPin.value = False
    # scan all the keys on the right half
    ## left-indexing, so starting at 7 and going to 14
    for cidx in range(7,14):
        keysDown = scan_rh_column(cidx)
        for ridx, keyDown in enumerate(keysDown):
            checkKey(cidx, ridx, keyDown, pressedKeys, releasedKeys)

    # send any released keys
    if len(releasedKeys) > 0:
        keycodes = []
        for keystate in releasedKeys:
            contents = getKeycode(keystate.x, keystate.y)
            if contents is not None:
                keycodes.append(contents)
        kbd.release(*keycodes)
    # then send any keys still depressed (sorry keys :( )
    if len(pressedKeys) > 0:
        keycodes = []
        for keystate in pressedKeys:
            contents = getKeycode(keystate.x, keystate.y)
            if contents is not None:
                keycodes.append(contents)
        kbd.press(*keycodes)
    for keycode, ledPin  in statusLeds.items():
      if kbd.led_on(keycode):
        ledPin.value = True
      else:
        ledPin.value = False

while True:
    beforeScan = time.monotonic_ns()
    doKeyboard(pressedKeys)
    afterScan = time.monotonic_ns()
    sleepTime = (target_ns - (afterScan - beforeScan)) / ns_in_s
    if sleepTime > 0:
      time.sleep(sleepTime)
    led_on = not led_on
    if led_on:
        neopixel_write.neopixel_write(pin, pixel_on)
    else:
        neopixel_write.neopixel_write(pin, pixel_off)
