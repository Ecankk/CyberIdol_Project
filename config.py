import json
import os
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / "static" / "models"
TMP_DIR = BASE_DIR / "tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)

TTS_API_URL = os.getenv("TTS_API_URL", "http://127.0.0.1:9880")
FISH_TTS_URL = os.getenv("FISH_TTS_URL", "https://api.fish.audio/v1/tts")


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
        sovits_path = (
            str((role_dir / sovits_filename).resolve()) if sovits_filename else ""
        )

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
            "preview": meta.get("preview", ""),
            "live2d": meta.get("live2d", ""),
            "live2d_config": meta.get("live2d_config", {}),
            "motions": meta.get("motions", {}),
            "expressions": meta.get("expressions", {}),
            "emotion_to_expression": meta.get("emotion_to_expression", {}),
            "fish_reference_id": meta.get("fish_reference_id", ""),
            "fish_model": meta.get("fish_model", ""),
            "gpt_path": gpt_path,
            "sovits_path": sovits_path,
            "default_emotion": meta.get("default_emotion", "neutral"),
            "emotions": abs_emotions,
            "available_emotions": meta.get(
                "available_emotions", list(abs_emotions.keys())
            ),
        }
    return presets


class Settings:
    """Simple settings container loaded from .env / environment variables."""

    def __init__(self) -> None:
        self.openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
        self.whisper_model: str = os.getenv("WHISPER_MODEL", "whisper-1")

        self.ffmpeg_path: str = os.getenv("FFMPEG_PATH", "ffmpeg")
        self.sample_rate: int = int(os.getenv("AUDIO_SAMPLE_RATE", "16000"))
        self.tmp_dir: Path = TMP_DIR

        self.baidu_app_id: str = os.getenv("BAIDU_APP_ID", "")
        self.baidu_api_key: str = os.getenv("BAIDU_API_KEY", "")
        self.baidu_secret_key: str = os.getenv("BAIDU_SECRET_KEY", "")
        self.baidu_asr_url: str = os.getenv(
            "BAIDU_ASR_URL", "https://vop.baidu.com/server_api"
        )
        self.baidu_dev_pid: int = int(os.getenv("BAIDU_DEV_PID", "1537"))
        self.asr_provider: str = os.getenv("ASR_PROVIDER", "baidu").lower()

        self.llm_provider: str = os.getenv("LLM_PROVIDER", "deepseek").lower()
        self.llm_api_key: str = os.getenv("LLM_API_KEY", "")
        self.llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
        self.llm_model: str = os.getenv("LLM_MODEL", "deepseek-chat")

        self.character_presets = CHARACTER_PRESETS

        self.tts_provider: str = os.getenv("TTS_PROVIDER", "gptsovits").lower()
        self.tts_api_url: str = TTS_API_URL
        self.fish_api_key: str = os.getenv("FISH_API_KEY", "")
        self.fish_tts_url: str = FISH_TTS_URL
        self.fish_model: str = os.getenv("FISH_MODEL", "s2-pro")
        self.fish_reference_id: str = os.getenv("FISH_REFERENCE_ID", "")
        self.fish_format: str = os.getenv("FISH_FORMAT", "wav").lower()
        self.fish_sample_rate: int = int(os.getenv("FISH_SAMPLE_RATE", "44100"))
        self.fish_latency: str = os.getenv("FISH_LATENCY", "normal")

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
        if self.asr_provider not in {"mock", "baidu", "openai"}:
            raise RuntimeError(f"不支持的 ASR_PROVIDER: {self.asr_provider}")

        if self.llm_provider == "deepseek" and not self.llm_api_key:
            raise RuntimeError("未设置 LLM_API_KEY（DeepSeek）。")
        if self.llm_provider not in {"mock", "deepseek"}:
            raise RuntimeError(f"不支持的 LLM_PROVIDER: {self.llm_provider}")

        if self.tts_provider in {"fish", "fishaudio", "fish-audio"}:
            if not self.fish_api_key:
                raise RuntimeError("未设置 FISH_API_KEY。")
        elif self.tts_provider not in {"mock", "gptsovits"}:
            raise RuntimeError(f"不支持的 TTS_PROVIDER: {self.tts_provider}")


def get_settings() -> "Settings":
    return Settings()


CHARACTER_PRESETS = load_character_presets()
