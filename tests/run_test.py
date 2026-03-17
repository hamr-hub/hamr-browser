"""
一键运行脚本：ASIN 采集 + API 压力测试

用法：
    python tests/run_test.py                          # 全流程（10w ASIN + 全量测试）
    python tests/run_test.py --phase crawl            # 仅采集
    python tests/run_test.py --phase test             # 仅测试（需先有 asins.txt）
    python tests/run_test.py --target 1000 --limit 1000 --concurrency 3  # 快速验证
"""

import argparse
import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).parent
DATA_DIR = TESTS_DIR / "data"
ASINS_FILE = DATA_DIR / "asins.txt"
RESULT_JSON = DATA_DIR / "stress_result.json"
RESULT_LINES = DATA_DIR / "stress_result.jsonl"


def count_asins() -> int:
    if not ASINS_FILE.exists():
        return 0
    return sum(1 for l in ASINS_FILE.read_text().splitlines() if l.strip())


def run(cmd: list[str]):
    print(f"\n$ {' '.join(str(c) for c in cmd)}\n")
    subprocess.run([str(c) for c in cmd], check=True)


def main():
    parser = argparse.ArgumentParser(description="ASIN 采集 + 压力测试一键脚本")
    parser.add_argument("--phase", choices=["crawl", "test", "all"], default="all")
    parser.add_argument("--target", type=int, default=100_000, help="采集目标 ASIN 数（默认 10w）")
    parser.add_argument("--api", type=str, default="http://localhost:8000")
    parser.add_argument("--market", type=str, default="UK")
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--limit", type=int, default=0, help="压测最大 ASIN 数（0=全部）")
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--no-headless", action="store_true")
    parser.add_argument("--no-resume", action="store_true", help="忽略断点续传重跑全量")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if args.phase in ("crawl", "all"):
        existing = count_asins()
        if existing >= args.target:
            print(f"[SKIP] 已有 {existing} 个 ASIN，跳过采集")
        else:
            crawl_cmd = [
                sys.executable, TESTS_DIR / "crawl_asins.py",
                "--target", args.target,
                "--output", ASINS_FILE,
            ]
            if args.no_headless:
                crawl_cmd.append("--no-headless")
            run(crawl_cmd)

    if args.phase in ("test", "all"):
        n = count_asins()
        if n == 0:
            print("[ERROR] asins.txt 不存在或为空，请先运行采集")
            sys.exit(1)
        print(f"[INFO] 当前 ASIN 文件：{n} 个")
        test_cmd = [
            sys.executable, TESTS_DIR / "stress_test.py",
            "--asins", ASINS_FILE,
            "--api", args.api,
            "--market", args.market,
            "--concurrency", args.concurrency,
            "--timeout", args.timeout,
            "--retries", args.retries,
            "--output", RESULT_JSON,
            "--result-lines", RESULT_LINES,
        ]
        if args.limit > 0:
            test_cmd += ["--limit", args.limit]
        if args.no_resume:
            test_cmd.append("--no-resume")
        run(test_cmd)


if __name__ == "__main__":
    main()
