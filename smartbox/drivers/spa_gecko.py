"""GeckoSpaDriver: Gecko-spabad (in.touch2 via HA:s gecko-integration). Entiteterna kommer ur installationen
(spa.entities) - inga husspecifika namn i koden:

  current_temp, target_temp   sensorer för vatten- och måltemperatur
  climate                     climate-entiteten (måltemperatur läses/sätts här)
  water_heater                värmarens läge (heating/idle)
  economy_mode                switch för Economy Mode
  power_phases / power_w      effekt per fas (lista) eller total - tas som belopp (CT-klämmans riktning)
  safety                      {overcurrent|overvoltage|overheated|power_exceeded: binary_sensor}
  activities                  {heating|circ_pump|pump1|blower|...: entitet} - för fasinlärningen
  smart_plug                  switch som bryter strömmen (omstart när spat tappat kontakten)

read_state() returnerar rådata (heater_state som HA visar den) - main.py:s villkor bor kvar där."""
import homeassistant
from drivers.spa import SpaDriver


class GeckoSpaDriver(SpaDriver):
    def __init__(self, entities: dict | None = None):
        self._e = entities or {}

    def read_state(self) -> dict:
        d = homeassistant.read_gecko(self._e) or {}
        return {
            "current_temp": d.get("current_temp"),
            "target_temp": d.get("target_temp"),
            "heater_state": d.get("heater_state"),
            "economy_mode": d.get("economy_mode"),
        }

    def set_target_temp(self, temp_c: float) -> None:
        homeassistant.set_gecko_target(temp_c, self._e.get("climate"))

    def set_economy(self, enable: bool) -> None:
        homeassistant.set_gecko_economy(enable, self._e.get("economy_mode"))

    def read_power_w(self) -> float | None:
        return (self.read_power_detail() or {}).get("total_w")

    def read_power_detail(self) -> dict:
        return homeassistant.read_spa_power(self._e) or {}

    def read_activities(self) -> dict:
        return homeassistant.read_spa_activities(self._e) or {}

    def set_plug_power(self, on: bool) -> bool:
        return homeassistant.toggle_spa_plug(on, self._e.get("smart_plug"))
