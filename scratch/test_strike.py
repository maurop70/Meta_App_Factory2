import asyncio
import os
import sys

# Ensure factory root is in path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from api_qa_orchestrator import _deduce_culprit_matrix
from playwright.async_api import async_playwright

async def main():
    trace = ""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.goto("http://localhost:5041/", timeout=3000)
            await browser.close()
    except Exception as e:
        trace = f"E       playwright._impl._errors.TimeoutError: {str(e)}"
        print("Trace captured:")
        print(trace)
    
    print("\n--- Running _deduce_culprit_matrix ---")
    result = await _deduce_culprit_matrix(trace, "http://localhost:5041/", "CFO_Agent")
    print(f"\nResult: {result}")

if __name__ == "__main__":
    asyncio.run(main())
