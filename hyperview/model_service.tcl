proc ::CAEReport::sourceOpen {id line} {
    set path [::CAEReport::jsonString $line path]
    if {$path eq "" || ![file exists $path]} {
        ::CAEReport::failure $id "SOURCE_MISSING" "H3D path does not exist"
        return
    }
    if {[catch {
        hwi OpenStack
        hwi GetSessionHandle caeSession
        caeSession GetProjectHandle caeProject
        caeProject GetPageHandle caePage [caeProject GetActivePage]
        caePage GetWindowHandle caeWindow [caePage GetActiveWindow]
        caeWindow SetClientType animation
        caeWindow GetClientHandle caeClient
        set modelId [caeClient AddModel $path]
        caeClient SetActiveModel $modelId
        caeClient GetModelHandle caeModel $modelId
        set resultCode [caeModel SetResult $path]
        if {$resultCode != 0} {
            error "HyperView SetResult failed with code $resultCode"
        }
        caeClient Draw
        hwi CloseStack
    } message]} {
        catch {hwi CloseStack}
        ::CAEReport::failure $id "HV_LOAD_FAILED" $message
        return
    }
    variable h3dPath
    set h3dPath $path
    ::CAEReport::success $id "{\"status\":\"ready\"}"
}

proc ::CAEReport::sourceStatus {id} {
    variable h3dPath
    if {$h3dPath eq ""} {
        ::CAEReport::success $id "{\"status\":\"empty\"}"
    } else {
        ::CAEReport::success $id "{\"status\":\"ready\"}"
    }
}

