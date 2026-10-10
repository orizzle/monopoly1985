#!/bin/bash
# e2e_session.sh NAME "ascii:scan:peeks ..."
# Runs the ORIGINAL programs (../../original) in DOSBox with the KEYFEED.COM key feeder and the port
# headless in node with the same key script, snapshots the screen state at every key and compares.
# A key becomes available after exactly <peeks> "no key" keyboard polls; a blocking read gets it at once.
# Needs dosbox and node. Work files go to $E2E_OUT (default /tmp/monopoly-e2e).
set -e
HERE=$(cd "$(dirname "$0")" && pwd); WEB=$(dirname "$HERE"); REPO=$(dirname "$WEB")
NAME=$1; shift
OUT=${E2E_OUT:-${TMPDIR:-/tmp}/monopoly-e2e}/$NAME
rm -rf "$OUT"; mkdir -p "$OUT/dos" "$OUT/pa" "$OUT/pb" "$OUT/run"
python3 -I - "$OUT" "$*" <<'P'
import json, struct, sys
out, spec = sys.argv[1], sys.argv[2]
keys = [[int(x, 0) for x in s.split(':')] + [1] for s in spec.split()]
json.dump(keys, open(out + '/script.json', 'w'))
r = b''.join(bytes([1]) + struct.pack('<H', n) + bytes([a, s, f]) for a, s, n, f in keys)
open(out + '/run/KEYS.BIN', 'wb').write(r + bytes([0]))
P
cp "$REPO"/original/* "$OUT/run/"; cp "$HERE/dos/KEYFEED.COM" "$OUT/run/"
printf '[sdl]\noutput=surface\n[dosbox]\nmachine=cga\nmemsize=4\n[cpu]\ncycles=max\n[mixer]\nnosound=true\n[speaker]\npcspeaker=false\n' > "$OUT/run/dbx.conf"
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy timeout "${TMO:-90}" dosbox -conf "$OUT/run/dbx.conf" \
  -c "mount c $OUT/run" -c "c:" -c "KEYFEED.COM" -c "MONOPOLY.COM" -c "exit" >/dev/null 2>&1 || true
mv "$OUT"/run/D*.BIN "$OUT/dos/" 2>/dev/null || true
cd "$WEB" && node test/e2e_port.mjs "$OUT/script.json" "$OUT/pa" 0 && node test/e2e_port.mjs "$OUT/script.json" "$OUT/pb" 1
python3 -I "$HERE/compare_e2e.py" "$OUT/dos" "$OUT/pa" "$OUT/pb"
