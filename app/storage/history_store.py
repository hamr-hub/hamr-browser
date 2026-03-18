"""
执行历史记录存储（内存 + 滚动写入 JSONL 文件）
"""
import json
import os
import time
from collections import deque
from typing import Any, Dict, List, Optional
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

MAX_MEMORY_RECORDS = 500


class HistoryRecord:
    def __init__(
        self,
        run_id: str,
        flow_id: str,
        params: Dict[str, Any],
        status: str,
        duration_ms: int,
        data: Any = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ):
        self.run_id = run_id
        self.flow_id = flow_id
        self.params = params
        self.status = status
        self.duration_ms = duration_ms
        self.data = data
        self.error_code = error_code
        self.error_message = error_message
        self.timestamp = time.time()
        self.created_at = time.strftime(
            "%Y-%m-%dT%H:%M:%S", time.localtime(self.timestamp)
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "flow_id": self.flow_id,
            "params": self.params,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "data": self.data,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "created_at": self.created_at,
        }


class HistoryStore:
    def __init__(self):
        self._records: deque = deque(maxlen=MAX_MEMORY_RECORDS)
        self._log_path = os.path.join(settings.logs_dir, "history.jsonl")
        os.makedirs(settings.logs_dir, exist_ok=True)

    def add(self, record: HistoryRecord):
        self._records.append(record)
        try:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning(f"写入执行历史文件失败: {e}")

    def list(
        self,
        flow_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        results = list(self._records)
        if flow_id:
            results = [r for r in results if r.flow_id == flow_id]
        if status:
            results = [r for r in results if r.status == status]
        # newest first
        results = list(reversed(results))
        return [r.to_dict() for r in results[:limit]]

    def get(self, run_id: str) -> Optional[Dict[str, Any]]:
        for r in self._records:
            if r.run_id == run_id:
                return r.to_dict()
        return None


history_store = HistoryStore()
