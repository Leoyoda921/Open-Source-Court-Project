"""裁判全体の進行役。"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from .agents import Judge, Juror, Lawyer
from .case import Case


@dataclass
class Entry:
    speaker: str
    text: str
    section: bool = False  # True なら見出し（開廷・争点名など）


class Transcript:
    """法廷記録。発言のたびに Markdown ファイルへ追記し、画面にも表示する。"""

    def __init__(self, path: Path | None, echo: bool = True) -> None:
        self.entries: list[Entry] = []
        self.path = path
        self.echo = echo
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")

    def section(self, title: str) -> None:
        self._add(Entry("", title, section=True), f"\n## {title}\n")

    def say(self, speaker: str, text: str) -> None:
        self._add(Entry(speaker, text), f"\n**{speaker}**\n\n{text}\n")

    def _add(self, entry: Entry, markdown: str) -> None:
        self.entries.append(entry)
        if self.path:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(markdown)
        if self.echo:
            print(markdown, flush=True)

    def as_text(self) -> str:
        """AI に渡す用の記録文字列。"""
        parts = []
        for e in self.entries:
            parts.append(f"\n【{e.text}】" if e.section else f"{e.speaker}: {e.text}")
        return "\n\n".join(parts).strip()


def status(msg: str) -> None:
    print(f"… {msg}", file=sys.stderr, flush=True)


class Courtroom:
    def __init__(
        self,
        llm,
        case: Case,
        transcript_path: Path | None = None,
        jurors: int = 3,
        research: bool = False,
        echo: bool = True,
    ) -> None:
        self.case = case
        self.judge = Judge(llm, case)
        self.lawyers = {
            side: Lawyer(llm, case, side, research=research) for side in ("plaintiff", "defendant")
        }
        self.jurors = [Juror(llm, case, i + 1) for i in range(jurors)]
        self.research = research
        self.log = Transcript(transcript_path, echo=echo)

    def run(self) -> str:
        """裁判を最初から最後まで進め、判決文を返す。"""
        c = self.case
        self.log.section(f"開廷: {c.title}")
        self.log.say(self.judge.name, f"これより「{c.title}」の審理を始めます。")

        if c.motions and self._pretrial():
            return self._dismissed_verdict()

        if self.research:
            self.log.section("事前調査")
            for lawyer in self.lawyers.values():
                status(f"{lawyer.name}が Web で判例などを調べています")
                lawyer.prepare()
                self.log.say(lawyer.name, "事前調査を終えました（内容は本人のみ参照）。")

        P, D = self.lawyers["plaintiff"], self.lawyers["defendant"]

        self.log.section("冒頭陳述")
        self._speak(P, "冒頭陳述をしてください。事件の概要と、これから何を立証するかを述べてください。")
        self._speak(D, "冒頭陳述をしてください。原告の主張に対する基本的な立場を述べてください。")

        for aspect in c.aspects:
            self.log.section(f"争点: {aspect}")
            self._speak(P, f"争点「{aspect}」について主張してください。")
            self._speak(D, f"争点「{aspect}」について、原告の主張に反論しつつ主張してください。")
            self._speak(P, f"争点「{aspect}」について、被告の主張に短く再反論してください（300字程度）。")
            status(f"{self.judge.name}が争点「{aspect}」を整理しています")
            self.log.say(self.judge.name, self.judge.comment(self.log.as_text(), aspect))

        self.log.section("最終弁論")
        self._speak(P, "最終弁論をしてください。裁判官の指摘した疑問点にも答えてください。")
        self._speak(D, "最終弁論をしてください。裁判官の指摘した疑問点にも答えてください。")

        jury_text = self._jury()

        self.log.section("判決")
        status(f"{self.judge.name}が判決を書いています")
        verdict = self.judge.verdict(self.log.as_text(), jury_text)
        self.log.say(self.judge.name, verdict)
        self.log.say(self.judge.name, "以上で閉廷します。")
        return verdict

    def _speak(self, lawyer: Lawyer, task: str) -> None:
        status(f"{lawyer.name}が発言を準備しています")
        self.log.say(lawyer.name, lawyer.speak(self.log.as_text(), task))

    def _pretrial(self) -> bool:
        """事前審理。訴えの却下などで裁判が終わるなら True を返す。"""
        self.log.section("事前審理（申し立て）")
        for motion in self.case.motions:
            mover = self.lawyers[motion.by]
            other = self.lawyers["defendant" if motion.by == "plaintiff" else "plaintiff"]
            self.log.say(mover.name, f"申し立てます。{motion.text}")
            self._speak(other, f"相手方の申し立て「{motion.text}」に対して意見を述べてください（300字程度）。")
            status(f"{self.judge.name}が申し立てを判断しています")
            ruling = self.judge.rule_on_motion(self.log.as_text(), motion.text, mover.name)
            self.log.say(self.judge.name, f"申し立てを{ruling['decision']}。{ruling['reason']}")
            if ruling["decision"] == "認める" and ruling["ends_case"]:
                return True
        return False

    def _dismissed_verdict(self) -> str:
        msg = "事前審理での決定により、本件の審理はここで終了します。以上で閉廷します。"
        self.log.section("終局")
        self.log.say(self.judge.name, msg)
        return msg

    def _jury(self) -> str:
        if not self.jurors:
            return ""
        self.log.section("陪審評議")
        votes = {"原告": 0, "被告": 0}
        lines = []
        record = self.log.as_text()  # 陪審員どうしは互いの票を見ずに投票する
        for juror in self.jurors:
            status(f"{juror.name}が評議しています")
            result = juror.vote(record)
            votes[result["vote"]] += 1
            line = f"{result['vote']}を支持。{result['reason']}"
            lines.append(f"{juror.name}（{juror.persona}）: {line}")
            self.log.say(f"{juror.name}（{juror.persona}）", line)
        tally = f"集計: 原告支持 {votes['原告']} / 被告支持 {votes['被告']}"
        self.log.say("書記官", tally)
        return "\n".join(lines + [tally])
