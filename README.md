# led-controller
REST/MQTT server for controlling LEDs on a Raspberry Pi.

This is something I wrote to work for my specific requirements.  It's definitely not for everyone.

## Features
- Can listen on REST interface, MQTT topics, or both
- Use any GPIO pins on the Pi for turning LEDs on/off.
- Can use 3 GPIO pins to control an RGB LED (but only for the 8 basic colors)
- Use the PWM pins for dimming LEDs.
- LED dimming is done with the Pi's hardware, **no software PWM**.
- Can fade to target level over specified time period.
- Supports extra dimmable channels via add-on [PCA9685 board](https://www.adafruit.com/product/815).
- Use 3 channels on a PCA9685 for full color control of an RGB light (or strip)

## Installation
Install required packages:
```
apt-get install python3-flask python3-pip
pip install wiringpi
```

Copy the files into place:
```
mv led-controller.py /usr/local/bin/
mv led-controller.service /etc/systemd/system/
```

Start the server at boot time:
```
systemctl daemon-reload
systemctl enable led-controller
systemctl start led-controller
```

To use a PCA9685, you'll also need to:
- install `pip install adafruit-circuitpython-pca9685`
- enable the Pi's I2C bus by using `raspi-config`

## Configuration
The config file goes in `/etc/led-controller.ini`

A sample config file is included.  Each section defines the name of an LED that will be controlled.  Under that section are the parameters for that LED.

Example:
```
[accent1]
type=onoff
pin=24
```

If no config file is found, it assumes the following:
```
[led]
type=pwm
pin=18
default=off
```

## REST Usage
Commands are sent via http to the server.  Each one starts with the name of the light to be controlled, then a command, optionally followed by parameters.  Replace `raspi` in the examples below with the name or IP address of your Pi (port 8123 is built-in to the server).

### Examples:
Turn on the light named 'accent1':
```
http://raspi:8123/accent1/on
```

Fade the light named 'led' from its current brightness to 50% over the next 2 seconds
```
http://raspi:8123/led/fade/50/2
```

PWM lights default to a 1 second fade time, even for `/on` and `/off` commands.  To Turn off a PWM light immediately, tell it to fade to 0 brightness in 0 seconds:
```
http://raspi:8123/led/fade/0/0
```

Turn a PWM light back on.  It will fade up to the brightness it last had before turning off in 1 second:
```
http://raspi:8123/led/on
```

## Lighting Types
### onoff
Configuration:
- `type=onoff`
- `pin=`*number*
- `default=`*\<on or off\>* default is off

Functions:
- `/on` turns on the light
- `/off` turns off the light

### rgb
Configuration:
- `type=rgb`
- `red=`*pinNumber* Which pin controls the red part of the LED
- `green=`*pinNumber* Which pin controls the green part of the LED
- `blue=`*pinNumber* Which pin controls the blue part of the LED
- `default=`*color* Initial color to use

Functions:
- `/on` turns on the light to the most recently set non-black color (white if none was ever used)
- `/off` turns off the light
- `/color/`*color* Change the light to the named color (e.g. red, green, blue, ... black is off)
  
### pwm
Configuration:
- `type=pwm`
- `pin=`*number* Defaults to 18
- `default=`*<on, off, or level>* Where *level* is a floating point nubmer between 0.0 (off) and 1.0 (full bright).  Default is off.

Functions:
- `/on` turns on the light to the most recent non-zero brightness (if none was ever set, it will go to 100%)
- `/off` turns off the light
- `/fade/`*level* fades the brightness from the current level to the new level over the course of 1 second
- `/fade/`*level*`/`*duration* fades to the new level over the course of *duration* seconds
- `/upTo/`*level*`/`*duration* If the current level is less than *level*, fades up to *level* over *duration* seconds -- If at or above *leve*, does nothing.
- `/downTo/`*level*`/`*duration* If the current level is more than *level*, fades down to *level* over *duration* seconds -- If at or below *leve*, does nothing.
- `/inc/`*step*`/`*duration* Increase the brightness by *step*% over the course of *duration* seconds.  Defaults to +10% in 0 seconds.
- `/dec/`*step*`/`*duration* Decrease the brightness by *step*% over the course of *duration* seconds.  Defaults to -10% in 0 seconds.

### pca9685
Configuration:
- `type=pca9685`
- `pin=`*channel* The channel number for this light, 0 - 15
- `default=`*<on, off, or level>* Where *level* is a floating point nubmer between 0.0 (off) and 1.0 (full bright).  Default is off.

Functions:
- All the same as the **pwm** section above.

## FAQ
Q: Should I use REST or MQTT?
 - A: If you're not intimidated by setting up an MQTT broker, doing so gives the benefit of providing feedback to the Hubitat when the lighting changes.

Q: Why would anyone use both REST and MQTT?
 - A: Each has its advantages.  If you run both, you can get all the advantages (collect the whole set!).  While MQTT provides feedback to the Hubitat, REST allows local buttons to work, even when your MQTT broker (or whole network) is down.


Q: Why not support software-based dimming?
 - A: The extra power draw, intermittent flickering, and low frequency really bother me.  Wave your hand under a software-PWM and a hardware-PWM to compare.
