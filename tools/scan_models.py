import os
import json
import re

# ================= 配置 =================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "static", "models")

EMOTION_MAP = {
    "开心": "happy", "高兴": "happy", "兴奋": "happy", "笑": "happy",
    "难过": "sad", "悲伤": "sad", "哭泣": "sad", "遗憾": "sad", "痛苦": "sad",
    "生气": "angry", "愤怒": "angry", "严肃": "angry",
    "恐惧": "fear", "害怕": "fear",
    "吃惊": "surprised", "惊讶": "surprised",
    "中立": "neutral", "默认": "neutral", "平静": "neutral", "普通": "neutral",
}

def get_english_emotion_key(chinese_key: str) -> str:
    for key, value in EMOTION_MAP.items():
        if key in chinese_key:
            return value
    return "neutral"


def scan_single_model(model_id: str, model_path: str) -> dict:
    print(f"[SCAN] 正在扫描角色: {model_id} ...")
    metadata = {
        "id": model_id,
        "name": model_id,
        "gpt_filename": "",
        "sovits_filename": "",
        "default_emotion": "neutral",
        "emotions": {},
        "available_emotions": [],
    }

    for root, _, files in os.walk(model_path):
        for file in files:
            full_path = os.path.join(root, file)
            if file.endswith(".ckpt"):
                rel_path = os.path.relpath(full_path, model_path).replace("\\", "/")
                metadata["gpt_filename"] = rel_path
                continue
            if file.endswith(".pth"):
                rel_path = os.path.relpath(full_path, model_path).replace("\\", "/")
                metadata["sovits_filename"] = rel_path
                continue
            if file.lower().endswith(".wav"):
                match = re.search(r"【(.*?)】", file)
                emotion_cn = "默认"
                text = file.replace(".wav", "")
                if match:
                    emotion_cn = match.group(1)
                    text = file.replace(match.group(0), "").replace(".wav", "").strip()
                emotion_key = get_english_emotion_key(emotion_cn)
                audio_rel_path = os.path.relpath(full_path, model_path).replace("\\", "/")
                metadata["emotions"][emotion_key] = {
                    "file": audio_rel_path,
                    "text": text,
                    "lang": "zh",
                }

    if "neutral" not in metadata["emotions"] and metadata["emotions"]:
        first_key = list(metadata["emotions"].keys())[0]
        metadata["emotions"]["neutral"] = metadata["emotions"][first_key]
        print(f"[WARN] 角色 {model_id} 没有中立音频，已使用 [{first_key}] 作为默认中立音频。")

    metadata["available_emotions"] = list(metadata["emotions"].keys())

    json_path = os.path.join(model_path, "metadata.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)

    print(f"[OK] 生成配置成功：{json_path}")
    print(f"     模型: {metadata['gpt_filename']} / {metadata['sovits_filename']}")
    print(f"     情绪: {metadata['available_emotions']}")
    return metadata


def main():
    if not os.path.exists(MODELS_DIR):
        print(f"[ERROR] 找不到模型目录: {MODELS_DIR}")
        return

    manifest = []
    for item in os.listdir(MODELS_DIR):
        item_path = os.path.join(MODELS_DIR, item)
        if os.path.isdir(item_path):
            meta = scan_single_model(item, item_path)
            if meta:
                manifest.append(meta)

    manifest_path = os.path.join(MODELS_DIR, "manifest.json")
    try:
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=4, ensure_ascii=False)
        print(f"[OK] 已生成汇总清单: {manifest_path}")
    except Exception as e:
        print(f"[ERROR] 写入 manifest.json 失败: {e}")


if __name__ == "__main__":
    main()
