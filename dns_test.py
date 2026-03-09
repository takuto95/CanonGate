import asyncio
import aiohttp
import socket
import os

GROQ_API_KEY = os.getenv("GROQ_API_KEY") # Use .env
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

async def test_conn(family=socket.AF_UNSPEC):
    print(f"Testing with family={'IPv4' if family == socket.AF_INET else 'Default'}...")
    connector = aiohttp.TCPConnector(family=family)
    try:
        async with aiohttp.ClientSession(connector=connector) as session:
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False
            }
            headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
            async with session.post(GROQ_URL, headers=headers, json=payload, timeout=5) as resp:
                print(f"Status: {resp.status}")
                if resp.status == 200:
                    print("Success!")
                else:
                    print(await resp.text())
    except Exception as e:
        print(f"Error: {e}")

async def main():
    await test_conn(socket.AF_UNSPEC)
    print("-" * 20)
    await test_conn(socket.AF_INET)

if __name__ == "__main__":
    asyncio.run(main())
