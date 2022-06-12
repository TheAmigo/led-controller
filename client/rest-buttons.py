#!/usr/bin/env python

import os
from urllib import request
from gpiozero import RotaryEncoder, Button
from threading import Event
import configparser

class InputButton:
    def __init__(self, config):
        pull_up = False
        if 'pull_up' in config:
            cpu = config['pull_up'].lower()
            if cpu == 'true' or cpu == 'yes':
                pull_up = True
        self.btn = Button(config['pin'], pull_up=pull_up)
        self.btn.when_pressed = self.click
        self.led = config.get('led', 'led')
        self.server = config.get('server', '127.0.0.1:8123')
        self.cmd = config.get('cmd', 'toggle')

    def click(self):
        request.urlopen(f'http://{self.server}/{self.led}/{self.cmd}')

class InputRotary:
    def __init__(self, config):
        self.rot = RotaryEncoder(config['pin_1'], config['pin_2'])
        self.rot.when_rotated_clockwise = self.cw
        self.rot.when_rotated_counter_clockwise = self.ccw
        self.led = config.get('led', 'led')
        self.server = config.get('server', '127.0.0.1:8123')
        self.cw_cmd = config.get('cw_cmd', 'inc')
        self.ccw_cmd = config.get('ccw_cmd', 'dec')

    def cw(self):
        request.urlopen(f'http://{self.server}/{self.led}/{self.cw_cmd}')

    def ccw(self):
        request.urlopen(f'http://{self.server}/{self.led}/{self.ccw_cmd}')

def parse_config():
    if config.sections():
        for section in config.sections():
            if section == 'rest':
                continue
            inputtype = config[section].get('type', 'button').lower()
            if inputtype == 'button':
                devs[section] = InputButton(config[section])
            elif inputtype == 'rotary':
                devs[section] = InputRotary(config[section])

if __name__ == '__main__':
    devs = {}
    config = configparser.ConfigParser()
    config.read('/etc/rest-buttons.ini')
    parse_config()
    try:
        server = config['rest']['server']
    except KeyError:
        server = '127.0.0.1:8123'

    try:
        Event().wait()
    except KeyboardInterrupt:
        os._exit(1)
