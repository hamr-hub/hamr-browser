"""
SellerSprite API 批量压力测试脚本

特性：
  - 生产者/消费者队列模式（固定 worker 数），避免一次性创建 10w 协程
  - 每个 ASIN 最多重试 N 次（指数退避）
  - 增量写入结果文件（断点续传，跳过已测试 ASIN）
  - 实时进度条（覆盖同行），含 ETA
  - 最终报告：code 分布、HTTP 状态、延迟分位数
  - 报告同时输出到控制台和 JSON 文件

用法：
    python tests/stress_test.py --asins tests/data/asins.txt --api http://localhost:8000
    python tests/stress_test.py --limit 500 --concurrency 3   # 快速验证
"""

import asyncio
import argparse
import json
import time
import sys
from collections import defaultdict
from pathlib import Path
from datetime import datetime, timedelta

import aiohttp

API_DEFAULT = "http://localhost:8000"
ASINS_DEFAULT = Path(__file__).parent / "data" / "asins.txt"
OUTPUT_DEFAULT = Path(__file__).parent / "data" / "stress_result.json"
RESULT_LINES_DEFAULT = Path(__file__).parent / "data" / "stress_result.jsonl"

MAX_RETRIES = 2
RETRY_BASE_DELAY = 3.0


def load_asins(path: Path, limit: int) -> list[str]:
    with open(path) as f:
        asins = [l.strip() for l in f if l.strip()]
    if limit and limit < len(asins):
        asins = asins[:limit]
    print(f"[INFO] 加载 {len(asins)} 个 ASIN")
    return asins


def load_done_asins(result_lines: Path) -> set[str]:
    if not result_lines.exists():
        return set()
    done = set()
    with open(result_lines) as f:
        for line in f:
            try:
                obj = json.loads(line)
                done.add(obj["asin"])
            except Exception:
                pass
    print(f"[断点续传] 已测试 {len(done)} 个 ASIN，跳过")
    return done


class Stats:
    def __init__(self):
        self.total = 0
        self.done = 0
        self.success = 0
        self.failed = 0
        self.retried = 0
        self.code_dist: dict[str, int] = defaultdict(int)
        self.http_dist: dict[int, int] = defaultdict(int)
        self.latencies: list[float] = []
        self.start_time = time.time()
        self._lock = asyncio.Lock()

    async def record(self, result: dict):
        async with self._lock:
            self.done += 1
            lat = result.get("duration_ms", 0)
            self.latencies.append(lat)
            code = result.get("data_code")
            http_s = result.get("http_status")
            err = result.get("error")

            if err:
                key = f"__{err.split(':')[0]}__" if ":" in err else f"__{err}__"
                self.code_dist[key] += 1
                self.failed += 1
            elif http_s and http_s != 200:
                self.code_dist[f"http_{http_s}"] += 1
                self.http_dist[http_s] += 1
                self.failed += 1
            else:
                self.code_dist[str(code)] += 1
                if http_s:
                    self.http_dist[http_s] += 1
                self.success += 1

            if result.get("retries", 0) > 0:
                self.retried += 1

    def eta_str(self) -> str:
        elapsed = time.time() - self.start_time
        if self.done == 0:
            return "--"
        rate = self.done / elapsed
        remaining = (self.total - self.done) / rate if rate > 0 else 0
        return str(timedelta(seconds=int(remaining)))

    def rate(self) -> float:
        elapsed = time.time() - self.start_time
        return self.done / elapsed if elapsed > 0 else 0

    def p_latency(self, pct: float) -> float:
        if not self.latencies:
            return 0
        s = sorted(self.latencies)
        idx = min(int(len(s) * pct), len(s) - 1)
        return s[idx]

    def print_progress(self):
        pct = self.done / self.total * 100 if self.total else 0
        bar_len = 30
        filled = int(bar_len * self.done / self.total) if self.total else 0
        bar = "#" * filled + "-" * (bar_len - filled)
        sys.stdout.write(
            f"\r[{bar}] {self.done}/{self.total} ({pct:.1f}%) "
            f"ok:{self.success} fail:{self.failed} "
            f"{self.rate():.1f}req/s ETA:{self.eta_str()}"
            "   "
        )
        sys.stdout.flush()

    def print_report(self):
        elapsed = time.time() - self.start_time
        print("\n\n" + "=" * 65)
        print("  压力测试报告")
        print("=" * 65)
        print(f"  总请求     : {self.total}")
        print(f"  成功       : {self.success}  ({self.success/self.total*100:.1f}%)" if self.total else "")
        print(f"  失败       : {self.failed}")
        print(f"  重试过     : {self.retried}")
        print(f"  总耗时     : {elapsed:.1f}s")
        print(f"  平均速率   : {self.rate():.2f} req/s")
        print(f"  延迟 P50   : {self.p_latency(0.50):.0f}ms")
        print(f"  延迟 P90   : {self.p_latency(0.90):.0f}ms")
        print(f"  延迟 P99   : {self.p_latency(0.99):.0f}ms")
        print(f"  延迟 Max   : {self.p_latency(1.00):.0f}ms")
        print()
        print("  data.code 分布：")
        total_c = sum(self.code_dist.values())
        for code, cnt in sorted(self.code_dist.items(), key=lambda x: -x[1]):
            pct = cnt / total_c * 100 if total_c else 0
            tag = " ✓" if code == "ok" else " ✗"
            print(f"    {code:<35} {cnt:>8}  ({pct:5.1f}%){tag}")
        print()
        print("  HTTP 状态码分布：")
        for s, cnt in sorted(self.http_dist.items()):
            pct = cnt / self.total * 100 if self.total else 0
            print(f"    HTTP {s}   {cnt:>8}  ({pct:5.1f}%)")
        print("=" * 65)

    def to_dict(self) -> dict:
        elapsed = time.time() - self.start_time
        return {
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total": self.total,
                "success": self.success,
                "failed": self.failed,
                "retried": self.retried,
                "elapsed_seconds": round(elapsed, 2),
                "avg_rate_per_second": round(self.rate(), 2),
            },
            "latency_ms": {
                "p50": round(self.p_latency(0.50), 1),
                "p90": round(self.p_latency(0.90), 1),
                "p99": round(self.p_latency(0.99), 1),
                "max": round(self.p_latency(1.00), 1),
            },
            "code_distribution": dict(self.code_dist),
            "http_status_distribution": {str(k): v for k, v in self.http_dist.items()},
        }


async def call_once(
    session: aiohttp.ClientSession,
    endpoint: str,
    asin: str,
    market: str,
    timeout: int,
) -> dict:
    t0 = time.perf_counter()
    result = {
        "asin": asin,
        "http_status": None,
        "flow_status": None,
        "data_code": None,
        "duration_ms": 0,
        "error": None,
        "retries": 0,
    }
    try:
        async with session.post(
            endpoint,
            json={"asin": asin, "market": market},
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as resp:
            result["http_status"] = resp.status
            if resp.status == 200:
                body = await resp.json(content_type=None)
                result["flow_status"] = body.get("status")
                data = body.get("data")
                if isinstance(data, dict):
                    result["data_code"] = data.get("code")
                else:
                    result["data_code"] = None if data is None else "__non_dict__"
            else:
                raw = await resp.text()
                result["error"] = f"http_{resp.status}"
    except asyncio.TimeoutError:
        result["error"] = "timeout"
    except aiohttp.ServerDisconnectedError:
        result["error"] = "server_disconnected"
    except aiohttp.ClientConnectorError as e:
        result["error"] = "connection_refused"
    except Exception as e:
        result["error"] = "exception"
    result["duration_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return result


async def call_with_retry(
    session: aiohttp.ClientSession,
    endpoint: str,
    asin: str,
    market: str,
    timeout: int,
    max_retries: int,
) -> dict:
    result = None
    for attempt in range(max_retries + 1):
        result = await call_once(session, endpoint, asin, market, timeout)
        result["retries"] = attempt
        if not result["error"] and result["http_status"] == 200:
            break
        if attempt < max_retries:
            delay = RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 1)
            await asyncio.sleep(delay)
    return result


async def worker(
    worker_id: int,
    queue: asyncio.Queue,
    session: aiohttp.ClientSession,
    endpoint: str,
    market: str,
    timeout: int,
    max_retries: int,
    stats: Stats,
    result_file,
    file_lock: asyncio.Lock,
):
    while True:
        try:
            asin = queue.get_nowait()
        except asyncio.QueueEmpty:
            break

        result = await call_with_retry(session, endpoint, asin, market, timeout, max_retries)
        await stats.record(result)
        stats.print_progress()

        async with file_lock:
            result_file.write(json.dumps(result, ensure_ascii=False) + "\n")
            result_file.flush()

        queue.task_done()


async def run_stress(
    asins: list[str],
    api_base: str,
    market: str,
    concurrency: int,
    timeout: int,
    max_retries: int,
    result_lines: Path,
    report_json: Path,
):
    stats = Stats()
    stats.total = len(asins)

    endpoint = f"{api_base.rstrip('/')}/flows/sellersprite_sales/run"
    queue: asyncio.Queue = asyncio.Queue()
    for asin in asins:
        queue.put_nowait(asin)

    file_lock = asyncio.Lock()
    result_lines.parent.mkdir(parents=True, exist_ok=True)

    connector = aiohttp.TCPConnector(limit=concurrency + 5, ttl_dns_cache=300)

    print(f"[INFO] 开始压力测试")
    print(f"  endpoint  : {endpoint}")
    print(f"  market    : {market}")
    print(f"  ASIN 数   : {len(asins)}")
    print(f"  并发 workers: {concurrency}")
    print(f"  超时      : {timeout}s")
    print(f"  最大重试  : {max_retries} 次")
    print()

    with open(result_lines, "a", encoding="utf-8") as rf:
        async with aiohttp.ClientSession(connector=connector) as session:
            workers = [
                asyncio.create_task(
                    worker(
                        i, queue, session, endpoint, market,
                        timeout, max_retries, stats, rf, file_lock,
                    )
                )
                for i in range(concurrency)
            ]
            await asyncio.gather(*workers)

    stats.print_report()

    report = stats.to_dict()
    report["config"] = {
        "api_base": api_base,
        "market": market,
        "concurrency": concurrency,
        "timeout": timeout,
        "max_retries": max_retries,
    }
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"[INFO] JSON 报告 → {report_json}")
    print(f"[INFO] 明细行   → {result_lines}")


import random


def main():
    parser = argparse.ArgumentParser(description="SellerSprite API 批量压力测试")
    parser.add_argument("--asins", type=Path, default=ASINS_DEFAULT)
    parser.add_argument("--api", type=str, default=API_DEFAULT)
    parser.add_argument("--market", type=str, default="UK")
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--limit", type=int, default=0, help="最大 ASIN 数（0=全部）")
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--retries", type=int, default=MAX_RETRIES)
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT, help="汇总 JSON 报告路径")
    parser.add_argument("--result-lines", type=Path, default=RESULT_LINES_DEFAULT, help="每条结果的 JSONL 路径")
    parser.add_argument("--no-resume", action="store_true", help="忽略断点续传，重新全量测试")
    args = parser.parse_args()

    asins = load_asins(args.asins, args.limit)

    if not args.no_resume:
        done = load_done_asins(args.result_lines)
        asins = [a for a in asins if a not in done]
        print(f"[INFO] 过滤后待测试: {len(asins)} 个")

    if not asins:
        print("[INFO] 所有 ASIN 已测试完毕")
        return

    asyncio.run(
        run_stress(
            asins=asins,
            api_base=args.api,
            market=args.market,
            concurrency=args.concurrency,
            timeout=args.timeout,
            max_retries=args.retries,
            result_lines=args.result_lines,
            report_json=args.output,
        )
    )


if __name__ == "__main__":
    main()
