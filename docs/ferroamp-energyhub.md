# Ferroamp EnergyHub control mapping

`ferroamp_modbus` adds local battery and grid-export drivers. It uses the existing
`pymodbus` dependency; no MQTT connection or portal account is required. Modbus must
be enabled by Ferroamp support. Writes are opt-in and have not been tested on hardware.

This branch starts from main and is independent of the battery-wear feature branch.
The optimizer, house priorities and existing `cycle_cost` remain unchanged.

## Comparison with existing controls

| EnergyWizard control | Existing implementations | EnergyHub equivalent in this branch |
| --- | --- | --- |
| Battery SOC/power/capacity | Generic HA sensors, including separate charge/discharge sensors | Aggregated Modbus input values; power sign normalized to positive charging |
| Battery `auto` | Inverter's own mode, e.g. Solax Self Use or Solis remote-control release | Default mode, only after the user confirms its release behavior on this firmware |
| Battery `charge` / `discharge` | HA select modes plus power number entities; Solax may need several selects; Growatt an apply button | Signed kW reference, activate power mode, verify mode/reference |
| Battery `hold` | Fronius Block Discharging, HomeWizard charge-only strategy | Unsupported: solar charging without discharge has no verified equivalent here |
| Battery `idle` | Explicit stop/standby where provided by an HA integration | Unsupported: an exact zero reference is not assumed to stay in power mode |
| Solar/export control | SolarEdge percentage, Huawei service, Growatt percentage, Sungrow watts plus enable switch, Fronius register writes through HA | System export boundary in watts, explicit apply, readback |
| Keepalive/release | Solis remote commands are refreshed; battery auto requested at startup/shutdown | No documented lease is assumed. Startup/shutdown release uses the existing battery lifecycle; abrupt process loss is not covered by that lifecycle |
| Fuse/peak protection | House engine uses the configured meter and phase currents | Same engine; forced battery discharge also rechecks device SOC and caps requested power |
| EV/heat pump/spa | Separate HA/local drivers coordinated by the house engine | Those drivers remain in charge; this addition does not configure EnergyHub OCPP or control other loads through it |
| Grid import and metering | HA-connected meter, e.g. Tibber Pulse/P1 | Keep the existing meter. No new direct meter driver, import-limit writer or ACE/phase-balancing control is added |

The reference operational flow prefers Modbus for forced power and export boundaries,
uses MQTT telemetry and has an MQTT command fallback. This implementation instead reads
telemetry directly over Modbus and reports a failed Modbus operation without silently
switching protocols. Command acceptance is not proof that the requested power is physically
delivered: battery limits, temperature and other system controllers can constrain it.

## Wire mapping and limitations

Addresses below are zero-based. Floats occupy two registers, low word first.

| Purpose | Holding register writes | Input register readback |
| --- | --- | --- |
| Battery power | 6064: negative kW charge, positive discharge; then 6000 = 1 | 6104: mode; 6106: reference |
| Release battery | 6000 = 0 | 6104 = 0 |
| Battery telemetry | None | 6016: SOC; 6008: rated kWh; 6100: output power |
| Export boundary | 8010: enable; 8012: W threshold; 8016 = 1: apply | 8010/8012: accepted system boundary |
| PV telemetry | None | 5100: output kW; 2000: inverter status |

RevD calls battery mode 0 "Default" but its adjacent instructions also describe it as
disabling charge/discharge. Therefore `default_mode_verified: true` is required before
any battery writes; confirm release behavior on the actual firmware first. Near-zero
discharge is not presented as a true hold/idle mode. Unknown or unavailable SOC blocks
forced power, but does not block release. Failed activation/readback attempts release.
No automatic write retry is made after a transport exception.

EnergyHub battery/PV power is DC-side; battery output is negated for EnergyWizard.
It must not be used as grid-import power. DC measurements also differ from AC throughput
when evaluating learned battery efficiency. The cumulative PV energy register is not
reported as today's energy. Configure usable battery capacity for planning separately.

Export control limits total system grid export, including battery export; it is not a
PV-generation throttle. `0` means a zero-export boundary; `100` disables that boundary.
Intermediate percentages require `max_export_w`. Only accepted system values are returned.
Do not use this dynamic boundary as a replacement for an installer's permanent safety limits.
No import boundary, SOC configuration or phase-balancing register is changed.

## Configuration

Example: read telemetry first. Replace the documentation address; obtain the correct unit
ID and register-map compatibility for the installation. Keep one EMS responsible for writes.

```yaml
battery:
  enabled: true
  driver: ferroamp_modbus
  control: samarbete           # read only; change to styr only after commissioning
  default_mode_verified: false # true only after verifying default-mode release
  capacity_kwh: 10             # usable planning capacity, set for the actual battery
  reserve_soc: 20              # also configure suitable native inverter/BMS protection
  max_soc: 100
  max_power_w: 3000
  cycle_cost: 0.30             # tune to the battery; this branch does not change it
  modbus:
    host: 192.0.2.10
    port: 502
    unit_id: 1
    timeout_s: 3
    verify_timeout_s: 2

solar:
  enabled: true
  driver: ferroamp_modbus
  control_enabled: false      # separate opt-in for grid-export writes
  max_export_w: 7000          # scaling for 1–99%; 0/100 do not need this value
  modbus:
    host: 192.0.2.10
    port: 502
    unit_id: 1
```

Battery cooperation/off modes block driver writes. Solar export has its own opt-in.
Shadow mode records commands without opening a connection for writes. Modbus is a local,
unauthenticated protocol: limit network access to the intended controller. There is no
assumed hardware watchdog; forced settings can persist if the process or host fails.
`hold`/`idle` requests use the existing controller's fallback to `auto`; native SOC
protection remains necessary. No entity-picker preset is installed automatically.

## Verification and sources

Mocked tests cover signed values, word order, write ordering, readback failures, SOC/power
limits, opt-in behavior, shadow mode, transport failures and registry wiring. They do not
establish firmware compatibility, watchdog behavior, physical power or hardware timing.

- [EnergyWizard inverter guide](https://murre87.github.io/energywizard/kunskapsbank/vaxelriktare.html)
- [Ferroamp APIs](https://ferroamp.com/kundservice/api/)
- [Ferroamp Modbus specification, current support attachment](https://support.ferroamp.com/helpdesk/attachments/47307478898)
- [Ferroamp firmware release notes](https://ferroamp.com/en/kundservice/uppdateringar/)
- [Ferroamp MQTT specification](https://ferroamp.com/wp-content/uploads/2023/04/Ferroamp-External-API-specification-E-1.pdf)
