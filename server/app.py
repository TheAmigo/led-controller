#!/usr/bin/env python3
#vim: ts=4:et:ai:smartindent

# Copyright 2022 Josh Harding
# licensed under the terms of the MIT license, see LICENSE file

from flask import Flask, json, abort
from threading import Timer
from colorzero import Color
from wiringpi import digitalWrite, pwmWrite, pinMode, OUTPUT, PWM_OUTPUT, wiringPiSetupGpio
from datetime import datetime, timedelta
import configparser

HAVE_PCA = True
try:
    from adafruit_pca9685 import PCA9685
    from board import SCL, SDA
    import busio
except ImportError:
    HAVE_PCA = False

# Global config
MAX_LEVEL = 100      # Accept percentages from client
PWM_PIN = 18         # Used if no config file is present
PWM_MAX = 0x0400     # Pi's PWM scale
PCA_MAX = 0xFFFF     # 12-bit resolution at the top of a 16-bit register
MIN_STEP_TIME = 0.01 # 100fps is fast enough for me
MIN_STEP_SIZE = MAX_LEVEL/PWM_MAX

# Base class for controlling an LED with a GPIO pin
class LEDPin:
    def __init__(self, name, pin, level):
        self.name = name
        self.level = 1 if level == 'on' else 0
        if pin == None:
            raise Exception(f"[{name}] missing pin number")
        self.pin = int(pin)
        self.pintype = 'onoff'
        pinMode(self.pin, OUTPUT)
        self.set_level()

    def on(self):
        self.level = 1
        return self.set_level()

    def off(self):
        self.level = 0
        return self.set_level()

    def fade(self, target, duration):
        if target > 0.5:
            self.on()
        else:
            self.off()
        return self.status()

    def set_level(self):
        self.log_level()
        if self.level > 0.5:
            digitalWrite(self.pin, 1)
        else:
            digitalWrite(self.pin, 0)
        return self.status()

    def log_level(self):
        print(f'{datetime.now()}: {self.name} level={self.level}')
        
    def status(self):
        return json.dumps({'level': self.level})

class LEDPWM(LEDPin):
    def __init__(self, name, pin, level):
        self.name = name
        self.pin = 18 if pin == None else int(pin)
        if level == 'on':
            self.level = 1
        elif level == 'off':
            self.level = 0
        else:
            self.level = float(level)
        self.timer = None
        self.target = self.level
        self.target_time = 0
        self.last_on_level = self.level if self.level > 0 else 100
        self.pintype = 'pwm'
        pinMode(self.pin, PWM_OUTPUT)
        self.fade(self.target, 0)

    def on(self, fade_time=1):
        return self.fade(self.last_on_level, fade_time)

    def off(self, fade_time=1):
        if self.level > 0:
            self.last_on_level = self.level
        return self.fade(0, fade_time)

    def fade(self, newlevel, fadetime):
        self.stop_timer()
        self.target = newlevel
        self.prev_level = self.level
        now = datetime.now()
        if self.level == self.target or fadetime == 0:
            print(f'{now}: {self.name} -- setting level from {self.level} to {self.target}')
            self.level = self.target
            self.set_level()
        else:
            print(f'{now}: {self.name} -- fading from {self.level} to {newlevel} in {fadetime} seconds')
            self.target_time = now + timedelta(seconds=fadetime)
            (step_time, step_level) = self.calc_next_step()
            self.timer = Timer(step_time, self.fade_step, {step_level})
            self.timer.start()
        return self.status()

    def fade_step(self, step_level):
        done = False
        if self.target > self.level:
            if step_level >= self.target:
                done = True
        else:
            if step_level <= self.target:
                done = True
        if self.target_time <= datetime.now():
            done = True

        if done:
            self.stop_timer()
            self.level = self.target
        else:
            self.level = step_level
            (step_time, step_level) = self.calc_next_step()
            self.timer = Timer(step_time, self.fade_step, {step_level})
            self.timer.start()
        self.set_level()

    def calc_next_step(self):
        nsteps = abs(self.target - self.level) / MIN_STEP_SIZE
        timeleft = (self.target_time - datetime.now()).total_seconds()
        steptime = timeleft / nsteps
        stepsize = (self.target - self.level) / nsteps

        steptime2 = max(steptime, MIN_STEP_TIME)
        nsteps2 = nsteps * steptime / steptime2
        stepsize2 = stepsize * nsteps / nsteps2

        return (steptime2, self.level + stepsize2)

    def stop_timer(self):
        if isinstance(self.timer, Timer):
            self.timer.cancel()
            self.timer = None

    def set_level(self):
        self.log_level()
        pwmWrite(int(self.pin), int(self.level * PWM_MAX / MAX_LEVEL))

    def log_level(self):
        #print(f'{datetime.now()}: {self.name} -- target={self.target} by {self.target_time}, level={self.level}')
        pass

    def status(self):
        return json.dumps({'level': self.target})

class LEDRGB(LEDPin):
    def __init__(self, name, pin_r, pin_g, pin_b, color):
        self.name = name
        if pin_r == None:
            raise Exception(f"[{section}] missing red pin number")
        if pin_g == None:
            raise Exception(f"[{section}] missing green pin number")
        if pin_b == None:
            raise Exception(f"[{section}] missing blue pin number")
        self.pins = [int(pin_r), int(pin_g), int(pin_b)]
        if color == 'on':
            color = 'white'
        elif color == 'off':
            color = 'black'
        self.color = Color(color)
        self.last_on_color = self.color if self.color.lightness > 0 else Color('white')
        self.pintype = 'rgb'
        pinMode(self.pins[0], OUTPUT)
        pinMode(self.pins[1], OUTPUT)
        pinMode(self.pins[2], OUTPUT)
        self.set_color(self.color)

    def off(self):
        return self.set_color('black')

    def on(self):
        return self.set_color(self.last_on_color)

    def set_color(self, newcolor):
        self.log_level()
        color = Color(newcolor)
        if self.color.lightness > 0:
            self.last_on_color = self.color
        self.color = color
        digitalWrite(self.pins[0], 1 if color[0] > 0.5 else 0)
        digitalWrite(self.pins[1], 1 if color[1] > 0.5 else 0)
        digitalWrite(self.pins[2], 1 if color[2] > 0.5 else 0)
        return self.status()

    def set_level(self):
        if self.level > 0.5:
            self.on()
        else:
            self.off()

    def log_level(self):
        print(f'{datetime.now()}: {self.name} -- setting color to {self.color.html}')
        
    def status(self):
        return json.dumps({'level': self.color.lightness, 'color': self.color.html})

class LEDPCA(LEDPWM):
    def __init__(self, name, pin, level):
        self.name = name
        self.pin = 0 if pin == None else int(pin)
        if level == 'on':
            self.level = 1
        elif level == 'off':
            self.level = 0
        else:
            self.level = float(level)
        self.timer = None
        self.target = self.level
        self.target_time = 0
        self.last_on_level = self.level
        self.pintype = 'pca'
        self.fade(self.target, 0)

    def set_level(self):
        self.log_level()
        pca.channels[int(self.pin)].duty_cycle = int(self.level * PCA_MAX / MAX_LEVEL)

app = Flask(__name__)

@app.route('/<name>/set/<int:newlevel>', methods=['GET'])
def set_dimmer(newlevel):
    if name in leds and newlevel <= MAX_LEVEL:
        return leds[name].fade(newlevel, 0)
    else:
        abort(404)

@app.route('/<name>/fade/<int:newlevel>', methods=['GET'])
@app.route('/<name>/fade/<int:newlevel>/<int:duration>', methods=['GET'])
@app.route('/<name>/fade/<int:newlevel>/<float:duration>', methods=['GET'])
def fade_dimmer(name, newlevel, duration=1):
    if name in leds and newlevel <= MAX_LEVEL:
        return leds[name].fade(newlevel, duration)
    else:
        abort(404)

@app.route('/<name>/color/<color>', methods=['GET'])
def set_color(name, color='black'):
    if name in leds:
        return leds[name].set_color(color)
    else:
        abort(404)

@app.route('/<name>/on', methods=['GET'])
def turn_on(name):
    if name in leds:
        return leds[name].on()
    else:
        abort(404)

@app.route('/<name>/off', methods=['GET'])
def turn_off(name):
    if name in leds:
        return leds[name].off()
    else:
        abort(404)

def parse_config():
    if config.sections():
        for section in config.sections():
            level = config[section].get('default', 'off').lower()
            pintype = config[section].get('type', 'onoff').lower()
            pin = config[section].get('pin', None)

            # Setup LED driver based on pintype
            if pintype == 'onoff':
                leds[section] = LEDPin(section, pin, level)
            elif pintype == 'pwm':
                leds[section] = LEDPWM(section, pin, level)
            elif pintype == 'rgb':
                leds[section] = LEDRGB(section,
                        config[section]['red'],
                        config[section]['green'],
                        config[section]['blue'],
                        config[section].get('default', 'black').lower()
                        )
            elif pintype == 'pca9685':
                if HAVE_PCA:
                    leds[section] = LEDPCA(section, pin, level)
                else:
                    raise Exception(f"Failed to load pca9685 module required for [{section}]")
            else:
                raise Exception(f"[{section}] unknown pin type '{pintype}'")
    else:
        leds['led'] = LEDPWM('led', PWM_PIN, 0)

if __name__ == '__main__':
    leds = {}
    wiringPiSetupGpio()
    if HAVE_PCA:
        pca = PCA9685(busio.I2C(SCL, SDA))
        pca.frequency = 1000
    config = configparser.ConfigParser()
    config.read('config.ini')
    parse_config()
    app.run(host='0.0.0.0', port=8123)
