from cae_report_desktop.process_supervisor import worker_environment_values, worker_restart_delay
from cae_report_worker.main import resolve_fake_hyperview


def test_worker_defaults_to_real_hyperview() -> None:
    assert not resolve_fake_hyperview(
        real_requested=False,
        fake_requested=False,
        environment={},
    )


def test_desktop_passes_configured_hyperview_path_to_worker(tmp_path) -> None:
    executable = (tmp_path / "hw.exe").resolve()
    worker_log = (tmp_path / "app" / "logs" / "worker.jsonl").resolve()

    values = worker_environment_values(
        server_url="http://127.0.0.1:8765",
        fake_hyperview=False,
        hyperview_executable=executable,
        worker_log_path=worker_log,
    )

    assert values["CAE_REPORT_HYPERVIEW_EXE"] == str(executable)
    assert values["CAE_REPORT_WORKER_LOG"] == str(worker_log)


def test_desktop_restarts_unexpected_worker_with_bounded_backoff() -> None:
    assert worker_restart_delay(attempt=0, stopping=False) == 1000
    assert worker_restart_delay(attempt=3, stopping=False) == 8000
    assert worker_restart_delay(attempt=5, stopping=False) is None
    assert worker_restart_delay(attempt=0, stopping=True) is None


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
