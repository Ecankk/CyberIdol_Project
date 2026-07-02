import logging
import os
from typing import Any

import requests

import config


class TTSClient:
    def __init__(
        self,
        *,
        provider: str | None = None,
        api_url: str | None = None,
        fish_api_key: str | None = None,
        fish_tts_url: str | None = None,
        fish_model: str | None = None,
        fish_reference_id: str | None = None,
        fish_format: str | None = None,
        fish_sample_rate: int | None = None,
        fish_latency: str | None = None,
    ) -> None:
        self.provider = (provider or os.getenv("TTS_PROVIDER", "gptsovits")).lower()

        # GPT-SoVITS settings.
        self.api_url = (api_url or config.TTS_API_URL).rstrip("/")
        self.current_gpt_path: str | None = None
        self.current_sovits_path: str | None = None

        # Fish Audio settings. See https://docs.fish.audio/api-reference/introduction
        self.fish_api_key = fish_api_key or os.getenv("FISH_API_KEY", "")
        self.fish_tts_url = (
            fish_tts_url
            or os.getenv("FISH_TTS_URL", "https://api.fish.audio/v1/tts")
        ).rstrip("/")
        self.fish_model = fish_model or os.getenv("FISH_MODEL", "s2-pro")
        self.fish_reference_id = fish_reference_id or os.getenv("FISH_REFERENCE_ID", "")
        self.fish_format = (fish_format or os.getenv("FISH_FORMAT", "wav")).lower()
        self.fish_sample_rate = int(
            fish_sample_rate or os.getenv("FISH_SAMPLE_RATE", "44100")
        )
        self.fish_latency = fish_latency or os.getenv("FISH_LATENCY", "normal")

    def switch_model(self, gpt_path: str | None, sovits_path: str | None) -> None:
        """
        Switch GPT-SoVITS model weights.
        api_v2.py exposes set_gpt_weights / set_sovits_weights as GET endpoints.
        """
        if gpt_path and gpt_path != self.current_gpt_path:
            try:
                logging.info("Switching GPT model: %s", gpt_path)
                resp = requests.get(
                    f"{self.api_url}/set_gpt_weights",
                    params={"weights_path": gpt_path},
                    timeout=30,
                )
                resp.raise_for_status()
                self.current_gpt_path = gpt_path
            except Exception as exc:  # noqa: BLE001
                logging.error("Failed to switch GPT model: %s", exc)

        if sovits_path and sovits_path != self.current_sovits_path:
            try:
                logging.info("Switching SoVITS model: %s", sovits_path)
                resp = requests.get(
                    f"{self.api_url}/set_sovits_weights",
                    params={"weights_path": sovits_path},
                    timeout=30,
                )
                resp.raise_for_status()
                self.current_sovits_path = sovits_path
            except Exception as exc:  # noqa: BLE001
                logging.error("Failed to switch SoVITS model: %s", exc)

    def speak(
        self,
        text: str,
        character_id: str = "robin",
        emotion: str = "neutral",
    ) -> bytes | None:
        """
        Synthesize speech and return audio bytes. Returns None on failure.
        """
        if not text:
            logging.warning("TTS text is empty")
            return None

        if self.provider in {"fish", "fishaudio", "fish-audio"}:
            return self._speak_fish_audio(text, character_id, emotion)

        return self._speak_gptsovits(text, character_id, emotion)

    def _speak_gptsovits(
        self,
        text: str,
        character_id: str,
        emotion: str,
    ) -> bytes | None:
        preset = config.CHARACTER_PRESETS.get(character_id)
        if not preset:
            logging.warning("Character %s not found", character_id)
            return None

        gpt_path = preset.get("gpt_path")
        sovits_path = preset.get("sovits_path")
        if gpt_path or sovits_path:
            self.switch_model(gpt_path, sovits_path)

        emotions = preset.get("emotions", {})
        selected_emotion = emotions.get(emotion)
        if not selected_emotion:
            default_key = preset.get("default_emotion", "neutral")
            logging.info("Emotion [%s] not found, fallback to [%s]", emotion, default_key)
            selected_emotion = emotions.get(default_key)
        if not selected_emotion and emotions:
            first_key = next(iter(emotions))
            logging.warning("No default emotion available, using %s", first_key)
            selected_emotion = emotions[first_key]
        if not selected_emotion:
            logging.error("Character %s has no available emotion audio", character_id)
            return None

        payload = {
            "text": text,
            "text_lang": "zh",
            "ref_audio_path": selected_emotion.get("ref_audio_path"),
            "prompt_text": selected_emotion.get("ref_text", ""),
            "prompt_lang": selected_emotion.get("lang", "zh"),
            "media_type": "wav",
        }

        try:
            response = requests.post(f"{self.api_url}/tts", json=payload, timeout=60)
            if response.status_code == 200:
                return response.content
            logging.error("TTS failed: %s - %s", response.status_code, response.text)
            return None
        except Exception as exc:  # noqa: BLE001
            logging.error("TTS request failed: %s", exc)
            return None

    def _speak_fish_audio(
        self,
        text: str,
        character_id: str,
        emotion: str,
    ) -> bytes | None:
        if not self.fish_api_key:
            logging.error("FISH_API_KEY is required when TTS_PROVIDER=fish")
            return None

        payload = self.build_fish_payload(text, character_id, emotion)
        if "reference_id" not in payload:
            logging.error(
                "FISH_REFERENCE_ID is required for Fish Audio single-speaker TTS"
            )
            return None

        headers = {
            "Authorization": f"Bearer {self.fish_api_key}",
            "Content-Type": "application/json",
            "Accept": f"audio/{self.fish_format}",
        }
        fish_model = self._fish_model_for_character(character_id)
        if fish_model:
            headers["model"] = fish_model

        try:
            response = requests.post(
                self.fish_tts_url,
                headers=headers,
                json=payload,
                timeout=60,
            )
            if response.status_code == 200:
                return response.content
            logging.error(
                "Fish Audio TTS failed: %s - %s",
                response.status_code,
                response.text,
            )
            return None
        except Exception as exc:  # noqa: BLE001
            logging.error("Fish Audio TTS request failed: %s", exc)
            return None

    def build_fish_payload(
        self,
        text: str,
        character_id: str = "robin",
        emotion: str = "neutral",
    ) -> dict[str, Any]:
        preset = config.CHARACTER_PRESETS.get(character_id, {})
        reference_id = preset.get("fish_reference_id") or self.fish_reference_id

        payload: dict[str, Any] = {
            "text": self._format_fish_text(text, emotion),
            "format": self.fish_format,
            "latency": self.fish_latency,
            "sample_rate": self.fish_sample_rate,
        }
        if reference_id:
            payload["reference_id"] = reference_id
        return payload

    def _fish_model_for_character(self, character_id: str) -> str:
        preset = config.CHARACTER_PRESETS.get(character_id, {})
        return preset.get("fish_model") or self.fish_model

    @staticmethod
    def _format_fish_text(text: str, emotion: str) -> str:
        if not emotion or emotion == "neutral":
            return text
        clean_text = text.strip()
        if clean_text.startswith("["):
            return clean_text
        return f"[{emotion}] {clean_text}"


tts_client = TTSClient()
