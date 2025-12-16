import json
import logging
import os
import re
import subprocess
import uuid
from pathlib import Path
from typing import Iterable

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from config import get_settings
from services.asr_service import create_asr_client
from services.llm_service import DeepSeekClient, DEFAULT_SYSTEM_PROMPT
from services.tts_service import TTSClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()
app = FastAPI(title="Cyber-Idol Backend")

asr_client = create_asr_client(settings)
llm_client = DeepSeekClient(
    api_key=settings.llm_api_key,
    base_url=settings.llm_base_url,
    model=settings.llm_model,
)
tts_client = TTSClient(api_url=settings.tts_api_url)

# 全局人设与对话记忆
current_system_prompt = DEFAULT_SYSTEM_PROMPT
conversation_history: list[dict] = []

# 静态资源目录
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
STATIC_TMP_DIR = STATIC_DIR / "tmp"
STATIC_TMP_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def convert_to_wav(
    source_path: Path, target_path: Path, sample_rate: int, ffmpeg_path: str
) -> None:
    command = [
        ffmpeg_path,
        "-y",
        "-i",
        str(source_path),
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        str(target_path),
    ]
    process = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )
    if process.returncode != 0:
        raise RuntimeError(f"ffmpeg 转码失败: {process.stderr}")


def cleanup_files(paths: Iterable[Path]) -> None:
    for path in paths:
        if path.exists():
            try:
                path.unlink()
            except OSError:
                logging.warning("无法删除临时文件: %s", path)


def extract_emotion_and_text(text: str) -> tuple[str, str]:
    if not text:
        return "neutral", ""
    match = re.search(r"\[(.*?)\]", text)
    emotion = match.group(1) if match else "neutral"
    clean_text = re.sub(r"\[.*?\]", "", text).strip()
    if not clean_text:
        clean_text = "..."
    return emotion, clean_text


@app.on_event("startup")
async def validate_settings() -> None:
    settings.validate()


@app.get("/")
async def serve_index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(content=b"", media_type="image/x-icon")


@app.get("/characters")
async def list_characters() -> list[dict[str, str]]:
    return [
        {"id": cid, "name": cfg.get("name", cid)}
        for cid, cfg in settings.character_presets.items()
    ]


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket) -> None:
    await websocket.accept()
    logging.info("WebSocket 客户端已连接")

    global current_system_prompt, conversation_history

    current_character_id: str = "robin"
    if current_character_id not in settings.character_presets and settings.character_presets:
        current_character_id = list(settings.character_presets.keys())[0]

    async def handle_text_flow(transcript: str, ws: WebSocket | None = None) -> None:
        nonlocal current_character_id
        global current_system_prompt, conversation_history

        preset = settings.character_presets.get(current_character_id, {})
        history = conversation_history + [{"role": "user", "content": transcript}]

        logging.info(f"使用人设 (前20字): {current_system_prompt[:20]}...")
        try:
            raw_reply = await run_in_threadpool(
                llm_client.get_response,
                transcript,
                history,
                preset,
                current_system_prompt,
            )
        except Exception:
            logging.exception("LLM 调用失败")
            raw_reply = "[neutral] 思考出现了一点问题..."

        emotion, clean_text = extract_emotion_and_text(raw_reply)
        logging.info(f"LLM 原始: {raw_reply} | 清洗后: [{emotion}] {clean_text}")

        tts_result = await run_in_threadpool(
            tts_client.speak, clean_text, current_character_id, emotion
        )
        if not tts_result:
            logging.warning("TTS 生成失败，未发送音频")
            if ws:
                await ws.send_json({"type": "tts", "url": None, "text": clean_text, "emotion": emotion})
            return

        filename = f"audio_{uuid.uuid4().hex}.wav"
        file_path = STATIC_TMP_DIR / filename
        with file_path.open("wb") as f:
            f.write(tts_result)

        audio_url = f"/static/tmp/{filename}"
        if ws:
            await ws.send_json(
                {"type": "tts", "url": audio_url, "text": clean_text, "emotion": emotion}
            )

        conversation_history.extend(
            [
                {"role": "user", "content": transcript},
                {"role": "assistant", "content": clean_text},
            ]
        )

    try:
        while True:
            message = await websocket.receive()
            # 客户端已发送断开消息时，直接退出循环，避免 RuntimeError
            if message.get("type") == "websocket.disconnect":
                break

            if message.get("text"):
                try:
                    payload = json.loads(message["text"])
                    if isinstance(payload, dict):
                        # 切换角色
                        if payload.get("character_id"):
                            cid = str(payload["character_id"])
                            if cid in settings.character_presets:
                                current_character_id = cid
                                await websocket.send_json(
                                    {"type": "info", "message": f"角色已切换为 {current_character_id}"}
                                )
                        # 更新人设，支持直接带 system_prompt 或 type=config
                        if payload.get("system_prompt") or (
                            payload.get("type") == "config" and payload.get("system_prompt")
                        ):
                            current_system_prompt = str(payload.get("system_prompt"))
                            conversation_history.clear()
                            logging.info(f"人设全局更新: {current_system_prompt[:30]}...")
                            await websocket.send_json(
                                {"type": "info", "message": "人设已更新成功！"}
                            )
                            continue
                        # 文本对话输入
                        if payload.get("text_input"):
                            transcript = str(payload["text_input"]).strip()
                            await handle_text_flow(transcript, websocket)
                        continue
                except json.JSONDecodeError:
                    pass

            if message.get("bytes"):
                audio_bytes: bytes = message["bytes"]
                webm_path = settings.tmp_dir / f"audio_{uuid.uuid4().hex}.webm"
                wav_path = settings.tmp_dir / f"{webm_path.stem}.wav"
                try:
                    with webm_path.open("wb") as file_handle:
                        file_handle.write(audio_bytes)

                    await run_in_threadpool(
                        convert_to_wav,
                        webm_path,
                        wav_path,
                        settings.sample_rate,
                        settings.ffmpeg_path,
                    )

                    transcript = await run_in_threadpool(
                        asr_client.transcribe_audio, wav_path
                    )

                    logging.info("识别结果: %s", transcript)
                    await websocket.send_json({"type": "transcript", "text": transcript})

                    if transcript:
                        await handle_text_flow(transcript, websocket)
                except Exception as exc:
                    logging.exception("处理音频失败")
                    if "3307" not in str(exc):
                        await websocket.send_json(
                            {"type": "error", "message": "无法识别语音"}
                        )
                finally:
                    cleanup_files([webm_path, wav_path])

    except WebSocketDisconnect:
        logging.info("WebSocket 连接断开")
@app.get("/models")
async def list_models() -> list[dict]:
    """返回 models 清单；优先读取 manifest.json，不存在则用 presets 构造简表。"""
    manifest_path = STATIC_DIR / "models" / "manifest.json"
    if manifest_path.exists():
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("读取 manifest.json 失败")
    return [
        {
            "id": cid,
            "name": cfg.get("name", cid),
            "available_emotions": cfg.get("available_emotions", []),
        }
        for cid, cfg in settings.character_presets.items()
    ]
