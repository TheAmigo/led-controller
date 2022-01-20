#!/usr/bin/env python3
#vim: ts=4:et:ai:smartindent

from flask import Flask, json, abort
from threading import Timer
import datetime
import wiringpi

# Global config
PWM_MAX = 1024
MAX_LEVEL = 100
MIN_STEP_TIME = 0.01
MIN_STEP_SIZE = MAX_LEVEL/PWM_MAX
PWM_PIN = 18

# Global variables to be shared across threads
class State:
    def __init__(self):
        self.level = 0
        self.timer = None
        self.target = 0
        self.target_time = 0
app = Flask(__name__)

@app.route('/led/set/<int:newlevel>', methods=['GET'])
def set_dimmer(newlevel):
    if newlevel > MAX_LEVEL:
        abort(404)
    fade_led(newlevel, 0)
    return show_status()

@app.route('/led/fade/<int:newlevel>', methods=['GET'])
@app.route('/led/fade/<int:newlevel>/<int:duration>', methods=['GET'])
@app.route('/led/fade/<int:newlevel>/<float:duration>', methods=['GET'])
def fade_dimmer(newlevel, duration=1):
    if newlevel > MAX_LEVEL:
        abort(404)
    fade_led(newlevel, duration)
    return show_status()

def fade_led(newlevel, fadetime):
    stop_timer()
    g.target = newlevel
    if g.level == g.target or fadetime == 0:
        g.level = g.target
        set_output()
    else:
        print('Fading from {} to {}'.format(g.level, newlevel))
        g.target_time = datetime.datetime.now() + datetime.timedelta(seconds=fadetime)
        (step_time, step_level) = calc_next_step()
        g.timer = Timer(step_time, fade_step, {step_level})
        g.timer.start()

def fade_step(step_level):
    done = False
    if g.target > g.level:
        if step_level >= g.target:
            done = True
    else:
        if step_level <= g.target:
            done = True
    if g.target_time <= datetime.datetime.now():
        done = True

    if done:
        stop_timer()
        g.level = g.target
    else:
        g.level = step_level
        (step_time, step_level) = calc_next_step()
        g.timer = Timer(step_time, fade_step, {step_level})
        g.timer.start()
    set_output()

def calc_next_step():
    nsteps = abs(g.target - g.level) / MIN_STEP_SIZE
    timeleft = (g.target_time - datetime.datetime.now()).total_seconds()
    steptime = timeleft / nsteps
    stepsize = (g.target - g.level) / nsteps

    steptime2 = max(steptime, MIN_STEP_TIME)
    nsteps2 = nsteps * steptime / steptime2
    stepsize2 = stepsize * nsteps / nsteps2

    return (steptime2, g.level + stepsize2)

def stop_timer():
    if isinstance(g.timer, Timer):
        g.timer.cancel()
        g.timer = None

def set_output():
    print('{}: target = {} by {}, level = {}'.format(datetime.datetime.now(), g.target, g.target_time, g.level))
    wiringpi.pwmWrite(PWM_PIN, int(PWM_MAX * g.level / MAX_LEVEL))

def show_status():
    return json.dumps({"level": g.target})

if __name__ == '__main__':
    wiringpi.wiringPiSetupGpio()
    wiringpi.pinMode(PWM_PIN, wiringpi.PWM_OUTPUT)
    g = State()
    set_output()
    app.run(host='0.0.0.0', port=8123)
