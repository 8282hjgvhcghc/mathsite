"""考研数学刷题本 - 本地 Flask 服务。"""
import os
import sqlite3
from flask import Flask, g, jsonify, request, send_from_directory

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "data", "math.db")
app = Flask(__name__, static_folder="static", static_url_path="/static")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


@app.get("/api/home")
def home():
    db = get_db()
    rows = db.execute("""
        SELECT s.id, s.name,
               COUNT(q.id) AS total,
               SUM(CASE WHEN a.status='correct' THEN 1 ELSE 0 END) AS correct,
               SUM(CASE WHEN a.status='wrong' THEN 1 ELSE 0 END) AS wrong
        FROM subjects s
        JOIN questions q ON q.subject_id = s.id
        LEFT JOIN attempts a ON a.question_id = q.id
        GROUP BY s.id ORDER BY s.id
    """).fetchall()
    chap_rows = db.execute("""
        SELECT c.subject_id, c.id, c.num AS cnum, c.title,
               COUNT(q.id) AS total,
               SUM(CASE WHEN a.status='correct' THEN 1 ELSE 0 END) AS correct,
               SUM(CASE WHEN a.status='wrong' THEN 1 ELSE 0 END) AS wrong
        FROM chapters c
        JOIN questions q ON q.chapter_id = c.id
        LEFT JOIN attempts a ON a.question_id = q.id
        GROUP BY c.id ORDER BY c.subject_id, c.num
    """).fetchall()
    chap_by_sub = {}
    for r in chap_rows:
        correct = r["correct"] or 0
        wrong = r["wrong"] or 0
        done = correct + wrong
        chap_by_sub.setdefault(r["subject_id"], []).append({
            "id": r["id"], "num": r["cnum"], "title": r["title"],
            "total": r["total"], "done": done, "correct": correct, "wrong": wrong,
            "accuracy": round(correct / done * 100, 1) if done else None,
        })
    subjects = []
    for r in rows:
        correct = r["correct"] or 0
        wrong = r["wrong"] or 0
        done = correct + wrong
        subjects.append({
            "id": r["id"], "name": r["name"], "total": r["total"],
            "done": done, "correct": correct, "wrong": wrong,
            "accuracy": round(correct / done * 100, 1) if done else None,
            "chapters": chap_by_sub.get(r["id"], []),
        })
    return jsonify({"subjects": subjects})


@app.get("/api/overview")
def overview():
    sid = request.args.get("subject", 1, type=int)
    db = get_db()
    chap_rows = db.execute("""
        SELECT c.id, c.num AS cnum, c.title,
               COUNT(q.id) AS total,
               SUM(CASE WHEN a.status='correct' THEN 1 ELSE 0 END) AS correct,
               SUM(CASE WHEN a.status='wrong' THEN 1 ELSE 0 END) AS wrong
        FROM chapters c
        JOIN questions q ON q.chapter_id = c.id AND q.subject_id = ?
        LEFT JOIN attempts a ON a.question_id = q.id
        GROUP BY c.id ORDER BY c.num
    """, (sid,)).fetchall()
    sec_rows = db.execute("""
        SELECT s.id, s.num AS snum, s.title, s.chapter_id,
               COUNT(q.id) AS total,
               SUM(CASE WHEN a.status='correct' THEN 1 ELSE 0 END) AS correct,
               SUM(CASE WHEN a.status='wrong' THEN 1 ELSE 0 END) AS wrong
        FROM sections s
        JOIN questions q ON q.section_id = s.id AND q.subject_id = ?
        LEFT JOIN attempts a ON a.question_id = q.id
        GROUP BY s.id
    """, (sid,)).fetchall()

    def sec_key(r):
        s = r["snum"] or ""
        if "." in s:
            a, b = s.split(".", 1)
            try:
                return (int(a), int(b))
            except ValueError:
                return (int(a), 999)
        if s.isdigit():
            return (int(s), 0)
        return (9999, 0)

    sec_rows = sorted(sec_rows, key=sec_key)
    q_rows = db.execute("""
        SELECT q.id, q.num, q.section_id, a.status
        FROM questions q LEFT JOIN attempts a ON a.question_id = q.id
        WHERE q.subject_id = ? ORDER BY q.section_id, q.qnum, COALESCE(q.sub, 0), q.num
    """, (sid,)).fetchall()
    chapters = []
    tot = cor = wro = 0
    for r in chap_rows:
        correct = r["correct"] or 0
        wrong = r["wrong"] or 0
        done = correct + wrong
        tot += r["total"]; cor += correct; wro += wrong
        chapters.append({
            "id": r["id"], "num": r["cnum"], "title": r["title"],
            "total": r["total"], "done": done, "correct": correct, "wrong": wrong,
            "accuracy": round(correct / done * 100, 1) if done else None,
            "sections": [],
        })
    by_cid = {c["id"]: c for c in chapters}
    sec_qmap = {}
    for r in q_rows:
        sec_qmap.setdefault(r["section_id"], []).append(
            {"id": r["id"], "num": r["num"], "status": r["status"]})
    for r in sec_rows:
        c = by_cid.get(r["chapter_id"])
        if not c:
            continue
        correct = r["correct"] or 0
        wrong = r["wrong"] or 0
        done = correct + wrong
        c["sections"].append({
            "id": r["id"], "num": r["snum"], "title": r["title"],
            "total": r["total"], "done": done, "correct": correct, "wrong": wrong,
            "accuracy": round(correct / done * 100, 1) if done else None,
            "questions": sec_qmap.get(r["id"], []),
        })
    done = cor + wro
    name = db.execute("SELECT name FROM subjects WHERE id=?", (sid,)).fetchone()
    return jsonify({
        "subject_id": sid,
        "subject": name["name"] if name else "",
        "total": tot, "done": done, "correct": cor, "wrong": wro,
        "accuracy": round(cor / done * 100, 1) if done else None,
        "chapters": chapters,
    })


@app.get("/api/section/<int:sid>")
def section(sid):
    db = get_db()
    rows = db.execute("""
        SELECT q.id, q.num, q.image, q.page, q.subject_id, a.status, a.updated_at
        FROM questions q LEFT JOIN attempts a ON a.question_id = q.id
        WHERE q.section_id = ? ORDER BY q.qnum, COALESCE(q.sub, 0), q.num
    """, (sid,)).fetchall()
    return jsonify([dict(r) for r in rows])


@app.post("/api/attempt")
def attempt():
    data = request.get_json(force=True)
    qid = int(data["question_id"])
    status = data.get("status")
    db = get_db()
    if status in ("correct", "wrong"):
        db.execute("""INSERT INTO attempts (question_id, status, note, updated_at)
                      VALUES (?, ?, '', datetime('now','localtime'))
                      ON CONFLICT(question_id) DO UPDATE SET status=excluded.status,
                      note='', updated_at=excluded.updated_at""", (qid, status))
    else:
        db.execute("DELETE FROM attempts WHERE question_id = ?", (qid,))
    db.commit()
    return jsonify({"ok": True})


@app.get("/api/weekly")
def weekly():
    db = get_db()
    rows = db.execute("""
        SELECT w.id, w.name, w.date, w.subject,
               COUNT(q.id) AS total,
               SUM(CASE WHEN a.status='correct' THEN 1 ELSE 0 END) AS correct,
               SUM(CASE WHEN a.status='wrong' THEN 1 ELSE 0 END) AS wrong
        FROM weekly_tests w
        JOIN questions q ON q.weekly_test_id = w.id
        LEFT JOIN attempts a ON a.question_id = q.id
        GROUP BY w.id ORDER BY w.date DESC, w.id DESC
    """).fetchall()
    items = []
    for r in rows:
        correct = r["correct"] or 0
        wrong = r["wrong"] or 0
        done = correct + wrong
        items.append({
            "id": r["id"], "name": r["name"], "date": r["date"], "subject": r["subject"],
            "total": r["total"], "done": done, "correct": correct, "wrong": wrong,
            "accuracy": round(correct / done * 100, 1) if done else None,
        })
    return jsonify(items)


@app.get("/api/weekly/<int:tid>")
def weekly_test(tid):
    db = get_db()
    test = db.execute("SELECT * FROM weekly_tests WHERE id=?", (tid,)).fetchone()
    if not test:
        return ("not found", 404)
    rows = db.execute("""
        SELECT q.id, q.num, q.image, q.page, q.subject_id, a.status, a.updated_at
        FROM questions q LEFT JOIN attempts a ON a.question_id = q.id
        WHERE q.weekly_test_id = ? ORDER BY q.qnum, COALESCE(q.sub, 0), q.num
    """, (tid,)).fetchall()
    return jsonify({"test": dict(test), "items": [dict(r) for r in rows]})


@app.get("/api/wrong")
def wrong():
    db = get_db()
    rows = db.execute("""
        SELECT q.id, q.num, q.image, q.page, s.name AS subject_name,
               c.title AS chapter_title, c.num AS cnum,
               sec.title AS section_title, w.name AS weekly_name, a.updated_at
        FROM attempts a JOIN questions q ON q.id = a.question_id
        LEFT JOIN subjects s ON s.id = q.subject_id
        LEFT JOIN chapters c ON c.id = q.chapter_id
        LEFT JOIN sections sec ON sec.id = q.section_id
        LEFT JOIN weekly_tests w ON w.id = q.weekly_test_id
        WHERE a.status = 'wrong' ORDER BY a.updated_at DESC
    """).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/images/<path:fn>")
def images(fn):
    return send_from_directory(os.path.join(BASE, "images"), fn)


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
