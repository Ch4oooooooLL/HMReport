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
        caeModel GetResultCtrlHandle caeResult
        set subcaseIds [caeResult GetSubcaseList]
        set subcases ""
        set simulations ""
        set resultTypes ""
        array set seenResultTypes {}
        foreach subcaseId $subcaseIds {
            set label [caeResult GetSubcaseLabel $subcaseId]
            if {$subcases ne ""} {append subcases ","}
            append subcases "{\"id\":$subcaseId,\"name\":\"[::CAEReport::jsonEscape $label]\"}"

            set simulationIndex 0
            foreach simulationLabel [caeResult GetSimulationList $subcaseId] {
                if {$simulations ne ""} {append simulations ","}
                set simulationId "${subcaseId}:${simulationIndex}"
                append simulations "{\"id\":\"[::CAEReport::jsonEscape $simulationId]\",\"subcase_id\":$subcaseId,\"name\":\"[::CAEReport::jsonEscape $simulationLabel]\",\"index\":$simulationIndex}"
                incr simulationIndex
            }

            foreach dataType [caeResult GetDataTypeList $subcaseId] {
                if {[info exists seenResultTypes($dataType)]} {
                    continue
                }
                set seenResultTypes($dataType) 1
                set components ""
                foreach component [caeResult GetDataComponentList $subcaseId $dataType] {
                    if {$components ne ""} {append components ","}
                    append components "\"[::CAEReport::jsonEscape $component]\""
                }
                if {$resultTypes ne ""} {append resultTypes ","}
                append resultTypes "{\"id\":\"[::CAEReport::jsonEscape $dataType]\",\"name\":\"[::CAEReport::jsonEscape $dataType]\",\"components\":\[$components\]}"
            }
        }
        hwi CloseStack
    } message]} {
        catch {hwi CloseStack}
        if {[info exists ::errorInfo] && $::errorInfo ne ""} {
            append message " | " $::errorInfo
        }
        ::CAEReport::failure $id "H3D_INDEX_FAILED" $message
        return
    }
    ::CAEReport::success $id "{\"subcases\":\[$subcases\],\"simulations\":\[$simulations\],\"result_types\":\[$resultTypes\]}"
}

proc ::CAEReport::resultQueryMax {id line} {
    set subcaseId [::CAEReport::jsonString $line subcase_id]
    set simulationIndex [::CAEReport::jsonString $line simulation_index]
    set dataType [::CAEReport::jsonString $line data_type]
    set component [::CAEReport::jsonString $line component]
    set count [::CAEReport::jsonString $line count]
    if {$subcaseId eq "" || $dataType eq "" || $component eq ""} {
        ::CAEReport::failure $id "RESULT_QUERY_INVALID" "subcase_id, data_type and component are required"
        return
    }
    if {![string is integer -strict $simulationIndex]} {
        set simulationIndex 0
    }
    if {![string is integer -strict $count] || $count < 1} {
        set count 1
    }
    if {$count > 100} {
        set count 100
    }
    if {[catch {
        hwi OpenStack
        hwi GetSessionHandle caeSession
        caeSession GetProjectHandle caeProject
        caeProject GetPageHandle caePage [caeProject GetActivePage]
        caePage GetWindowHandle caeWindow [caePage GetActiveWindow]
        caeWindow GetClientHandle caeClient
        set modelId [caeClient GetActiveModel]
        caeClient GetModelHandle caeModel $modelId
        caeModel GetResultCtrlHandle caeResult
        caeResult SetCurrentSubcase $subcaseId
        caeResult SetCurrentSimulation $simulationIndex
        caeResult GetContourCtrlHandle caeContour
        caeContour SetDataType $dataType
        caeContour SetDataComponent $component
        caeContour SetEnableState true
        caeClient SetDisplayOptions contour true
        caeClient SetDisplayOptions legend true
        caeClient Draw

        set binding [caeContour GetBinding]
        set selectionId [caeModel AddSelectionSet $binding]
        caeModel GetSelectionSetHandle caeSelection $selectionId
        caeSelection Add "contour top $count"
        set values [lsort -index 1 -real -decreasing [caeContour GetValueList $selectionId]]
        caeModel RemoveSelectionSet $selectionId

        set items ""
        foreach valuePair $values {
            set entityId [lindex $valuePair 0]
            set value [lindex $valuePair 1]
            if {![string is integer -strict $entityId] || ![string is double -strict $value]} {
                continue
            }
            if {$items ne ""} {append items ","}
            append items "{\"entity_type\":\"[::CAEReport::jsonEscape $binding]\",\"entity_id\":$entityId,\"value\":$value}"
        }
        hwi CloseStack
    } message]} {
        catch {hwi CloseStack}
        if {[info exists ::errorInfo] && $::errorInfo ne ""} {
            append message " | " $::errorInfo
        }
        ::CAEReport::failure $id "RESULT_QUERY_FAILED" $message
        return
    }
    ::CAEReport::success $id "{\"subcase_id\":$subcaseId,\"simulation_index\":$simulationIndex,\"data_type\":\"[::CAEReport::jsonEscape $dataType]\",\"component\":\"[::CAEReport::jsonEscape $component]\",\"items\":\[$items\]}"
}

