# Battery wear and switching protection

EnergyWizard already accounts for round-trip losses, reserve levels, discharge wear,
mode-switch cost and a five-minute command interval. This addition preserves those
defaults and adds optional charge/discharge wear and physical reversal penalties.

| Battery YAML parameter | Unit | Default |
| --- | --- | --- |
| `cycle_cost` (existing) | SEK per discharged AC kWh | 0.30 |
| `charge_wear_cost_sek_per_kwh` | Extra SEK per stored kWh added | 0 |
| `discharge_wear_cost_sek_per_kwh` | Extra SEK per stored kWh removed | 0 |
| `reversal_cost_sek` | SEK per physical direction reversal | 0 |
| `min_change_minutes` | Minutes between changed commands, minimum 5 | 5 |

`cycle_cost` keeps its existing meaning and default. Existing configured values,
including zero, remain effective. The two new wear rates are additive, not aliases
or replacements: avoid counting the same battery replacement cost twice. Derive any
extra wear rates from battery cost and expected lifetime throughput. The direct
`optimize()` API keeps its existing `cycle_cost=0.0` default; application configuration
continues to supply 0.30 when no value is configured.

The planner compares full import/export prices, efficiency losses, all wear costs
and reversal penalties. `cost`, row `cost` and `baseline_cost` continue to include
energy and wear costs. `wear_cost_sek` separately reports total plan wear, including
`cycle_cost`; `reversal_cost_sek` reports reversal penalties. Savings apply the same
wear and reversal rates to plan and self-consumption baseline. Terminal valuation,
planning styles and export restrictions retain main's behavior.

Negative-price charging and no-plan fallback retain their existing behavior, even
when optional wear rates are configured. Changing that policy is outside this PR.
Fuse/peak protection, stale-data fallback, driver refresh and cooperation mode retain
their existing precedence and behavior. Emergency transitions bypass command dwell.

Reversal penalties remember the last physical direction through idle slots and
changes within auto mode. They are economic preferences, not hard physical lockouts.
Each recalculation starts without a previous physical direction. Command dwell limits
writes, not inverter-controlled transitions in auto/hold. A hard lockout would require
measured direction and timestamps persisted across replans/restarts and a supported
neutral mode. Rates, mode mappings and actual transitions still need hardware testing.

## 36-hour runtime

Synthetic 144-quarter horizon, 10 kWh battery, 0.1 kWh energy step (101 levels), five
actions, 3 kW charge/discharge, 90% round-trip efficiency, 20% reserve, 50% initial SOC.
The profile has cheap nights, expensive evenings, midday solar and overnight EV load.
Five timed runs after warmup on Windows 11 / Python 3.13.12, Intel Family 6 Model 198:

| Version | Median | Range |
| --- | --- | --- |
| Main (`daf9e33`) | 0.0692 s | 0.0673–0.0820 s |
| Addition, new settings at defaults | 0.2442 s | 0.2300–0.2533 s |
| Addition, new costs enabled | 0.2428 s | 0.2377–0.2577 s |

Enabled costs were 0.05 SEK/stored kWh charged, 0.10 discharged and 0.50 per reversal;
all runs used `cycle_cost=0.30`. Roughly 3.5× CPU time reflects the three direction
states and their accounting. This measures the pure planner, excluding database,
forecast and driver I/O. It is not a target-device benchmark.
