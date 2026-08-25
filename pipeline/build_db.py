"""从 OCR JSON 裁剪每题截图（行归组 v2），识别章节与题号（含子题号），写入 SQLite。"""
import sys, io, os, json, re, sqlite3
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import pypdfium2 as pdfium

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
IMG = os.path.join(BASE, "images")
OCR_FILE = os.path.join(DATA, "ocr_linear_algebra.json")
DB = os.path.join(DATA, "math.db")
SCALE = 2.0
PAD_TOP = 40
PAD_BOTTOM = 50

NUMBER_RE = re.compile(r"【\s*(\d+)\s*[.．]\s*(\d+)\s*(?:[.．]\s*(\d+)\s*)?】")
FOOTER_RE = re.compile(r"第\s*\d+\s*页")
CHAPTER_RE = re.compile(r"^(\d+)\s*([\u4e00-\u9fff]{2,6})$")
HEADER_JUNK = ("邂逅遗憾", "公众号", "b站", "B站", "知乎", "小红书")

def find_chapter(lines, first_anchor_y):
    for l in lines:
        if l["y1"] >= first_anchor_y:
            break
        t = l["text"].strip()
        if any(j in t for j in HEADER_JUNK):
            continue
        m = CHAPTER_RE.match(t)
        if m:
            return int(m.group(1)), m.group(2)
        m2 = re.match(r"^第\s*(\d+)\s*章\s*([\u4e00-\u9fff]{2,6})$", t)
        if m2:
            return int(m2.group(1)), m2.group(2)
    return None, None

def parse_book(ocr):
    questions = []
    for pg in ocr["pages"]:
        pno = pg["page"]
        lines = pg["lines"]
        anchors = []
        for li, l in enumerate(lines):
            m = NUMBER_RE.search(l["text"])
            if m:
                anchors.append({"li": li, "c": int(m.group(1)), "q": int(m.group(2)),
                                "sub": int(m.group(3)) if m.group(3) else None, "line": l,
                                "variant": "修改版" in l["text"]})
        if not anchors:
            continue
        footer_y = None
        for l in lines:
            if FOOTER_RE.search(l["text"]):
                footer_y = min(footer_y, l["y0"]) if footer_y is not None else l["y0"]
        page_bottom = footer_y if footer_y is not None else pg["h"]
        chap_num, chap_title = find_chapter(lines, anchors[0]["line"]["y0"])

        groups = [[] for _ in anchors]
        anchor_ys = [a["line"]["y0"] for a in anchors]
        for li, l in enumerate(lines):
            if FOOTER_RE.search(l["text"]) or l["y0"] >= page_bottom:
                continue
            if any(a["li"] == li for a in anchors):
                continue
            y0, y1 = l["y0"], l["y1"]
            up = None
            for k, ay in enumerate(anchor_ys):
                if ay <= y0:
                    up = k
                else:
                    break
            if up is None:
                down = 0
                if anchor_ys[down] - y1 < 50:
                    groups[down].append(li)
                continue
            if up == len(anchors) - 1:
                groups[up].append(li)
                continue
            down = up + 1
            d_down = anchor_ys[down] - y0
            d_up = y0 - anchor_ys[up]
            if y1 >= anchor_ys[down] - 60 and d_down <= d_up:
                groups[down].append(li)
            else:
                groups[up].append(li)

        for k, a in enumerate(anchors):
            rows = [a["li"]] + groups[k]
            rows = list(dict.fromkeys(rows))
            top = a["line"]["y0"] - PAD_TOP
            bottom = a["line"]["y1"] + PAD_BOTTOM
            for r in rows:
                l = lines[r]
                top = min(top, l["y0"] - PAD_TOP)
                bottom = max(bottom, l["y1"] + PAD_BOTTOM)
            if k + 1 < len(anchors):
                bottom = min(bottom, anchors[k + 1]["line"]["y0"] - 60)
            else:
                bottom = min(bottom, page_bottom - 6)
            if bottom <= top:
                bottom = top + 60
            texts = [lines[r]["text"] for r in rows]
            num = f'{a["c"]}.{a["q"]}' + (f'.{a["sub"]}' if a["sub"] is not None else '') + ('（修改版）' if a["variant"] else '')
            questions.append({
                "page": pno, "chapter": chap_num, "chapter_title": chap_title,
                "num": num, "cnum": a["c"], "qnum": a["q"], "sub": a["sub"],
                "top": max(top, 0), "bottom": min(bottom, pg["h"]),
                "text": " ".join(texts),
            })
    return questions

def cut_images(ocr, questions):
    doc = pdfium.PdfDocument(ocr["pdf"])
    book_dir = os.path.join(IMG, "linear_algebra")
    os.makedirs(book_dir, exist_ok=True)
    for q in questions:
        page = doc[q["page"] - 1]
        bmp = page.render(scale=SCALE)
        img = bmp.to_pil()
        crop = img.crop((0, q["top"], img.width, q["bottom"]))
        fn = f'q_{q["num"].replace(".", "_")}.png'
        q["image"] = f"images/linear_algebra/{fn}"
        crop.save(os.path.join(BASE, q["image"]))
        q.pop("top"); q.pop("bottom")
    doc.close()

def init_db():
    con = sqlite3.connect(DB)
    con.executescript("""
    CREATE TABLE IF NOT EXISTS subjects (id INTEGER PRIMARY KEY, name TEXT UNIQUE);
    CREATE TABLE IF NOT EXISTS chapters (
        id INTEGER PRIMARY KEY, subject_id INTEGER, num INTEGER, title TEXT,
        UNIQUE(subject_id, num));
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY, subject_id INTEGER, chapter_id INTEGER,
        num TEXT, cnum INTEGER, qnum INTEGER, sub INTEGER, image TEXT, page INTEGER, text TEXT,
        UNIQUE(subject_id, num));
    CREATE TABLE IF NOT EXISTS attempts (
        question_id INTEGER PRIMARY KEY, status TEXT, note TEXT DEFAULT '',
        updated_at TEXT);
    """)
    return con

def main():
    with open(OCR_FILE, encoding="utf-8") as f:
        ocr = json.load(f)
    questions = parse_book(ocr)
    print(f"解析出 {len(questions)} 道题")
    cut_images(ocr, questions)
    con = init_db()
    con.execute("INSERT OR REPLACE INTO subjects (id, name) VALUES (1, '线性代数')")
    con.execute("DELETE FROM questions WHERE subject_id=1")
    for q in questions:
        chap = q["chapter"] or 0
        title = q["chapter_title"] or f"第{q['cnum']}章"
        row = con.execute("SELECT id FROM chapters WHERE subject_id=1 AND num=?", (chap,)).fetchone()
        if row:
            cid = row[0]
        else:
            cur = con.execute("INSERT INTO chapters (subject_id, num, title) VALUES (1, ?, ?)", (chap, title))
            cid = cur.lastrowid
        con.execute("""INSERT OR REPLACE INTO questions
            (subject_id, chapter_id, num, cnum, qnum, sub, image, page, text)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (cid, q["num"], q["cnum"], q["qnum"], q["sub"], q["image"], q["page"], q["text"]))
    con.commit()
    print("\n章节统计：")
    for row in con.execute("SELECT c.num, c.title, COUNT(*) FROM chapters c JOIN questions q ON q.chapter_id=c.id WHERE q.subject_id=1 GROUP BY c.id ORDER BY c.num"):
        print(f"  第{row[0]}章 {row[1]}: {row[2]} 题")
    print("子题:", [r[0] for r in con.execute("SELECT num FROM questions WHERE sub IS NOT NULL ORDER BY num")])
    con.close()
    print("DONE")

if __name__ == "__main__":
    main()
