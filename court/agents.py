"""AI 弁護士・裁判官・陪審員。

どのエージェントも「事件の説明」と「ここまでの法廷記録」を受け取って発言する。
"""

from __future__ import annotations

from .case import Case

COMMON_RULES = """\
- 日本語で、法廷での発言として書いてください。
- 事件ファイルにない事実を作らないでください。推測するときは推測だと明示してください。
- 見出しや箇条書きは最小限にし、1回の発言は400〜800字程度にまとめてください。"""


class Lawyer:
    def __init__(self, llm, case: Case, side: str, research: bool = False) -> None:
        self.llm = llm
        self.case = case
        self.side = side
        self.research = research
        self.client = case.party(side)
        self.opponent = case.party("defendant" if side == "plaintiff" else "plaintiff")
        self.name = f"{'原告' if side == 'plaintiff' else '被告'}代理人"
        self.notes = ""  # 事前調査のメモ（相手には見えない）

    @property
    def system(self) -> str:
        return f"""\
あなたは {self.client.name} の代理人を務める AI 弁護士です。
依頼人の主張: {self.client.claim}
相手方（{self.opponent.name}）の主張: {self.opponent.claim}

依頼人に有利な結論を、証拠と論理で説得力をもって主張してください。
ただし相手の強い論点を無視せず、正面から反論してください。
{COMMON_RULES}"""

    def prepare(self) -> str:
        """Web で判例やルールを調べ、主張の材料をメモにする。"""
        prompt = f"""{self.case.summary()}

この事件で依頼人の主張を支える判例・法律・ルール・前例を Web で調べ、
使えそうな論点を出典つきで箇条書きのメモにまとめてください。
不利な情報が見つかった場合も、反論の準備のために書いてください。"""
        self.notes = self.llm.ask(self.system, prompt, research=self.research)
        return self.notes

    def speak(self, transcript: str, task: str) -> str:
        notes = f"\n\n## あなたの事前調査メモ（相手には見えません）\n{self.notes}" if self.notes else ""
        prompt = f"""{self.case.summary()}{notes}

## ここまでの法廷記録
{transcript or "（まだ発言はありません）"}

## あなたの番です
{task}"""
        return self.llm.ask(self.system, prompt)


class Judge:
    name = "裁判官"

    def __init__(self, llm, case: Case) -> None:
        self.llm = llm
        self.case = case

    system = f"""\
あなたは公正で中立な AI 裁判官です。
どちらにも肩入れせず、証拠・論理・適用されるルールにもとづいて判断してください。
感情的な訴えや根拠のない主張は重視しないでください。
{COMMON_RULES}"""

    def rule_on_motion(self, transcript: str, motion_text: str, by_name: str) -> dict:
        prompt = f"""{self.case.summary()}

## ここまでの法廷記録
{transcript}

## 判断してほしい申し立て（{by_name}から）
{motion_text}

この申し立てを認めるか退けるかを決め、理由を述べてください。
認めた結果この裁判をこれ以上続ける必要がなくなる場合（例: 訴えの却下を認めた）だけ ends_case を true にしてください。"""
        schema = {
            "type": "object",
            "properties": {
                "decision": {"type": "string", "enum": ["認める", "退ける"]},
                "reason": {"type": "string"},
                "ends_case": {"type": "boolean"},
            },
            "required": ["decision", "reason", "ends_case"],
            "additionalProperties": False,
        }
        return self.llm.ask_json(self.system, prompt, schema)

    def comment(self, transcript: str, aspect: str) -> str:
        prompt = f"""{self.case.summary()}

## ここまでの法廷記録
{transcript}

## あなたの番です
争点「{aspect}」についての双方の主張を整理してください。
どちらの主張のどこが強く、どこが弱いかを指摘し、残っている疑問点があれば述べてください。
まだ最終的な結論は出さないでください。"""
        return self.llm.ask(self.system, prompt)

    def verdict(self, transcript: str, jury_text: str) -> str:
        prompt = f"""{self.case.summary()}

## 法廷記録
{transcript}

## 陪審員の評決（参考意見）
{jury_text or "（陪審なし）"}

## あなたの番です
判決を言い渡してください。次の形で書いてください。
1. 主文（どちらの主張を認めるか。一部だけ認める場合はその範囲）
2. 争点ごとの判断と理由
3. 陪審の意見をどう考慮したか（陪審がない場合は省略）
この判決は AI による模擬的なものであり、実際の法的効力はないことを最後に一文で添えてください。"""
        return self.llm.ask(self.system, prompt)


JUROR_PERSONAS = [
    "常識と生活感覚を大切にする会社員",
    "数字と証拠を重視するエンジニア",
    "立場の弱い側の事情にも目を向ける元教師",
    "ルールの文言を厳密に読む元公務員",
    "当事者どうしの関係修復を重く見る自営業者",
    "スポーツの審判経験があり、公平な手続きを重視する人",
]


class Juror:
    def __init__(self, llm, case: Case, number: int) -> None:
        self.llm = llm
        self.case = case
        self.persona = JUROR_PERSONAS[(number - 1) % len(JUROR_PERSONAS)]
        self.name = f"陪審員{number}"

    @property
    def system(self) -> str:
        return f"""\
あなたは AI 陪審員です。人物像: {self.persona}。
法廷記録だけを根拠に、どちらの主張がより納得できるかを自分の視点で判断してください。
理由は200〜400字の日本語で書いてください。"""

    def vote(self, transcript: str) -> dict:
        prompt = f"""{self.case.summary()}

## 法廷記録
{transcript}

原告（{self.case.plaintiff.name}）と被告（{self.case.defendant.name}）の
どちらを支持するか投票し、理由を述べてください。"""
        schema = {
            "type": "object",
            "properties": {
                "vote": {"type": "string", "enum": ["原告", "被告"]},
                "reason": {"type": "string"},
            },
            "required": ["vote", "reason"],
            "additionalProperties": False,
        }
        return self.llm.ask_json(self.system, prompt, schema)
