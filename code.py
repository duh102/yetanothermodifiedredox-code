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
target_ns = 50 * ns_in_ms
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
commbuf = bytearray([IOE_PORTSEL_ADDR, 0, 0xff, 0x00, 0x00, 0b11111])
with ioe:
    ioe.write(commbuf)
# port 1 should be set as all outputs by default on startup, but let's make it explicit
commbuf = bytearray([IOE_PORTSEL_ADDR, 1, 0xff, 0x00, 0x00, 0])
with ioe:
    ioe.write(commbuf)
    
class KeyState(object):
    def __init__(self, keycode, isModifier=None):
        self.keycode = keycode
        self.state = False
        self.isModifier = isModifier
        if self.isModifier is None:
            self.isModifier = False
            
class Layer(object):
    def __init__(self, layerId, transformed):
        self.layerId = layerId
        self.transformed = transformed

layerFn = Layer('Function', {Keycode.ONE: Keycode.F1, Keycode.TWO: Keycode.F2, Keycode.THREE: Keycode.F3, Keycode.FOUR: Keycode.F4, Keycode.FIVE: Keycode.F5, Keycode.W: Keycode.UP_ARROW, Keycode.A: Keycode.LEFT_ARROW, Keycode.D: Keycode.RIGHT_ARROW, Keycode.S: Keycode.DOWN_ARROW})
layerNav = Layer('Navigation', {})
layerNumPad = Layer('Numpad', {})


matrix = {
    0: {
      0:KeyState(Keycode.GRAVE_ACCENT),
      1:KeyState(Keycode.TAB),
      2:KeyState(Keycode.CAPS_LOCK),
      3:KeyState(Keycode.LEFT_SHIFT),
      4:KeyState(Keycode.LEFT_CONTROL)
    },
    1: {
      0:KeyState(Keycode.ONE),
      1:KeyState(Keycode.Q),
      2:KeyState(Keycode.A),
      3:KeyState(Keycode.Z),
      4:KeyState(Keycode.GUI)
    },
    2: {
      0:KeyState(Keycode.TWO),
      1:KeyState(Keycode.W),
      2:KeyState(Keycode.S),
      3:KeyState(Keycode.X),
      4:KeyState(layerFn, isModifier=True)
    },
    3: {
      0:KeyState(Keycode.THREE),
      1:KeyState(Keycode.E),
      2:KeyState(Keycode.D),
      3:KeyState(Keycode.C),
      4:KeyState(Keycode.MINUS)
    },
    4: {
      0:KeyState(Keycode.FOUR),
      1:KeyState(Keycode.R),
      2:KeyState(Keycode.F),
      3:KeyState(Keycode.V),
      4:KeyState(Keycode.LEFT_ALT)
    },
    5: {
      0:KeyState(Keycode.FIVE),
      1:KeyState(Keycode.T),
      2:KeyState(Keycode.G),
      3:KeyState(Keycode.B),
      4:KeyState(Keycode.SPACEBAR)
    },
    6: {
      0:KeyState(Keycode.ESCAPE),
      1:KeyState(layerNav, isModifier=True),
      2:KeyState(Keycode.LEFT_BRACKET),
      3:KeyState(Keycode.HOME),
      4:KeyState(Keycode.END)
    },
    7: {
      0:KeyState(Keycode.INSERT),
      1:KeyState(Keycode.SIX),
    },
    8: {
      0:KeyState(Keycode.BACKSPACE),
      1:KeyState(Keycode.Y),
    }
}

reverseMatrix = {}
pressedKeys = []
modifiers = []

## check the whole matrix, make sure it's a sane configuration
brokenMatrixEntries = []
for column, columnCon in matrix.items():
  for row, rowCon in columnCon.items():
    if not (hasattr(rowCon, 'keycode') and hasattr(rowCon, 'state') and hasattr(rowCon, 'isModifier')):
      brokenMatrixEntries.append((column, row, rowCon, 'attributes keycode {} state {} isModifier {}'.format(hasattr(rowCon, 'keycode'), hasattr(rowCon, 'state'), hasattr(rowCon, 'isModifier'))))
      continue
    if type(rowCon.keycode) != int and not rowCon.isModifier:
      brokenMatrixEntries.append((column,  row, rowCon, 'keycode not integer but key not modifier'))
      continue
    if rowCon.keycode not in reverseMatrix:
      reverseMatrix[rowCon.keycode] = []
    reverseMatrix[rowCon.keycode].append((column, row))

def enable_modifier(layer):
  modifiers.append(layer)
  for keycode in pressedKeys.copy():
    if keycode in layer.transformed:
      try:
        pressedKeys.remove(keycode)
      except ValueError:
        pass
      releasedKeys.append(keycode)
      pressedKeys.append(layer.transformed.get(keycode))
  for keycode, trans in layer.transformed.items():
    replacedKeys = reverseMatrix.get(keycode)
    if replacedKeys is None:
      continue
    for replacedKey in replacedKeys:
      matrix[replacedKey[0]][replacedKey[1]].keycode = trans
      
def disable_modifier(layer):
    modifiers.remove(layer)
    ## we have to release the modified keys and press the unmodified keys now
    for keycode, trans in layer.transformed.items():
      replacedKeys = reverseMatrix.get(keycode)
      ## if we still have modifiers in the stack, we have to see if any modifiers also modified the current keys
      if len(modifiers) > 0:
        for newLayer in modifiers[::-1]:
          if keycode in newLayer.transformed:
            keycode = newLayer.transformed[keycode]
            break
      if replacedKeys is not None:
        for replacedKey in replacedKeys:
          matrix[replacedKey[0]][replacedKey[1]].keycode = keycode
      if trans in pressedKeys:
        try:
          pressedKeys.remove(trans)
        except ValueError:
          pass
        pressedKeys.add(keycode)
        releasedKeys.add(trans)
        
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
    keyState.state = keyDown
    if keyDown:
        if keyState.isModifier:
          enable_modifier(keyState.keycode)
        else:
          pressedKeys.append(keyState.keycode)
    else:
        if keyState.isModifier:
          disable_modifier(keyState.keycode)
        else:
          try:
            pressedKeys.remove(keyState.keycode)
          except ValueError:
            pass
          releasedKeys.append(keyState.keycode)

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
        kbd.release(*releasedKeys)
    # then send any keys still depressed (sorry keys :( )
    if len(pressedKeys) > 0:
        kbd.press(*pressedKeys)
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