#!/bin/bash
# start_sims.sh - startar Sourcefuls enhetssimulator (srcfl/device-simulator, headless "run") med en enhet per körning,
# på var sin portbas. Skriver tests/simulator/out/devices.json: [{driver, modbus_port, unit_id, http, spec}].
# Körs i GitHub Actions (.github/workflows/simulator.yml) - aldrig på servern.
set -u
SIM=${1:?sökväg till simulatorbinären}
OUT=$(cd "$(dirname "$0")" && pwd)/out
mkdir -p "$OUT"
DEVICES="sungrow huawei solaredge fronius sma solis deye pixii"
base=18700
echo "[]" > "$OUT/devices.json"
for d in $DEVICES; do
  dir="$OUT/$d"; mkdir -p "$dir"
  cat > "$dir/house.json" <<EOF
{"name": "ew-$d", "duration_s": 0, "site": {"fuse_a": 25, "house_w": [600, 600, 600]},
 "devices": [{"id": "inv", "driver": "$d", "battery_kwh": 10, "soc_pct": 50, "min_soc_pct": 5, "pv_w": 3000}]}
EOF
  "$SIM" run -spec "$dir/house.json" -port-base "$base" -out "$dir" > "$dir/sim.log" 2>&1 &
  pid=$!
  for i in $(seq 1 40); do
    [ -f "$dir/ports.json" ] && break
    kill -0 $pid 2>/dev/null || break
    sleep 0.5
  done
  if [ -f "$dir/ports.json" ]; then
    python3 - "$OUT/devices.json" "$dir/ports.json" "$d" "$dir/house.json" <<'PY'
import json, sys
lst = json.load(open(sys.argv[1]))
p = json.load(open(sys.argv[2]))
dev = p["devices"]["inv"]
lst.append({"driver": sys.argv[3], "modbus_port": dev.get("modbus_port"), "unit_id": dev.get("unit_id") or 1,
            "http": p["http"], "spec": json.load(open(sys.argv[4]))["devices"][0]})
json.dump(lst, open(sys.argv[1], "w"), indent=1)
PY
    echo "✅ $d på portbas $base"
  else
    echo "⏭️  $d startade inte (ingen modell i simulatorn?):"; tail -3 "$dir/sim.log"
  fi
  base=$((base + 100))
done
cat "$OUT/devices.json"
