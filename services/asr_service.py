import base64
import logging
import time
import wave
from pathlib import Path
from typing import Optional, Union

import requests
from openai import OpenAI


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes()


class WhisperASRClient:
    """OpenAI Whisper wrapper."""

    def __init__(self, api_key: str, model: str = "whisper-1") -> None:
        if not api_key:
            raise ValueError("缺少 OPENAI_API_KEY，无法进行语音识别。")
        self.model = model
        self.client = OpenAI(api_key=api_key)

    def transcribe_audio(
        self, audio_path: Union[str, Path], *, language: Optional[str] = None
    ) -> str:
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"未找到音频文件: {path}")

        logging.info("Whisper transcription: %s", path)
        try:
            with path.open("rb") as file_handle:
                response = self.client.audio.transcriptions.create(
                    model=self.model,
                    file=file_handle,
                    language=language,
                )
        except Exception as exc:
            logging.exception("Whisper transcription failed")
            raise RuntimeError("语音转写失败") from exc

        text = getattr(response, "text", None)
        if not text:
            raise RuntimeError("语音转写结果为空。")

        return text.strip()


class MockASRClient:
    """Local fallback client for startup verification."""

    def transcribe_audio(
        self, audio_path: Union[str, Path], *, language: Optional[str] = None
    ) -> str:
        del language
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"未找到音频文件: {path}")
        logging.info("Mock ASR used for %s", path)
        return "这是一段本地 mock 语音输入。"


class BaiduASRClient:
    TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"

    def __init__(
        self,
        app_id: str,
        api_key: str,
        secret_key: str,
        *,
        sample_rate: int = 16000,
        dev_pid: int = 1537,
        asr_url: str = "https://vop.baidu.com/server_api",
    ) -> None:
        if not (app_id and api_key and secret_key):
            raise ValueError("缺少百度语音识别配置。")

        self.app_id = app_id
        self.api_key = api_key
        self.secret_key = secret_key
        self.sample_rate = sample_rate
        self.dev_pid = dev_pid
        self.asr_url = asr_url

        self._access_token: Optional[str] = None
        self._token_expire_ts: float = 0.0

    def _ensure_token(self) -> str:
        if self._access_token and time.time() < self._token_expire_ts - 60:
            return self._access_token

        params = {
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.secret_key,
        }
        resp = requests.get(self.TOKEN_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        token = data.get("access_token")
        expires_in = int(data.get("expires_in", 0))
        if not token:
            raise RuntimeError(f"获取百度 Token 失败: {data}")

        self._access_token = token
        self._token_expire_ts = time.time() + expires_in
        return token

    def transcribe_audio(
        self, audio_path: Union[str, Path], *, language: Optional[str] = None
    ) -> str:
        del language
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {path}")

        pcm_data = b""
        try:
            with wave.open(str(path), "rb") as wav_file:
                if wav_file.getframerate() != self.sample_rate:
                    logging.warning(
                        "音频采样率为 %s，当前百度 ASR 配置为 %s。",
                        wav_file.getframerate(),
                        self.sample_rate,
                    )
                pcm_data = wav_file.readframes(wav_file.getnframes())
        except wave.Error:
            pcm_data = _read_bytes(path)

        if not pcm_data:
            raise RuntimeError("音频数据为空。")

        token = self._ensure_token()
        payload = {
            "format": "pcm",
            "rate": self.sample_rate,
            "dev_pid": self.dev_pid,
            "channel": 1,
            "token": token,
            "cuid": f"cyber-idol-{self.app_id}",
            "len": len(pcm_data),
            "speech": base64.b64encode(pcm_data).decode("utf-8"),
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        logging.info("Sending audio to Baidu ASR: %s (PID=%s)", self.asr_url, self.dev_pid)

        resp = requests.post(
            self.asr_url,
            json=payload,
            headers=headers,
            timeout=20,
            proxies={"http": None, "https": None},
        )
        resp.raise_for_status()
        result_json = resp.json()

        if result_json.get("err_no") != 0:
            err_no = result_json.get("err_no")
            err_msg = result_json.get("err_msg", "未知错误")
            logging.error("Baidu ASR error detail: %s", result_json)
            if err_no == 3302:
                raise RuntimeError(
                    "权限验证失败 (3302)。请检查百度云控制台是否已开通当前 endpoint 对应的识别能力。"
                )
            raise RuntimeError(f"ASR Error [{err_no}]: {err_msg}")

        if "result" in result_json and result_json["result"]:
            return str(result_json["result"][0]).strip()
        return ""


def create_asr_client(
    settings,
) -> Union[WhisperASRClient, BaiduASRClient, MockASRClient]:
    provider = settings.asr_provider
    if provider == "mock":
        return MockASRClient()
    if provider == "baidu":
        return BaiduASRClient(
            app_id=settings.baidu_app_id,
            api_key=settings.baidu_api_key,
            secret_key=settings.baidu_secret_key,
            sample_rate=settings.sample_rate,
            dev_pid=settings.baidu_dev_pid,
            asr_url=settings.baidu_asr_url,
        )
    if provider == "openai":
        return WhisperASRClient(
            api_key=settings.openai_api_key,
            model=settings.whisper_model,
        )
    raise ValueError(f"未知的 ASR_PROVIDER: {provider}")
