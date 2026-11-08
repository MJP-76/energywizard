"""HaEntitiesHeatPumpDriver: värmepump som redan finns i Home Assistant via en integration (t.ex. HA:s egen myUplink-
integration för NIBE, eller nibe_heatpump), läst via dess entiteter.

Issue #158 (2026-11-06): en NIBE F750 via HA:s myUplink-integration hittades inte. Vår drivrutin "myuplink" pratar
direkt med molnet (eget OAuth-konto), så den kunde inte använda integrationen som redan fanns. Den här drivrutinen
läser i stället de entiteter installationsguiden kopplat (heat_pump.entities i house_config.yaml):

  indoor_temp, outdoor_temp, forward_temp, return_temp, water_temp, degree_minutes  (sensor-/number-entiteter)
  compressor   (valfri, binary_sensor/sensor: på/av eller frekvens > 0 = går)
  room_target  (valfri, number-entitet för rumsbörvärdet)
  curve_offset (valfri, number-entitet för värmekurvans förskjutning, t.ex. NIBE 47011 "Heating offset climate system 1",
               #200 Jonas: F730 via nibegw). Används när rumsbörvärde saknas: önskad innetemp -> förskjutning med
               offset_steps_per_c steg per grad kring offset_base_c (standard 2 steg/°C kring 20,5 °C), inom
               offset_min..offset_max (standard -5..+5).

Guiden kopplar NIBE:s givarkoder i entiteternas namn (BT1 ute, BT2 framledning, BT3 retur, BT7/BT6 varmvatten, BT50
rum), som är desamma på alla språk (discovery.py, _nibe_bt_entities). room_target kopplas aldrig automatiskt: vilket
börvärde som är rätt skiljer mellan modeller, och myUplink kräver premiumabonnemang för att skriva. Utan den läser
drivrutinen bara, och styrningen svarar ärligt False.
"""
import homeassistant
from drivers.heatpump import HeatPumpDriver

_READ = ("indoor_temp", "outdoor_temp", "forward_temp", "return_temp", "water_temp", "degree_minutes")


class HaEntitiesHeatPumpDriver(HeatPumpDriver):
    def __init__(self, entities: dict | None = None, cfg: dict | None = None):
        self._e = {k: v for k, v in (entities or {}).items() if isinstance(v, str) and "." in v}
        self._cfg = cfg or {}                     # offset_steps_per_c, offset_base_c, offset_min, offset_max (#200)
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
        if comp is None and self._e.get("compressor"):           # binary_sensor/statustext: på/av
            raw = str(homeassistant._get_raw_state(self._e["compressor"]) or "").strip().lower()
            comp = 1.0 if raw in ("on", "true", "running", "drift", "går", "heating", "värme", "hot water", "varmvatten") \
                else 0.0 if raw in ("off", "false", "idle", "stopped", "av", "vilar", "standby", "från") else None
        out["compressor_running"] = None if comp is None else comp > 0
        out["compressor_power_kw"] = None
        return out

    def set_room_temp(self, target_c: float) -> bool:
        ent = self._e.get("room_target")
        if not ent and self._e.get("curve_offset"):
            return self._set_offset_for(target_c)
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

    def _set_offset_for(self, target_c: float) -> bool:
        def num(k, d):
            try:
                return float(self._cfg.get(k, d))
            except (TypeError, ValueError):
                return d
        steps = num("offset_steps_per_c", 2.0) * (float(target_c) - num("offset_base_c", 20.5))
        off = int(round(min(max(steps, num("offset_min", -5.0)), num("offset_max", 5.0))))
        ent = self._e["curve_offset"]
        import shadow
        if shadow.active():
            shadow.record("Värmepump (HA, kurva)", f"{ent}={off}")
            return True
        return homeassistant.set_number(ent, off)

    def set_water_stop_temp(self, target_c: float) -> bool:
        return False

    def set_water_start_temp(self, target_c: float) -> bool:
        return False

    def set_heating_start_temp(self, target_c: float) -> bool:
        return False

    def set_operating_mode(self, mode) -> bool:
        return False
