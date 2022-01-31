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

Where `type` is one of:
- `onoff`: can only be turned on or off -- works on any GPIO pin
- `pwm`: can be dimmed -- only works on hardware PWM pins
- `rgb`: requires 3 GPIO pins and can be set to one of 8 colors: red, green, blue, cyan, yellow, magenta, white, black (off)
- `pca9685`: like pwm, but for LEDs controlled by the channels of a PCA9685

If no config file is found, it assumes the following:
```
[led]
type=pwm
pin=18
```
