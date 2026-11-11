# Open-Source-Court-Project（作り直し版）

AI の **弁護士・裁判官・陪審員** が、事件ファイルにもとづいて模擬裁判を行うプログラムです。
AI には Anthropic の Claude を使い、法廷でのやり取りはすべて日本語で行います。

> 元のアイデアは [starsitar/Open-Source-Court-Project](https://github.com/starsitar/Open-Source-Court-Project) です。
> 元のコードは動かない状態だったため、このフォークでは設計を引き継いでコードを全面的に書き直しています。

## できること

1. **事前審理** — 当事者の申し立て（例: 証拠の除外）を AI 裁判官が「認める／退ける」で判断します
2. **事前調査**（任意）— AI 弁護士が Web 検索で判例・法律・ルールを調べます
3. **冒頭陳述** — 原告側・被告側がそれぞれ立場を述べます
4. **争点ごとの弁論** — 主張 → 反論 → 再反論のあと、裁判官が論点を整理します
5. **最終弁論**
6. **陪審評議** — 視点の違う AI 陪審員が、互いの票を見ずに投票します
7. **判決** — 裁判官が主文と理由を書きます

やり取りはすべて画面に表示され、`transcripts/` に Markdown 形式で保存されます。

## 使い方

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...   # Anthropic の API キー

# サッカーの判定をめぐる裁判
python main.py examples/offside_dispute.json

# マンションの騒音トラブル。陪審員5人、Web で判例を調べさせる
python main.py examples/noise_dispute.json --jurors 5 --research

# API キーなし・料金なしで流れだけ確認する
python main.py examples/noise_dispute.json --dry-run
```

| オプション | 意味 |
|---|---|
| `--jurors N` | 陪審員の人数（既定 3。0 で陪審なし） |
| `--research` | 弁護士に Web 検索で事前調査をさせる |
| `--effort` | AI の考える深さ `low` / `medium`（既定）/ `high` / `xhigh` / `max` |
| `--model` | 使う Claude のモデル（既定 `claude-opus-5-5`） |
| `--out` | 法廷記録の保存先 |
| `--dry-run` | API を呼ばずにダミー応答で動かす |
| `--quiet` | 画面に記録を表示しない |

1 回の裁判で、AI を 20〜30 回ほど呼び出します（争点の数と陪審員の人数によって変わります）。
料金を抑えたいときは、争点を減らすか `--effort low` を使ってください。

## 事件ファイルの書き方

`examples/` の JSON をコピーして書き換えるのがいちばん簡単です。

```json
{
  "title": "事件名",
  "plaintiff": { "name": "訴える側", "claim": "訴える側の主張" },
  "defendant": { "name": "訴えられる側", "claim": "訴えられる側の主張" },
  "facts": ["事実1", "事実2"],
  "evidence": ["証拠1"],
  "rules": "判断の基準にする法律やルール（任意）",
  "aspects": ["争点1", "争点2"],
  "motions": [{ "by": "defendant", "text": "事前審理での申し立て（任意）" }]
}
```

必須なのは `title`・`plaintiff`・`defendant`・`facts`・`aspects` です。

## 他のプロジェクトで使う

```python
from court import Courtroom, LLM, load_case

case = load_case("examples/offside_dispute.json")
verdict = Courtroom(LLM(), case, jurors=3).run()
```

「複数の AI に立場を与えて議論させ、最後に中立の AI が判定する」という仕組みなので、
裁判以外（スポーツの判定、企画案の比較、ディベート練習など）にも使えます。

## ファイル構成

| ファイル | 役割 |
|---|---|
| `main.py` | コマンドラインの入口 |
| `court/case.py` | 事件ファイルの読み込み |
| `court/agents.py` | AI 弁護士・裁判官・陪審員 |
| `court/courtroom.py` | 裁判の進行と法廷記録 |
| `court/llm.py` | Claude API の呼び出し（Web 検索・構造化出力・ダミー応答） |

## 注意

これは学習・研究・遊び目的の **模擬裁判** です。出てくる判決に法的な効力はなく、
実際の法律相談の代わりにはなりません。
