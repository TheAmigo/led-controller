#!/usr/bin/env python3
#vim: ts=4:et:ai:smartindent

# Copyright 2022 Josh Harding
# licensed under the terms of the MIT license, see LICENSE file

# TODO:
# - Allow remote config (e.g. from Hubitat)
# - Save config changes to file
# - Consider other functions like blink(), pulse(), strobe()

from threading import Timer, Event, Thread
from colorzero import Color
from wiringpi import digitalWrite, pwmWrite, pinMode, OUTPUT, PWM_OUTPUT, wiringPiSetupGpio
from datetime import datetime, timedelta
import configparser
import os
import json

HAVE_MQTT = True
try:
    import paho.mqtt.client as mqtt
except ImportError:
    HAVE_MQTT = False

HAVE_PCA = True
try:
    from adafruit_pca9685 import PCA9685
    from board import SCL, SDA
    import busio
except ImportError:
    HAVE_PCA = False

HAVE_REST = True
try:
    from flask import Flask, abort
except ImportError:
    HAVE_REST = False

# Global config
MAX_LEVEL = 100      # Accept percentages from client
PWM_PIN = 18         # Used if no config file is present
PWM_MAX = 0x0400     # Pi's PWM scale
PCA_MAX = 0xFFFF     # 12-bit resolution at the top of a 16-bit register
MIN_STEP_TIME = 0.01 # 100fps is fast enough for me
MIN_STEP_SIZE = MAX_LEVEL/PWM_MAX

# Base class for controlling an LED with a GPIO pin
class LEDPin:
    pintype = 'onoff'

    def __init__(self, name, pin, level):
        self.name = name
        self.pin = int(pin)
        self._def_level(level)
        self.last_on_level = self.level if self.level else 100
        self.last_on_timer = None
        self.toggling = ''
        self._setup_cmds()
        self.err_msg = None
        self.fade({'level': self.level, 'duration': 0})
        self._init_pin()
        if 'mqtt' in config.sections():
            self._mqtt_listen()

    def _init_pin(self):
        pinMode(self.pin, OUTPUT)

    def _setup_cmds(self):
        self.commands = {
            'on'    : self.on,
            'off'   : self.off,
            'toggle': self.toggle,
            'fade'  : self.fade,
        }

        self.defaults = {
            'fade' : [['level', int, 0]],
            'on'   : [['duration', float, 1]],
            'off'  : [['level', int, 0], ['duration', float, 1]],
        }

    def _def_level(self, level):
        self.level = 1 if level == 'on' else 0

    def _mqtt_listen(self):
        if HAVE_MQTT:
            self.topic = f"cmd/{config['mqtt'].get('topic','led')}/{self.name}"
            self._mqtt_setup()

    def _mqtt_setup(self):
        self.client = mqtt.Client()
        self.client.on_connect = self._mqtt_connect
        self.client.on_message = self._mqtt_message
        self.client.connect(config['mqtt'].get('broker', 'mqtt-broker'))
        self.client.loop_start()

    def _mqtt_connect(self, client, userdata, flags, rc):
        print(f"MQTT subscribing to topic {self.topic}/req")
        self.client.subscribe(f"{self.topic}/req")

    def _mqtt_message(self, client, userdata, msg):
        self.err_msg = None
        try:
            data = json.loads(msg.payload)
            if data['cmd'] in self.commands:
                self._set_default_args_mqtt(data)
                self.prev_status = self._get_status()
                self.commands[data['cmd']](data)
                self.send_status()
        except json.JSONDecodeError:
            self.err_msg = 'non-json data'
        except KeyError:
            self.err_msg = 'missing or invalid cmd'

    def _set_default_args_mqtt(self, data):
        cmd=data['cmd']
        if cmd in self.defaults:
            for setting in self.defaults[cmd]:
                name, datatype, value = setting
                if name not in data:
                    data[name] = datatype(value)

    def _set_default_args_rest(self, data, args=[]):
        cmd=data['cmd']
        if cmd in self.defaults:
            for i in range(len(self.defaults[cmd])):
                name, datatype, value = self.defaults[cmd][i]
                data[name] = datatype(value if args[i] == None else args[i])

    def on(self):
        self.level = 1
        self.toggling = ''
        self._set_level()

    def off(self):
        self.level = 0
        self.toggling = ''
        self._set_level()

    def toggle(self, data=None):
        if self.toggling == 'on' or self.level:
            self.toggling = 'off'
            self.off(data)
        else:
            self.toggling = 'on'
            self.on(data)

    def fade(self, data):
        self.level = round(data['level'])
        self._set_level()

    def _set_level(self):
        self._log_level()
        digitalWrite(self.pin, self.level)

    def _log_level(self):
        print(f'{datetime.now()}: {self.name} level={self.level}')

    def _get_status(self):
        return {
            'level' : self.level,
            'switch': 'on' if self.level else 'off',
        }
        
    def send_status(self):
        # See if status has changed
        curr_status_json = self._get_status()
        curr_status_str = json.dumps(curr_status_json, sort_keys=True)
        prev_status_str = json.dumps(self.prev_status, sort_keys=True)
        isStateChange = True
        if prev_status_str == curr_status_str:
            isStateChange = False
        curr_status_json.update({'isStateChange': isStateChange})
        if self.err_msg:
            curr_status_json.update({'error': self.err_msg})

        status_msg = json.dumps(curr_status_json)
        if HAVE_MQTT:
            self.client.publish(f"{self.topic}/resp", status_msg)
        return status_msg

class LEDRGB(LEDPin):
    pintype = 'rgb'

    def __init__(self, name, pin_r, pin_g, pin_b, color):
        self.name = name
        if pin_r == None:
            raise Exception(f"[{name}] missing red pin number")
        if pin_g == None:
            raise Exception(f"[{name}] missing green pin number")
        if pin_b == None:
            raise Exception(f"[{name}] missing blue pin number")
        self.pins = [int(pin_r), int(pin_g), int(pin_b)]
        if color == 'on':
            color = 'white'
        elif color == 'off':
            color = 'black'
        self.color = Color(color)
        self.last_on_color = self.color if self.color.lightness > 0 else Color('white')
        self._init_pins()
        self._set_color(self.color)
        self._setup_cmds()
        super()._mqtt_listen()

    def _setup_cmds(self):
        super()._setup_cmds()
        self.commands.update({
            'color': self._set_color
        })
        self.defaults = {
            'color': [['color', str, 'black']]
        }

    def _init_pins(self):
        pinMode(self.pins[0], OUTPUT)
        pinMode(self.pins[1], OUTPUT)
        pinMode(self.pins[2], OUTPUT)

    def off(self, data=None):
        self._set_color({"color": 'black'})

    def on(self, data={}):
        if 'color' in data:
            self._set_color(data)
        else:
            self._set_color({"color": self.last_on_color})

    def _set_color(self, data):
        try:
            color = Color(data['color'])
        except Exception:
            color = Color('black')
            self.err_msg = 'Invalid color, using black instead'
        self.color = Color(round(color[0]), round(color[1]), round(color[2]))
        self.level = 1 if self.color.lightness else 0
        self._set_last_on_timer()
        self._log_level()
        digitalWrite(self.pins[0], int(self.color[0]))
        digitalWrite(self.pins[1], int(self.color[1]))
        digitalWrite(self.pins[2], int(self.color[2]))

    def _set_level(self):
        if round(self.level):
            self.on()
        else:
            self.off()

    def _set_last_on_timer(self):
        if self.last_on_timer:
            self.last_on_timer.cancel()
            self.last_on_timer = None
        self.last_on_timer = Timer(2, self._set_last_on)
        self.last_on_timer.start()

    def _set_last_on(self):
        if self.color.lightness:
            self.last_on_color = self.color
        self.last_on_timer = None

    def _log_level(self):
        print(f'{datetime.now()}: {self.name} -- setting color to {self.color.html}')
        
    def _get_status(self):
        status = super()._get_status()
        status.update({
            'color': self.color.html,
            'level': self.color.lightness,
            'switch': 'on' if self.color.lightness else 'off'
        })
        return status

class LEDPWM(LEDPin):
    pintype = 'pwm'
    def __init__(self, name, pin, level=0):
        self.timer = None
        super().__init__(name, pin, level)
        self.target = self.level
        self.target_time = 0
        #self.last_on_level = self.level
        #self._setup_cmds()
        #self._init_pin()

    def _init_pin(self):
        pinMode(self.pin, PWM_OUTPUT)

    def _def_level(self, level):
        if level == 'on':
            self.level = 1
        elif level == 'off':
            self.level = 0
        else:
            self.level = float(level)

    def _setup_cmds(self):
        super()._setup_cmds()
        # Add commands
        self.commands.update({
            'downto': self.downto,
            'upto'  : self.upto,
            'inc'   : self.inc,
            'dec'   : self.dec,
            'set'   : self.fade
        })

        # Set defaults
        self.defaults.update({
            'downto': [['level', int,   0], ['duration', float, 1]],
            'upto':   [['level', int, 100], ['duration', float, 1]],
            'fade':   [['level', int,   0], ['duration', float, 1]],
            'inc':    [['level', int,  10], ['duration', float, 0]],
            'dec':    [['level', int,  10], ['duration', float, 0]],
            'set':    [['level', int,   0], ['duration', float, 0]],
            'toggle': [['duration', float, 1]]
        })

    def on(self, data={}):
        if 'level' not in data:
            data['level'] = self.last_on_level
        self.fade(data)

    def off(self, data={}):
        data['level'] = 0
        self.fade(data)

    def inc(self, data={}):
        data['level'] = max(min(self.level + data['level'], 100), 0)
        self.fade(data)

    def dec(self, data={}):
        data['level'] = max(min(self.level - data['level'], 100), 0)
        self.fade(data)

    def fade(self, data):
        self._stop_timer()
        self.target = max(min(data['level'], 100), 0)
        self.prev_level = self.level
        now = datetime.now()
        if self.level == self.target or data['duration'] == 0:
            print(f'{now}: {self.name} -- setting level from {self.level} to {self.target}')
            self.level = self.target
            self._set_level()
            self.toggling = ''
        else:
            print(f'{now}: {self.name} -- fading from {self.level} to {data["level"]} in {data["duration"]} seconds')
            self.target_time = now + timedelta(seconds=data['duration'])
            (step_time, step_level) = self._calc_next_step()
            self.timer = Timer(step_time, self._fade_step, {step_level})
            self.timer.start()

    def _fade_step(self, step_level):
        done = False
        print(f"{self.name}: fading to {step_level})")
        if self.target > self.level:
            if step_level >= self.target:
                done = True
        else:
            if step_level <= self.target:
                done = True
        if self.target_time <= datetime.now():
            done = True

        if done:
            self._stop_timer()
            self._toggle_complete()
        else:
            self.level = step_level
            (step_time, step_level) = self._calc_next_step()
            self.timer = Timer(step_time, self._fade_step, {step_level})
            self.timer.start()
        self._set_level()

    def _toggle_complete(self):
        self.toggling = ''
        self.level = self.target
        if hasattr(self, '_notify_parent'):
            self._notify_parent()

    def _calc_next_step(self):
        nsteps = abs(self.target - self.level) / MIN_STEP_SIZE
        timeleft = (self.target_time - datetime.now()).total_seconds()
        steptime = timeleft / nsteps
        stepsize = (self.target - self.level) / nsteps

        steptime2 = max(steptime, MIN_STEP_TIME)
        nsteps2 = nsteps * steptime / steptime2
        stepsize2 = stepsize * nsteps / nsteps2

        return (steptime2, self.level + stepsize2)

    def _stop_timer(self):
        if isinstance(self.timer, Timer):
            self.timer.cancel()
            self.timer = None

    def _set_level(self):
        self._log_level()
        self._set_last_on_timer()
        pwmWrite(int(self.pin), int(self.level * PWM_MAX / MAX_LEVEL))

    def _set_last_on_timer(self):
        if self.last_on_timer:
            self.last_on_timer.cancel()
            self.last_on_timer = None
        self.last_on_timer = Timer(2, self._set_last_on)
        self.last_on_timer.start()

    def _set_last_on(self):
        if self.level:
            self.last_on_level = self.level
        self.last_on_timer = None

    def _log_level(self):
        #print(f'{datetime.now()}: {self.name} -- target={self.target} by {self.target_time}, level={self.level}')
        pass

    def downto(self, data):
        if self.level > data['level']:
            self.fade(data)

    def upto(self, data):
        if self.level < data['level']:
            self.fade(data)

    def _get_status(self):
        return {
            'level' : self.target,
            'switch': 'on' if self.target else 'off',
        }
        
class LEDPCA(LEDPWM):
    pintype = 'pca'

    def __init__(self, name, pin=0, level=0):
        if not HAVE_PCA:
            raise Exception(f"Failed to load pca9685 module required for [{name}]")
        super().__init__(name, pin, level)

    def _init_pin(self):
        pass

    def _set_level(self):
        super()._log_level()
        pca.channels[int(self.pin)].duty_cycle = int(self.level * PCA_MAX / MAX_LEVEL)

class LEDPCARGB(LEDPCA):
    pintype = 'pcargb'

    def __init__(self, name, pin_r, pin_g, pin_b, color):
        self.name = name
        if pin_r == None:
            raise Exception(f"[{name}] missing red pin number")
        if pin_g == None:
            raise Exception(f"[{name}] missing green pin number")
        if pin_b == None:
            raise Exception(f"[{name}] missing blue pin number")
        if color == 'on':
            color = 'white'
        elif color == 'off':
            color = 'black'
        self.color = Color(color)
        self.last_on_color = self.color if self.color.lightness > 0 else Color('white')

        # Create 3 PCA LED's
        self.led_r = LEDPCA(name + "_r", pin_r, self.color[0])
        self.led_g = LEDPCA(name + "_g", pin_g, self.color[1])
        self.led_b = LEDPCA(name + "_b", pin_b, self.color[2])
        self.led_r._notify_parent = self._update_color
        self.led_g._notify_parent = self._update_color
        self.led_b._notify_parent = self._update_color

        self._set_color(self.color)
        self._setup_cmds()
        super()._mqtt_listen()

    def _init_pins(self):
        pass

    def _setup_cmds(self):
        super()._setup_cmds()
        self.commands.update({
            'color' : self.set_color
        })

        # Extra args for colors
        self.defaults.update({
            'inc': [['level', int, 10], ['duration', float, 0],
                ['red', int, 0], ['green', int, 0], ['blue', int, 0]],
            'dec': [['level', int, 10], ['duration', float, 0],
                ['red', int, 0], ['green', int, 0], ['blue', int, 0]],
            'color': [['color', str, 'black'], ['duration', float, 1]]
        })

    def _set_color(self, data):
        try:
            self.color = Color(data['color'])
        except Exception:
            self.color = Color('black')
            self.err_msg = 'Invalid color, using black instead'
        self.level = self.color.lightness
        self._set_last_on_timer()
        self.led_r.level = self.color[0]
        self.led_g.level = self.color[1]
        self.led_b.level = self.color[2]
        self.led_r._set_level()
        self.led_g._set_level()
        self.led_b._set_level()
        self._update_color()

    def inc(self, data={}):
        if data['level'] and not data['red'] and not data['green'] and not data['blue']:
            data['red'] = data['green'] = data['blue'] = data['level']
        data['level'] = 0
        data['red']   = max(min(int(self.color[0]*100) + data['red'],   100), 0)
        data['green'] = max(min(int(self.color[1]*100) + data['green'], 100), 0)
        data['blue']  = max(min(int(self.color[2]*100) + data['blue'],  100), 0)
        self.fade(data)

    def dec(self, data={}):
        if data['level'] and not data['red'] and not data['green'] and not data['blue']:
            data['red'] = data['green'] = data['blue'] = data['level']
        data['level'] = 0
        data['red']   = max(min(int(self.color[0]*100) - data['red'],   100), 0)
        data['green'] = max(min(int(self.color[1]*100) - data['green'], 100), 0)
        data['blue']  = max(min(int(self.color[2]*100) - data['blue'],  100), 0)
        self.fade(data)

    def fade(self, data={}):
        self._update_color()
        defaults = {'red': 0, 'green': 0, 'blue': 0, 'color': 'black', 'level': 0}
        defaults.update(data)
        data = defaults
        if data['color'] and not data['level'] and not data['red'] and not data['green'] and not data['blue']:
            r,g,b = Color(data['color'])
            data['red']   = r*100
            data['green'] = g*100
            data['blue']  = b*100
        elif data['level'] and not data['red'] and not data['green'] and not data['blue']:
            data['red'] = data['green'] = data['blue'] = data['level']
        self.led_r.fade({'level': data['red'],   'duration': data['duration']})
        self.led_g.fade({'level': data['green'], 'duration': data['duration']})
        self.led_b.fade({'level': data['blue'],  'duration': data['duration']})
        self.color = Color(
            self.led_r.target/100,
            self.led_g.target/100,
            self.led_b.target/100
        )

    def toggle(self, data={}):
        toggling = self.led_r.toggling + self.led_g.toggling + self.led_b.toggling
        self._update_color()
        if self.color.lightness or 'on' in toggling:
            self.led_r.toggling = 'off'
            self.led_g.toggling = 'off'
            self.led_b.toggling = 'off'
            self.led_r.off(data)
            self.led_g.off(data)
            self.led_b.off(data)
        else:
            r,g,b = self.last_on_color
            self.led_r.toggling = self.led_g.toggling = self.led_b.toggling = 'on'
            data.update({'level': r*100})
            self.led_r.on(data)
            data.update({'level': g*100})
            self.led_g.on(data)
            data.update({'level': b*100})
            self.led_b.on(data)

    def set_color(self, data=None):
        try:
            self.color = Color(data['color'])
        except Exception:
            self.color = Color('black')
            self.err_msg = 'Invalid color, using black instead'
        self.fade({
            'red'  : self.color[0]*100,
            'green': self.color[1]*100,
            'blue' : self.color[2]*100,
            'duration': data['duration']
        })

    def _update_color(self):
        self.color = Color(
            self.led_r.level/100,
            self.led_g.level/100,
            self.led_b.level/100
        )

    def _set_last_on(self):
        if self.color.lightness:
            self.last_on_color = self.color
        self.last_on_timer = None

    def _get_status(self):
        return {
            'color' : self.color.html,
            'level' : self.color.lightness,
            'switch': 'on' if self.color.lightness else 'off'
        }

if HAVE_REST:
    app = Flask(__name__)

def parse_config():
    if config.sections():
        for section in config.sections():
            if section == 'mqtt' or section == 'rest':
                continue
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
                leds[section] = LEDPCA(section, pin, level)
            elif pintype == 'pcargb':
                leds[section] = LEDPCARGB(section,
                    config[section]['red'],
                    config[section]['green'],
                    config[section]['blue'],
                    config[section].get('default', 'black').lower()
                )
            else:
                raise Exception(f"[{section}] unknown pin type '{pintype}'")
        if 'mqtt' not in config.sections():
            config['mqtt'] = {'topic': 'led', 'broker': 'mqtt-broker'}
        if 'rest' not in config.sections():
            config['rest'] = {'port': 8123}
    else:
        # Default to using a single PWM LED on pin 18
        leds['led'] = LEDPWM('led', PWM_PIN, 0)

def rest_listen():
    base_url = config['rest'].get('base', '')
    if base_url:
        base_url = '/' + base_url

    @app.route(base_url + '/<name>/<func>', methods=['GET'])
    @app.route(base_url + '/<name>/<func>/<argone>', methods=['GET'])
    @app.route(base_url + '/<name>/<func>/<argone>/<argtwo>', methods=['GET'])
    def dispatch(name, func, argone=None, argtwo=None):
        if name in leds:
            led = leds[name]
            if func in led.commands:
                data = {'cmd': func}
                led._set_default_args_rest(data, [argone, argtwo])
                led.prev_status = led._get_status()
                led.commands[func](data)
                return led.send_status()
            else:
                abort(404)
        else:
            abort(404)
    print(f"REST interface listening on port {config['rest']['port']} with url={base_url}/")
    app.run(host='0.0.0.0', port=config['rest']['port'])

if __name__ == '__main__':
    leds = {}
    wiringPiSetupGpio()
    if HAVE_PCA:
        try:
            pca = PCA9685(busio.I2C(SCL, SDA))
            pca.frequency = 1000
        except ValueError:
            HAVE_PCA = False
    config = configparser.ConfigParser()
    config.read('/etc/led-controller.ini')
    parse_config()

    if HAVE_REST:
        rest_thread = Thread(target=rest_listen)
        rest_thread.start()

    try:
        Event().wait()
    except KeyboardInterrupt:
        os._exit(1)
