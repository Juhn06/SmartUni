"""Chạy bộ kiểm thử UniBot học viên, không ghi gì vào cơ sở dữ liệu.

Cách dùng:
  python eval_student_bot.py                 chạy cả bộ câu hỏi chung và bộ tình huống theo tài khoản
  python eval_student_bot.py general         chỉ bộ câu hỏi chung (eval_questions.json, tài khoản E2eMba)
  python eval_student_bot.py scenarios       chỉ bộ tình huống theo tài khoản (eval_scenarios.json)
  python eval_student_bot.py E2eMscm         chỉ các tình huống của một tài khoản
"""

from __future__ import annotations

import json
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

import student_bot as sb

ANSWERED = {"personal", "smart", "faq", "llm", "extractive"}
DATA = HERE / "data" / "student_kb"


def passed(expect, mode: str) -> bool:
    if isinstance(expect, list):
        return any(passed(e, mode) for e in expect)
    if expect == "answer":
        return mode in ANSWERED
    return mode == expect


def content_ok(case: dict, answer: str) -> tuple[bool, str]:
    low = answer.lower()
    missing = [m for m in case.get("must", []) if m.lower() not in low]
    if missing:
        return False, f"thiếu {missing}"
    if case.get("must_any") and not any(m.lower() in low for m in case["must_any"]):
        return False, f"thiếu một trong {case['must_any']}"
    banned = [m for m in case.get("must_not", []) if m.lower() in low]
    if banned:
        return False, f"có nội dung sai {banned}"
    return True, ""


def contexts(conn) -> dict:
    cache: dict = {}

    def get(login: str) -> dict:
        if login not in cache:
            row = conn.execute("SELECT id FROM user WHERE email = ?", (login,)).fetchone()
            ctx = sb.student_context(conn, row[0]) if row else None
            if not ctx:
                sys.exit(f"Tài khoản {login} chưa có hoặc chưa gắn hồ sơ học viên")
            cache[login] = ctx
        return cache[login]

    return get


def run(conn, cases: list[dict], visible: bool) -> list[dict]:
    get_ctx = contexts(conn)
    results = []
    for case in cases:
        ctx = get_ctx(case.get("account", "E2eMba"))
        question = sb.normalize_question(case["q"])
        lang = sb.question_lang(question)
        start = time.time()
        decision = sb.route(conn, ctx, question, lang)
        reply = sb.compose_reply(ctx, question, decision, lang) if visible else (decision.get("text") or "")
        conn.commit()
        took = time.time() - start
        expect = case.get("expect", "answer")
        route_ok = passed(expect, decision["mode"])
        checked = any(k in case for k in ("must", "must_any", "must_not"))
        fine, note = content_ok(case, reply) if checked else (True, "")
        good = route_ok and fine
        if not route_ok:
            note = f"hướng xử lý sai, mong đợi {expect}" + (f"; {note}" if note else "")
        shown = (reply or "(chuyển cán bộ)").replace("\n", " / ")
        tag = f"{case.get('account', 'E2eMba')} · {case['group']} · " if "group" in case else ""
        print(f"[{'ĐẠT' if good else 'SAI'}] {tag}{case['q']}" + (f"  ({note})" if note else ""))
        print(f"      bot chọn {decision['mode']}, {took:.1f}s: {shown[:240]}")
        results.append({**case, "route_ok": route_ok, "content_ok": fine, "checked": checked, "ok": good, "seconds": took})
    return results


def summary(title: str, results: list[dict]) -> None:
    if not results:
        return
    ok = sum(r["ok"] for r in results)
    route = sum(r["route_ok"] for r in results)
    checked = [r for r in results if r["checked"]]
    content = sum(r["content_ok"] for r in checked)
    print(f"\n{title}: {ok}/{len(results)} câu đạt hoàn toàn; {route}/{len(results)} đúng hướng xử lý; {content}/{len(checked)} đúng nội dung.")


def breakdown(results: list[dict], key: str, label: str) -> None:
    groups: dict = defaultdict(list)
    for r in results:
        groups[r.get(key, "")].append(r)
    print(f"  Theo {label}:")
    for name, rows in groups.items():
        ok = sum(r["ok"] for r in rows)
        print(f"    {name:<12} {ok}/{len(rows)}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"
    from e2e_pipeline import seed_e2e_pipeline

    with sqlite3.connect(HERE / "db" / "website.db", timeout=30) as seed_conn:
        seed_e2e_pipeline(seed_conn)
    conn = sqlite3.connect(HERE / "db" / "website.db", timeout=30)
    conn.row_factory = sqlite3.Row
    sb.ensure_tables(conn.cursor())
    conn.commit()
    general, scenarios = [], []
    if arg in ("all", "general"):
        print("=== Bộ câu hỏi chung (E2eMba) ===")
        cases = json.loads((DATA / "eval_questions.json").read_text(encoding="utf-8"))
        general = run(conn, cases, visible=False)
    if arg != "general":
        cases = json.loads((DATA / "eval_scenarios.json").read_text(encoding="utf-8"))
        if arg not in ("all", "scenarios"):
            cases = [c for c in cases if c["account"].lower() == arg.lower()]
            if not cases:
                sys.exit(f"Không có tình huống nào cho {arg}")
        print("\n=== Bộ tình huống theo tài khoản ===")
        scenarios = run(conn, cases, visible=True)
    summary("Bộ câu hỏi chung", general)
    summary("Bộ tình huống theo tài khoản", scenarios)
    if scenarios:
        breakdown(scenarios, "account", "tài khoản")
        breakdown(scenarios, "group", "nhóm tình huống")


if __name__ == "__main__":
    main()
