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

# Resolve the component that owns an entity. HyperView 2019 does not expose
# GetComponentList/GetCompCtrlHandle on poIModel; component enumeration and
# membership queries must go through selection sets.
#
# Returns {component_id component_name component_pool}.
proc ::CAEReport::resolveEntityComponent {modelHandle entityType entityPool entityId} {
    set compId ""
    set compName ""
    set compPool ""
    set componentSetId ""
    set entitySetId ""
    if {[catch {
        set componentSetId [$modelHandle AddSelectionSet component]
        $modelHandle GetSelectionSetHandle componentSet $componentSetId
        componentSet Add all

        set entitySetId [$modelHandle AddSelectionSet $entityType]
        $modelHandle GetSelectionSetHandle entitySet $entitySetId

        set componentPools [componentSet GetPoolList]
        if {[llength $componentPools] == 0} {
            set componentPools [list ""]
        }
        foreach pool $componentPools {
            if {$pool eq ""} {
                set componentIds [componentSet GetList]
            } else {
                set componentIds [componentSet GetList $pool]
            }
            foreach candidateId $componentIds {
                if {![string is integer -strict $candidateId]} {continue}
                entitySet Clear
                entitySet Add "component $candidateId"
                if {$entityPool eq ""} {
                    set ownedIds [entitySet GetList]
                } else {
                    set ownedIds [entitySet GetList $entityPool]
                }
                if {[lsearch -integer -exact $ownedIds $entityId] < 0} {
                    continue
                }
                set compId $candidateId
                set compPool $pool
                if {![catch {$modelHandle GetComponentHandle componentHandle $candidateId}]} {
                    catch {set compName [componentHandle GetLabel]}
                    catch {componentHandle ReleaseHandle}
                }
                break
            }
            if {$compId ne ""} {break}
        }
    }]} {
        # Component metadata is useful but must not make the result query fail.
        set compId ""
        set compName ""
        set compPool ""
    }
    catch {componentSet ReleaseHandle}
    catch {entitySet ReleaseHandle}
    if {$componentSetId ne ""} {
        catch {$modelHandle RemoveSelectionSet $componentSetId}
    }
    if {$entitySetId ne ""} {
        catch {$modelHandle RemoveSelectionSet $entitySetId}
    }
    return [list $compId $compName $compPool]
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

        set items ""
        foreach valuePair $values {
            set entityId [lindex $valuePair 0]
            set value [lindex $valuePair 1]
            if {![string is integer -strict $entityId] || ![string is double -strict $value]} {
                continue
            }
            set entityPool ""
            foreach pool [caeSelection GetPoolList] {
                if {[lsearch -integer -exact [caeSelection GetList $pool] $entityId] >= 0} {
                    set entityPool $pool
                    break
                }
            }
            set compIdStr ""
            set compNameStr ""
            set compPoolStr ""
            set resolved [
                ::CAEReport::resolveEntityComponent caeModel $binding $entityPool $entityId
            ]
            set compIdStr [lindex $resolved 0]
            set compNameStr [lindex $resolved 1]
            set compPoolStr [lindex $resolved 2]
            if {$compIdStr eq "" || ![string is integer -strict $compIdStr]} {
                set compIdJson 0
            } else {
                set compIdJson $compIdStr
            }
            if {$items ne ""} {append items ","}
            append items "{\"entity_type\":\"[::CAEReport::jsonEscape $binding]\",\"entity_pool\":\"[::CAEReport::jsonEscape $entityPool]\",\"entity_id\":$entityId,\"value\":$value,\"component_id\":$compIdJson,\"component_pool\":\"[::CAEReport::jsonEscape $compPoolStr]\",\"component_name\":\"[::CAEReport::jsonEscape $compNameStr]\"}"
        }
        catch {caeSelection ReleaseHandle}
        caeModel RemoveSelectionSet $selectionId
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

