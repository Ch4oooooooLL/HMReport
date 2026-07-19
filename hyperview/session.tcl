namespace eval ::CAEReport {
    variable shouldStop 0
    variable sessionId ""
    variable authToken ""
    variable h3dPath ""
}

proc ::CAEReport::dispatch {line} {
    variable shouldStop
    variable authToken
    set id [::CAEReport::jsonString $line id]
    set command [::CAEReport::jsonString $line command]
    if {$command eq "session.ping"} {
        ::CAEReport::success $id "{\"status\":\"ready\",\"version\":\"HyperView 2019\"}"
    } elseif {$command eq "session.capabilities"} {
        ::CAEReport::success $id {"protocol_version":"1.0","capabilities":["session.ping","session.capabilities","source.open","source.status","source.index","view.apply","view.read","capture.execute","view.restore","session.shutdown"]}
    } elseif {$command eq "session.shutdown"} {
        ::CAEReport::success $id "{\"status\":\"stopping\"}"
        set shouldStop 1
    } elseif {$command eq "source.status"} {
        ::CAEReport::sourceStatus $id
    } elseif {$command eq "source.open"} {
        ::CAEReport::sourceOpen $id $line
    } elseif {$command eq "source.index"} {
        ::CAEReport::sourceIndex $id
    } elseif {$command eq "view.read"} {
        ::CAEReport::viewRead $id
    } elseif {$command eq "view.apply" || $command eq "view.restore"} {
        ::CAEReport::viewApply $id $line
    } elseif {$command eq "capture.execute"} {
        ::CAEReport::captureExecute $id $line
    } else {
        ::CAEReport::failure $id "COMMAND_NOT_ALLOWED" "Command is not in the protocol whitelist"
    }
}
