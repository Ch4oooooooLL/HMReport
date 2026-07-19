proc ::CAEReport::viewApply {id line} {
    set subcaseName [::CAEReport::jsonString $line subcase_name]
    set simulationName [::CAEReport::jsonString $line simulation_name]
    set resultType [::CAEReport::jsonString $line result_type]
    set resultComponent [::CAEReport::jsonString $line result_component]
    set contourEnabled [string tolower [::CAEReport::jsonString $line contour_enabled]]
    set averaging [string tolower [::CAEReport::jsonString $line averaging]]
    set legendPrecision [::CAEReport::jsonString $line legend_precision]
    set legendVisible [string tolower [::CAEReport::jsonString $line legend_visible]]
    set targetType [string tolower [::CAEReport::jsonString $line target_entity_type]]
    set targetPool [::CAEReport::jsonString $line target_entity_pool]
    set targetId [::CAEReport::jsonString $line target_entity_id]
    set targetComponentId [::CAEReport::jsonString $line target_component_id]
    set targetComponentPool [::CAEReport::jsonString $line target_component_pool]
    set preset [string tolower [::CAEReport::jsonString $line camera_preset]]
    set cameraMatrix [::CAEReport::jsonString $line camera_matrix]
    set missing {}
    set warnings {}
    set appliedTarget ""
    set appliedViewMode ""

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
        caeWindow GetViewControlHandle caeView
    } message]} {
        catch {hwi CloseStack}
        ::CAEReport::failure $id "VIEW_RESTORE_FAILED" $message
        return
    }

    set currentSubcaseId ""
    if {$subcaseName ne ""} {
        foreach subcaseId [caeResult GetSubcaseList] {
            if {[caeResult GetSubcaseLabel $subcaseId] eq $subcaseName} {
                set currentSubcaseId $subcaseId
                break
            }
        }
        if {$currentSubcaseId eq "" || [catch {
            caeResult SetCurrentSubcase $currentSubcaseId
        } message]} {
            lappend missing "subcase.name"
            if {[info exists message] && $message ne ""} {lappend warnings $message}
        }
    } else {
        set currentSubcaseId [lindex [caeResult GetSubcaseList] 0]
    }

    if {$simulationName ne ""} {
        set simulationIndex -1
        set index 0
        foreach simulationLabel [caeResult GetSimulationList $currentSubcaseId] {
            if {$simulationLabel eq $simulationName} {
                set simulationIndex $index
                break
            }
            incr index
        }
        if {$simulationIndex < 0 || [catch {
            caeResult SetCurrentSimulation $simulationIndex
        } message]} {
            lappend missing "simulation.name"
            if {[info exists message] && $message ne ""} {lappend warnings $message}
        }
    }

    set hasContourRequest [expr {
        $resultType ne "" || $resultComponent ne "" || $averaging ne "" ||
        $legendPrecision ne "" || $contourEnabled ne ""
    }]
    if {$hasContourRequest} {
        if {[catch {caeResult GetContourCtrlHandle caeContour} message]} {
            foreach field {result.type result.component contour.enabled contour.averaging contour.precision} {
                lappend missing $field
            }
            lappend warnings $message
        } else {
            if {$resultType ne "" && [catch {
                caeContour SetDataType $resultType
            } message]} {
                lappend missing "result.type"
                lappend warnings $message
            }
            if {$resultComponent ne "" && [catch {
                caeContour SetDataComponent $resultComponent
            } message]} {
                lappend missing "result.component"
                lappend warnings $message
            }
            if {$averaging ne "" && [catch {
                caeContour SetAverageMode $averaging
            } message]} {
                lappend missing "contour.averaging"
                lappend warnings $message
            }
            if {$contourEnabled ne "" && [catch {
                caeContour SetEnableState $contourEnabled
                caeClient SetDisplayOptions contour $contourEnabled
            } message]} {
                lappend missing "contour.enabled"
                lappend warnings $message
            }
            if {$legendPrecision ne ""} {
                if {![string is integer -strict $legendPrecision] ||
                    $legendPrecision < 0 || $legendPrecision > 10 ||
                    [catch {
                        caeContour GetLegendHandle caeLegend
                        caeLegend SetNumericPrecision $legendPrecision
                        caeLegend ReleaseHandle
                    } message]} {
                    lappend missing "contour.precision"
                    if {[info exists message] && $message ne ""} {lappend warnings $message}
                }
            }
        }
    }

    if {$legendVisible ne "" && [catch {
        caeClient SetDisplayOptions legend $legendVisible
    } message]} {
        lappend missing "render.legend_visible"
        lappend warnings $message
    }

    set targetApplied 0
    set componentPreset [expr {
        $preset in {"component_isolate" "component_context" "local_isometric"}
    }]

    if {$componentPreset} {
        if {![string is integer -strict $targetComponentId] &&
            $targetType ne "" && [string is integer -strict $targetId]} {
            set resolved [
                ::CAEReport::resolveEntityComponent caeModel $targetType $targetPool $targetId
            ]
            set targetComponentId [lindex $resolved 0]
            set targetComponentPool [lindex $resolved 2]
        }
        if {![string is integer -strict $targetComponentId]} {
            lappend missing "target.component_id"
            lappend warnings "component focus requires a resolvable component id"
        } elseif {[catch {
            set transparent [expr {$preset eq "component_context"}]
            ::CAEReport::setComponentFocus \
                caeModel caeClient $targetComponentId $transparent
            caeView SetOrientation iso
            caeView Fit
            set targetApplied 1
            set appliedTarget "component [list $targetComponentPool $targetComponentId]"
            set appliedViewMode $preset
        } message]} {
            lappend missing "target"
            lappend warnings $message
        }
    } elseif {[catch {
        # Clear a previous focus before standard/global/directional views.
        ::CAEReport::setComponentFocus caeModel caeClient "" false
    } message]} {
        lappend missing "visibility"
        lappend warnings $message
    }

    if {$cameraMatrix ne ""} {
        set matrixValues [split $cameraMatrix]
        set matrixValid [expr {[llength $matrixValues] == 16}]
        foreach value $matrixValues {
            if {![string is double -strict $value]} {
                set matrixValid 0
                break
            }
        }
        if {!$matrixValid || [catch {
            caeView SetViewMatrix $cameraMatrix
        } message]} {
            lappend missing "camera.matrix"
            if {[info exists message] && $message ne ""} {lappend warnings $message}
        }
    } elseif {!$targetApplied && $preset ne ""} {
        switch -glob -- $preset {
            "front" {set orientation "front"}
            "rear" - "back" {set orientation "back"}
            "left" {set orientation "left"}
            "right" {set orientation "right"}
            "top" {set orientation "top"}
            "bottom" {set orientation "bottom"}
            default {set orientation "iso"}
        }
        if {[catch {
            caeView SetOrientation $orientation
            caeView Fit
        } message]} {
            lappend missing "camera.preset"
            lappend warnings $message
        }
    }

    if {[catch {
        caeClient Draw true
        update
    } message]} {
        lappend missing "display.draw"
        lappend warnings $message
    }
    catch {caeView ReleaseHandle}
    catch {hwi CloseStack}

    set missing [lsort -unique $missing]
    set restore [expr {[llength $missing] == 0 ? "exact" : "partial"}]
    set result "{\"restore\":\"$restore\",\"missing\":[::CAEReport::jsonStringArray $missing]"
    if {$appliedTarget ne ""} {
        append result ",\"applied_target\":\"[::CAEReport::jsonEscape $appliedTarget]\""
    }
    if {$appliedViewMode ne ""} {
        append result ",\"applied_view_mode\":\"[::CAEReport::jsonEscape $appliedViewMode]\""
    }
    if {[llength $warnings] > 0} {
        append result ",\"warning\":\"[::CAEReport::jsonEscape [join $warnings { | }]]\""
    }
    append result "}"
    ::CAEReport::success $id $result
}
