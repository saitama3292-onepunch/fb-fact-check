#!/bin/bash
# 影片語音轉文字（含時間軸輸出）
set -e

URL="$1"
MODEL="${2:-small}"
WORKDIR="/tmp/transcribe_$$"
mkdir -p "$WORKDIR"

echo "⬇️  下載中..."
yt-dlp -x --audio-format wav --audio-quality 0 \
  -o "$WORKDIR/audio.%(ext)s" "$URL" 2>&1 | tail -3

AUDIO="$WORKDIR/audio.wav"
[ ! -f "$AUDIO" ] && echo "❌ 下載失敗" && exit 1

echo "🎙️  Whisper 辨識中 (model: $MODEL)..."
whisper "$AUDIO" --model "$MODEL" --language zh --output_dir "$WORKDIR" 2>&1 | grep -v "^$"

echo ""
echo "===== 逐字稿 ====="
cat "$WORKDIR/audio.txt" 2>/dev/null
echo ""
echo "📁 完整輸出（含時間軸）: $WORKDIR/"
ls "$WORKDIR"/audio.* 2>/dev/null
