"""
Amazon UK ASIN 批量采集脚本

策略（多层递进，确保能达到 10w 量级）：
  Phase 1 - 分类榜单：bestsellers / new-releases / movers-and-shakers，每个分类翻 5 页
  Phase 2 - 关键词搜索：50+ 关键词 × 20 页，每页约 16 个 ASIN
  Phase 3 - 子分类深挖：通过解析页面中的子分类链接递归抓取（BFS，深度 2）
  Phase 4 - 深翻页：对已有分类再翻 10 页

特性：
  - 断点续传：每 1000 个自动保存，程序重启后跳过已有 ASIN
  - 随机延迟 + UA 轮换 + 反 webdriver 检测
  - 遇到 CAPTCHA / 反爬页面自动等待并重试
  - 仅提取标准 10 位 ASIN（字母+数字，排除纯数字）

用法：
    python tests/crawl_asins.py --target 100000
    python tests/crawl_asins.py --target 100000 --no-headless   # 调试模式显示浏览器
"""

import asyncio
import argparse
import re
import random
import time
from collections import deque
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlencode, parse_qs

from playwright.async_api import async_playwright, Page, BrowserContext, Browser

TARGET_DEFAULT = 100_000
OUTPUT_DEFAULT = Path(__file__).parent / "data" / "asins.txt"
SAVE_INTERVAL = 1000

ASIN_RE = re.compile(r"/dp/([A-Z][A-Z0-9]{9})")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
]

CATEGORY_SEEDS = [
    "electronics", "computers", "kitchen", "garden", "sports",
    "toys", "books", "music", "dvd", "clothing", "shoes",
    "beauty", "health", "grocery", "pet-supplies", "automotive",
    "diy", "office-products", "stationery", "luggage", "lighting",
    "baby", "jewelry", "watches", "musical-instruments",
    "software", "video-games", "camera", "mobile-phones",
    "tv", "home-audio", "handmade", "arts-crafts",
]

BESTSELLER_URLS = [f"https://www.amazon.co.uk/gp/bestsellers/{c}" for c in CATEGORY_SEEDS]
NEW_RELEASE_URLS = [f"https://www.amazon.co.uk/gp/new-releases/{c}" for c in CATEGORY_SEEDS]
MOVERS_URLS = [f"https://www.amazon.co.uk/gp/movers-and-shakers/{c}" for c in CATEGORY_SEEDS]

SEARCH_KEYWORDS = [
    "laptop", "headphones", "gaming keyboard", "mechanical keyboard", "wireless mouse",
    "4k monitor", "tablet stand", "usb hub", "webcam", "microphone",
    "coffee maker", "air fryer", "instant pot", "blender", "kettle",
    "vacuum cleaner", "steam iron", "clothes rack", "storage box", "hangers",
    "running shoes", "yoga mat", "protein powder", "resistance bands", "dumbbells",
    "bicycle helmet", "water bottle", "gym bag", "sports watch", "football",
    "desk lamp", "bookshelf", "wall clock", "throw pillow", "duvet",
    "face moisturiser", "shampoo", "electric toothbrush", "razor blades", "perfume",
    "dog food", "cat food", "pet bed", "dog lead", "cat toy",
    "lego sets", "jigsaw puzzle", "board game", "remote control car", "doll house",
    "bestselling novel", "cookbook", "self help book", "history book", "children book",
    "garden hose", "plant pots", "compost", "lawn mower", "garden gloves",
    "phone charger", "power bank", "screen protector", "phone case", "earbuds",
    "drawing tablet", "printer ink", "desk organizer", "sticky notes", "pens set",
    "vitamin d", "omega 3", "multivitamin", "protein bar", "collagen",
    "candles", "picture frame", "bath towel", "shower curtain", "bath mat",
    "suitcase", "backpack", "travel pillow", "packing cubes", "padlock",
    "car phone holder", "car charger", "jump starter", "dashboard camera", "car vacuum",
    "guitar strings", "piano keyboard", "drum sticks", "ukulele", "violin",
]


def extract_asins(html: str) -> list[str]:
    return list(set(ASIN_RE.findall(html)))


def make_category_page_url(base_url: str, page: int) -> str:
    if page <= 1:
        return base_url
    parsed = urlparse(base_url)
    path = parsed.path.rstrip("/")
    return f"https://www.amazon.co.uk{path}?pg={page}&ajax=1"


def make_search_url(keyword: str, page: int) -> str:
    return f"https://www.amazon.co.uk/s?k={keyword.replace(' ', '+')}&page={page}"


def load_existing(path: Path) -> set[str]:
    if path.exists():
        asins = {l.strip() for l in path.read_text().splitlines() if l.strip()}
        print(f"[断点续传] 已有 {len(asins)} 个 ASIN")
        return asins
    return set()


def save(asins: set[str], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(sorted(asins)) + "\n")
    print(f"  [SAVE] {len(asins)} 个 ASIN → {path}")


def is_blocked(html: str) -> bool:
    signals = [
        "robot check", "captcha", "automated access",
        "api-services.amazon.co.uk", "validateCaptcha",
        "Sorry, we just need to make sure",
    ]
    lower = html.lower()
    return any(s in lower for s in signals)


async def safe_goto(page: Page, url: str, retries: int = 3) -> str | None:
    for attempt in range(retries):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(random.uniform(1.2, 2.8))
            html = await page.content()
            if is_blocked(html):
                print(f"  [BLOCKED] {url[:80]} 触发反爬，等待 {10 + attempt * 10}s...")
                await asyncio.sleep(10 + attempt * 10)
                continue
            return html
        except Exception as e:
            wait = 5 + attempt * 5
            print(f"  [ERROR] {url[:80]}: {e}，{wait}s 后重试")
            await asyncio.sleep(wait)
    return None


async def scroll_page(page: Page):
    for _ in range(4):
        await page.keyboard.press("End")
        await asyncio.sleep(0.4)


async def collect_page(page: Page, url: str, collected: set[str]) -> list[str]:
    html = await safe_goto(page, url)
    if not html:
        return []
    await scroll_page(page)
    html2 = await page.content()
    new_asins = [a for a in extract_asins(html + html2) if a not in collected]
    return new_asins


async def extract_subcategory_links(page: Page, base_url: str) -> list[str]:
    html = await page.content()
    all_links = await page.eval_on_selector_all(
        "a[href]", "els => els.map(e => e.href)"
    )
    subcats = []
    for link in all_links:
        if not link:
            continue
        if "amazon.co.uk" not in link:
            continue
        parsed = urlparse(link)
        path = parsed.path
        if any(x in path for x in ["/gp/bestsellers/", "/gp/new-releases/", "/gp/movers-and-shakers/"]):
            clean = f"https://www.amazon.co.uk{path}"
            if clean != base_url and clean not in BESTSELLER_URLS + NEW_RELEASE_URLS + MOVERS_URLS:
                subcats.append(clean)
    return list(set(subcats))


class Crawler:
    def __init__(self, target: int, output: Path, headless: bool):
        self.target = target
        self.output = output
        self.headless = headless
        self.collected: set[str] = set()
        self._last_save_count = 0

    def _add(self, asins: list[str]):
        before = len(self.collected)
        self.collected.update(asins)
        added = len(self.collected) - before
        return added

    def _maybe_save(self):
        if len(self.collected) - self._last_save_count >= SAVE_INTERVAL:
            save(self.collected, self.output)
            self._last_save_count = len(self.collected)

    def _done(self) -> bool:
        return len(self.collected) >= self.target

    async def _run_phase(self, name: str, urls: list[str], page: Page, max_pages: int = 5):
        print(f"\n=== Phase: {name} ({len(urls)} 个入口，每个翻 {max_pages} 页) ===")
        for base_url in urls:
            if self._done():
                return
            label = urlparse(base_url).path
            for pg in range(1, max_pages + 1):
                if self._done():
                    return
                url = make_category_page_url(base_url, pg)
                batch = await collect_page(page, url, self.collected)
                added = self._add(batch)
                print(f"  {label} p{pg} +{added} → 累计 {len(self.collected)}")
                self._maybe_save()
                await asyncio.sleep(random.uniform(0.8, 2.0))

    async def _run_search_phase(self, page: Page, max_pages: int = 20):
        print(f"\n=== Phase: 搜索关键词 ({len(SEARCH_KEYWORDS)} 个词 × {max_pages} 页) ===")
        kws = list(SEARCH_KEYWORDS)
        random.shuffle(kws)
        for kw in kws:
            if self._done():
                return
            consecutive_empty = 0
            for pg in range(1, max_pages + 1):
                if self._done():
                    return
                url = make_search_url(kw, pg)
                batch = await collect_page(page, url, self.collected)
                added = self._add(batch)
                print(f"  搜索'{kw}' p{pg} +{added} → 累计 {len(self.collected)}")
                self._maybe_save()
                if added == 0:
                    consecutive_empty += 1
                    if consecutive_empty >= 2:
                        break
                else:
                    consecutive_empty = 0
                await asyncio.sleep(random.uniform(0.8, 1.8))

    async def _run_subcat_phase(self, base_urls: list[str], page: Page, max_depth: int = 2, max_pages: int = 3):
        print(f"\n=== Phase: 子分类 BFS (深度 {max_depth}) ===")
        queue: deque[tuple[str, int]] = deque()
        visited: set[str] = set()

        for u in base_urls:
            queue.append((u, 0))

        while queue and not self._done():
            url, depth = queue.popleft()
            if url in visited:
                continue
            visited.add(url)

            html = await safe_goto(page, url)
            if not html:
                continue
            await scroll_page(page)
            html2 = await page.content()
            batch = [a for a in extract_asins(html + html2) if a not in self.collected]
            added = self._add(batch)
            label = urlparse(url).path[:50]
            print(f"  [d{depth}] {label} +{added} → 累计 {len(self.collected)}")
            self._maybe_save()

            if depth < max_depth:
                subcats = await extract_subcategory_links(page, url)
                for sc in subcats[:20]:
                    if sc not in visited:
                        queue.append((sc, depth + 1))

            await asyncio.sleep(random.uniform(0.8, 1.8))

    async def run(self):
        self.collected = load_existing(self.output)
        self._last_save_count = len(self.collected)

        async with async_playwright() as p:
            browser: Browser = await p.chromium.launch(
                headless=self.headless,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            context: BrowserContext = await browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                locale="en-GB",
                timezone_id="Europe/London",
                viewport={"width": 1440, "height": 900},
                extra_http_headers={
                    "Accept-Language": "en-GB,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "DNT": "1",
                },
            )
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page = await context.new_page()

            print(f"[START] 目标 {self.target} 个 ASIN，当前 {len(self.collected)} 个\n")

            if not self._done():
                await self._run_phase("Bestsellers", BESTSELLER_URLS, page, max_pages=5)

            if not self._done():
                await self._run_phase("New Releases", NEW_RELEASE_URLS, page, max_pages=5)

            if not self._done():
                await self._run_phase("Movers & Shakers", MOVERS_URLS, page, max_pages=5)

            if not self._done():
                await self._run_search_phase(page, max_pages=20)

            if not self._done():
                all_seeds = BESTSELLER_URLS + NEW_RELEASE_URLS
                await self._run_subcat_phase(all_seeds, page, max_depth=2, max_pages=3)

            if not self._done():
                await self._run_phase("Bestsellers Deep", BESTSELLER_URLS, page, max_pages=10)

            if not self._done():
                await self._run_search_phase(page, max_pages=50)

            await browser.close()

        save(self.collected, self.output)
        print(f"\n[DONE] 采集完成：{len(self.collected)} 个 ASIN → {self.output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Amazon UK ASIN 批量采集")
    parser.add_argument("--target", type=int, default=TARGET_DEFAULT)
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    parser.add_argument("--no-headless", action="store_true")
    args = parser.parse_args()
    asyncio.run(Crawler(args.target, args.output, headless=not args.no_headless).run())
