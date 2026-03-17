"""
一键运行脚本：采集 ASIN + 压力测试

用法：
    python tests/run_test.py [--phase crawl|test|all] [--target 100000] [--concurrency 5]
"""

import asyncio
import argparse
import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).parent
DATA_DIR = TESTS_DIR / "data"
ASINS_FILE = DATA_DIR / "asins.txt"
RESULT_FILE = DATA_DIR / "stress_result.json"


def count_asins() -> int:
    if not ASINS_FILE.exists():
        return 0
    with open(ASINS_FILE) as f:
        return sum(1 for line in f if line.strip())


def run_crawl(target: int, no_headless: bool):
    args = [
        sys.executable, str(TESTS_DIR / "crawl_asins.py"),
        "--target", str(target),
        "--output", str(ASINS_FILE),
    ]
    if no_headless:
        args.append("--no-headless")
    print(f"[STEP 1] 启动 ASIN 采集（目标 {target} 个）...")
    subprocess.run(args, check=True)


def run_stress(api: str, market: str, concurrency: int, limit: int, timeout: int):
    args = [
        sys.executable, str(TESTS_DIR / "stress_test.py"),
        "--asins", str(ASINS_FILE),
        "--api", api,
        "--market", market,
        "--concurrency", str(concurrency),
        "--output", str(RESULT_FILE),
        "--timeout", str(timeout),
    ]
    if limit > 0:
        args += ["--limit", str(limit)]
    print(f"[STEP 2] 启动压力测试（并发 {concurrency}，市场 {market}）...")
    subprocess.run(args, check=True)


def main():
    parser = argparse.ArgumentParser(description="ASIN 采集 + API 压力测试一键脚本")
    parser.add_argument("--phase", choices=["crawl", "test", "all"], default="all",
                        help="执行阶段：crawl=仅采集, test=仅测试, all=全部（默认）")
    parser.add_argument("--target", type=int, default=100_000, help="目标 ASIN 数量（默认 10w）")
    parser.add_argument("--api", type=str, default="http://localhost:8000", help="API 服务地址")
    parser.add_argument("--market", type=str, default="UK", help="市场站点（默认 UK）")
    parser.add_argument("--concurrency", type=int, default=5, help="API 并发数（默认 5）")
    parser.add_argument("--limit", type=int, default=0, help="压力测试最大 ASIN 数（0=全部）")
    parser.add_argument("--timeout", type=int, default=90, help="API 超时秒数（默认 90）")
    parser.add_argument("--no-headless", action="store_true", help="采集时显示浏览器窗口")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if args.phase in ("crawl", "all"):
        existing = count_asins()
        if existing >= args.target:
            print(f"[INFO] 已有 {existing} 个 ASIN，跳过采集阶段")
        else:
            run_crawl(args.target, args.no_headless)

    if args.phase in ("test", "all"):
        existing = count_asins()
        if existing == 0:
            print("[ERROR] 未找到 ASIN 文件，请先运行采集阶段")
            sys.exit(1)
        print(f"[INFO] 当前 ASIN 文件包含 {existing} 个")
        run_stress(args.api, args.market, args.concurrency, args.limit, args.timeout)


if __name__ == "__main__":
    main()
