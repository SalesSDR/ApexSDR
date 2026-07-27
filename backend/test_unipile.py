import asyncio
import httpx

async def run():
    async with httpx.AsyncClient() as c:
        for base in ["https://api39.unipile.com:16907", "https://api39.unipile.com:16907/api/v1"]:
            try:
                r = await c.get(
                    f"{base}/users/shreyanshi-s-587256255?account_id=pmcw0j3KRza5oxAb0dN_Kw",
                    headers={"X-API-KEY": "A+j1BfCF.rySa+DX1OSgGCabpPXWFco08qpAQ87Nr91CHJFvsJKo=", "accept": "application/json"}
                )
                print(f"Base: {base} -> {r.status_code} {r.text}")
            except Exception as e:
                print(f"Base: {base} -> Error: {e}")

if __name__ == "__main__":
    asyncio.run(run())
