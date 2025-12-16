import logging
import requests

import config


class TTSClient:
    def __init__(self, api_url: str | None = None):
        self.api_url = (api_url or config.TTS_API_URL).rstrip("/")
        # 记录当前加载的模型路径，避免重复切换
        self.current_gpt_path: str | None = None
        self.current_sovits_path: str | None = None

    def switch_model(self, gpt_path: str | None, sovits_path: str | None) -> None:
        """
        切换 GPT-SoVITS 的模型。
        注意：api_v2.py 中 set_gpt_weights / set_sovits_weights 都是 GET。
        """
        # 切 GPT
        if gpt_path and gpt_path != self.current_gpt_path:
            try:
                logging.info(f"正在切换 GPT 模型: {gpt_path}")
                resp = requests.get(
                    f"{self.api_url}/set_gpt_weights",
                    params={"weights_path": gpt_path},
                    timeout=30,
                )
                resp.raise_for_status()
                self.current_gpt_path = gpt_path
            except Exception as e:  # noqa: BLE001
                logging.error(f"切换 GPT 模型失败: {e}")

        # 切 SoVITS
        if sovits_path and sovits_path != self.current_sovits_path:
            try:
                logging.info(f"正在切换 SoVITS 模型: {sovits_path}")
                resp = requests.get(
                    f"{self.api_url}/set_sovits_weights",
                    params={"weights_path": sovits_path},
                    timeout=30,
                )
                resp.raise_for_status()
                self.current_sovits_path = sovits_path
            except Exception as e:  # noqa: BLE001
                logging.error(f"切换 SoVITS 模型失败: {e}")

    def speak(self, text: str, character_id: str = "robin", emotion: str = "neutral"):
        """
        发送 TTS 请求 (POST)。返回 bytes，若失败返回 None。
        """
        preset = config.CHARACTER_PRESETS.get(character_id)
        if not preset:
            logging.warning(f"角色 {character_id} 未找到")
            return None

        # 切换模型
        gpt_path = preset.get("gpt_path")
        sovits_path = preset.get("sovits_path")
        if gpt_path or sovits_path:
            self.switch_model(gpt_path, sovits_path)

        # 情绪兜底
        emotions = preset.get("emotions", {})
        selected_emotion = emotions.get(emotion)
        if not selected_emotion:
            default_key = preset.get("default_emotion", "neutral")
            logging.info(f"情绪 [{emotion}] 未找到，回退 [{default_key}]")
            selected_emotion = emotions.get(default_key)
        if not selected_emotion and emotions:
            first_key = next(iter(emotions))
            logging.warning(f"无默认情绪可用，使用首个 {first_key}")
            selected_emotion = emotions[first_key]
        if not selected_emotion:
            logging.error(f"角色 {character_id} 没有任何可用情绪音频")
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
            logging.error(
                "TTS 生成失败: %s - %s", response.status_code, response.text
            )
            return None
        except Exception as e:  # noqa: BLE001
            logging.error(f"TTS 请求异常: {e}")
            return None


tts_client = TTSClient()
