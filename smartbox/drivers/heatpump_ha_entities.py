"""HaEntitiesHeatPumpDriver: värmepump som redan finns i Home Assistant via en integration (t.ex. HA:s egen myUplink-
integration för NIBE, eller nibe_heatpump), läst via dess entiteter.

Issue #158 (2026-11-06): en NIBE F750 via HA:s myUplink-integration hittades inte. Vår drivrutin "myuplink" pratar
direkt med molnet (eget OAuth-konto), så den kunde inte använda integrationen som redan fanns. Den här drivrutinen
läser i stället de entiteter installationsguiden kopplat (heat_pump.entities i house_config.yaml):

  indoor_temp, outdoor_temp, forward_temp, return_temp, water_temp, degree_minutes  (sensor-/number-entiteter)
  compressor   (valfri, binary_sensor/sensor: på/av eller frekvens > 0 = går)
  room_target  (valfri, number-entitet för rumsbörvärdet; utan den styrs inget)

Guiden kopplar NIBE:s givarkoder i entiteternas namn (BT1 ute, BT2 framledning, BT3 retur, BT7/BT6 varmvatten, BT50
rum), som är desamma på alla språk (discovery.py, _nibe_bt_entities). room_target kopplas aldrig automatiskt: vilket
börvärde som är rätt skiljer mellan modeller, och myUplink kräver premiumabonnemang för att skriva. Utan den läser
drivrutinen bara, och styrningen svarar ärligt False.
"""
import homeassistant
from drivers.heatpump import HeatPumpDriver

_READ = ("indoor_temp", "outdoor_temp", "forward_temp", "return_temp", "water_temp", "degree_minutes")


class HaEntitiesHeatPumpDriver(HeatPumpDriver):
    def __init__(self, entities: dict | None = None):
        self._e = {k: v for k, v in (entities or {}).items() if isinstance(v, str) and "." in v}
        self._warned = set()

    def _num(self, key):
        ent = self._e.get(key)
        if not ent:
            return None
        v = homeassistant._get_numeric_state(ent)
        return float(v) if isinstance(v, (int, float)) else None

    def _warn_once(self, key, msg):
        if key not in self._warned:
            print(msg)
            self._warned.add(key)

    def read_sensors(self) -> dict:
        if not self._e:
            return {}
        out = {k: self._num(k) for k in _READ}
        comp = self._num("compressor")
        out["compressor_running"] = None if comp is None else comp > 0
        out["compressor_power_kw"] = None
        return out

    def set_room_temp(self, target_c: float) -> bool:
        ent = self._e.get("room_target")
        if not ent:
            self._warn_once("room", "ℹ️ Värmepumpen (Home Assistant-entiteter): inget rumsbörvärde valt "
                                    "(heat_pump.entities.room_target) - läser bara, styr inte.")
            return False
        v = round(min(max(float(target_c), 5.0), 30.0), 1)
        import shadow
        if shadow.active():
            shadow.record("Värmepump (HA)", f"{ent}={v}")
            return True
        return homeassistant.set_number(ent, v)

    def set_water_stop_temp(self, target_c: float) -> bool:
        return False

    def set_water_start_temp(self, target_c: float) -> bool:
        return False

    def set_heating_start_temp(self, target_c: float) -> bool:
        return False

    def set_operating_mode(self, mode) -> bool:
        return False
