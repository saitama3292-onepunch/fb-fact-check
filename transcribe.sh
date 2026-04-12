#!/bin/bash
# Video speech-to-text using Groq Whisper API (free, fast, no local GPU)
# Requires: GROQ_API_KEY env var (get free key at https://console.groq.com/keys)
set -e

URL="$1"
MODEL="${2:-whisper-large-v3-turbo}"
WORKDIR="/tmp/transcribe_$$"
mkdir -p "$WORKDIR"

if [ -z "$GROQ_API_KEY" ]; then
  echo "❌ GROQ_API_KEY not set. Get a free key at https://console.groq.com/keys"
  exit 1
fi

echo "⬇️  Downloading..."
yt-dlp -x --audio-format mp3 --audio-quality 5 \
  -o "$WORKDIR/audio.%(ext)s" "$URL" 2>&1 | tail -3

AUDIO="$WORKDIR/audio.mp3"
[ ! -f "$AUDIO" ] && echo "❌ Download failed" && exit 1

# Compress if >24MB
FSIZE=$(stat -c%s "$AUDIO" 2>/dev/null || stat -f%z "$AUDIO")
if [ "$FSIZE" -gt 25165824 ]; then
  echo "🔧 Compressing audio (${FSIZE} bytes > 24MB limit)..."
  ffmpeg -y -i "$AUDIO" -ar 16000 -ac 1 -c:a flac "$WORKDIR/audio.flac" 2>/dev/null
  AUDIO="$WORKDIR/audio.flac"
fi

echo "🎙️  Groq Whisper transcribing (model: $MODEL)..."
RESULT=$(curl -s -X POST "https://api.groq.com/openai/v1/audio/transcriptions" \
  -H "Authorization: Bearer $GROQ_API_KEY" \
  -F "file=@$AUDIO" \
  -F "model=$MODEL" \
  -F "response_format=verbose_json")

echo ""
echo "===== Transcript ====="
echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('text',''))" 2>/dev/null || echo "$RESULT"
echo ""

# Save outputs
echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('text',''))" > "$WORKDIR/audio.txt" 2>/dev/null
echo "$RESULT" > "$WORKDIR/audio.json"
echo "📁 Full output: $WORKDIR/"
ls "$WORKDIR"/audio.* 2>/dev/null
