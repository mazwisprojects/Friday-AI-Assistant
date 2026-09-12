import json
from pathlib import Path


def test_device_discovery_is_not_hardcoded():
    settings_file = Path(__file__).resolve().parents[1] / 'backend' / 'settings.json'
    settings = json.loads(settings_file.read_text(encoding='utf-8'))

    assert settings.get('kasa_devices', []) == []
    assert settings.get('printers', []) == []
