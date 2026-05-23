"""
End-to-end integration test for the TTS Microservice HTTP API.

Prerequisites:
    - The server must be running at http://127.0.0.1:8002
      (launch via `python main.py` in tts_microservice)
"""

import httpx
import asyncio
import time
import base64

BASE_URL = "http://127.0.0.1:8002"


# ----------------------------------------------
# HELPERS
# ----------------------------------------------

def print_header(title: str) -> None:
    print(f"\n{'-'*50}")
    print(f"  {title}")
    print(f"{'-'*50}")


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
        payload = {"text": "Hello, this is a batch text-to-speech synthesis test."}
        resp = await client.post(f"{BASE_URL}/process/batch", json=payload)
        body = resp.json()
        status_ok = resp.status_code == 200 and body.get("status") == "success"
        
        audio_data_b64 = body.get("data", {}).get("audio_data_base64", "")
        has_audio = len(audio_data_b64) > 0
        
        # Test base64 decoding
        if has_audio:
            raw_audio = base64.b64decode(audio_data_b64)
            has_audio = len(raw_audio) > 0

        ok = status_ok and has_audio
        print_result("Batch Synthesis", ok, f"status={resp.status_code} audio_len_b64={len(audio_data_b64)}")
        return ok
    except Exception as e:
        print_result("Batch Synthesis", False, f"Exception: {e}")
        return False


async def test_process_stream(client: httpx.AsyncClient) -> bool:
    print_header("4. Streaming Synthesis  ->  POST /process/stream")
    try:
        content_payload = "Hello!\nThis is a real-time speech streaming test."
        
        audio_len = 0
        async with client.stream("POST", f"{BASE_URL}/process/stream", content=content_payload) as resp:
            async for chunk in resp.aiter_bytes():
                audio_len += len(chunk)

        ok = resp.status_code == 200 and audio_len > 0
        print_result("Streaming Synthesis", ok, f"status={resp.status_code} total_audio_received={audio_len} bytes")
        return ok
    except Exception as e:
        print_result("Streaming Synthesis", False, f"Exception: {e}")
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
