proc ::CAEReport::captureExecute {id line} {
    set path [::CAEReport::jsonString $line path]
    set width [::CAEReport::jsonString $line width]
    set height [::CAEReport::jsonString $line height]
    if {$path eq ""} {
        ::CAEReport::failure $id "CAPTURE_FAILED" "Output path is required"
        return
    }
    if {![string is integer -strict $width] || $width < 1} {
        set width 1920
    }
    if {![string is integer -strict $height] || $height < 1} {
        set height 1080
    }
    if {[catch {
        file mkdir [file dirname $path]
        hwi OpenStack
        hwi GetSessionHandle caeSession
        caeSession CaptureActiveWindow png $path pixels $width $height
        hwi CloseStack
    } message]} {
        catch {hwi CloseStack}
        ::CAEReport::failure $id "CAPTURE_FAILED" $message
        return
    }
    ::CAEReport::success $id "{\"status\":\"captured\",\"path\":\"[::CAEReport::jsonEscape $path]\",\"width\":$width,\"height\":$height}"
}
