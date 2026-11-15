#!/usr/bin/env bash
# Runs the reference engine (OpenStudio-HPXML) on its sample houses, design loads
# only (no annual simulation), and keeps the outputs the comparison needs.
#
# Needs: OpenStudio 3.11.0 on PATH and a clone of
# https://github.com/NatLabRockies/OpenStudio-HPXML (commit fb18723 was used).
#
# Usage: validation/run_reference.sh <path to OpenStudio-HPXML clone> <output dir> [jobs]
set -euo pipefail
REPO=$(realpath "$1"); OUT=$(realpath -m "$2"); JOBS=${3:-4}
mkdir -p "$OUT"
run_one() {
  f=$1; name=$(basename "$f" .xml); d="$OUT/$name"
  [ -f "$d/run/results_annual.csv" ] && return 0
  openstudio "$REPO/workflow/run_simulation.rb" -x "$f" --skip-simulation -o "$d" > "$d.log" 2>&1 || echo "FAILED $name"
  rm -f "$d/run/in.osm" "$d/run/in.epw"
}
export -f run_one; export REPO OUT
ls "$REPO"/workflow/sample_files/*.xml | xargs -P "$JOBS" -I{} bash -c 'run_one {}'
