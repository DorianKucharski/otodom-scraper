import asyncio
import aiohttp
import time


async def fetch(session, url, request_id):
    start = time.perf_counter()
    try:
        async with session.get(url) as response:
            status = response.status
            await response.text()
            duration = time.perf_counter() - start
            print(f"Request {request_id}: {status} in {duration:.3f}s")
            return status, duration
    except Exception as e:
        duration = time.perf_counter() - start
        print(f"Request {request_id}: ERROR {e} in {duration:.3f}s")
        return None, duration


async def main():
    url = "https://strapp.sollers.eu/api/trip/dictionary/supplierConfigs"

    # Wklej cały string cookie z przeglądarki
    cookie_string = "hasSeenDoneTasksOnboardingTooltip=true; hasSeenFullPageOnboardingTooltip=true; onboarding_tooltip_deactivation_billable-engagement-show-tooltip=1769554800000; _pk_id.1.daa8=ed94a2bcba1710db.1761838776.; _pk_id.1.d294=0413708fccff87f1.1762187663.; LAST_CLOSED_BANNER_INFORMATION=1605; LAST_CLOSED_BANNER_INSTALLATION=1605; Authorization=Bearer%20eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIsIng1dCI6IlBjWDk4R1g0MjBUMVg2c0JEa3poUW1xZ3dNVSIsImtpZCI6IlBjWDk4R1g0MjBUMVg2c0JEa3poUW1xZ3dNVSJ9.eyJhdWQiOiIyM2I2M2M5OS02NTZkLTRlYjctYjg4NS0yNTNlYzJhODAxYTAiLCJpc3MiOiJodHRwczovL3N0cy53aW5kb3dzLm5ldC85YmY0YzY0NC1iZDdmLTRmZTUtYTBkMS0yZDE0OTIyMjNhYjgvIiwiaWF0IjoxNzY4MzA4NzgxLCJuYmYiOjE3NjgzMDg3ODEsImV4cCI6MTc2ODMxMjY4MSwiYWlvIjoiQVdRQW0vOGFBQUFBN3RzaDZJaEY1MTdLN1ArQnBHdUF2UU5lb3VIdEprN0lMc3haM0I3YytqL1V1ZnRwK1dLbUJ4SjlQV2FENWxPa1JYamJMdGxRdlMyMHFXSCszSnZrd0dkSEw4L1JYUFp3Ty9LZGxWazJSdHA0ZGdGZm1VcEh2ZE9ZbW9tcnJRbmEiLCJhbXIiOlsicHdkIiwibWZhIl0sImZhbWlseV9uYW1lIjoiS3VjaGFyc2tpIiwiZ2l2ZW5fbmFtZSI6IkRvcmlhbiIsImlwYWRkciI6IjE1Ny4yNS4xMjEuOTIiLCJuYW1lIjoiRG9yaWFuIEt1Y2hhcnNraSIsIm5vbmNlIjoiMDQxZWUzM2MtOWE5My00ZGZhLWI1YjEtMTg2ZjU1ZGFkOTc4Iiwib2lkIjoiMjU0NTMyMmEtZWRlNC00MGY4LWI2ODUtYjQ3MjM1NGFkNDY1Iiwib25wcmVtX3NpZCI6IlMtMS01LTIxLTEyNzkzMDE5NjktMTQ0MzE3MDI5My04Njc2NTA5MzItMzQzMzYiLCJyaCI6IjEuQVNFQVJNYjBtMy05NVUtZzBTMFVraUk2dUprOHRpTnRaYmRPdUlVbFBzS29BYUNHQUJvaEFBLiIsInJvbGVzIjpbIlNPTExFUlMiLCJTVVBFUkRFViIsIkFXRkRFVkVMT1BFUlMiLCJERVYiXSwic2lkIjoiMDA5YmY5YzktYmI3My1iMmNjLWE4ZmItNTcyNWUxMjNhMzdiIiwic3ViIjoibVZOZk9xcGJNbl9nVG1XZ1NYbHN6cV9kZmJwdjJyOFBZMkh4Rlp2YUl4dyIsInRpZCI6IjliZjRjNjQ0LWJkN2YtNGZlNS1hMGQxLTJkMTQ5MjIyM2FiOCIsInVuaXF1ZV9uYW1lIjoiZG9yaWFuLmt1Y2hhcnNraUBzb2xsZXJzLmV1IiwidXBuIjoiZG9yaWFuLmt1Y2hhcnNraUBzb2xsZXJzLmV1IiwidXRpIjoiU2I1WHRxYl9ha0tSd0hONWZ5eHhBQSIsInZlciI6IjEuMCJ9.Vvrqx-S8Jtn8_qVWIOVijNBoKl506VocnKorfT37jT4P-UiGbKVE4geWYLN8FarCXT1QMxamacpl2R23qvNKWgVq915lwSPqHWZRJSKcgRqw2pXXMFU0bRBBy1VnppbxAuAHjyJo8aC9AaEu4A-6oDCumyGD5atcB-quRBgv8EG1sz8Dn_2FD0L934uvsqIpp8yw3IXdsDS329uzUuhKiaAlEkXG3etP_ieY_hvK_6QLxhxm7oOflm4FYZeSU5SSQGFEwRFizGUYSmww_w08UHac2Gxuio8Z-20O3USl1q0wMqJIbbuyUphQGDsnPq6b3nKX2OjoU_p8frrCJkhwog; _pk_ses.1.d294=1; _pk_ref.1.daa8=%5B%22%22%2C%22%22%2C1768311513%2C%22https%3A%2F%2Flogin.microsoftonline.com%2F%22%5D"

    headers = {
        "Cookie": cookie_string
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        tasks = [fetch(session, url, i) for i in range(1, 20)]

        start = time.perf_counter()
        results = await asyncio.gather(*tasks)
        total = time.perf_counter() - start

        print(f"\n--- Summary ---")
        print(f"Total time: {total:.3f}s")
        print(f"Successful: {sum(1 for s, _ in results if s == 200)}/10")


if __name__ == "__main__":
    asyncio.run(main())