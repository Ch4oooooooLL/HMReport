proc ::CAEReport::sourceIndex {id} {
    if {[catch {
        hwi OpenStack
        hwi GetSessionHandle caeSession
        caeSession GetProjectHandle caeProject
        caeProject GetPageHandle caePage [caeProject GetActivePage]
        caePage GetWindowHandle caeWindow [caePage GetActiveWindow]
        caeWindow GetClientHandle caeClient
        set modelId [caeClient GetActiveModel]
        caeClient GetModelHandle caeModel $modelId
        set subcaseIds [caeModel GetSubcaseList]
        set subcases ""
        foreach subcaseId $subcaseIds {
            set label [caeModel GetSubcaseLabel $subcaseId]
            if {$subcases ne ""} {append subcases ","}
            append subcases "{\"id\":$subcaseId,\"name\":\"[::CAEReport::jsonEscape $label]\"}"
        }
        hwi CloseStack
    } message]} {
        catch {hwi CloseStack}
        ::CAEReport::failure $id "H3D_INDEX_FAILED" $message
        return
    }
    ::CAEReport::success $id "{\"subcases\":\[$subcases\],\"simulations\":\[\],\"result_types\":\[\]}"
}

