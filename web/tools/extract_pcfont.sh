#!/bin/bash
# Writes web/pcfont.bin: the 8x8 PC character set taken from the BIOS of your own DOSBox
# (run tools/PCFONT.COM in it). The port uses pcfont.bin automatically when it exists, giving
# the exact original text glyphs. Needs dosbox (headless is fine).
#   usage: tools/extract_pcfont.sh            (from the web/ directory)
set -e
WEB=$(cd "$(dirname "$0")/.." && pwd)
TMP=$(mktemp -d)
cp "$WEB/tools/PCFONT.COM" "$TMP/"
printf '[sdl]\noutput=surface\n[dosbox]\nmachine=cga\n[mixer]\nnosound=true\n' > "$TMP/dosbox.conf"
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy timeout 60 dosbox -conf "$TMP/dosbox.conf" \
  -c "mount c $TMP" -c "c:" -c "PCFONT.COM" -c "exit" >/dev/null 2>&1 || true
if [ "$(stat -c %s "$TMP/PCFONT.BIN" 2>/dev/null)" = 2048 ]; then
  cp "$TMP/PCFONT.BIN" "$WEB/pcfont.bin"; echo "wrote $WEB/pcfont.bin"
else
  echo "failed: DOSBox did not produce PCFONT.BIN" >&2; exit 1
fi
rm -rf "$TMP"
