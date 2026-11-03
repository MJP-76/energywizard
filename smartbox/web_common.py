"""API som webben och mobilappen delar: sponsring och installationens språk.

register(app, role_of, open_setup) där role_of(request) ger 'owner'|'family'|'guest'|None och
open_setup() säger om startguiden pågår (inget lösenord valt än)."""
from fastapi import Request
from fastapi.responses import JSONResponse

import ew_settings
import i18n_routes
import sponsor


def register(app, role_of, open_setup=lambda: False):
    @app.get("/api/sponsor")
    async def api_sponsor(request: Request, lang: str = ""):
        st = sponsor.state(lang or i18n_routes.default_language())
        if role_of(request) != "owner":
            st["show"] = False                       # påminnelsen är till ägaren, länken till alla
        return st

    @app.post("/api/sponsor/dismiss")
    async def api_sponsor_dismiss(request: Request):
        if role_of(request) != "owner":
            return JSONResponse({"detail": "Bara ägaren"}, status_code=403)
        sponsor.dismiss()
        return {"ok": True}

    @app.post("/api/sponsor/notice")
    async def api_sponsor_notice(request: Request):
        if role_of(request) != "owner":
            return JSONResponse({"detail": "Bara ägaren kan ändra det här"}, status_code=403)
        body = await request.json()
        sponsor.set_enabled(bool(body.get("enabled", True)))
        return {"ok": True, "enabled": sponsor.enabled()}

    @app.post("/api/setup/language")
    async def api_setup_language(request: Request):
        """Installationens språk (standard för alla enheter). I startguiden, eller av ägaren."""
        if not (open_setup() or role_of(request) == "owner"):
            return JSONResponse({"detail": "Bara ägaren kan ändra språket för hela installationen"}, status_code=403)
        body = await request.json()
        lang = str(body.get("language", ""))
        if lang not in i18n_routes.languages():
            return JSONResponse({"detail": "Okänt språk"}, status_code=400)
        ew_settings.update(language=lang)
        return {"ok": True, "language": lang}
