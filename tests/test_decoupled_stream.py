"""
Verification test for the decoupled streaming endpoints.

Usage:
    1. Start the TTS microservice:  python main.py
    2. Run this test:               python tests/test_decoupled_stream.py

This script:
    - POSTs a multi-line text block to POST /process/stream/set
    - GETs the synthesized audio from   GET  /process/stream/get
    - Validates that audio bytes are streamed back and terminates gracefully.
"""

import asyncio
import httpx
import sys
import os

BASE_URL = os.getenv("TTS_TEST_BASE_URL", "http://127.0.0.1:8002")


async def TestDecoupledStream():
    """End-to-end test for set_stream / get_stream decoupled flow."""

    textPayload = (
        "Hello, this is the first sentence.\n"
        "This is the second sentence for streaming.\n"
        "And a third sentence to verify multi-chunk behaviour.\n"
    )

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Step 1: POST /process/stream/set — should return 202
        print("[1/3] Sending text to POST /process/stream/set ...")
        setResponse = await client.post(
            f"{BASE_URL}/process/stream/set",
            content=textPayload,
            headers={"Content-Type": "text/plain"},
        )

        assert setResponse.status_code == 202, (
            f"Expected 202 Accepted, got {setResponse.status_code}: {setResponse.text}"
        )
        print(f"      -> Received {setResponse.status_code} Accepted")

        # Small delay so background generation can produce at least one chunk
        await asyncio.sleep(0.5)

        # Step 2: GET /process/stream/get — should stream audio bytes
        print("[2/3] Streaming audio from GET /process/stream/get ...")
        totalBytes = 0
        chunkCount = 0

        async with client.stream("GET", f"{BASE_URL}/process/stream/get") as getResponse:
            assert getResponse.status_code == 200, (
                f"Expected 200 OK, got {getResponse.status_code}"
            )

            async for chunk in getResponse.aiter_bytes():
                totalBytes += len(chunk)
                chunkCount += 1

        # Step 3: Validate
        print(f"[3/3] Validation:")
        print(f"      -> Chunks received : {chunkCount}")
        print(f"      -> Total bytes     : {totalBytes}")

        assert chunkCount > 0, "Expected at least one audio chunk but got none"
        assert totalBytes > 0, "Expected non-zero audio data but got 0 bytes"

        print("\n=== PASS: Decoupled stream test completed successfully ===")


if __name__ == "__main__":
    try:
        asyncio.run(TestDecoupledStream())
    except AssertionError as e:
        print(f"\n=== FAIL: {e} ===")
        sys.exit(1)
    except httpx.ConnectError:
        print(
            f"\n=== ERROR: Could not connect to {BASE_URL}. "
            "Is the TTS microservice running? ==="
        )
        sys.exit(1)
