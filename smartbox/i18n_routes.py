"""Serverar översättningarna (smartbox/i18n/) till webben och mobilappen, utan inloggning
(inloggningssidan och startguiden behöver dem också).

  GET /i18n/config         -> {"default": "sv", "languages": {"sv": "Svenska", "en": "English"}}
  GET /i18n/<språk>.json   -> ordlistan
  GET /i18n/i18n.js        -> översättningsmotorn
"""
import json
import os
import re

from fastapi.responses import FileResponse, JSONResponse

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "i18n")
_NAME = re.compile(r"^(?:[a-z]{2,3}(?:-[A-Za-z]{2,4})?\.json|i18n\.js)$")


def languages() -> dict:
    try:
        with open(os.path.join(DIR, "languages.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"sv": "Svenska"}


def default_language() -> str:
    """Installationens språk (valt i startguiden eller inställningarna), annars svenska."""
    try:
        import ew_settings
        lang = ew_settings.get("language") or "sv"
    except Exception:
        lang = "sv"
    return lang if lang in languages() else "sv"


def register(app):
    @app.get("/i18n/config")
    def i18n_config():
        return JSONResponse({"default": default_language(), "languages": languages()},
                            headers={"Cache-Control": "no-cache"})

    @app.get("/i18n/{name}")
    def i18n_file(name: str):
        if not _NAME.match(name) or not os.path.isfile(os.path.join(DIR, name)):
            return JSONResponse({"detail": "Finns inte"}, status_code=404)
        kind = "application/javascript" if name.endswith(".js") else "application/json"
        return FileResponse(os.path.join(DIR, name), media_type=kind, headers={"Cache-Control": "no-cache"})
