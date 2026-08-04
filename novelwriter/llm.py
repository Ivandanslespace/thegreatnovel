"""llm.py —— LLM 环节可插拔适配层（宪章第 5 节第 4 条）。

默认 ManualAdapter：把提示词写入 prompts/，作者粘贴到 ChatGPT 桌面端，
零依赖。ApiAdapter 仅在 book.json 配置了 llm_api 时启用；任何异常
（缺 key / 网络失败 / 非 200 / 响应非法 JSON）包成 RuntimeError 抛出，
由调用方（cli.cmd_plan）打印原因并降级为 ManualAdapter 行为。
api_key 绝不落入日志、报告或提示词。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request


class ManualAdapter:
    """默认适配：导出提示词文件，人工粘贴给外部 LLM。"""

    name = "manual"

    def write_prompt(self, project_dir, chapter_no: int, prompt_md: str):
        """写 prompts/chapter_NNN.md 并打印指引。幂等（覆盖同名文件）。"""
        prompts_dir = project_dir / "prompts"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        path = prompts_dir / f"chapter_{chapter_no:03d}.md"
        path.write_text(prompt_md, encoding="utf-8")
        print(f"[manual] prompt written: {path}")
        print("[manual] please paste the prompt into ChatGPT desktop; "
              "then run: python -m novelwriter record <slug> "
              f"--chapter {chapter_no} --file <chapter-file>")
        return path


class ApiAdapter:
    """可选适配：OpenAI 兼容 /chat/completions（标准库 urllib，懒加载）。"""

    name = "api"

    def __init__(self, config: dict, timeout: int = 120):
        self.config = config or {}
        self.timeout = timeout

    def complete(self, prompt_md: str) -> str:
        """调用 API 返回正文文本；任何异常抛出，由 create_adapter 层降级。"""
        base_url = (self.config.get("base_url") or "").rstrip("/")
        api_key = self.config.get("api_key")
        model = self.config.get("model")
        if not base_url or not api_key or not model:
            raise RuntimeError("llm_api config incomplete: "
                               "need base_url / api_key / model")
        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt_md}],
        }).encode("utf-8")
        req = urllib.request.Request(
            base_url + "/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {api_key}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if getattr(resp, "status", 200) != 200:
                    raise RuntimeError(f"HTTP {resp.status}")
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"HTTP {exc.code}: {exc.reason}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError(f"network error: {exc}") from exc
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"invalid JSON response: {raw!r:.200}") from exc
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"unexpected API response: {data!r:.200}") from exc

    def write_prompt(self, project_dir, chapter_no: int, prompt_md: str):
        """调用 API；失败时抛出，交由调用方（cli.cmd_plan）降级处理。"""
        return self.complete(prompt_md)


def create_adapter(book_state: dict | None):
    """工厂：book.json 有完整 llm_api 配置时返回 ApiAdapter，
    否则（或任何异常）返回 ManualAdapter 并打印原因。懒加载。"""
    cfg = (book_state or {}).get("llm_api")
    if not cfg:
        return ManualAdapter()
    try:
        adapter = ApiAdapter(cfg)
        base_url = cfg.get("base_url")
        api_key = cfg.get("api_key")
        model = cfg.get("model")
        if not base_url or not api_key or not model:
            raise RuntimeError("llm_api config incomplete: "
                               "need base_url / api_key / model")
        return adapter
    except Exception as exc:  # 任何配置异常 → 降级
        print(f"[llm] fallback to ManualAdapter: {exc}")
        return ManualAdapter()
