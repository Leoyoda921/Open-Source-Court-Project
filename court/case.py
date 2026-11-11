"""事件（ケース）の定義と JSON ファイルからの読み込み。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

SIDES = ("plaintiff", "defendant")


@dataclass
class Party:
    name: str
    claim: str


@dataclass
class Motion:
    by: str  # "plaintiff" か "defendant"
    text: str


@dataclass
class Case:
    title: str
    plaintiff: Party
    defendant: Party
    facts: list[str]
    aspects: list[str]
    evidence: list[str] = field(default_factory=list)
    rules: str = ""
    motions: list[Motion] = field(default_factory=list)

    def party(self, side: str) -> Party:
        return self.plaintiff if side == "plaintiff" else self.defendant

    def summary(self) -> str:
        """全員が共有する事件の説明文。"""
        lines = [
            f"# 事件名: {self.title}",
            f"- 原告: {self.plaintiff.name} — 主張: {self.plaintiff.claim}",
            f"- 被告: {self.defendant.name} — 主張: {self.defendant.claim}",
            "",
            "## 事実関係",
            *[f"- {f}" for f in self.facts],
        ]
        if self.evidence:
            lines += ["", "## 証拠", *[f"- {e}" for e in self.evidence]]
        if self.rules:
            lines += ["", "## 判断の基準とするルール・法律", self.rules]
        lines += ["", "## 争点", *[f"- {a}" for a in self.aspects]]
        return "\n".join(lines)


def load_case(path: str | Path) -> Case:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    try:
        motions = [Motion(**m) for m in data.get("motions", [])]
        for m in motions:
            if m.by not in SIDES:
                raise ValueError(f'motions の by は "plaintiff" か "defendant" にしてください: {m.by}')
        case = Case(
            title=data["title"],
            plaintiff=Party(**data["plaintiff"]),
            defendant=Party(**data["defendant"]),
            facts=list(data["facts"]),
            aspects=list(data["aspects"]),
            evidence=list(data.get("evidence", [])),
            rules=data.get("rules", ""),
            motions=motions,
        )
    except KeyError as e:
        raise ValueError(f"事件ファイルに必須項目がありません: {e}") from e
    if not case.aspects:
        raise ValueError("aspects（争点）を1つ以上書いてください。")
    return case
