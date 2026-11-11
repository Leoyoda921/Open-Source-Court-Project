"""コマンドラインから模擬裁判を実行する。

例:
    python main.py examples/offside_dispute.json
    python main.py examples/noise_dispute.json --jurors 5 --research
    python main.py examples/noise_dispute.json --dry-run   # API キーなしで流れだけ確認
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from court import Courtroom, LLM, LLMError, MockLLM, load_case
from court.llm import DEFAULT_MODEL


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="AI 弁護士・裁判官・陪審員による模擬裁判")
    p.add_argument("case", help="事件ファイル（JSON）のパス")
    p.add_argument("--jurors", type=int, default=3, help="陪審員の人数（0 で陪審なし。既定: 3）")
    p.add_argument("--research", action="store_true", help="弁護士に Web で判例などを調べさせる")
    p.add_argument("--out", help="法廷記録の保存先（既定: transcripts/日時_事件ファイル名.md）")
    p.add_argument("--model", default=DEFAULT_MODEL, help=f"使う Claude のモデル（既定: {DEFAULT_MODEL}）")
    p.add_argument(
        "--effort",
        default="medium",
        choices=["low", "medium", "high", "xhigh", "max"],
        help="AI がどれだけ深く考えるか（既定: medium。上げるほど丁寧だが遅く高くなる）",
    )
    p.add_argument("--dry-run", action="store_true", help="API を呼ばずにダミー応答で流れだけ確認する")
    p.add_argument("--quiet", action="store_true", help="画面に法廷記録を表示しない")
    args = p.parse_args(argv)

    if args.jurors < 0:
        p.error("--jurors は 0 以上にしてください")

    try:
        case = load_case(args.case)
    except (OSError, ValueError) as e:
        print(f"事件ファイルを読めませんでした: {e}", file=sys.stderr)
        return 2

    out = Path(args.out) if args.out else Path("transcripts") / (
        f"{datetime.now():%Y%m%d_%H%M%S}_{Path(args.case).stem}.md"
    )
    llm = MockLLM() if args.dry_run else LLM(model=args.model, effort=args.effort)

    court = Courtroom(
        llm,
        case,
        transcript_path=out,
        jurors=args.jurors,
        research=args.research,
        echo=not args.quiet,
    )
    try:
        court.run()
    except LLMError as e:
        print(f"\n裁判を続けられませんでした: {e}", file=sys.stderr)
        print(f"途中までの記録: {out}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001 - API エラーを日本語で案内するため
        msg = _api_error_message(e)
        if msg is None:
            raise
        print(f"\n{msg}", file=sys.stderr)
        print(f"途中までの記録: {out}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print(f"\n中断しました。途中までの記録: {out}", file=sys.stderr)
        return 130

    print(f"\n法廷記録を保存しました: {out}", file=sys.stderr)
    return 0


def _api_error_message(e: Exception) -> str | None:
    try:
        import anthropic
    except ImportError:
        return None
    if isinstance(e, anthropic.AuthenticationError):
        return "API キーが無効です。環境変数 ANTHROPIC_API_KEY を確認してください。"
    if isinstance(e, anthropic.RateLimitError):
        return "API の利用上限に達しました。しばらく待ってから再実行してください。"
    if isinstance(e, anthropic.APIStatusError):
        return f"API がエラーを返しました（{e.status_code}）: {e.message}"
    if isinstance(e, anthropic.APIConnectionError):
        return "API に接続できませんでした。ネットワークを確認してください。"
    if isinstance(e, TypeError) and "api_key" in str(e):
        return "API キーが見つかりません。環境変数 ANTHROPIC_API_KEY を設定してください。"
    return None


if __name__ == "__main__":
    sys.exit(main())
