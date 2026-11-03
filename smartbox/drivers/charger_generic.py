"""GenericChargerDriver: täcker de flesta laddboxar utan en handbyggd drivrutin per
märke, genom HA:s generiska switch.turn_on/off och number.set_value (om laddaren
exponerar strömgräns som en vanlig number-entitet). Easees "dynamiska" gräns och
fasväxling är äkta märkesspecifika HA-tjänster utan generisk motsvarighet.

OCPP (lbbrhzn/ocpp, HA:s OCPP-integration) - lärdomar från SpotNav (henrikekblad/spotnav-home-
assistant, MIT, bekräftat mot riktig hårdvara: Charge Amps HALO):
  - Strömgränsen skrivs till sessionens gräns (number.<cp>_session_current_limit eller
    ..._connector_<n>_session_current_limit), ALDRIG till number.<cp>_maximum_current - den är
    laddboxens bestående tak. Sessionens gräns är 'unavailable' utan pågående laddning; det är normalt.
  - IEC 61851-laddare levererar inte under 6 A: en gräns mellan 0 och 6 A höjs till 6 A, och 0 A
    betyder "stäng av" (switch av), inte en gräns på 0 som laddboxen kan avvisa.
  - Högst en skrivning per 10 s per laddbox.
  - Statusen normaliseras till samma ord som Easee-drivrutinen (connector-statusen i OCPP 1.6),
    så resten av motorn (anslutning, laddstopp-vakten) fungerar likadant.
"""
import time

import homeassistant
from drivers.charger import ChargerDriver

MIN_CHARGE_A = 6
MIN_WRITE_INTERVAL_S = 10.0

# OCPP 1.6 connector-status (och vanliga generiska ord) -> samma ord som Easee-drivrutinen använder.
_STATUS = {
    "available": "disconnected", "preparing": "awaiting_start", "charging": "charging",
    "suspendedev": "completed", "suspendedevse": "paused", "finishing": "completed",
    "reserved": "awaiting_start", "unavailable": "offline", "faulted": "offline",
    "disconnected": "disconnected", "connected": "awaiting_start", "ready": "awaiting_start",
    "completed": "completed", "paused": "paused", "offline": "offline", "error": "offline",
}


def normalize_status(raw):
    if raw is None:
        return None
    key = str(raw).strip().lower().replace(" ", "").replace("_", "").replace("-", "")
    for k, v in _STATUS.items():
        if key == k.replace("_", ""):
            return v
    return str(raw).strip().lower()


class GenericChargerDriver(ChargerDriver):
    """Default för laddare utan egen drivrutin. Kräver bara en switch-entitet
    (på/av) - strömgräns är valfri, fasväxling stöds inte."""
    supports_phase_switch = False

    def __init__(self, id: str, entities: dict | None = None):
        self.id = id
        self._e = entities or {}
        self._last_write = {"amps": None, "t": 0.0}

    def read_state(self) -> dict:
        status_e = self._e.get("status")
        current_e = self._e.get("current_limit")
        import_e = self._e.get("current_import")
        raw = homeassistant._get_raw_state(status_e) if status_e else None
        return {
            "status": normalize_status(raw),
            "status_raw": raw,
            "current_a": homeassistant._get_numeric_state(import_e) if import_e else
                         (homeassistant._get_numeric_state(current_e) if current_e else None),
            "phases": None,
        }

    def set_limit_a(self, amps: int, reason: str | None = None) -> bool:
        amps = int(amps or 0)
        if amps <= 0:
            self.turn_off()
            self._last_write = {"amps": 0, "t": time.time()}
            return True
        amps = max(MIN_CHARGE_A, amps)
        current_e = self._e.get("current_limit")
        if not current_e:
            return False
        now = time.time()
        if self._last_write["amps"] == amps:
            return True
        if now - self._last_write["t"] < MIN_WRITE_INTERVAL_S:
            return False                                  # försök igen nästa varv
        ok = homeassistant.set_number(current_e, amps)
        if ok:
            self._last_write = {"amps": amps, "t": now}
        return ok

    def set_phases(self, phases: int) -> None:
        pass

    def turn_on(self) -> None:
        switch_e = self._e.get("switch")
        if switch_e:
            homeassistant.set_switch(switch_e, True)

    def turn_off(self) -> None:
        switch_e = self._e.get("switch")
        if switch_e:
            homeassistant.set_switch(switch_e, False)
