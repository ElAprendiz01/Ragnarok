import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1400, "height": 900})
        await page.goto("http://127.0.0.1:5757", wait_until="networkidle")
        await page.screenshot(path="scratch/optimized_dashboard.png")

        # Ir a Estudio de Video
        btn_estudio = page.locator("#nav-estudio")
        if await btn_estudio.count() > 0:
            await btn_estudio.click()
            await page.wait_for_timeout(1000)
            await page.screenshot(path="scratch/optimized_estudio.png")

        # Ir a Mis Videos
        btn_videos = page.locator("#nav-videos")
        if await btn_videos.count() > 0:
            await btn_videos.click()
            await page.wait_for_timeout(1000)
            await page.screenshot(path="scratch/optimized_videos.png")

        await browser.close()
        print("Screenshots captured successfully.")

if __name__ == "__main__":
    asyncio.run(main())
