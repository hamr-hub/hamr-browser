import os
import yaml
from typing import Dict, List, Optional
from app.models.flow import FlowConfig
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class FlowStore:
    def __init__(self):
        self.flows_dir = settings.flows_dir
        os.makedirs(self.flows_dir, exist_ok=True)

    def list_flows(self) -> List[FlowConfig]:
        flows = []
        for fname in os.listdir(self.flows_dir):
            if fname.endswith(".yaml") or fname.endswith(".yml"):
                flow = self._load_file(os.path.join(self.flows_dir, fname))
                if flow:
                    flows.append(flow)
        return flows

    def get_flow(self, flow_id: str) -> Optional[FlowConfig]:
        for ext in [".yaml", ".yml"]:
            path = os.path.join(self.flows_dir, f"{flow_id}{ext}")
            if os.path.exists(path):
                return self._load_file(path)
        return None

    def save_flow(self, flow_id: str, content: str) -> FlowConfig:
        path = os.path.join(self.flows_dir, f"{flow_id}.yaml")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        flow = self._load_file(path)
        if not flow:
            raise ValueError(f"流程配置解析失败：{flow_id}")
        return flow

    def delete_flow(self, flow_id: str) -> bool:
        for ext in [".yaml", ".yml"]:
            path = os.path.join(self.flows_dir, f"{flow_id}{ext}")
            if os.path.exists(path):
                os.remove(path)
                return True
        return False

    def _load_file(self, path: str) -> Optional[FlowConfig]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return FlowConfig(**data)
        except Exception as e:
            logger.error(f"加载流程配置失败 {path}: {e}")
            return None


flow_store = FlowStore()
