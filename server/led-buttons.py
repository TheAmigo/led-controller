#!/usr/bin/env python3

from threading import Event
from gpiozero import Button
from urllib import request

btn_cabinets = Button(27)
btn_counter  = Button(22)
btn_cabinets.when_pressed = lambda: request.urlopen("http://127.0.0.1:8123/cabinets/toggle")
btn_counter.when_pressed  = lambda: request.urlopen("http://127.0.0.1:8123/counter/toggle")

Event().wait()
