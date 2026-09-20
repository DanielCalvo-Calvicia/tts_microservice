"""Runs pyttsx3 in an isolated process: the only module that knows how pyttsx3 is driven.

Spawning a fresh interpreter for each synthesis keeps SAPI5/COM out of the service's threads,
which avoids STA/MTA apartment conflicts and event-loop hangs on Windows.
"""

import asyncio
import sys

from shared_logging import get_logger

from application.errors import SynthesisFailed

logger = get_logger(__name__)


class Pyttsx3Subprocess:
    def __init__(self, speech_rate: int, voice_name_preference: str) -> None:
        self._speech_rate = speech_rate
        self._voice_name_preference = voice_name_preference

    async def synthesize_to_file(self, text: str, file_path: str) -> None:
        """Speak ``text`` into the WAV file at ``file_path``. Raises SynthesisFailed."""
        script = self._script(text, file_path)
        logger.info(
            "TTS subprocess starting",
            text_length=len(text),
            file_path=file_path,
            speech_rate=self._speech_rate,
            voice=self._voice_name_preference,
        )
        logger.debug("TTS subprocess script", script=script)
        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
        except OSError as error:
            raise SynthesisFailed(f"Could not start the TTS subprocess: {error}") from error

        stdout_text = stdout.decode("utf-8", errors="ignore")
        stderr_text = stderr.decode("utf-8", errors="ignore")
        logger.info(
            "TTS subprocess finished",
            pid=process.pid,
            returncode=process.returncode,
            stdout_length=len(stdout_text),
            stderr_length=len(stderr_text),
        )
        if stdout_text:
            logger.debug("TTS subprocess stdout", stdout_text=stdout_text)
        if process.returncode != 0:
            raise SynthesisFailed(f"TTS Subprocess synthesis failed: {stderr_text}")

    async def is_working(self) -> bool:
        """True if pyttsx3 can be initialised in a fresh process."""
        script = "import pyttsx3; engine = pyttsx3.init(); del engine"
        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
        except OSError:
            logger.exception("TTS availability probe could not start")
            return False
        logger.info("TTS availability probe", returncode=process.returncode)
        return process.returncode == 0

    def _script(self, text: str, file_path: str) -> str:
        return (
            "import pyttsx3\n"
            "engine = pyttsx3.init()\n"
            f"engine.setProperty('rate', {self._speech_rate})\n"
            "voices = engine.getProperty('voices')\n"
            "selected_voice = None\n"
            "for voice in voices:\n"
            # Prefer the configured voice; otherwise the first English one.
            f"    if {self._voice_name_preference!r} in voice.name or 'en' in voice.id:\n"
            "        selected_voice = voice.id\n"
            "        break\n"
            "if selected_voice:\n"
            "    engine.setProperty('voice', selected_voice)\n"
            f"engine.save_to_file({text!r}, {file_path!r})\n"
            "engine.runAndWait()\n"
        )
