"""Runtime checks never write the current account's checkout lease authority."""
import pytest


@pytest.fixture(autouse=True)
def isolated_checkout_lease_authority(tmp_path_factory, monkeypatch):
    authority = tmp_path_factory.mktemp("shared-authority") / "leases.sqlite"
    monkeypatch.setattr("workspace_engineering.state.lease_authority_path", lambda: authority)
    return authority
