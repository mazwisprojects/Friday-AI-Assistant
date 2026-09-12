from pathlib import Path


def test_google_account_has_google_home_scopes():
    backend_dir = Path(__file__).resolve().parents[1] / 'backend'
    google_account = (backend_dir / 'google_account.py').read_text(encoding='utf-8')

    assert 'sdm.service' in google_account
    assert 'homegraph' in google_account


def test_google_home_bridge_module_exists():
    bridge_file = Path(__file__).resolve().parents[1] / 'backend' / 'google_home.py'
    assert bridge_file.exists()
