from jinja2 import Template, Undefined
from typing import Any, Dict


def render_template(template_str: str, params: Dict[str, Any]) -> str:
    if not template_str or "{{" not in template_str:
        return template_str
    return Template(template_str).render(**params)
