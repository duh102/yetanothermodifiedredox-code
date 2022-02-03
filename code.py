import board, neopixel_write, digitalio, time, usb_hid
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keycode import Keycode

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


def doKeyboard(pressedKeys):
    releasedKeys = []
    # scan all the keys
    for cidx, columnPin in enumerate(columns):
        try:
            columnDict = matrix.get(cidx, {})
            columnPin.value = True
            for ridx, rowPin in enumerate(rows):
                keyState = columnDict.get(ridx, None)
                if keyState is None:
                    continue
                # keyState is True when pressed, False when released
                # rowPin, on the other hand, is pulled down when pressed, hence it will be False
                if rowPin.value == keyState.state:
                    continue
                keyState.state = rowPin.value
                if rowPin.value:
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
        finally:
            columnPin.value = False
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