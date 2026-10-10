#!/bin/bash
# Writes web/pcfont.bin (8x8, 2048 bytes) and web/pcfont16.bin (VGA 8x16, 4096 bytes): the PC
# character sets taken from the BIOS of your own DOSBox (tools/PCFONT.COM, tools/PCFONT16.COM).
# The port uses these files automatically when they exist, giving the exact original text glyphs:
# pcfont16.bin for VGA text screens, pcfont.bin for CGA text screens and graphics-mode text.
# Needs dosbox (headless is fine).      usage: tools/extract_pcfont.sh   (from the web/ directory)
set -e
WEB=$(cd "$(dirname "$0")/.." && pwd)
TMP=$(mktemp -d)
cp "$WEB/tools/PCFONT.COM" "$WEB/tools/PCFONT16.COM" "$TMP/"
printf '[sdl]\noutput=surface\n[dosbox]\nmachine=vgaonly\n[mixer]\nnosound=true\n' > "$TMP/dosbox.conf"
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy timeout 60 dosbox -conf "$TMP/dosbox.conf" \
  -c "mount c $TMP" -c "c:" -c "PCFONT.COM" -c "PCFONT16.COM" -c "exit" >/dev/null 2>&1 || true
ok=0
if [ "$(stat -c %s "$TMP/PCFONT.BIN" 2>/dev/null)" = 2048 ]; then cp "$TMP/PCFONT.BIN" "$WEB/pcfont.bin"; echo "wrote $WEB/pcfont.bin"; ok=1; fi
if [ "$(stat -c %s "$TMP/PCFONT16.BIN" 2>/dev/null)" = 4096 ]; then cp "$TMP/PCFONT16.BIN" "$WEB/pcfont16.bin"; echo "wrote $WEB/pcfont16.bin"; ok=1; fi
rm -rf "$TMP"
[ $ok = 1 ] || { echo "failed: DOSBox did not produce the font files" >&2; exit 1; }
