## Sample clients

While it's nice to have a Hubitat that's able to control LED strips, there are times when you just want a local physical button (just like z-wave light switches have clickable buttons).

### MQTT client
`mqtt-buttons.py` runs as a local service on the Pi listening for button presses and rotary knob turns.  Use the config file to tell it what to do in response to the inputs.  Since it's using MQTT, it can control any device, not just the local machine.

For configuration, see the notes in the sample config file `mqtt-buttons.ini`

### REST client
`rest-buttons.py` runs as a local service on the Pi listening for button presses.  When pressed, it sends a command to the local server (`led-controller.py`) via http.

As this one is just a proof-of-concept, there's no config file. You'll have to edit the code to specify which button(s) to use and what command they should send.

## Installation
```
mv mqtt-buttons.py /usr/local/bin/
mv mqtt-buttons.service /etc/systemd/system/
mv mqtt-buttons.ini /etc/
systemctl daemon-reload
systemctl enable mqtt-buttons
systemctl start mqtt-buttons
```
