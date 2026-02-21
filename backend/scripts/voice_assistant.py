import logging
# Load env before importing snapdish (which uses OPENAI_API_KEY)
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
"""
Real-time voice assistant for Chef Marco (SnapDish).

Run from repo root:
  python -m backend.scripts.voice_assistant

Or from backend directory:
  python scripts/voice_assistant.py

Requires: OPENAI_API_KEY in env (or .env). Optional: SNAPDISH_MODEL.
Press Enter to start recording, then Enter again to send. Type 'esc' to exit.
"""

from __future__ import annotations

import asyncio
import os
import sys

# Ensure backend is on path when run as script
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_SCRIPT_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# Load env before importing snapdish (which uses OPENAI_API_KEY)
from dotenv import load_dotenv
load_dotenv()

if not os.environ.get("OPENAI_API_KEY"):
    sys.exit("Missing OPENAI_API_KEY. Set it in .env or the environment.")

import numpy as np
import sounddevice as sd

from snapdish.voice_agent import (
    build_chef_marco_voice_agent,
    get_voice_pipeline_config,
)


# Default sample rate for TTS output (OpenAI voice often uses 24kHz)
OUTPUT_SAMPLERATE = 24000


async def run_voice_assistant() -> None:
    agent = build_chef_marco_voice_agent()
    config = get_voice_pipeline_config()

    from agents.voice import (
        AudioInput,
        SingleAgentVoiceWorkflow,
        VoicePipeline,
    )

    pipeline = VoicePipeline(
        workflow=SingleAgentVoiceWorkflow(agent),
        config=config,
    )

    # Use default input device sample rate for recording
    try:
        dev = sd.query_devices(kind="input")
        samplerate = int(dev.get("default_samplerate", OUTPUT_SAMPLERATE))
    except Exception:
        samplerate = OUTPUT_SAMPLERATE

    logging.info("Chef Marco voice assistant — real-time voice with SnapDish")
    logging.info("Press Enter to start recording, then Enter again to send. Type 'esc' to exit.\n")

    while True:
        cmd = input("Press Enter to speak (or type 'esc' to exit): ").strip()
        if cmd.lower() == "esc":
            logging.info("Exiting.")
            break

        logging.info("Listening... (press Enter when done speaking)")
        recorded_chunks: list[np.ndarray] = []

        def callback(indata, frames, time, status):
            if status:
                logging.warning(f"Audio status: {status}")
            recorded_chunks.append(indata.copy())

        with sd.InputStream(
            samplerate=samplerate,
            channels=1,
            dtype="int16",
            callback=callback,
        ):
            input()

        if not recorded_chunks:
            logging.warning("No audio recorded. Try again.")
            continue

        recording = np.concatenate(recorded_chunks, axis=0)
        audio_input = AudioInput(buffer=recording)

        logging.info("Chef Marco is thinking...")
        try:
            result = await pipeline.run(audio_input)
        except Exception as e:
            logging.error(f"Error running pipeline: {e}")
            continue

        response_chunks: list[np.ndarray] = []
        async for event in result.stream():
            if getattr(event, "type", None) == "voice_stream_event_audio":
                response_chunks.append(event.data)

        if not response_chunks:
            logging.warning("No audio response.")
            continue

        response_audio = np.concatenate(response_chunks, axis=0)
        logging.info("Assistant is responding...")
        sd.play(response_audio, samplerate=OUTPUT_SAMPLERATE)
        sd.wait()
        logging.info("---\n")


def main() -> None:
    asyncio.run(run_voice_assistant())


if __name__ == "__main__":
    main()
