import pytest

from pmars_simulation.hil import driver


def test_native_host_failure_explains_repository_or_editable_install(monkeypatch, tmp_path):
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    with pytest.raises(RuntimeError, match="repository checkout or"):
        driver._load_host()
