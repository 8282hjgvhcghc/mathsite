"""周测卷批量录入：pdfplumber 提题号坐标 + 渲染裁剪每题图 + 入库。"""
import sys, io, os, re, sqlite3
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import pdfplumber
import pypdfium2 as pdfium

BASE = r'D:\408\mathsite'
SRC = r'C:\Users\19168\Desktop\周测\题目'
DB = os.path.join(BASE, 'data', 'math.db')
IMG = os.path.join(BASE, 'images', 'weekly')
SCALE = 2.0
PAD = 8  # pt
NUM_RE = re.compile(r'^(\d+)\s*[.．]')

def ingest(pdf_path):
    fname = os.path.basename(pdf_path)
    m = re.match(r'^(\d+)\.(\d+)', fname)
    if not m:
        print('跳过（无日期）:', fname)
        return
    date_str = f'2026-{int(m.group(1)):02d}-{int(m.group(2)):02d}'
    name = f'{m.group(1)}.{m.group(2)}周测'
    con = sqlite3.connect(DB)
    row = con.execute("SELECT id FROM weekly_tests WHERE name=?", (name,)).fetchone()
    if row:
        con.execute("DELETE FROM questions WHERE weekly_test_id=?", (row[0],))
        tid = row[0]
        con.execute("UPDATE weekly_tests SET date=?, subject='数学' WHERE id=?", (date_str, tid))
    else:
        cur = con.execute("INSERT INTO weekly_tests (name, date, subject) VALUES (?, ?, '数学')", (name, date_str))
        tid = cur.lastrowid
    con.commit()

    # 提题号坐标
    anchors = []  # (page_idx, num, top_pt, text)
    pdf = pdfplumber.open(pdf_path)
    for pi, page in enumerate(pdf.pages):
        for w in page.extract_words():
            t = w['text'].strip()
            mm = NUM_RE.match(t)
            if mm:
                n = int(mm.group(1))
                if n < 1 or n > 100 or t.startswith('2026'):
                    continue
                anchors.append({'page': pi, 'num': n, 'top': w['top'], 'text': t[:60]})
    pdf.close()
    if not anchors:
        print('无题号:', fname)
        return
    # 按页、位置排序；题号应连续递增
    anchors.sort(key=lambda a: (a['page'], a['top']))
    seen = set()
    qlist = []
    for a in anchors:
        if a['num'] in seen:
            continue
        seen.add(a['num'])
        qlist.append(a)
    qlist.sort(key=lambda a: a['num'])
    print(f'{name}: {len(qlist)} 题 (日期 {date_str})')

    # 渲染裁剪
    doc = pdfium.PdfDocument(pdf_path)
    book_dir = os.path.join(IMG, name)
    os.makedirs(book_dir, exist_ok=True)
    for i, a in enumerate(qlist):
        page = doc[a['page']]
        bmp = page.render(scale=SCALE)
        img = bmp.to_pil()
        factor = img.height / 842.0
        y0 = max(a['top'] - PAD, 0) * factor
        if i + 1 < len(qlist) and qlist[i + 1]['page'] == a['page']:
            y1 = (qlist[i + 1]['top'] - PAD) * factor
        else:
            y1 = img.height - 30
        crop = img.crop((0, int(y0), img.width, int(y1)))
        fn = f'q_{a["num"]}.png'
        rel = f'images/weekly/{name}/{fn}'
        crop.save(os.path.join(BASE, rel))
        con.execute("""INSERT INTO questions
            (subject_id, chapter_id, section_id, weekly_test_id, num, cnum, qnum, sub, image, page, text)
            VALUES (NULL, NULL, NULL, ?, ?, NULL, ?, NULL, ?, ?, ?)""",
            (tid, str(a['num']), a['num'], rel, a['page'] + 1, a['text']))
    doc.close()
    con.commit()
    con.close()

for f in sorted(os.listdir(SRC)):
    if f.lower().endswith('.pdf'):
        ingest(os.path.join(SRC, f))
print('ALL DONE')
