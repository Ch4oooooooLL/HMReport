proc ::CAEReport::viewApply {id line} {
    # Individual HyperView 2019 fields are applied by the adapter as supported.
    # Unsupported fields intentionally return partial rather than being guessed.
    ::CAEReport::success $id {"restore":"partial","missing":["camera.matrix","legend.precision"]}
}
