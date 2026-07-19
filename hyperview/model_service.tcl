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

# Set every element visible, or focus one component by masking everything
# outside it. HyperView 2019 has no poIPost AddBestView API, and its component
# SetVisibility calls do not reliably refresh in -b mode. Altair recommends
# poIModel Mask for bulk component visibility. With transparency enabled,
# poIPost SetTransparencyMode renders the masked elements as context.
proc ::CAEReport::setComponentFocus {modelHandle clientHandle targetCompId transparency} {
    # Reset the global hidden-geometry mode. Context uses per-component
    # polygon transparency because SetTransparencyMode does not affect batch
    # captures consistently in HyperView 2019.
    set transparencyStatus [$clientHandle SetTransparencyMode false]
    if {$transparencyStatus ne "" && $transparencyStatus != 0} {
        error "SetTransparencyMode returned $transparencyStatus"
    }

    # Reset every component to visible/opaque, then make non-target components
    # transparent for a context capture.
    set componentSetId [$modelHandle AddSelectionSet component]
    $modelHandle GetSelectionSetHandle componentSet $componentSetId
    componentSet SetSelectMode all
    componentSet Add all
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
        foreach componentId $componentIds {
            if {![string is integer -strict $componentId]} {continue}
            set polygonMode [expr {
                $transparency && $targetCompId ne "" && $componentId != $targetCompId
                ? "transparent" : "opaque"
            }]
            $modelHandle GetComponentHandle componentHandle $componentId
            set visibilityStatus [componentHandle SetVisibility true]
            set polygonStatus [componentHandle SetPolygonMode $polygonMode]
            componentHandle ReleaseHandle
            if {$visibilityStatus ne "" && $visibilityStatus != 0} {
                error "component $componentId SetVisibility returned $visibilityStatus"
            }
            if {$polygonStatus ne "" && $polygonStatus != 0} {
                error "component $componentId SetPolygonMode returned $polygonStatus"
            }
        }
    }
    componentSet ReleaseHandle
    $modelHandle RemoveSelectionSet $componentSetId

    set allSetId [$modelHandle AddSelectionSet element]
    $modelHandle GetSelectionSetHandle allSet $allSetId
    allSet SetSelectMode all
    allSet Add all
    set unmaskStatus [$modelHandle UnMask $allSetId]
    if {$unmaskStatus ne "" && $unmaskStatus != 0} {
        error "UnMask returned $unmaskStatus"
    }
    allSet ReleaseHandle
    $modelHandle RemoveSelectionSet $allSetId

    if {$targetCompId ne "" && !$transparency} {
        set outsideSetId [$modelHandle AddSelectionSet element]
        $modelHandle GetSelectionSetHandle outsideSet $outsideSetId
        outsideSet SetSelectMode all
        outsideSet Add "component $targetCompId"
        if {[outsideSet GetSize] == 0} {
            outsideSet ReleaseHandle
            $modelHandle RemoveSelectionSet $outsideSetId
            error "component $targetCompId has no selectable elements"
        }
        outsideSet Reverse
        set maskStatus [$modelHandle Mask $outsideSetId]
        outsideSet ReleaseHandle
        $modelHandle RemoveSelectionSet $outsideSetId
        if {$maskStatus ne "" && $maskStatus != 0} {
            error "Mask returned $maskStatus"
        }
    }

}
