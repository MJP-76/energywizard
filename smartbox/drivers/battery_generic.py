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

Växelriktare där lägesvalet bara sparas lokalt tills en knapp trycks (t.ex. Growatt via
wills106/homeassistant-solax-modbus: "Time 1 Mode" + knappen "Time 1 Update") anger knappen
som mode_apply_button - den trycks efter varje lägesbyte:

    battery:
      entities:
        mode_select: select.growatt_time_1_mode
        mode_apply_button: button.growatt_time_1_update
      modes:
        auto: "Load First"
        hold: "Battery First"        # utan AC-laddning: tar solen, laddar inte ur
        charge: "Battery First"      # kräver att AC-laddning är påslagen i växelriktaren
        discharge: "Grid First"
    (Ställ in Time 1 till 00:00-23:59 och Aktiv en gång i HA - sedan byter EnergyWizard bara läget.)

Ett läge kan också kräva FLERA val samtidigt - då anges det som {select-entitet: alternativ}.
T.ex. Solax (Gen4-6) via wills106/homeassistant-solax-modbus:

    modes:
      auto:      {select.solax_charger_use_mode: "Self Use Mode"}
      hold:      {select.solax_charger_use_mode: "Back Up Mode"}
      idle:      {select.solax_charger_use_mode: "Manual Mode", select.solax_manual_mode_select: "Stop Charge and Discharge"}
      charge:    {select.solax_charger_use_mode: "Manual Mode", select.solax_manual_mode_select: "Force Charge"}
      discharge: {select.solax_charger_use_mode: "Manual Mode", select.solax_manual_mode_select: "Force Discharge"}

Effekt: antingen en tecknad sensor (power, + = laddar) eller två positiva (power_charge och
power_discharge, som Growatt via Solax Modbus har).

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
        soc = homeassistant._get_numeric_state(soc_e) if soc_e else None
        power = homeassistant._get_numeric_state(power_e) if power_e else None
        if power is None and (self._e.get("power_charge") or self._e.get("power_discharge")):
            pc = homeassistant._get_numeric_state(self._e["power_charge"]) if self._e.get("power_charge") else 0.0
            pd = homeassistant._get_numeric_state(self._e["power_discharge"]) if self._e.get("power_discharge") else 0.0
            power = None if pc is None and pd is None else (pc or 0.0) - (pd or 0.0)
        return {
            "soc_pct": soc,
            "power_w": power,
            "capacity_kwh": self.capacity_kwh,
            "mode": homeassistant._get_raw_state(mode_e) if mode_e else None,
        }

    def supports_control(self) -> bool:
        if not self._modes:
            return False
        return bool(self._e.get("mode_select")) or all(isinstance(v, dict) for v in self._modes.values())

    def supported_intents(self) -> set:
        return set(self._modes) if self.supports_control() else set()

    def set_mode(self, mode: str) -> bool:
        mode_e = self._e.get("mode_select")
        if not mode_e:
            return False
        return homeassistant.set_select(mode_e, mode)

    def apply_intent(self, intent: str, power_w: float | None = None) -> bool:
        option = self._modes.get(intent)
        if not option or (not isinstance(option, dict) and not self._e.get("mode_select")):
            return False
        ok = True
        if power_w is not None:
            num = self._e.get("charge_power" if intent == "charge" else "discharge_power" if intent == "discharge" else "")
            if num:
                ok = homeassistant.set_number(num, int(round(abs(power_w))))
        if isinstance(option, dict):                     # flera val i tur och ordning (t.ex. Solax)
            for entity, opt in option.items():
                ok = ok and homeassistant.set_select(entity, opt)
        else:
            ok = ok and self.set_mode(option)
        btn = self._e.get("mode_apply_button")
        if ok and btn:
            ok = bool(homeassistant.press_button(btn))
        return ok
