proc ::CAEReport::viewRead {id} {
    set matrixJson "null"
    set presetJson "null"
    if {[catch {
        hwi OpenStack
        hwi GetSessionHandle caeSession
        caeSession GetProjectHandle caeProject
        caeProject GetPageHandle caePage [caeProject GetActivePage]
        caePage GetWindowHandle caeWindow [caePage GetActiveWindow]
        caeWindow GetViewControlHandle caeView
        set rawMatrix [caeView GetViewMatrix]
        set flattened [string map [list "{" "" "}" ""] $rawMatrix]
        set matrixValues {}
        foreach value [split $flattened] {
            if {$value eq ""} {
                continue
            }
            if {![string is double -strict $value]} {
                error "GetViewMatrix returned a non-numeric value: $value"
            }
            lappend matrixValues [format %.17g $value]
        }
        if {[llength $matrixValues] != 16} {
            error "GetViewMatrix returned [llength $matrixValues] values instead of 16"
        }
        set matrixJson "\[[join $matrixValues ,]\]"
        set orientation [caeView GetOrientation]
        set presetJson "\"[::CAEReport::jsonEscape $orientation]\""
        caeView ReleaseHandle
        hwi CloseStack
    } message]} {
        catch {hwi CloseStack}
        ::CAEReport::failure $id "VIEW_READ_FAILED" $message
        return
    }
    ::CAEReport::success $id "{\"schema_version\":1,\"camera\":{\"preset\":$presetJson,\"matrix\":$matrixJson}}"
}
