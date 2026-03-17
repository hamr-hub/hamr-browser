"""
Amazon UK ASIN 批量采集脚本

策略：
- 遍历多个商品分类页面（bestsellers / new-releases / movers-and-shakers）
- 每个分类翻多页，提取 ASIN
- 支持断点续传（已采集的 ASIN 持久化到文件）
- 目标：采集 100,000 个不重复 ASIN

用法：
    python tests/crawl_asins.py --target 100000 --output tests/data/asins.txt
"""

import asyncio
import argparse
import json
import re
import random
import time
from pathlib import Path
from playwright.async_api import async_playwright, Page, BrowserContext

TARGET_DEFAULT = 100_000
OUTPUT_DEFAULT = Path(__file__).parent / "data" / "asins.txt"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

ASIN_PATTERN = re.compile(r"/dp/([A-Z0-9]{10})")

CATEGORIES = [
    "https://www.amazon.co.uk/gp/bestsellers/electronics",
    "https://www.amazon.co.uk/gp/bestsellers/computers",
    "https://www.amazon.co.uk/gp/bestsellers/kitchen",
    "https://www.amazon.co.uk/gp/bestsellers/garden",
    "https://www.amazon.co.uk/gp/bestsellers/sports",
    "https://www.amazon.co.uk/gp/bestsellers/toys",
    "https://www.amazon.co.uk/gp/bestsellers/books",
    "https://www.amazon.co.uk/gp/bestsellers/music",
    "https://www.amazon.co.uk/gp/bestsellers/dvd",
    "https://www.amazon.co.uk/gp/bestsellers/clothing",
    "https://www.amazon.co.uk/gp/bestsellers/shoes",
    "https://www.amazon.co.uk/gp/bestsellers/beauty",
    "https://www.amazon.co.uk/gp/bestsellers/health",
    "https://www.amazon.co.uk/gp/bestsellers/grocery",
    "https://www.amazon.co.uk/gp/bestsellers/pet-supplies",
    "https://www.amazon.co.uk/gp/bestsellers/automotive",
    "https://www.amazon.co.uk/gp/bestsellers/diy",
    "https://www.amazon.co.uk/gp/bestsellers/office-products",
    "https://www.amazon.co.uk/gp/bestsellers/stationery",
    "https://www.amazon.co.uk/gp/bestsellers/luggage",
    "https://www.amazon.co.uk/gp/new-releases/electronics",
    "https://www.amazon.co.uk/gp/new-releases/computers",
    "https://www.amazon.co.uk/gp/new-releases/kitchen",
    "https://www.amazon.co.uk/gp/new-releases/garden",
    "https://www.amazon.co.uk/gp/new-releases/sports",
    "https://www.amazon.co.uk/gp/new-releases/toys",
    "https://www.amazon.co.uk/gp/new-releases/books",
    "https://www.amazon.co.uk/gp/new-releases/clothing",
    "https://www.amazon.co.uk/gp/new-releases/beauty",
    "https://www.amazon.co.uk/gp/new-releases/health",
    "https://www.amazon.co.uk/gp/new-releases/grocery",
    "https://www.amazon.co.uk/gp/new-releases/pet-supplies",
    "https://www.amazon.co.uk/gp/movers-and-shakers/electronics",
    "https://www.amazon.co.uk/gp/movers-and-shakers/computers",
    "https://www.amazon.co.uk/gp/movers-and-shakers/kitchen",
    "https://www.amazon.co.uk/gp/movers-and-shakers/sports",
    "https://www.amazon.co.uk/gp/movers-and-shakers/toys",
    "https://www.amazon.co.uk/gp/movers-and-shakers/books",
    "https://www.amazon.co.uk/gp/movers-and-shakers/clothing",
    "https://www.amazon.co.uk/gp/movers-and-shakers/beauty",
]

SEARCH_KEYWORDS = [
    "laptop", "headphones", "phone case", "keyboard", "mouse",
    "monitor", "tablet", "speaker", "camera", "printer",
    "coffee maker", "air fryer", "blender", "vacuum cleaner", "iron",
    "running shoes", "yoga mat", "protein powder", "dumbbells", "bicycle",
    "book shelf", "desk lamp", "chair", "pillow", "bedsheet",
    "skincare", "shampoo", "toothbrush", "razor", "perfume",
    "dog food", "cat toy", "bird cage", "fish tank", "hamster",
    "lego", "puzzle", "board game", "action figure", "doll",
    "novel", "cookbook", "history", "science fiction", "biography",
    "garden hose", "plant pot", "seeds", "lawn mower", "shovel",
]


def extract_asins_from_html(html: str) -> list[str]:
    return list(set(ASIN_PATTERN.findall(html)))


async def scroll_and_collect(page: Page, timeout_ms: int = 3000) -> list[str]:
    asins = []
    content = await page.content()
    asins.extend(extract_asins_from_html(content))
    for _ in range(3):
        await page.keyboard.press("End")
        await asyncio.sleep(0.5)
        content = await page.content()
        asins.extend(extract_asins_from_html(content))
    return list(set(asins))


async def fetch_page_asins(
    page: Page,
    url: str,
    collected: set[str],
) -> list[str]:
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(random.uniform(1.5, 3.0))
        asins = await scroll_and_collect(page)
        new_asins = [a for a in asins if a not in collected]
        return new_asins
    except Exception as e:
        print(f"  [WARN] 页面加载失败 {url}: {e}")
        return []


async def crawl_category(
    page: Page,
    base_url: str,
    collected: set[str],
    max_pages: int = 5,
) -> list[str]:
    new_asins = []
    for pg in range(1, max_pages + 1):
        url = f"{base_url}/ref=zg_bs_pg_{pg}?pg={pg}" if pg > 1 else base_url
        batch = await fetch_page_asins(page, url, collected)
        new_asins.extend(batch)
        collected.update(batch)
        print(f"  分类 {base_url.split('/')[-1]} 第{pg}页 +{len(batch)} 个，累计 {len(collected)}")
        if len(collected) % 1000 < len(batch):
            pass
        await asyncio.sleep(random.uniform(1.0, 2.5))
    return new_asins


async def crawl_search(
    page: Page,
    keyword: str,
    collected: set[str],
    max_pages: int = 10,
) -> list[str]:
    new_asins = []
    for pg in range(1, max_pages + 1):
        url = f"https://www.amazon.co.uk/s?k={keyword.replace(' ', '+')}&page={pg}"
        batch = await fetch_page_asins(page, url, collected)
        new_asins.extend(batch)
        collected.update(batch)
        print(f"  搜索 '{keyword}' 第{pg}页 +{len(batch)} 个，累计 {len(collected)}")
        await asyncio.sleep(random.uniform(1.0, 2.5))
        if not batch and pg > 2:
            break
    return new_asins


def save_asins(asins: set[str], output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        for asin in sorted(asins):
            f.write(asin + "\n")
    print(f"[INFO] 已保存 {len(asins)} 个 ASIN 到 {output_path}")


def load_existing_asins(output_path: Path) -> set[str]:
    if output_path.exists():
        with open(output_path) as f:
            asins = {line.strip() for line in f if line.strip()}
        print(f"[INFO] 断点续传：已有 {len(asins)} 个 ASIN")
        return asins
    return set()


async def main(target: int, output: Path, headless: bool = True):
    collected = load_existing_asins(output)
    print(f"[INFO] 目标采集 {target} 个 ASIN，当前已有 {len(collected)} 个")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
            ],
        )
        context: BrowserContext = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            locale="en-GB",
            timezone_id="Europe/London",
            viewport={"width": 1280, "height": 900},
            extra_http_headers={
                "Accept-Language": "en-GB,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            },
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = await context.new_page()

        save_interval = 500

        phase = "categories"
        cat_idx = 0
        kw_idx = 0

        while len(collected) < target:
            if phase == "categories" and cat_idx < len(CATEGORIES):
                cat_url = CATEGORIES[cat_idx]
                print(f"\n[分类阶段] {cat_url.split('amazon.co.uk')[1]}")
                await crawl_category(page, cat_url, collected, max_pages=5)
                cat_idx += 1

                if len(collected) % save_interval < 50:
                    save_asins(collected, output)
                    await context.clear_cookies()
                    await context.add_init_script(
                        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
                    )

            elif phase == "categories":
                phase = "search"
                print(f"\n[INFO] 分类阶段完成，切换搜索阶段，当前 {len(collected)} 个")

            elif phase == "search" and kw_idx < len(SEARCH_KEYWORDS):
                kw = SEARCH_KEYWORDS[kw_idx]
                print(f"\n[搜索阶段] 关键词: {kw}")
                await crawl_search(page, kw, collected, max_pages=10)
                kw_idx += 1

                if len(collected) % save_interval < 50:
                    save_asins(collected, output)

            elif phase == "search":
                print(f"\n[INFO] 搜索关键词已用尽，重新循环分类（扩展翻页）")
                phase = "deep_categories"
                cat_idx = 0

            elif phase == "deep_categories" and cat_idx < len(CATEGORIES):
                cat_url = CATEGORIES[cat_idx]
                print(f"\n[深度分类] {cat_url.split('amazon.co.uk')[1]}")
                await crawl_category(page, cat_url, collected, max_pages=10)
                cat_idx += 1
                save_asins(collected, output)

            else:
                print(f"[WARN] 已穷举所有策略，当前采集 {len(collected)} 个，未达到目标 {target}")
                break

        await browser.close()

    save_asins(collected, output)
    print(f"\n[DONE] 采集完成！共 {len(collected)} 个 ASIN，保存到 {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Amazon UK ASIN 批量采集")
    parser.add_argument("--target", type=int, default=TARGET_DEFAULT, help=f"目标采集数量（默认 {TARGET_DEFAULT}）")
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT, help="输出文件路径")
    parser.add_argument("--no-headless", action="store_true", help="显示浏览器窗口（调试用）")
    args = parser.parse_args()

    asyncio.run(main(args.target, args.output, headless=not args.no_headless))
