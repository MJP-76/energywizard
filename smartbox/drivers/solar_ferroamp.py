"""EnergyHub system grid-export boundary, not a PV production percentage.

RevD sections 6.8/6.9: stage flag + float32 W threshold, apply, verify system values.
100% releases the boundary. Lifetime PV energy is not labelled as today's energy.
"""
import math

from drivers.solar import SolarDriver
from drivers.ferroamp_modbus import (
    EnergyHubConnection, read_float, read_words, shadow_write, write_float, write_word,
)


class FerroampSolarDriver(SolarDriver):
    def __init__(self, modbus=None, control_enabled=False, max_export_w=None):
        self._bus = EnergyHubConnection(modbus)
        self._enabled = control_enabled is True
        self._max_export = float(max_export_w) if max_export_w is not None else None
        if self._max_export is not None and (not math.isfinite(self._max_export) or not 0 < self._max_export <= 1e9):
            raise ValueError("EnergyHub max_export_w must be finite and positive")

    def read_production(self):
        state = {"pv_power_w": None, "today_kwh": None, "status": None}
        with self._bus.connect() as client:
            if client is None:
                return state
            power = read_float(client, 5100, self._bus.unit_id)
            state["pv_power_w"] = power * 1000 if power is not None and power >= 0 else None
            status = read_words(client, 2000, 1, self._bus.unit_id)
            state["status"] = str(status[0]) if status is not None else None
        return state

    def supports_curtailment(self):
        return bool(self._bus.host) and self._enabled

    def set_export_limit_pct(self, pct):
        if not self.supports_curtailment() or isinstance(pct, bool):
            return False
        try:
            pct = float(pct)
        except (TypeError, ValueError):
            return False
        if not math.isfinite(pct) or not 0 <= pct <= 100:
            return False
        enabled = pct < 100
        if 0 < pct < 100 and self._max_export is None:
            return False
        threshold = (self._max_export or 0.0) * pct / 100
        if shadow_write(f"grid export enabled={enabled}, threshold={threshold:g} W"):
            return True
        unit = self._bus.unit_id
        with self._bus.connect() as client:
            if client is None:
                return False
            if not write_word(client, 8010, int(enabled), unit):
                return False
            if enabled and not write_float(client, 8012, threshold, unit):
                return False
            if not write_word(client, 8016, 1, unit):
                return False
            return self._bus.verify(lambda: self._matches(client, enabled, threshold))
        return False

    def _matches(self, client, enabled, threshold):
        flag = read_words(client, 8010, 1, self._bus.unit_id)
        if flag != [int(enabled)]:
            return False
        if not enabled:
            return True
        actual = read_float(client, 8012, self._bus.unit_id)
        return actual is not None and abs(actual - threshold) <= 1.0

    def get_export_limit_pct(self):
        if not self.supports_curtailment():
            return None
        unit = self._bus.unit_id
        with self._bus.connect() as client:
            if client is None:
                return None
            flag = read_words(client, 8010, 1, unit)
            if flag == [0]:
                return 100.0
            if flag == [1]:
                threshold = read_float(client, 8012, unit)
                if threshold is not None and threshold >= 0:
                    if threshold == 0:
                        return 0.0
                    if self._max_export:
                        return max(0.0, min(100.0, threshold / self._max_export * 100))
        return None
