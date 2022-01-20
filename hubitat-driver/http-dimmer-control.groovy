metadata {
    definition (name: "HTTP Dimmer Control", namespace: "amigo", author: "TheAmigo") {
        capability "Switch"
        capability "SwitchLevel"
    }

    preferences {
        input(name: "endpoint", type: "string", title:"REST endpoint", description: "Enter URL for the server's endpoint", required: true, displayDuringSetup: true)
        input name: "logEnable", type: "bool", title: "Enable debug logging", defaultValue: true, required: false
    }
}

def parse(String msg) {
    writeLog(msg)
}

def on() {
    setLevel(100)
}

def off() {
    setLevel(0)
}

def setLevel(BigDecimal level, BigDecimal fadetime=0) {
    // Convert seconds to milliseconds
    writeLog("${device.name}: setLevel($level, $fadetime)")
    fadetime *= 1000
    httpGet("$endpoint/fade/$level/$fadetime", {} )
    sendEvent(name: "level", value: level, isStateChange: true)
    if (level == 0) {
        sendEvent(name: "switch", value: "off", isStateChange: true)
    } else {
        sendEvent(name: "switch", value: "on", isStateChange: true)
    }
}

private writeLog(String msg) {
    if (logEnable) log.debug(msg)
}
