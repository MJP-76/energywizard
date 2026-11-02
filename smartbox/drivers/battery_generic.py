"""GenericBatteryDriver: läser/styr ett husbatteri via vad batteriets egna HA-integration
redan exponerar - samma väg Predbat (github.com/springfall2008/batpred) bevisat fungerar för
GivEnergy/Huawei/Solis/Powerwall m.fl.

Styrning (valfri): en select-entitet för läget och en mappning från EnergyWizards avsikter till
batteriets egna lägesnamn, t.ex. för SolarEdge Modbus (HA 2026.10) "Storage command mode":

    battery:
      entities:
        soc: sensor.batteri_soc
        power: sensor.batteri_effekt          # + = laddar
        mode_select: select.solaredge_storage_command_mode
        charge_power: number.batteri_laddeffekt          # valfri, W
        discharge_power: number.batteri_urladdningseffekt # valfri, W
      modes:
        auto: "Maximize self-consumption"
        hold: "Charge from solar power"
        idle: "Off"
        charge: "Charge from solar power and grid"
        discharge: "Maximize export"

Lägesnamnen ovan är EXEMPEL - skriv exakt de alternativ din egen select-entitet visar i
Home Assistant (Utvecklarverktyg -> Tillstånd -> entiteten -> attributet options).
Bara de avsikter som finns under modes: används.
"""
import homeassistant
from drivers.battery import BatteryDriver, INTENTS


class GenericBatteryDriver(BatteryDriver):
    """Default för batterier utan egen drivrutin. Alla entiteter valfria - supports_control()
    är bara True om en mode_select-entitet OCH minst en lägesmappning finns."""
    def __init__(self, capacity_kwh: float | None = None, entities: dict | None = None, modes: dict | None = None):
        self.capacity_kwh = capacity_kwh
        self._e = entities or {}
        self._modes = {k: v for k, v in (modes or {}).items() if k in INTENTS and v}

    def read_state(self) -> dict:
        soc_e = self._e.get("soc")
        power_e = self._e.get("power")
        mode_e = self._e.get("mode_select")
        return {
            "soc_pct": homeassistant._get_numeric_state(soc_e) if soc_e else None,
            "power_w": homeassistant._get_numeric_state(power_e) if power_e else None,
            "capacity_kwh": self.capacity_kwh,
            "mode": homeassistant._get_raw_state(mode_e) if mode_e else None,
        }

    def supports_control(self) -> bool:
        return bool(self._e.get("mode_select")) and bool(self._modes)

    def supported_intents(self) -> set:
        return set(self._modes) if self.supports_control() else set()

    def set_mode(self, mode: str) -> bool:
        mode_e = self._e.get("mode_select")
        if not mode_e:
            return False
        return homeassistant.set_select(mode_e, mode)

    def apply_intent(self, intent: str, power_w: float | None = None) -> bool:
        option = self._modes.get(intent)
        if not option or not self._e.get("mode_select"):
            return False
        ok = True
        if power_w is not None:
            num = self._e.get("charge_power" if intent == "charge" else "discharge_power" if intent == "discharge" else "")
            if num:
                ok = homeassistant.set_number(num, int(round(abs(power_w))))
        return ok and self.set_mode(option)
