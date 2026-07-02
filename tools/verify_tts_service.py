import argparse
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = BASE_DIR / "static" / "tmp"
sys.path.insert(0, str(BASE_DIR))

from services.tts_service import TTSClient  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify services.tts_service without starting the FastAPI app."
    )
    parser.add_argument("--text", default="你好，这是 Fish Audio 语音合成测试。")
    parser.add_argument("--emotion", default="happy")
    parser.add_argument("--character-id", default="robin")
    parser.add_argument("--provider", default="fish")
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--reference-id", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--format", default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the Fish Audio request payload without sending the request.",
    )
    return parser.parse_args()


def main() -> int:
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    args = parse_args()

    client = TTSClient(
        provider=args.provider,
        fish_api_key=args.api_key,
        fish_reference_id=args.reference_id,
        fish_model=args.model,
        fish_format=args.format,
    )

    if client.provider in {"fish", "fishaudio", "fish-audio"}:
        payload = client.build_fish_payload(
            args.text,
            character_id=args.character_id,
            emotion=args.emotion,
        )
        print("Fish Audio request preview:")
        print(
            json.dumps(
                {
                    "url": client.fish_tts_url,
                    "model_header": client._fish_model_for_character(
                        args.character_id
                    ),
                    "payload": payload,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        if args.dry_run:
            return 0

        if not client.fish_api_key:
            print("Missing FISH_API_KEY. Set it in .env or pass --api-key.")
            return 2
        if "reference_id" not in payload:
            print(
                "Missing FISH_REFERENCE_ID. Set it in .env or pass --reference-id."
            )
            return 2

    audio = client.speak(
        args.text,
        character_id=args.character_id,
        emotion=args.emotion,
    )
    if not audio:
        print("TTS verification failed: no audio bytes returned.")
        return 1

    output_path = Path(args.output) if args.output else None
    if output_path is None:
        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = DEFAULT_OUTPUT_DIR / f"tts_service_test.{client.fish_format}"
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_bytes(audio)
    print(f"TTS verification passed: wrote {len(audio)} bytes to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
