"""Claude API の呼び出しをまとめたモジュール。

各エージェント（弁護士・裁判官・陪審員）はここの LLM クラスだけを使う。
API キーなしで流れを確認できるよう、ダミー応答を返す MockLLM も用意している。
"""

from __future__ import annotations

import json
from typing import Any

DEFAULT_MODEL = "claude-opus-5-5"

# 安全フィルタで断られたとき、サーバー側で自動的に別モデルへ切り替える機能
FALLBACK_BETA = "server-side-fallback-2026-07-01"

WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search", "max_uses": 3}

# Web 検索が長引くと応答が途中で一時停止（pause_turn）するので、続きを取りに行く上限回数
MAX_CONTINUATIONS = 5


class LLMError(RuntimeError):
    """AI から有効な応答が得られなかったときの例外。"""


class LLM:
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        effort: str = "medium",
        max_tokens: int = 32000,
        client: Any = None,
    ) -> None:
        if client is None:
            import anthropic

            client = anthropic.Anthropic()
        self.client = client
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens

    def ask(self, system: str, prompt: str, research: bool = False) -> str:
        """文章で答えさせる。research=True なら Web 検索を使わせる。"""
        tools = [WEB_SEARCH_TOOL] if research else None
        return self._run(system, prompt, tools=tools)

    def ask_json(self, system: str, prompt: str, schema: dict) -> dict:
        """JSON スキーマどおりの形で答えさせる（評決・裁定など）。"""
        text = self._run(
            system,
            prompt,
            output_format={"type": "json_schema", "schema": schema},
        )
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise LLMError(f"JSON として読めない応答が返りました: {text[:200]}") from e

    def _run(
        self,
        system: str,
        prompt: str,
        tools: list | None = None,
        output_format: dict | None = None,
    ) -> str:
        messages: list[dict] = [{"role": "user", "content": prompt}]
        output_config: dict = {"effort": self.effort}
        if output_format:
            output_config["format"] = output_format

        texts: list[str] = []
        for _ in range(MAX_CONTINUATIONS):
            kwargs: dict = dict(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                messages=messages,
                thinking={"type": "adaptive"},
                output_config=output_config,
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
            if tools:
                kwargs["tools"] = tools
            with self.client.beta.messages.stream(**kwargs) as stream:
                response = stream.get_final_message()

            texts.extend(b.text for b in response.content if b.type == "text")

            if response.stop_reason == "pause_turn":
                # 応答をそのまま戻すと、サーバーが続きから再開する
                messages = messages + [{"role": "assistant", "content": response.content}]
                continue
            if response.stop_reason == "refusal":
                detail = getattr(response, "stop_details", None)
                reason = getattr(detail, "explanation", None) or "理由不明"
                raise LLMError(f"AI が回答を断りました: {reason}")
            if response.stop_reason == "max_tokens":
                texts.append("\n（※ 文字数の上限に達したため、ここで途切れています）")
            break

        text = "".join(texts).strip()
        if not text:
            raise LLMError("AI から空の応答が返りました。")
        return text


class MockLLM:
    """API を呼ばずに決まった文を返す。動作確認（--dry-run）用。"""

    def __init__(self) -> None:
        self.calls = 0

    def ask(self, system: str, prompt: str, research: bool = False) -> str:
        self.calls += 1
        first_line = system.strip().splitlines()[0]
        tag = "（Web調査あり）" if research else ""
        return f"[ダミー応答 #{self.calls}{tag}] {first_line}"

    def ask_json(self, system: str, prompt: str, schema: dict) -> dict:
        self.calls += 1
        return _dummy_from_schema(schema, self.calls)


def _dummy_from_schema(schema: dict, n: int) -> Any:
    t = schema.get("type")
    if "enum" in schema:
        return schema["enum"][n % len(schema["enum"])]
    if t == "object":
        return {k: _dummy_from_schema(v, n) for k, v in schema.get("properties", {}).items()}
    if t == "array":
        return [_dummy_from_schema(schema.get("items", {}), n)]
    if t == "boolean":
        return False  # ends_case などは常に False（最後まで流れを確認できるように）
    if t in ("integer", "number"):
        return n
    return f"ダミー理由 #{n}"
