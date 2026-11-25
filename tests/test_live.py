import re

from app.live import LiveStore, group_answers, normalize
from tests.test_app import STUDENT, TEACHER, app, client, csrf, login, start_session  # noqa: F401


def test_normalize_ignores_case_spacing_and_punctuation():
    assert normalize("  Ohm's  Law! ") == normalize("ohms law") == "ohmslaw"
    assert normalize("กฎของโอห์ม") == normalize("กฎ ของ โอห์ม")
    assert normalize("ＡＢＣ") == "abc"  # full-width


def test_group_answers():
    texts = ["Ohm's law", "ohms law", "Ohm law", "OHMS LAW", "resistor", "resistors", "5V", "9V", "กฎของโอห์ม",
             "กฎ ของโอห์ม", "C++", "c"]
    groups = {g["text"]: g["count"] for g in group_answers(texts)}
    assert sum(groups.values()) == len(texts)
    ohm = [g for g in group_answers(texts) if "law" in g["text"].lower()]
    assert len(ohm) == 1 and ohm[0]["count"] == 4
    assert any(c == 2 and t.startswith("resistor") for t, c in groups.items())
    assert groups["5V"] == 1 and groups["9V"] == 1          # different numbers stay apart
    assert sum(c for t, c in groups.items() if "โอห์ม" in t) == 2
    assert groups["C++"] == 1 and groups["c"] == 1          # short answers are never fuzzy-merged
    assert group_answers([]) == []


def test_opposites_and_typos():
    def merged(a, b):
        return len(group_answers([a, b])) == 1
    for a, b in [("stable", "unstable"), ("correct", "incorrect"), ("symmetric", "asymmetric"),
                 ("possible", "impossible"), ("เป็นไปได้", "เป็นไปไม่ได้"), ("increase", "decrease"), ("5V", "9V")]:
        assert not merged(a, b), (a, b)
    for a, b in [("resistor", "resistors"), ("Thevenin", "Thevenim"), ("capacitor", "capasitor"),
                 ("superposition", "superpositon"), ("Kirchhoff", "Kirchoff")]:
        assert merged(a, b), (a, b)


def test_store_vote_and_limits():
    store = LiveStore()
    r = store.start(1, "vote", "Pick one", ["A", "B", " ", "C"])
    assert [o["label"] for o in r["options"]] == ["A", "B", "C"]
    store.vote(1, r["id"], "a@x", 0)
    store.vote(1, r["id"], "a@x", 2)  # changing a vote replaces it
    r = store.vote(1, r["id"], "b@x", 2)
    assert [o["count"] for o in r["options"]] == [0, 0, 2] and r["people"] == 2
    store.update(1, open=False)
    try:
        store.vote(1, r["id"], "c@x", 0)
        raise AssertionError("closed vote accepted")
    except ValueError:
        pass
    t = store.start(1, "text", "One word", [])
    for i in range(3):
        store.answer(1, t["id"], "a@x", f"word {i}")
    try:
        store.answer(1, t["id"], "a@x", "too many")
        raise AssertionError("fourth answer accepted")
    except ValueError:
        pass
    store.end_session(1)
    assert store.for_student(1, "a@x") == {"ended": True}


def test_live_flow(app):  # noqa: F811
    with client(app) as t:
        login(app, t, TEACHER, "Dr Teacher")
        sid, _ = start_session(app, t)
        h = {"X-CSRF-Token": csrf(t, "/attendance/")}
        info = t.get(f"/attendance/sessions/{sid}/live").json()
        assert info["activity"] is None and "<svg" in info["join_qr"]
        join = re.sub(r"^http://testserver", "", info["join_url"])

        r = t.post(f"/attendance/sessions/{sid}/live", headers=h,
                   data={"kind": "vote", "question": "Best?", "option": ["Red", "Blue"], "chart": "pie"})
        act = r.json()["activity"]
        assert act["chart"] == "pie" and act["total"] == 0

        with client(app) as s:
            assert "Sign in" in s.get(join).text
            login(app, s, STUDENT)
            assert "live.js" in s.get(join).text
            assert s.get(join[:-2] + "zz/poll").status_code == 404
            view = s.get(join + "/poll").json()["activity"]
            assert view["options"] == ["Red", "Blue"] and view["mine"] is None
            sh = {"X-CSRF-Token": re.search(r'data-csrf="([^"]+)"', s.get(join).text).group(1)}
            assert s.post(join + "/vote", headers=sh, data={"activity": act["id"], "option": 1}).json()["activity"]["mine"] == 1
            res = t.get(f"/attendance/sessions/{sid}/live").json()["activity"]
            assert [o["count"] for o in res["options"]] == [0, 1]
            assert STUDENT not in str(res)  # the screen is anonymous

            # Short answers, grouped
            r = t.post(f"/attendance/sessions/{sid}/live", headers=h, data={"kind": "text", "question": "One word?"})
            act = r.json()["activity"]
            s.post(join + "/answer", headers=sh, data={"activity": act["id"], "text": "Voltage"})
            s.post(join + "/answer", headers=sh, data={"activity": act["id"], "text": "voltage!"})
            res = t.get(f"/attendance/sessions/{sid}/live").json()["activity"]
            assert res["groups"] == [{"text": "Voltage", "count": 2}]

            # Students can't drive the teacher controls.
            assert s.post(f"/attendance/sessions/{sid}/live/stop", headers=sh).status_code == 403

            t.post(f"/attendance/sessions/{sid}/close", data={"csrf": h["X-CSRF-Token"]})
            assert s.get(join + "/poll").json() == {"ended": True}
