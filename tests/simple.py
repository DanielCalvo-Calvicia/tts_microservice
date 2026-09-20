"""
End-to-end integration test for the TTS Microservice HTTP API.

Prerequisites:
    - The server must be running at http://127.0.0.1:8002
      (launch via `python main.py` in tts_microservice)
"""

import asyncio
import base64

import httpx
from contracts.stream.codec import EventSequencer, NdjsonDecoder, encode_ndjson
from contracts.stream.common.base import EventType
from contracts.stream.common.start_stream import StartStreamEvent
from contracts.stream.microservices.tts.inbound.completed import (
    TTSCompletedInboundEvent,
    TTSCompletedInboundEventDTO,
)
from contracts.stream.schemas import TTS_OUTBOUND

BASE_URL = "http://127.0.0.1:8002"


# ----------------------------------------------
# HELPERS
# ----------------------------------------------


def print_header(title: str) -> None:
    print(f"\n{'-' * 50}")
    print(f"  {title}")
    print(f"{'-' * 50}")


def print_result(label: str, success: bool, detail: str = "") -> None:
    icon = "[PASS]" if success else "[FAIL]"
    msg = f"  {icon} {label}"
    if detail:
        msg += f"  ->  {detail}"
    print(msg)


# ----------------------------------------------
# TEST STEPS
# ----------------------------------------------


async def test_health(client: httpx.AsyncClient) -> bool:
    print_header("1. Health Check  ->  GET /health")
    try:
        resp = await client.get(f"{BASE_URL}/health")
        body = resp.json()
        ok = resp.status_code == 200 and body.get("status") == "success"
        print_result("Health", ok, f"status={resp.status_code}  body={body}")
        return ok
    except Exception as e:
        print_result("Health", False, f"Exception: {e}")
        return False


async def test_available(client: httpx.AsyncClient) -> bool:
    print_header("2. Availability Check  ->  GET /available")
    try:
        resp = await client.get(f"{BASE_URL}/available")
        body = resp.json()
        data = body.get("data", {})
        ok = resp.status_code == 200 and data.get("is_available") is True
        print_result("Available", ok, f"status={resp.status_code}  body={body}")
        return ok
    except Exception as e:
        print_result("Available", False, f"Exception: {e}")
        return False


async def test_process_batch(client: httpx.AsyncClient) -> bool:
    print_header("3. Batch Synthesis  ->  POST /process/batch")
    try:
        params = {"text": "Hello, this is a batch text-to-speech synthesis test."}
        resp = await client.post(f"{BASE_URL}/process/batch", params=params)
        body = resp.json()
        status_ok = resp.status_code == 200 and body.get("status") == "success"

        audio_data_b64 = body.get("data", {}).get("audio_data_base64", "")
        has_audio = len(audio_data_b64) > 0

        # Test base64 decoding
        if has_audio:
            raw_audio = base64.b64decode(audio_data_b64)
            has_audio = len(raw_audio) > 0

        ok = status_ok and has_audio
        print_result(
            "Batch Synthesis", ok, f"status={resp.status_code} audio_len_b64={len(audio_data_b64)}"
        )
        return ok
    except Exception as e:
        print_result("Batch Synthesis", False, f"Exception: {e}")
        return False


async def test_process_stream(client: httpx.AsyncClient) -> bool:
    print_header("4. Streaming Synthesis  ->  POST /process/stream")
    try:
        content_payload = "Hello!\nThis is a real-time speech streaming test."

        audio_len = 0
        async with client.stream(
            "POST", f"{BASE_URL}/process/stream", content=content_payload
        ) as resp:
            async for chunk in resp.aiter_bytes():
                audio_len += len(chunk)

        ok = resp.status_code == 200 and audio_len > 0
        print_result(
            "Streaming Synthesis",
            ok,
            f"status={resp.status_code} total_audio_received={audio_len} bytes",
        )
        return ok
    except Exception as e:
        print_result("Streaming Synthesis", False, f"Exception: {e}")
        return False


async def test_event_streams(client: httpx.AsyncClient) -> bool:
    print_header("5. Event streams  ->  POST /process/stream/set + GET /process/stream/get")
    try:
        events = EventSequencer()
        upload = encode_ndjson(events.next(StartStreamEvent)) + b"".join(
            encode_ndjson(
                events.next(
                    TTSCompletedInboundEvent,
                    TTSCompletedInboundEventDTO(reason="completed", output=text),
                )
            )
            for text in ("Hello!", "This is the event protocol.")
        )
        resp = await client.post(
            f"{BASE_URL}/process/stream/set",
            params={"sample_rate": 24000, "channels": 1},
            content=upload,
            headers={"Content-Type": "application/x-ndjson"},
        )
        set_ok = resp.status_code == 202

        completed = 0
        audio_bytes = 0
        decoder = NdjsonDecoder(TTS_OUTBOUND)  # validates the contract and sequence numbers
        async with client.stream("GET", f"{BASE_URL}/process/stream/get") as get_resp:
            async for body in get_resp.aiter_bytes():
                for event in decoder.feed(body):
                    if event.type is EventType.PARTIAL:
                        audio_bytes += event.payload.byte_count
                    elif event.type is EventType.COMPLETED:
                        completed += 1
                if completed == 2:
                    break

        ok = set_ok and completed == 2 and audio_bytes > 0
        print_result("Event streams", ok, f"set={resp.status_code} texts={completed} audio={audio_bytes} bytes (24 kHz PCM16)")
        return ok
    except Exception as e:
        print_result("Event streams", False, f"Exception: {e}")
        return False


# ----------------------------------------------
# MAIN
# ----------------------------------------------


async def run_tests() -> None:
    print("\n" + "=" * 50)
    print("  TTS Microservice  -  Integration Test")
    print("=" * 50)

    results: list[bool] = []

    async with httpx.AsyncClient(timeout=15.0) as client:
        # 1. Health
        results.append(await test_health(client))

        # 2. Available
        results.append(await test_available(client))

        # 3. Batch Synthesis
        results.append(await test_process_batch(client))

        # 4. Streaming Synthesis
        results.append(await test_process_stream(client))

        # 5. Event streams (the protocol Brain uses)
        results.append(await test_event_streams(client))

    # Summary
    passed = sum(results)
    total = len(results)
    print("\n" + "=" * 50)
    if passed == total:
        print(f"  [SUCCESS] ALL PASSED  ({passed}/{total})")
    else:
        print(f"  [FAILURE] FAILURES  ({passed}/{total} passed)")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    asyncio.run(run_tests())
