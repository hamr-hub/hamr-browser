"""
批量 API 压力测试脚本

功能：
- 从 asins.txt 读取 ASIN 列表
- 并发批量调用 POST /flows/sellersprite_sales/run
- 统计返回 JSON 中 data.code 的分布（正常值为 "ok"）
- 实时输出进度和统计，最终生成报告

用法：
    python tests/stress_test.py \
        --asins tests/data/asins.txt \
        --api http://localhost:8000 \
        --market UK \
        --concurrency 5 \
        --limit 100000 \
        --output tests/data/stress_result.json
"""

import asyncio
import argparse
import json
import time
import random
from collections import defaultdict
from pathlib import Path
from datetime import datetime
import aiohttp


API_DEFAULT = "http://localhost:8000"
ASINS_DEFAULT = Path(__file__).parent / "data" / "asins.txt"
OUTPUT_DEFAULT = Path(__file__).parent / "data" / "stress_result.json"


def load_asins(path: Path, limit: int) -> list[str]:
    with open(path) as f:
        asins = [line.strip() for line in f if line.strip()]
    if limit and limit < len(asins):
        asins = asins[:limit]
    print(f"[INFO] 加载 {len(asins)} 个 ASIN（来自 {path}）")
    return asins


class StressTestRunner:
    def __init__(
        self,
        api_base: str,
        market: str,
        concurrency: int,
        output: Path,
        timeout: int,
    ):
        self.api_base = api_base.rstrip("/")
        self.market = market
        self.concurrency = concurrency
        self.output = output
        self.timeout = timeout
        self.endpoint = f"{self.api_base}/flows/sellersprite_sales/run"

        self.total = 0
        self.done = 0
        self.success = 0
        self.failed = 0
        self.http_errors = 0

        self.code_dist: dict[str, int] = defaultdict(int)
        self.http_status_dist: dict[int, int] = defaultdict(int)
        self.latencies: list[float] = []
        self.errors: list[dict] = []

        self.start_time: float = 0.0

    async def call_api(
        self,
        session: aiohttp.ClientSession,
        asin: str,
        sem: asyncio.Semaphore,
    ) -> dict:
        payload = {"asin": asin, "market": self.market}
        t0 = time.perf_counter()
        result = {
            "asin": asin,
            "http_status": None,
            "flow_status": None,
            "data_code": None,
            "duration_ms": 0,
            "error": None,
        }
        async with sem:
            try:
                async with session.post(
                    self.endpoint,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as resp:
                    result["http_status"] = resp.status
                    self.http_status_dist[resp.status] += 1

                    if resp.status == 200:
                        body = await resp.json()
                        result["flow_status"] = body.get("status")
                        data = body.get("data")
                        if isinstance(data, dict):
                            result["data_code"] = data.get("code")
                        elif data is None:
                            result["data_code"] = None
                        else:
                            result["data_code"] = "__non_dict_data__"
                        self.code_dist[str(result["data_code"])] += 1
                        self.success += 1
                    else:
                        raw = await resp.text()
                        result["error"] = raw[:300]
                        self.code_dist[f"http_{resp.status}"] += 1
                        self.http_errors += 1
                        self.failed += 1
            except asyncio.TimeoutError:
                result["error"] = "timeout"
                self.code_dist["__timeout__"] += 1
                self.failed += 1
            except aiohttp.ClientConnectionError as e:
                result["error"] = f"connection_error: {e}"
                self.code_dist["__connection_error__"] += 1
                self.failed += 1
            except Exception as e:
                result["error"] = str(e)
                self.code_dist["__exception__"] += 1
                self.failed += 1

        elapsed = (time.perf_counter() - t0) * 1000
        result["duration_ms"] = round(elapsed, 1)
        self.latencies.append(elapsed)
        self.done += 1

        if self.done % 100 == 0 or self.done == self.total:
            self._print_progress()

        if result.get("error") or result["data_code"] not in ("ok", None):
            if len(self.errors) < 1000:
                self.errors.append(result)

        return result

    def _print_progress(self):
        elapsed = time.time() - self.start_time
        rate = self.done / elapsed if elapsed > 0 else 0
        pct = self.done / self.total * 100 if self.total else 0
        p50 = sorted(self.latencies)[len(self.latencies) // 2] if self.latencies else 0
        print(
            f"\r[{datetime.now().strftime('%H:%M:%S')}] "
            f"{self.done}/{self.total} ({pct:.1f}%) "
            f"成功:{self.success} 失败:{self.failed} "
            f"速率:{rate:.1f}/s P50延迟:{p50:.0f}ms",
            end="",
            flush=True,
        )

    async def run(self, asins: list[str]):
        self.total = len(asins)
        self.start_time = time.time()
        sem = asyncio.Semaphore(self.concurrency)

        connector = aiohttp.TCPConnector(limit=self.concurrency + 10)
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = [self.call_api(session, asin, sem) for asin in asins]
            await asyncio.gather(*tasks)

        print()
        self._print_report()
        self._save_report()

    def _print_report(self):
        elapsed = time.time() - self.start_time
        print("\n" + "=" * 60)
        print("压力测试报告")
        print("=" * 60)
        print(f"总请求数  : {self.total}")
        print(f"成功      : {self.success}")
        print(f"失败      : {self.failed}")
        print(f"HTTP错误  : {self.http_errors}")
        print(f"总耗时    : {elapsed:.1f}s")
        print(f"平均速率  : {self.total / elapsed:.1f} req/s")
        if self.latencies:
            sorted_lat = sorted(self.latencies)
            n = len(sorted_lat)
            print(f"延迟 P50  : {sorted_lat[n // 2]:.0f}ms")
            print(f"延迟 P90  : {sorted_lat[int(n * 0.9)]:.0f}ms")
            print(f"延迟 P99  : {sorted_lat[int(n * 0.99)]:.0f}ms")
            print(f"延迟 Max  : {sorted_lat[-1]:.0f}ms")
        print()
        print("data.code 分布：")
        total_counted = sum(self.code_dist.values())
        for code, cnt in sorted(self.code_dist.items(), key=lambda x: -x[1]):
            pct = cnt / total_counted * 100 if total_counted else 0
            mark = " ✓" if code == "ok" else " ✗"
            print(f"  {code:<30} {cnt:>8} ({pct:5.1f}%){mark}")
        print()
        print("HTTP 状态码分布：")
        for status, cnt in sorted(self.http_status_dist.items()):
            pct = cnt / self.total * 100 if self.total else 0
            print(f"  HTTP {status:<6} {cnt:>8} ({pct:5.1f}%)")
        print("=" * 60)

    def _save_report(self):
        self.output.parent.mkdir(parents=True, exist_ok=True)
        elapsed = time.time() - self.start_time
        sorted_lat = sorted(self.latencies) if self.latencies else [0]
        n = len(sorted_lat)
        report = {
            "generated_at": datetime.now().isoformat(),
            "config": {
                "api_base": self.api_base,
                "market": self.market,
                "concurrency": self.concurrency,
            },
            "summary": {
                "total": self.total,
                "success": self.success,
                "failed": self.failed,
                "http_errors": self.http_errors,
                "elapsed_seconds": round(elapsed, 2),
                "avg_rate_per_second": round(self.total / elapsed, 2) if elapsed else 0,
            },
            "latency_ms": {
                "p50": round(sorted_lat[n // 2], 1),
                "p90": round(sorted_lat[int(n * 0.9)], 1),
                "p99": round(sorted_lat[int(n * 0.99)], 1),
                "max": round(sorted_lat[-1], 1),
            },
            "code_distribution": dict(self.code_dist),
            "http_status_distribution": {str(k): v for k, v in self.http_status_dist.items()},
            "sample_errors": self.errors[:100],
        }
        with open(self.output, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"[INFO] 报告已保存到 {self.output}")


async def main(
    asins_path: Path,
    api: str,
    market: str,
    concurrency: int,
    limit: int,
    output: Path,
    timeout: int,
):
    asins = load_asins(asins_path, limit)
    if not asins:
        print("[ERROR] ASIN 列表为空，退出")
        return

    print(f"[INFO] 开始压力测试")
    print(f"  API     : {api}")
    print(f"  Market  : {market}")
    print(f"  并发数  : {concurrency}")
    print(f"  ASIN数  : {len(asins)}")
    print(f"  超时    : {timeout}s")
    print()

    runner = StressTestRunner(
        api_base=api,
        market=market,
        concurrency=concurrency,
        output=output,
        timeout=timeout,
    )
    await runner.run(asins)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SellerSprite API 批量压力测试")
    parser.add_argument("--asins", type=Path, default=ASINS_DEFAULT, help="ASIN 文件路径")
    parser.add_argument("--api", type=str, default=API_DEFAULT, help="API 服务地址")
    parser.add_argument("--market", type=str, default="UK", help="站点代码（默认 UK）")
    parser.add_argument("--concurrency", type=int, default=5, help="并发请求数（默认 5）")
    parser.add_argument("--limit", type=int, default=0, help="最大测试 ASIN 数（0=全部）")
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT, help="结果报告输出路径")
    parser.add_argument("--timeout", type=int, default=90, help="单次请求超时秒数（默认 90）")
    args = parser.parse_args()

    asyncio.run(
        main(
            asins_path=args.asins,
            api=args.api,
            market=args.market,
            concurrency=args.concurrency,
            limit=args.limit,
            output=args.output,
            timeout=args.timeout,
        )
    )
