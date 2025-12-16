import json
import os
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv

load_dotenv()

# 基础路径
BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / "static" / "models"
TMP_DIR = BASE_DIR / "tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)

# TTS 接口地址
TTS_API_URL = "http://127.0.0.1:9880"


def load_character_presets() -> Dict[str, Dict[str, Any]]:
    presets: Dict[str, Dict[str, Any]] = {}
    if not MODELS_DIR.exists():
        return presets

    for role_dir in MODELS_DIR.iterdir():
        if not role_dir.is_dir():
            continue
        meta_path = role_dir / "metadata.json"
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        role_id = meta.get("id") or role_dir.name
        gpt_filename = meta.get("gpt_filename") or meta.get("gpt_path", "")
        sovits_filename = meta.get("sovits_filename") or meta.get("sovits_path", "")

        gpt_path = str((role_dir / gpt_filename).resolve()) if gpt_filename else ""
        sovits_path = str((role_dir / sovits_filename).resolve()) if sovits_filename else ""

        emotions = meta.get("emotions") or {}
        abs_emotions: Dict[str, Dict[str, Any]] = {}
        for emo_key, emo_val in emotions.items():
            file_rel = emo_val.get("file", "") or emo_val.get("ref_audio_path", "")
            ref_audio_path = str((role_dir / file_rel).resolve()) if file_rel else ""
            abs_emotions[emo_key] = {
                "ref_audio_path": ref_audio_path,
                "ref_text": emo_val.get("text", "") or emo_val.get("ref_text", ""),
                "lang": emo_val.get("lang", "zh"),
            }

        presets[role_id] = {
            "id": role_id,
            "name": meta.get("name", role_id),
            "gpt_path": gpt_path,
            "sovits_path": sovits_path,
            "default_emotion": meta.get("default_emotion", "neutral"),
            "emotions": abs_emotions,
            "available_emotions": meta.get("available_emotions", list(abs_emotions.keys())),
        }
    return presets


class Settings:
    """简单的配置容器；值来自 .env / 环境变量。"""

    def __init__(self) -> None:
        # Whisper（保留兼容）
        self.openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
        self.whisper_model: str = os.getenv("WHISPER_MODEL", "whisper-1")

        # 通用音频与路径
        self.ffmpeg_path: str = os.getenv("FFMPEG_PATH", "ffmpeg")
        self.sample_rate: int = int(os.getenv("AUDIO_SAMPLE_RATE", "16000"))
        self.tmp_dir: Path = TMP_DIR

        # 百度语音识别配置
        self.baidu_app_id: str = os.getenv("BAIDU_APP_ID", "")
        self.baidu_api_key: str = os.getenv("BAIDU_API_KEY", "")
        self.baidu_secret_key: str = os.getenv("BAIDU_SECRET_KEY", "")

        # 默认使用百度 ASR，可通过环境变量切换
        self.asr_provider: str = os.getenv("ASR_PROVIDER", "baidu").lower()

        # LLM (DeepSeek) 配置
        self.llm_api_key: str = os.getenv("LLM_API_KEY", "")
        self.llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
        self.llm_model: str = os.getenv("LLM_MODEL", "deepseek-chat")

        # 音色预设
        self.character_presets = CHARACTER_PRESETS

        # TTS API
        self.tts_api_url: str = TTS_API_URL

    def validate(self) -> None:
        has_baidu = bool(
            self.baidu_app_id and self.baidu_api_key and self.baidu_secret_key
        )
        has_openai = bool(self.openai_api_key)

        if self.asr_provider == "baidu" and not has_baidu:
            raise RuntimeError(
                "未设置百度语音识别所需的 BAIDU_APP_ID / BAIDU_API_KEY / BAIDU_SECRET_KEY。"
            )

        if self.asr_provider == "openai" and not has_openai:
            raise RuntimeError("未设置 OPENAI_API_KEY。")

        if not (has_baidu or has_openai):
            raise RuntimeError("至少提供百度或 OpenAI 的 ASR 凭据。")

        if not self.llm_api_key:
            raise RuntimeError("未设置 LLM_API_KEY（DeepSeek）。")


def get_settings() -> "Settings":
    return Settings()


# 加载音色预设
CHARACTER_PRESETS = load_character_presets()
