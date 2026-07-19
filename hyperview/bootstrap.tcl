set scriptDir [file dirname [file normalize [info script]]]
source [file join $scriptDir protocol.tcl]
source [file join $scriptDir session.tcl]
source [file join $scriptDir model_service.tcl]
source [file join $scriptDir result_service.tcl]
source [file join $scriptDir display_service.tcl]
source [file join $scriptDir camera_service.tcl]
source [file join $scriptDir capture_service.tcl]
source [file join $scriptDir adapters hyperview_2019.tcl]

if {![info exists ::env(CAE_REPORT_HV_CONTEXT)]} {
    error "CAE_REPORT_HV_CONTEXT is not set"
}
set contextPath $::env(CAE_REPORT_HV_CONTEXT)
set contextFile [open $contextPath r]
fconfigure $contextFile -encoding utf-8
set contextJson [read $contextFile]
close $contextFile

set ::CAEReport::sessionId [::CAEReport::jsonString $contextJson session_id]
set ::CAEReport::authToken [::CAEReport::jsonString $contextJson auth_token]
set ::CAEReport::h3dPath [::CAEReport::jsonString $contextJson h3d_path]
set host [::CAEReport::jsonString $contextJson worker_host]
regexp {"worker_port"[[:space:]]*:[[:space:]]*([0-9]+)} $contextJson -> port

set ::CAEReport::socketChannel [socket $host $port]
fconfigure $::CAEReport::socketChannel -encoding utf-8 -translation lf -buffering line -blocking 1
set capabilitiesJson {["session.ping","session.capabilities","source.open","source.status","source.index","view.apply","view.read","capture.execute","view.restore","session.shutdown"]}
::CAEReport::sendLine "{\"type\":\"handshake\",\"session_id\":\"[::CAEReport::jsonEscape $::CAEReport::sessionId]\",\"token\":\"[::CAEReport::jsonEscape $::CAEReport::authToken]\",\"hyperview_version\":\"2019\",\"protocol_version\":\"1.0\",\"capabilities\":$capabilitiesJson}"

while {!$::CAEReport::shouldStop && [gets $::CAEReport::socketChannel line] >= 0} {
    if {$line ne ""} {
        if {[catch {::CAEReport::dispatch $line} message]} {
            ::CAEReport::failure "" "HV_COMMAND_FAILED" $message
        }
    }
    update
}
catch {close $::CAEReport::socketChannel}
after 100
exit
