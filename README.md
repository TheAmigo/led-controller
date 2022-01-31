# led-controller
REST server for controlling LEDs on a Raspberry Pi.

This is something I wrote to work for my specific requirements.  It's definitely not for everyone.

## Features
- Use any GPIO pins on the Pi for turning LEDs on/off.
- Can use 3 GPIO pins to control an RGB LED (but only for the 8 basic colors)
- Use the PWM pins for dimming LEDs.
- LED dimming is done with the Pi's hardware, **no software PWM**.
- Can fade to target level over specified time period.
- Supports extra dimmable channels via add-on [PCA9685 board](https://www.adafruit.com/product/815).

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
A sample config file is included.  Each section defines the name of an LED that will be controlled.  Under that section are the parameters for that LED.

Example:
```
[accent_light]
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

## Lighting Types
### onoff
Configuration:
- `type=onoff`
- `pin=`*number*
- `default=`*<on or off>* default is off

Functions:
- `/on` turns on the light
- `/off` turns off the light

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
  
### pca9685
Configuration:
- `type=pca9685`
- `pin=`*channel* The channel number for this light, 0 - 15
- `default=`*<on, off, or level>* Where *level* is a floating point nubmer between 0.0 (off) and 1.0 (full bright).  Default is off.

Functions:
- All the same as the **pwm** section above.
