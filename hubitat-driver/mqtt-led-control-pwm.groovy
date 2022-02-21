/*
 * Copyright 2022 Josh Harding
 * Licensed under the terms of the MIT licese, see LICENSE file
 */

import groovy.json.JsonSlurper

metadata {
    definition (name: "MQTT LED Control (PWM)", namespace: "amigo", author: "Josh Harding", importUrl: "https://raw.githubusercontent.com/TheAmigo/led-controller/main/hubitat-driver/mqtt-led-control-pwm.groovy") {
        capability "Switch"
        capability "SwitchLevel"
        command "downTo", [
            [name: "level", type: "NUMBER", description: "Level to set (0 to 100)"],
            [name: "duration", type: "NUMBER", description: "Transition duration in seconds"]
        ]
        command "upTo", [
            [name: "level", type: "NUMBER", description: "Level to set (0 to 100)"],
            [name: "duration", type: "NUMBER", description: "Transition duration in seconds"]
        ]
    }

    preferences {
        input(name: "brokerIP", type: "string", title: "MQTT Broker", description: "Hostname or IP address of broker", defaultValue: "mqtt-broker", required: true, displayDuringSetup: true)
        input(name: "brokerPort", type: "string", title: "MQTT Broker's port", description: "TCP port number of broker", defaultValue: "1883", required: true, displayDuringSetup: true)
        input(name: "topic", type: "string", title:"MQTT topic for light", description: "This topic may contain slashes and will be sandwiched as cmd/{topic}/req", required: true, displayDuringSetup: true)
        input(name: "logEnable", type: "bool", title: "Enable debug logging", defaultValue: true, required: false)
    }
}

def sendCmd(String payload) {
    topic = "cmd/${settings?.topic}/req"
    if (!interfaces.mqtt.isConnected()) {
        writeLog("Warning: MQTT not connected, retrying...")
        initialize()
    }
    try {
        writeLog("Info: publishing to ${topic}: ${payload}")
        interfaces.mqtt.publish(topic, payload, qos=2, false)
    } catch (Exception e) {
        writeLog("ERROR: while trying to publish: ${e}")
    }
}

def on() {
    writeLog("on()")
    sendCmd('{"cmd": "on"}')
}

def off() {
    writeLog("off()")
    sendCmd('{"cmd": "off"}')
}

def downTo(BigDecimal level, BigDecimal fadetime=0) {
    writeLog("downTo($level, $fadetime)")
    sendCmd('{"cmd": "downto", "level": ' + level + ', "duration": ' + fadetime + '}')
}

def upTo(BigDecimal level, BigDecimal fadetime=0) {
    writeLog("upTo($level, $fadetime)")
    sendCmd('{"cmd": "upto", "level": ' + level + ', "duration": ' + fadetime + '}')
}

def setLevel(BigDecimal level, BigDecimal fadetime=0) {
    writeLog("setLevel($level, $fadetime)")
    sendCmd('{"cmd": "fade", "level": ' + level + ', "duration": ' + fadetime + '}')
}

void initialize() {
    try {
        writeLog("Attempting connection to tcp://${settings?.brokerIp}:${settings?.brokerPort}")
        interfaces.mqtt.connect(
            "tcp://${settings?.brokerIP}:${settings?.brokerPort}",
            location.hubs[0].name.replaceAll("[^a-zA-Z0-9]","-") + ":" + location.hubs[0].hardwareID + ":" + device.name,
            null, null
        )
        
        // Listen for results
        interfaces.mqtt.subscribe("cmd/${settings?.topic}/resp", 2)
    } catch (Exception e) {
        writeLog("Exception when connecting MQTT: ${e}")
    }
}

def parse(String data) {
    payload = interfaces.mqtt.parseMessage(data).payload
    writeLog("Received: ${payload}")
    js = new JsonSlurper()
    parsed = js.parseText(payload)
    isSC = true // default to true if it's not specified
    if (parsed['isStateChange'] == false) {
        isSC = false
    }
    parsed.remove('isStateChange')
    parsed.each { entry -> 
        sendEvent(name: entry.key, value: entry.value, isStateChange: isSC)
    }
}

def mqttClientStatus(String msg) {
    writeLog("MQTT ClientStatus: ${msg}")
}

private writeLog(String msg) {
    if (logEnable) log.debug(device.name + ": " + msg)
}

// vim: et:ts=4:ai:smartindent
