"""Live class activities: quick votes and short answers, shown on the class screen.

Nothing here is stored in the database. Each running session holds at most one
activity in memory; it disappears when the teacher ends it, closes the session
or the server restarts. Run a single worker (the default in the Docker image).
"""

import re
import threading
import time
import unicodedata
from dataclasses import dataclass, field

KINDS = ("vote", "text")
CHARTS = ("bar", "pie")
MAX_OPTIONS = 8
MAX_OPTION_LEN = 80
MAX_QUESTION_LEN = 200
MAX_ANSWER_LEN = 60
MAX_ANSWERS_PER_STUDENT = 3

_ZERO_WIDTH = re.compile("[​-‍⁠﻿]")
_DIGITS = re.compile(r"\d+")


@dataclass
class Activity:
    id: int
    kind: str
    question: str
    options: list[str]
    chart: str = "bar"
    open: bool = True
    started_at: float = field(default_factory=time.time)
    votes: dict[str, int] = field(default_factory=dict)            # email -> option index
    answers: dict[str, list[str]] = field(default_factory=dict)    # email -> answers, oldest first
    rev: int = 0                                                   # bumped on every change

    def results(self) -> dict:
        """What the class screen shows. Anonymous: no emails or names.

        Short answers come back as raw `_texts`; `finish()` groups them outside the lock.
        """
        data = {"id": self.id, "rev": self.rev, "kind": self.kind, "question": self.question, "chart": self.chart,
                "open": self.open, "people": len(self.votes) if self.kind == "vote" else len(self.answers)}
        if self.kind == "vote":
            counts = [0] * len(self.options)
            for i in self.votes.values():
                counts[i] += 1
            data["options"] = [{"label": o, "count": c} for o, c in zip(self.options, counts)]
            data["total"] = sum(counts)
        else:
            data["_texts"] = [a for answers in self.answers.values() for a in answers]
        return data

    def for_student(self, email: str) -> dict:
        data = {"id": self.id, "kind": self.kind, "question": self.question, "open": self.open}
        if self.kind == "vote":
            data["options"] = self.options
            data["mine"] = self.votes.get(email)
        else:
            data["mine"] = list(self.answers.get(email, []))
            data["max_answers"] = MAX_ANSWERS_PER_STUDENT
            data["max_len"] = MAX_ANSWER_LEN
        return data


class LiveStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._activities: dict[int, Activity] = {}
        self._ended: set[int] = set()
        self._seq = 0

    def start(self, session_id: int, kind: str, question: str, options: list[str], chart: str = "bar") -> dict:
        if kind not in KINDS:
            raise ValueError("Unknown activity type.")
        question = " ".join(question.split())[:MAX_QUESTION_LEN]  # optional: the teacher may just ask aloud
        options = [" ".join(o.split())[:MAX_OPTION_LEN] for o in options]
        options = [o for o in options if o][:MAX_OPTIONS]
        if kind == "vote" and len(options) < 2:
            raise ValueError("A vote needs at least two choices.")
        with self._lock:
            self._seq += 1
            act = Activity(self._seq, kind, question, options if kind == "vote" else [],
                           chart if chart in CHARTS else "bar")
            self._activities[session_id] = act
            self._ended.discard(session_id)
            data = act.results()
        return finish(data)

    def results(self, session_id: int) -> dict | None:
        with self._lock:
            act = self._activities.get(session_id)
            data = act.results() if act else None
        return finish(data)

    def update(self, session_id: int, *, open: bool | None = None, chart: str | None = None) -> dict | None:
        with self._lock:
            act = self._activities.get(session_id)
            if act is None:
                return None
            if open is not None:
                act.open = open
            if chart in CHARTS:
                act.chart = chart
            act.rev += 1
            data = act.results()
        return finish(data)

    def stop(self, session_id: int) -> None:
        """The teacher ended the activity; students go back to waiting."""
        with self._lock:
            self._activities.pop(session_id, None)

    def end_session(self, session_id: int) -> None:
        with self._lock:
            self._activities.pop(session_id, None)
            self._ended.add(session_id)

    def for_student(self, session_id: int, email: str) -> dict:
        with self._lock:
            if session_id in self._ended:
                return {"ended": True}
            act = self._activities.get(session_id)
            return {"activity": act.for_student(email) if act else None}

    def vote(self, session_id: int, activity_id: int, email: str, option: int) -> dict:
        with self._lock:
            act = self._check(session_id, activity_id, "vote")
            if not 0 <= option < len(act.options):
                raise ValueError("Unknown choice.")
            act.votes[email] = option
            act.rev += 1
            data = act.results()
        return finish(data)

    def answer(self, session_id: int, activity_id: int, email: str, text: str) -> dict:
        text = _ZERO_WIDTH.sub("", " ".join(text.split()))[:MAX_ANSWER_LEN].strip()
        if not text:
            raise ValueError("Type an answer first.")
        with self._lock:
            act = self._check(session_id, activity_id, "text")
            mine = act.answers.setdefault(email, [])
            if len(mine) >= MAX_ANSWERS_PER_STUDENT:
                raise ValueError("You have sent the most answers allowed.")
            mine.append(text)
            act.rev += 1
            data = act.results()
        return finish(data)

    def _check(self, session_id: int, activity_id: int, kind: str) -> Activity:
        act = self._activities.get(session_id)
        if act is None or act.id != activity_id or act.kind != kind:
            raise ValueError("This question has ended.")
        if not act.open:
            raise ValueError("Answers are closed.")
        return act


def finish(data: dict | None) -> dict | None:
    """Group short answers (slow with many answers) after the lock is released."""
    if data is not None and "_texts" in data:
        texts = data.pop("_texts")
        data["groups"] = group_answers(texts)
        data["total"] = len(texts)
    return data


# --- Grouping short answers -------------------------------------------------

def normalize(text: str) -> str:
    """Comparison key: case, width, spacing and punctuation don't matter.

    Thai has no spaces between words, so the whole answer is the unit and
    spaces are dropped from the key altogether.
    """
    text = _ZERO_WIDTH.sub("", unicodedata.normalize("NFKC", text)).casefold()
    text = "".join(" " if unicodedata.category(ch).startswith("P") else ch for ch in text)
    return "".join(text.split())


def _within(a: str, b: str, limit: int) -> bool:
    """Levenshtein distance(a, b) <= limit, stopping early."""
    if abs(len(a) - len(b)) > limit:
        return False
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        if min(cur) > limit:
            return False
        prev = cur
    return prev[-1] <= limit


def _similar(a: str, b: str) -> bool:
    """Conservative fuzzy match for typos and plurals ("resistor" ~ "resistors").

    Opposites built with a prefix ("stable"/"unstable", "เป็นไปได้"/"เป็นไปไม่ได้") stay apart:
    the first character must match and only one or two letters may differ.
    """
    if min(len(a), len(b)) < 5 or a[0] != b[0]:
        return False
    if _DIGITS.findall(a) != _DIGITS.findall(b):
        return False  # "5V" and "9V" are different answers
    return _within(a, b, 1 if min(len(a), len(b)) < 10 else 2)


def group_answers(texts: list[str]) -> list[dict]:
    """Group similar answers. Each group is labelled with its most common wording.

    Returns [{"text", "count"}] with the largest group first.
    """
    exact: dict[str, dict[str, int]] = {}
    for t in texts:
        key = normalize(t)
        if key:
            forms = exact.setdefault(key, {})
            forms[t] = forms.get(t, 0) + 1

    # Merge near-identical keys into the bigger group, biggest first.
    keys = sorted(exact, key=lambda k: -sum(exact[k].values()))
    groups: list[tuple[str, dict[str, int]]] = []
    for key in keys:
        for gkey, forms in groups:
            if _similar(key, gkey):
                for form, n in exact[key].items():
                    forms[form] = forms.get(form, 0) + n
                break
        else:
            groups.append((key, dict(exact[key])))

    out = []
    for _key, forms in groups:
        label = max(forms.items(), key=lambda kv: (kv[1], -len(kv[0])))[0]
        out.append({"text": label, "count": sum(forms.values())})
    out.sort(key=lambda g: (-g["count"], g["text"]))
    return out
