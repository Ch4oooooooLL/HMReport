proc ::CAEReport::captureExecute {id line} {
    set path [::CAEReport::jsonString $line path]
    if {$path eq ""} {
        ::CAEReport::failure $id "CAPTURE_FAILED" "Output path is required"
        return
    }
    if {[catch {
        file mkdir [file dirname $path]
        hwi OpenStack
        hwi GetSessionHandle caeSession
        caeSession CaptureScreen png $path
        hwi CloseStack
    } message]} {
        catch {hwi CloseStack}
        ::CAEReport::failure $id "CAPTURE_FAILED" $message
        return
    }
    ::CAEReport::success $id "{\"status\":\"captured\",\"path\":\"[::CAEReport::jsonEscape $path]\"}"
}

