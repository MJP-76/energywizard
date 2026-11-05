# FTW-drivrutiner

Filerna här (93 Lua-drivrutiner) kommer från [srcfl/device-drivers](https://github.com/srcfl/device-drivers)
(Copyright 2026 Sourceful Labs AB and contributors), commit `e07d27038e83` (hämtade 2026-11-05),
licensierade under GNU AGPL-3.0 som EnergyWizard. Sourceful har gett sitt OK till att EnergyWizard använder dem.

De körs **oförändrade** av `smartbox/lua_host.py` och används som EnergyWizard-drivrutiner via
`smartbox/drivers/ftw_device.py` (`driver: ftw` för batteri och solceller i house_config.yaml).

Styrning (laddning, urladdning, exportbegränsning) är avstängd för alla drivrutiner som inte finns i
`FTW_CONTROL_VERIFIED` i ftw_device.py, om inte installationen uttryckligen sätter `control_unverified: true`.
Läsning fungerar för alla.
