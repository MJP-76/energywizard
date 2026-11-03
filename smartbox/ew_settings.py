"""Inställningar som sätts i webben vid första start: lösenord och anslutning till Home Assistant.

Sparas i /data/energywizard.json (samma datamapp som databasen och house_config.yaml), så att
ingen behöver redigera filer eller miljövariabler. Miljövariabler (DASHBOARD_PASSWORD, HA_URL,
HA_IP, HA_TOKEN) går alltid före, så befintliga installationer fungerar som förut.
"""
import json
import os
import tempfile

PATH = os.environ.get("EW_SETTINGS_PATH", "/data/energywizard.json")

_cache = {"mtime": None, "data": {}}


def load() -> dict:
    """Inställningarna, eller {} om filen saknas eller inte går att läsa."""
    try:
        mtime = os.stat(PATH).st_mtime_ns
    except OSError:
        _cache.update(mtime=None, data={})
        return {}
    if mtime != _cache["mtime"]:
        try:
            with open(PATH, encoding="utf-8") as f:
                data = json.load(f)
            _cache.update(mtime=mtime, data=data if isinstance(data, dict) else {})
        except (OSError, ValueError):
            return dict(_cache["data"])
    return dict(_cache["data"])


def get(key, default=None):
    return load().get(key, default)


def update(**values) -> dict:
    """Sparar nya värden (None tar bort ett värde). Skrivs atomiskt och bara läsbart för ägaren."""
    data = load()
    for k, v in values.items():
        if v is None:
            data.pop(k, None)
        else:
            data[k] = v
    folder = os.path.dirname(PATH) or "."
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".energywizard.", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.chmod(tmp, 0o600)
        os.replace(tmp, PATH)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    _cache.update(mtime=None)
    return load()
