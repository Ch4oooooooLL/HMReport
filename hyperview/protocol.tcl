namespace eval ::CAEReport {
    variable socketChannel ""
}

proc ::CAEReport::jsonEscape {value} {
    return [string map [list "\\" "\\\\" "\"" "\\\"" "\n" "\\n" "\r" "\\r"] $value]
}

proc ::CAEReport::sendLine {json} {
    variable socketChannel
    puts $socketChannel $json
    flush $socketChannel
}

proc ::CAEReport::success {id resultJson} {
    ::CAEReport::sendLine "{\"id\":\"[::CAEReport::jsonEscape $id]\",\"success\":true,\"result\":$resultJson}"
}

proc ::CAEReport::failure {id code message} {
    ::CAEReport::sendLine "{\"id\":\"[::CAEReport::jsonEscape $id]\",\"success\":false,\"error\":{\"code\":\"[::CAEReport::jsonEscape $code]\",\"message\":\"[::CAEReport::jsonEscape $message]\",\"details\":{}}}"
}

proc ::CAEReport::jsonString {json key} {
    # Keep character classes inside a braced format string. In a double-quoted
    # Tcl string, square brackets trigger command substitution (for example,
    # [[:space:]] would try to execute a command named ":space:").
    set pattern [format {"%s"[[:space:]]*:[[:space:]]*"([^"]*)"} $key]
    if {[regexp $pattern $json -> value]} {
        return [string map [list "\\\"" "\"" "\\\\" "\\"] $value]
    }
    return ""
}

proc ::CAEReport::jsonStringArray {values} {
    set result ""
    foreach value $values {
        if {$result ne ""} {
            append result ","
        }
        append result "\"[::CAEReport::jsonEscape $value]\""
    }
    return "\[$result\]"
}
