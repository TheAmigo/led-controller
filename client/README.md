## Sample client

`led-buttons.py` runs as a local service on the Pi listening for button presses.  When pressed, it sends a command to the local server (`led-controller.py`).

I wrote this because while it's nice to have a Hubitat that's able to control LED strips, there are times when you just want a local physical button (just like z-wave light switches have clickable buttons).

There's no config file, you'll have to edit the code to specify which button(s) to use and what command they should send.

## Installation
```
mv led-buttons.py /usr/local/bin
mv led-buttons.service /etc/systemd/system
systemctl daemon-reload
systemctl enable led-buttons
systemctl start led-buttons
```
