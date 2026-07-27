import asyncio
import httpx

async def main():
    async with httpx.AsyncClient() as client:
        try:
            async with client.stream("GET", "http://localhost:8000/api/v1/prospects/stream?tenant_id=org_test_123") as response:
                print(f"Status: {response.status_code}")
                async for line in response.aiter_lines():
                    print(line)
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
