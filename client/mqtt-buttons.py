#!/usr/bin/env python

import os
import sys
import socket
import paho.mqtt.client as mqtt
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
        self.topic = config['topic']
        self.cmd = config['cmd']

    def click(self):
        client.publish(f'cmd/{self.topic}/req', '{"cmd": "'+self.cmd+'"}', qos=2)

class InputRotary:
    def __init__(self, config):
        self.rot = RotaryEncoder(config['pin_1'], config['pin_2'])
        self.rot.when_rotated_clockwise = self.cw
        self.rot.when_rotated_counter_clockwise = self.ccw
        self.cw_cmd = config['cw_cmd']
        self.ccw_cmd = config['ccw_cmd']
        self.topic = config['topic']

    def cw(self):
        client.publish(f'cmd/{self.topic}/req', '{"cmd": "'+self.cw_cmd+'"}', qos=2)

    def ccw(self):
        client.publish(f'cmd/{self.topic}/req', '{"cmd": "'+self.ccw_cmd+'"}', qos=2)

def parse_config():
    if config.sections():
        for section in config.sections():
            if section == 'mqtt':
                continue
            inputtype = config[section].get('type', 'button').lower()
            if inputtype == 'button':
                devs[section] = InputButton(config[section])
            elif inputtype == 'rotary':
                devs[section] = InputRotary(config[section])

def reconnect(client, userdata, rc):
    client.reconnect()

def get_client_id(config):
    client_id = ''
    try:
        # 1: if it's in the config file, use that
        client_id = config['mqtt']['client_id']
    except KeyError:
        # 2: try the hostname + script name
        hostname = socket.gethostname()
        if hostname in ['localhost', 'raspberrypi']:
            # 3: hostname is too generic, use the IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0)
            try:
                s.connect(('192.168.0.1', 1)) # could be any random IP
                hostname = s.getsockname()[0]
            except Exception:
                # 4: can't get IP, use a placeholder
                hostname = '127.0.0.1'
        # got hostname, add the scriptname
        try:
            scriptname = os.path.basename(__file__)
        except Exception:
            scriptname = sys.argv[0]
            if scriptname == '':
                scriptname = 'mqtt-buttons.py'
        client_id = hostname + '-' + scriptname
    return client_id

if __name__ == '__main__':
    devs = {}
    config = configparser.ConfigParser()
    config.read('/etc/mqtt-buttons.ini')
    parse_config()
    client = mqtt.Client(client_id=get_client_id(config), clean_session=False)
    client.on_disconnect = reconnect
    try:
        broker = config['mqtt']['broker']
    except KeyError:
        broker = 'mqtt-broker'
    client.connect(broker)
    client.loop_start()

    try:
        Event().wait()
    except KeyboardInterrupt:
        os._exit(1)
