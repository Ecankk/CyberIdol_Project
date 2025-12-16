import base64
import json
import logging
import time
import wave
from pathlib import Path
from typing import Optional, Union

import requests
from openai import OpenAI


def _read_bytes(path: Path) -> bytes:
    """读取二进制音频数据。"""
    return path.read_bytes()

# ... WhisperASRClient 类保持不变 ...
class WhisperASRClient:
    """OpenAI Whisper 封装（保留兼容）。"""

    def __init__(self, api_key: str, model: str = "whisper-1") -> None:
        if not api_key:
            raise ValueError("缺少 OpenAI API Key，无法进行语音识别。")
        self.model = model
        self.client = OpenAI(api_key=api_key)

    def transcribe_audio(
        self, audio_path: Union[str, Path], *, language: Optional[str] = None
    ) -> str:
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"未找到音频文件: {path}")

        logging.info("Whisper 转写中: %s", path)
        try:
            with path.open("rb") as file_handle:
                response = self.client.audio.transcriptions.create(
                    model=self.model,
                    file=file_handle,
                    language=language,
                )
        except Exception as exc:
            logging.exception("Whisper 转写失败")
            raise RuntimeError("语音转写失败") from exc

        text = getattr(response, "text", None)
        if not text:
            raise RuntimeError("转写结果为空。")

        return text.strip()


class BaiduASRClient:
    """
    百度【短语音识别】HTTP 客户端。
    URL: http://vop.baidu.com/server_api
    策略: 使用 dev_pid=1537 (标准版普通话)，这是兼容性最好的模型。
    """

    TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
    ASR_URL = "http://vop.baidu.com/server_api"

    def __init__(
        self,
        app_id: str,
        api_key: str,
        secret_key: str,
        *,
        sample_rate: int = 16000,
        # 【关键修改】：改为 1537 (标准版普通话)，解决 3302 权限错误
        dev_pid: int = 1537,  
        chunk_size: int = 3200,
    ) -> None:
        if not (app_id and api_key and secret_key):
            raise ValueError("缺少百度语音识别配置")

        self.app_id = app_id
        self.api_key = api_key
        self.secret_key = secret_key
        self.sample_rate = sample_rate
        self.dev_pid = dev_pid
        self.chunk_size = chunk_size

        self._access_token: Optional[str] = None
        self._token_expire_ts: float = 0.0

    def _ensure_token(self) -> str:
        """获取 Access Token（带简单缓存）。"""
        if self._access_token and time.time() < self._token_expire_ts - 60:
            return self._access_token

        params = {
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.secret_key,
        }
        try:
            resp = requests.get(self.TOKEN_URL, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            token = data.get("access_token")
            expires_in = data.get("expires_in", 0)

            if not token:
                raise RuntimeError(f"获取 Token 失败: {data}")

            self._access_token = token
            self._token_expire_ts = time.time() + int(expires_in)
            logging.info("百度 Access Token 获取成功")
            return token
        except Exception as exc:
            logging.error("获取 Token 异常: %s", exc)
            raise

    def transcribe_audio(
        self, audio_path: Union[str, Path], *, language: Optional[str] = None
    ) -> str:
        """
        发送音频 PCM 数据到百度 HTTP 接口。
        """
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {path}")

        # 读取音频数据
        # 这里为了稳妥，我们提取 WAV 里面的 PCM 裸数据发送
        # 避免 WAV 头信息导致的格式识别错误
        pcm_data = b""
        try:
            with wave.open(str(path), "rb") as wav_file:
                # 校验采样率
                if wav_file.getframerate() != 16000:
                    logging.warning(f"警告：音频采样率为 {wav_file.getframerate()}，百度建议 16000")
                pcm_data = wav_file.readframes(wav_file.getnframes())
        except wave.Error:
            # 如果不是标准 WAV，尝试直接读取所有字节
            pcm_data = _read_bytes(path)
        
        if not pcm_data:
            raise RuntimeError("音频数据为空")

        token = self._ensure_token()
        # CUID 必须是唯一的，百度以此区分用户
        cuid = "cyber-idol-user-001" 

        payload = {
            "format": "pcm",    # 推荐使用 pcm，兼容性最好
            "rate": 16000,
            "dev_pid": self.dev_pid,
            "channel": 1,
            "token": token,
            "cuid": cuid,
            "len": len(pcm_data),
            "speech": base64.b64encode(pcm_data).decode("utf-8"),
        }

        headers = {"Content-Type": "application/json"}
        logging.info(f"发送音频至百度 (PID={self.dev_pid})...")

        try:
            resp = requests.post(self.ASR_URL, json=payload, headers=headers, timeout=15)
            # 百度可能返回 200 但内容是错误码，所以这里 raise_for_status 抓不到逻辑错误
            # 但网络错误能抓到
            resp.raise_for_status() 
            result_json = resp.json()

            # 严格检查业务错误
            if result_json.get("err_no") != 0:
                logging.error(f"百度识别报错详情: {result_json}")
                err_msg = result_json.get("err_msg", "未知错误")
                err_no = result_json.get("err_no")
                
                if err_no == 3302:
                     raise RuntimeError(f"权限验证失败 (3302)。请检查百度云控制台是否开启了'短语音识别'。")
                
                raise RuntimeError(f"ASR Error [{err_no}]: {err_msg}")

            if "result" in result_json:
                text = result_json["result"][0]
                return text.strip()
            return ""
        except Exception as exc:
            logging.exception("ASR HTTP 请求异常")
            # 简化错误信息抛出给前端
            raise RuntimeError(f"识别服务异常: {str(exc)}") from exc


def create_asr_client(settings) -> Union[WhisperASRClient, BaiduASRClient]:
    """根据配置选择 Baidu 或 OpenAI ASR。"""
    provider = settings.asr_provider
    if provider == "baidu":
        return BaiduASRClient(
            app_id=settings.baidu_app_id,
            api_key=settings.baidu_api_key,
            secret_key=settings.baidu_secret_key,
            sample_rate=settings.sample_rate,
        )
    if provider == "openai":
        return WhisperASRClient(
            api_key=settings.openai_api_key,
            model=settings.whisper_model,
        )
    raise ValueError(f"未知的 ASR_PROVIDER: {provider}")