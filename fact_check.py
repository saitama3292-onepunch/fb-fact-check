#!/usr/bin/env python3
"""FB 影片事實查核工具 — 本地 Whisper 轉錄，無需 API Key"""
import sys, os, tempfile, subprocess, json


def download_audio(url: str) -> str:
    """用 yt-dlp 下載影片音訊。"""
    out = os.path.join(tempfile.gettempdir(), "fb_audio")
    subprocess.run(
        ["yt-dlp", "-x", "--audio-format", "mp3",
         "-o", out + ".%(ext)s", "--force-overwrites", url],
        check=True, capture_output=True,
    )
    for ext in ("mp3", "m4a", "wav", "webm", "opus"):
        p = f"{out}.{ext}"
        if os.path.exists(p):
            return p
    raise FileNotFoundError("下載失敗，找不到音訊檔")


def transcribe(path: str, model_name: str = "small") -> str:
    """用本地 Whisper 模型轉錄音訊。"""
    import whisper
    model = whisper.load_model(model_name)
    result = model.transcribe(path)
    return result["text"]


def main():
    if len(sys.argv) < 2:
        print("用法：python3 fact_check.py <影片網址> [whisper模型]")
        print("模型選項：tiny, base, small (預設), medium, large")
        sys.exit(1)

    url = sys.argv[1]
    model_name = sys.argv[2] if len(sys.argv) > 2 else "small"

    print("📥 下載影片音訊...")
    audio = download_audio(url)
    print(f"  ✓ 下載完成：{audio}")

    print(f"🎙️ 語音轉文字（Whisper {model_name}）...")
    transcript = transcribe(audio, model_name)
    print(f"  ✓ 轉錄完成（{len(transcript)} 字）")

    print("\n📝 逐字稿：")
    print(transcript)

    out = {"url": url, "model": model_name, "transcript": transcript}
    out_path = os.path.join(tempfile.gettempdir(), "fact_check_result.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n結果已存至 {out_path}")


if __name__ == "__main__":
    main()
