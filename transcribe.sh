#!/bin/bash
# Video speech-to-text (with timestamp output)
set -e

URL="$1"
MODEL="${2:-small}"
WORKDIR="/tmp/transcribe_$$"
mkdir -p "$WORKDIR"

echo "⬇️  Downloading..."
yt-dlp -x --audio-format wav --audio-quality 0 \
  -o "$WORKDIR/audio.%(ext)s" "$URL" 2>&1 | tail -3

AUDIO="$WORKDIR/audio.wav"
[ ! -f "$AUDIO" ] && echo "❌ Download failed" && exit 1

echo "🎙️  Whisper transcribing (model: $MODEL)..."
whisper "$AUDIO" --model "$MODEL" --output_dir "$WORKDIR" 2>&1 | grep -v "^$"

echo ""
echo "===== Transcript ====="
cat "$WORKDIR/audio.txt" 2>/dev/null
echo ""
echo "📁 Full output (with timestamps): $WORKDIR/"
ls "$WORKDIR"/audio.* 2>/dev/null
