/*
 * Copyright 2022 Josh Harding
 * Licensed under the terms of the MIT licese, see LICENSE file
 */

import groovy.json.JsonSlurper

metadata {
    definition (name: "HTTP LED Control (PWM)", namespace: "amigo", author: "Josh Harding", importUrl: "https://raw.githubusercontent.com/TheAmigo/led-controller/main/hubitat-driver/http-led-control-pwm.groovy") {
        capability "Switch"
        capability "SwitchLevel"
	}

    preferences {
        input(name: "endpoint", type: "string", title:"REST endpoint", description: "Enter URL for the server's endpoint", required: true, displayDuringSetup: true)
        input name: "logEnable", type: "bool", title: "Enable debug logging", defaultValue: true, required: false
    }
}

def sendCmd(String cmd) {
    httpGet("$endpoint/" + cmd, { res ->
        if (res.isSuccess()) {
            def jsonSlurper = new JsonSlurper()
            jsonSlurper.parseText(res.getData().toString()).each { entry ->
                sendEvent(name: entry.key, value: entry.value, isStateChange: true)
            }
        } else {
            writeLog("Error code " + res.getStatus())
        }
    })
}

def on() {
    writeLog("${device.name}: on()")
    sendCmd("on")
}

def off() {
    writeLog("${device.name}: off()")
    sendCmd("off")
}

def setLevel(BigDecimal level, BigDecimal fadetime=0) {
    writeLog("${device.name}: setLevel($level, $fadetime)")
    sendCmd("fade/$level/0$fadetime")
}

private writeLog(String msg) {
    if (logEnable) log.debug(msg)
}
