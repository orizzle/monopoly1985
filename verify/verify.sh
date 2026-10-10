#!/bin/bash
# verify.sh -- rebuild the original programs from src/ and compare them byte for byte with original/.
#
# Compiles src/MONOCODE.PAS (+ includes) and src/MONOPOLY.PAS with Turbo Pascal 3.02 (run headless
# under the emu2 DOS emulator), relocates the output from the 3.02 runtime onto the 1985 runtime the
# originals were built with (relocate.py: runtime call targets, code addresses +0x2F, data addresses
# -2, two version words in the header), and compares with cmp.
#
# Needs: python3 with capstone, Turbo Pascal 3.02 (TURBO.COM, TURBO.MSG, GRAPH.P, GRAPH.BIN) in
# verify/tp302 or $TP302, and emu2 (https://github.com/dmsc/emu2) in verify/emu2/emu2 or $EMU2.
set -e
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(dirname "$HERE")
TP302=${TP302:-$HERE/tp302}; export TP302 EMU2
W=$(mktemp -d)
cp "$REPO"/src/* "$TP302/GRAPH.P" "$TP302/GRAPH.BIN" "$W/"
cd "$W"
python3 -I "$HERE/tpc.py" MONOCODE.PAS game --chn --inc GRAPH.P MONOCOD1.INC MONOCOD2.INC --raw GRAPH.BIN \
  --wname monocode --timeout 500 >/dev/null
python3 -I "$HERE/tpc.py" MONOPOLY.PAS loader --code 0C72 --data 05CE --timeout 120 >/dev/null
python3 -I "$HERE/relocate.py" chn game/MONOCODE.CHN game/MONOCODE.000 MONOCODE.CHN MONOCODE.000
python3 -I "$HERE/relocate.py" com loader/MONOPOLY.COM MONOPOLY.COM
status=0
for f in MONOCODE.CHN MONOCODE.000; do
  if cmp -s "$f" "$REPO/original/$f"; then echo "$f: byte-identical"; else echo "$f: DIFFERS"; status=1; fi
done
if cmp -s MONOPOLY.COM "$REPO/original/monopoly.com"; then echo "MONOPOLY.COM: byte-identical"; else echo "MONOPOLY.COM: DIFFERS"; status=1; fi
rm -rf "$W"
exit $status
