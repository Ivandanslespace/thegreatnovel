"""可选行动的编译与执行适配器。

实际规则仍由 :class:`GameEngine` 负责；该薄层让主持器和测试可以明确
区分“生成候选”与“读取已保存契约”。
"""

from __future__ import annotations

from typing import Any, Mapping


class OptionCompiler:
    def __init__(self, engine):
        self.engine = engine

    def compile(self, candidates: list[Mapping[str, Any]], *, persist: bool = True):
        return self.engine.compile_options(candidates, persist=persist)

    compile_candidates = compile

    def present(self, candidates: list[Mapping[str, Any]], *, persist: bool = True):
        result = self.compile(candidates, persist=persist)
        return result["options"]

    def preview(self, option_id: str):
        return self.engine.preview_player_choice(option_id)

    def execute(self, option_id: str, *, persist: bool = True):
        return self.engine.execute_player_choice(option_id, persist=persist)


class OptionDirector(OptionCompiler):
    """兼容主持器语义的命名：导演只负责候选编排，规则仍在编译器。"""
