"""mqtt_bridge.py - EnergyWizard i Home Assistant via MQTT med autodiscovery (idé från FTW, docs/ha-integration.md).

Utan MQTT publicerar ha_publisher.py sina sensorer via HA:s REST-API: de saknar unikt id, går inte att redigera i HA
och försvinner när HA startar om (tills nästa minut). Med en MQTT-broker inställd (Inställningar -> Home Assistant via
MQTT, eller MQTT_HOST m.fl.) blir samma sensorer riktiga entiteter under enheten "EnergyWizard", och två brytare
går att styra från HA: Skuggläge och Automatisk exportstyrning.

- Samma entitets-id som förut (sensor.smartbox_* via default_entity_id/object_id), så befintliga dashboards fungerar.
  De gamla REST-entiteterna tas bort en gång innan discovery skickas, annars skulle HA ge de nya ett _2-suffix.
- Tillgänglighet (energywizard/status) med "last will": stannar EnergyWizard visas entiteterna som otillgängliga.
- Status skrivs till inställningarna (mqtt_status) så att webben kan visa om anslutningen fungerar.
- Rör aldrig styrningen: egen tråd, alla fel fångas.
"""
import json
import os
import threading
import time

PREFIX = "homeassistant"
BASE = "energywizard"
AVAIL = f"{BASE}/status"
DEVICE = {"identifiers": ["energywizard"], "name": "EnergyWizard", "manufacturer": "EnergyWizard Open",
          "model": "smartbox", "sw_version": os.environ.get("APP_VERSION", "dev")}
SWITCHES = {                    # nycklar och id i ASCII (HA:s entitets-id), visningsnamnen på svenska
    "shadow_mode": ("energywizard_shadow_mode", "Skuggläge", "mdi:incognito"),
    "auto_export": ("energywizard_auto_export", "Automatisk exportstyrning", "mdi:solar-power"),
}

_state = {"client": None, "cfg": None, "removed_rest": False}


def config() -> dict | None:
    """Broker ur inställningarna (webben) eller miljön. None = MQTT av."""
    try:
        import ew_settings
        st = ew_settings.load()
    except Exception:
        st = {}
    host = (st.get("mqtt_host") or os.environ.get("MQTT_HOST", "")).strip()
    if not host:
        return None
    return {"host": host, "port": int(st.get("mqtt_port") or os.environ.get("MQTT_PORT") or 1883),
            "user": st.get("mqtt_user") or os.environ.get("MQTT_USER") or None,
            "password": st.get("mqtt_password") or os.environ.get("MQTT_PASSWORD") or None}


def active() -> bool:
    c = _state["client"]
    return c is not None and c.is_connected()


def _status(ok: bool, msg: str):
    try:
        import ew_settings
        ew_settings.update(mqtt_status={"ok": ok, "msg": msg, "at": int(time.time())})
    except Exception:
        pass


def _object_id(entity_id: str) -> str:
    return entity_id.split(".", 1)[1]


def discovery_payload(entity_id: str, attrs: dict) -> tuple:
    """(topic, payload) för en sensors discovery-konfiguration. Ren funktion - testas i tests/test_mqtt_bridge.py."""
    domain = entity_id.split(".", 1)[0]
    oid = _object_id(entity_id)
    name = str(attrs.get("friendly_name") or oid)
    for p in ("Smartbox ", "smartbox "):
        if name.startswith(p):
            name = name[len(p):]
    cfg = {"name": name, "unique_id": f"energywizard_{oid}", "object_id": oid, "default_entity_id": entity_id,
           "state_topic": f"{BASE}/{oid}/state", "json_attributes_topic": f"{BASE}/{oid}/attributes",
           "availability_topic": AVAIL, "device": DEVICE}
    for k in ("unit_of_measurement", "device_class", "icon", "state_class"):
        if attrs.get(k):
            cfg[k] = attrs[k]
    if domain == "binary_sensor":
        cfg.update(payload_on="on", payload_off="off")
    return f"{PREFIX}/{domain}/{BASE}/{oid}/config", cfg


def switch_payload(key: str) -> tuple:
    oid, name, icon = SWITCHES[key]
    return f"{PREFIX}/switch/{BASE}/{oid}/config", {
        "name": name, "unique_id": oid, "object_id": oid, "default_entity_id": f"switch.{oid}", "icon": icon,
        "state_topic": f"{BASE}/switch/{key}/state", "command_topic": f"{BASE}/switch/{key}/set",
        "payload_on": "ON", "payload_off": "OFF", "availability_topic": AVAIL, "device": DEVICE}


def _switch_state(key: str) -> bool:
    if key == "shadow_mode":
        import shadow
        return shadow.active()
    import logger
    return str(logger.get_all_overrides().get("solar_auto_export", "true")).lower() != "false"


def _set_switch(key: str, on: bool):
    if key == "shadow_mode":
        import ew_settings
        ew_settings.update(shadow_mode=True if on else None)
    else:
        import logger
        logger.set_override("solar_auto_export", "true" if on else "false")
    print(f"📡 MQTT: {SWITCHES[key][1]} {'på' if on else 'av'} (från Home Assistant)")


def _connect(cfg):
    import paho.mqtt.client as mqtt
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="energywizard-smartbox")
    if cfg["user"]:
        c.username_pw_set(cfg["user"], cfg["password"])
    c.will_set(AVAIL, "offline", retain=True)

    def on_connect(client, userdata, flags, reason, props=None):
        if getattr(reason, "is_failure", False):
            _status(False, f"Brokern nekade anslutningen: {reason}")
            return
        client.publish(AVAIL, "online", retain=True)
        for key in SWITCHES:
            topic, payload = switch_payload(key)
            client.publish(topic, json.dumps(payload, ensure_ascii=False), retain=True)
            client.subscribe(f"{BASE}/switch/{key}/set")
        _status(True, f"Ansluten till {cfg['host']}:{cfg['port']}")
        print(f"📡 MQTT: ansluten till {cfg['host']}:{cfg['port']} - EnergyWizard syns som enhet i Home Assistant")

    def on_message(client, userdata, msg):
        try:
            key = msg.topic.split("/")[2]
            if key in SWITCHES:
                _set_switch(key, msg.payload.decode().strip().upper() == "ON")
                client.publish(f"{BASE}/switch/{key}/state", "ON" if _switch_state(key) else "OFF", retain=True)
        except Exception as e:
            print(f"⚠️ MQTT-kommando: {e}")

    c.on_connect = on_connect
    c.on_message = on_message
    c.connect_async(cfg["host"], cfg["port"], keepalive=60)
    c.loop_start()
    return c


def ensure():
    """Anropas varje minut av ha_publisher: (åter)ansluter när inställningarna ändrats, kopplar ner när MQTT stängts av."""
    cfg = config()
    if cfg == _state["cfg"] and (_state["client"] is not None or cfg is None):
        return
    old = _state["client"]
    if old is not None:
        try:
            old.publish(AVAIL, "offline", retain=True)
            old.loop_stop()
            old.disconnect()
        except Exception:
            pass
    _state.update(client=None, cfg=cfg, removed_rest=False)
    if cfg is None:
        return
    try:
        _state["client"] = _connect(cfg)
    except Exception as e:
        _status(False, f"Kunde inte ansluta till {cfg['host']}:{cfg['port']}: {e}")
        print(f"⚠️ MQTT: {e}")


def publish(entities: dict) -> bool:
    """Publicerar ha_publisher._collect() via MQTT. False = MQTT inte aktivt (ha_publisher använder REST som förut)."""
    if not active():
        return False
    c = _state["client"]
    if not _state["removed_rest"]:                   # de gamla REST-entiteterna bort, annars får de nya _2-suffix
        try:
            import homeassistant
            for entity_id in entities:
                homeassistant.requests.delete(f"{homeassistant._BASE}/states/{entity_id}", headers=homeassistant._HEADERS,
                                              timeout=3, verify=homeassistant._VERIFY)
        except Exception:
            pass
        _state["removed_rest"] = True
    for entity_id, (state, attrs) in entities.items():
        if state is None:
            continue
        topic, payload = discovery_payload(entity_id, attrs or {})
        c.publish(topic, json.dumps(payload, ensure_ascii=False), retain=True)
        oid = _object_id(entity_id)
        c.publish(f"{BASE}/{oid}/state", str(state), retain=True)
        extra = {k: v for k, v in (attrs or {}).items()
                 if k not in ("friendly_name", "unit_of_measurement", "device_class", "icon", "state_class")}
        c.publish(f"{BASE}/{oid}/attributes", json.dumps(extra, ensure_ascii=False, default=str), retain=True)
    for key in SWITCHES:
        c.publish(f"{BASE}/switch/{key}/state", "ON" if _switch_state(key) else "OFF", retain=True)
    return True
