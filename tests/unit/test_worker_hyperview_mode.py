from cae_report_worker.main import resolve_fake_hyperview


def test_worker_defaults_to_real_hyperview() -> None:
    assert not resolve_fake_hyperview(
        real_requested=False,
        fake_requested=False,
        environment={},
    )


def test_worker_fake_mode_can_be_selected_by_flag_or_environment() -> None:
    assert resolve_fake_hyperview(
        real_requested=False,
        fake_requested=True,
        environment={},
    )
    assert resolve_fake_hyperview(
        real_requested=False,
        fake_requested=False,
        environment={"CAE_REPORT_FAKE_HV": "1"},
    )


def test_worker_real_flag_overrides_fake_environment() -> None:
    assert not resolve_fake_hyperview(
        real_requested=True,
        fake_requested=False,
        environment={"CAE_REPORT_FAKE_HV": "1"},
    )
