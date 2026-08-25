"""高数做题本：OCR JSON -> 裁剪每题截图 -> 章节/小节映射 -> 入库。"""
import sys, io, os, json, re, sqlite3
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import pypdfium2 as pdfium

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
IMG = os.path.join(BASE, "images")
OCR_FILE = os.path.join(DATA, "ocr_advanced_math.json")
TOC_FILE = os.path.join(DATA, "am_toc.json")
DB = os.path.join(DATA, "math.db")
SCALE = 2.0
PAD_TOP = 40
PAD_BOTTOM = 50
SUBJECT_ID = 2

NUMBER_RE = re.compile(r"【\s*(\d+)\s*[.．]\s*(\d+)\s*(?:[.．]\s*(\d+)\s*)?】")
FOOTER_RE = re.compile(r"第\s*\d+\s*页")
HEADER_JUNK = ("邂逅遗憾", "公众号", "b站", "B站", "知乎", "小红书", "思维课")
CHAP_HEADER_RE = re.compile(r"^(\d+)\s*([\u4e00-\u9fff]{2,10})$")

# 手稿印刷页偏移：idx - 7 = 印刷页（第一章 idx8 -> 印刷1）
AM_OFFSET = 7
P_FIX = {'1.19': 9, '2.52': 156, '2.59': 161, '2.60': 161,
         '3.36': 228, '3.46': 236, '5.42': 380, '1.80': 63, '1.81': 63,
         '5.55': 396, '5.59': 401, '1.3': 2, '1.26': 18, '3.31': 219,
         '3.66': 251, '3.73': 256, '3.89': 270, '4.25': 319, '6.12': 426}

def main():
    with open(OCR_FILE, encoding="utf-8") as f:
        ocr = json.load(f)
    toc = json.load(open(TOC_FILE, encoding="utf-8"))
    for t in toc:
        if t["print_page"] is not None:
            t["print_page"] = t["print_page"] + (5 - AM_OFFSET)  # 原存 idx-5，改为 idx-7
    chapters_toc = [t for t in toc if t["level"] == 0 and t["print_page"] is not None]
    sections_toc = [t for t in toc if t["level"] == 1 and t["print_page"] is not None]
    # 章号 -> 手稿章名
    chap_name = {}
    for t in chapters_toc:
        m = re.match(r'^第([一二三四五六七八九十]+)章\s*(.*)$', t["title"])
        if m:
            cn = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}
            chap_name[cn[m.group(1)]] = t["title"].strip()

    con = sqlite3.connect(DB)
    con.execute("INSERT OR REPLACE INTO subjects (id, name) VALUES (?, '高等数学')", (SUBJECT_ID,))
    con.execute("DELETE FROM questions WHERE subject_id=?", (SUBJECT_ID,))
    con.execute("DELETE FROM chapters WHERE subject_id=?", (SUBJECT_ID,))
    con.execute("DELETE FROM sections WHERE subject_id=?", (SUBJECT_ID,))
    if 'section_id' not in [r[1] for r in con.execute("PRAGMA table_info(questions)")]:
        con.execute("ALTER TABLE questions ADD COLUMN section_id INTEGER")
    con.commit()

    # 章节缓存
    chap_cache = {}
    sec_cache = {}

    def get_chapter(cnum):
        if cnum in chap_cache:
            return chap_cache[cnum]
        title = chap_name.get(cnum, f"第{cnum}章")
        cur = con.execute("INSERT INTO chapters (subject_id, num, title) VALUES (?, ?, ?)",
                          (SUBJECT_ID, cnum, title))
        chap_cache[cnum] = cur.lastrowid
        return cur.lastrowid

    def section_of(p):
        best = None
        for t in sections_toc:
            if t["print_page"] <= p:
                best = t
        return best

    def get_section(sec, cnum):
        if sec is None:
            return None
        key = sec["title"]
        if key in sec_cache:
            return sec_cache[key]
        m = re.match(r'^(\d+\.\d+)', key)
        snum = m.group(1) if m else '补'
        cid = get_chapter(cnum)
        # num 冲突（如 4.2 与 4.2续）时加后缀
        base = snum
        k = 0
        while True:
            try:
                cur = con.execute("INSERT INTO sections (subject_id, chapter_id, num, title) VALUES (?, ?, ?, ?)",
                                  (SUBJECT_ID, cid, snum, key))
                break
            except sqlite3.IntegrityError:
                k += 1
                snum = base + chr(96 + k)
        sec_cache[key] = cur.lastrowid
        return cur.lastrowid

    questions = []
    for pg in ocr["pages"]:
        pno = pg["page"]
        lines = pg["lines"]
        anchors = []
        for li, l in enumerate(lines):
            m = NUMBER_RE.search(l["text"])
            if m:
                vm = re.search(r'例\s*(\d+\.\d+)', l["text"])
                anchors.append({"li": li, "c": int(m.group(1)), "q": int(m.group(2)),
                                "sub": int(m.group(3)) if m.group(3) else None, "line": l,
                                "variant": f'（例{vm.group(1)}）' if vm else None})
        if not anchors:
            continue
        footer_y = None
        for l in lines:
            if FOOTER_RE.search(l["text"]):
                footer_y = min(footer_y, l["y0"]) if footer_y is not None else l["y0"]
        page_bottom = footer_y if footer_y is not None else pg["h"]
        # 页眉章名：第一锚点上方
        chap_num = None
        for l in lines:
            if l["y1"] >= anchors[0]["line"]["y0"]:
                break
            t = l["text"].strip()
            if any(j in t for j in HEADER_JUNK):
                continue
            m = CHAP_HEADER_RE.match(t)
            if m:
                chap_num = int(m.group(1))
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
                if anchor_ys[0] - y1 < 50:
                    groups[0].append(li)
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
            num = f'{a["c"]}.{a["q"]}' + (f'.{a["sub"]}' if a["sub"] is not None else '') + (a["variant"] or '')
            questions.append({
                "page": pno, "chap_num": chap_num, "num": num,
                "cnum": a["c"], "qnum": a["q"], "sub": a["sub"],
                "top": max(top, 0), "bottom": min(bottom, pg["h"]),
                "text": " ".join(texts),
            })

    print(f"解析出 {len(questions)} 道题")

    # 裁剪图片
    doc = pdfium.PdfDocument(ocr["pdf"])
    book_dir = os.path.join(IMG, "advanced_math")
    os.makedirs(book_dir, exist_ok=True)
    P_RE = re.compile(r'[(（]\s*P\s*(\d{1,3})\s*(?:[/／]\s*\d{1,3})?\s*[)）]')
    count = 0
    for q in questions:
        page = doc[q["page"] - 1]
        bmp = page.render(scale=SCALE)
        img = bmp.to_pil()
        crop = img.crop((0, q["top"], img.width, q["bottom"]))
        fn = f'q_{q["num"].replace(".", "_")}.png'
        q["image"] = f"images/advanced_math/{fn}"
        crop.save(os.path.join(BASE, q["image"]))
        # P 页码
        m = P_RE.findall(q["text"])
        q["p"] = int(m[-1]) if m else None
        if q["num"] in P_FIX:
            q["p"] = P_FIX[q["num"]]
        q.pop("top"); q.pop("bottom")
    doc.close()

    # 入库
    no_p = []
    for q in questions:
        cid = get_chapter(q["chap_num"] if q["chap_num"] else q["cnum"])
        sec = section_of(q["p"]) if q["p"] is not None else None
        if q["p"] is None:
            no_p.append(q["num"])
        sid = get_section(sec, q["chap_num"] if q["chap_num"] else q["cnum"])
        con.execute("""INSERT OR REPLACE INTO questions
            (subject_id, chapter_id, section_id, num, cnum, qnum, sub, image, page, text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (SUBJECT_ID, cid, sid, q["num"], q["cnum"], q["qnum"], q["sub"],
             q["image"], q["page"], q["text"]))
    con.commit()
    print("无 P 页码的题:", no_p)
    # 章节统计
    for r in con.execute("""SELECT c.num, c.title, COUNT(q.id) FROM chapters c
        JOIN questions q ON q.chapter_id=c.id AND q.subject_id=?
        GROUP BY c.id ORDER BY c.num""", (SUBJECT_ID,)):
        print(f"  第{r[0]}章 {r[1]}: {r[2]} 题")
    print("总题数:", len(questions))
    con.close()
    print("DONE")

if __name__ == "__main__":
    main()
