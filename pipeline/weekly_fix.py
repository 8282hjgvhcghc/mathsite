"""用 rapidocr 补充 pdfplumber 漏掉的周测题号（夹逼验证），重新裁剪入库。"""
import sys, io, os, re, sqlite3
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import pdfplumber
import pypdfium2 as pdfium
import numpy as np
from rapidocr_onnxruntime import RapidOCR

BASE = r'D:\408\mathsite'
SRC = r'C:\Users\19168\Desktop\周测\题目'
DB = os.path.join(BASE, 'data', 'math.db')
IMG = os.path.join(BASE, 'images', 'weekly')
SCALE = 2.0
PAD = 8
NUM_RE = re.compile(r'^(\d+)\s*[.．]')

engine = RapidOCR()

def fix_book(pdf_path, name, date_str):
    pdf = pdfplumber.open(pdf_path)
    plumber = []
    for pi, page in enumerate(pdf.pages):
        for w in page.extract_words():
            t = w['text'].strip()
            mm = NUM_RE.match(t)
            if mm:
                n = int(mm.group(1))
                if 1 <= n <= 100 and not t.startswith('2026'):
                    plumber.append({'page': pi, 'num': n, 'top': w['top'], 'text': t[:60]})
    pdf.close()

    doc = pdfium.PdfDocument(pdf_path)
    ocr_anchors = []
    for pi in range(len(doc)):
        page = doc[pi]
        bmp = page.render(scale=SCALE)
        img = bmp.to_pil()
        res, _ = engine(np.array(img))
        factor = 842.0 / img.height
        for box, text, conf in (res or []):
            t = text.strip()
            mm = NUM_RE.match(t)
            if not mm:
                continue
            n = int(mm.group(1))
            if n < 1 or n > 100 or t.startswith('2026'):
                continue
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            x_pt = min(xs) * factor
            top_pt = min(ys) * factor
            if x_pt < 40 or x_pt > 300 or top_pt < 50 or top_pt > 790:
                continue
            ocr_anchors.append({'page': pi, 'num': n, 'top': top_pt, 'text': t[:60]})

    by_num = {a['num']: a for a in plumber}
    # 夹逼补充：OCR 锚点 num=k 必须位于 plumber k-1 与 k+1 之间
    plumber_sorted = sorted(plumber, key=lambda a: (a['page'], a['top']))
    added = []
    for a in ocr_anchors:
        k = a['num']
        if k in by_num:
            continue
        prev = by_num.get(k - 1)
        nxt = by_num.get(k + 1)
        if prev and nxt:
            in_between = (
                (prev['page'], prev['top']) < (a['page'], a['top']) < (nxt['page'], nxt['top'])
            )
            if in_between:
                by_num[k] = a
                added.append(k)
    qlist = [by_num[k] for k in sorted(by_num)]
    nums = sorted(by_num)
    missing = [n for n in range(1, max(nums) + 1) if n not in nums]
    print(f'{name}: {len(qlist)}题 补充:{added if added else "无"} 缺失:{missing if missing else "无"}')
    if not added:
        return
    # 重新裁剪入库（按页内 top 顺序裁剪）
    con = sqlite3.connect(DB)
    tid = con.execute("SELECT id FROM weekly_tests WHERE name=?", (name,)).fetchone()[0]
    con.execute("DELETE FROM questions WHERE weekly_test_id=?", (tid,))
    con.commit()
    doc2 = pdfium.PdfDocument(pdf_path)
    book_dir = os.path.join(IMG, name)
    qlist.sort(key=lambda a: (a['page'], a['top']))
    for i, a in enumerate(qlist):
        page = doc2[a['page']]
        bmp = page.render(scale=SCALE)
        img = bmp.to_pil()
        factor = img.height / 842.0
        y0 = max(a['top'] - PAD, 0) * factor
        nxt = qlist[i + 1] if i + 1 < len(qlist) else None
        if nxt and nxt['page'] == a['page']:
            y1 = max((nxt['top'] - PAD) * factor, y0 + 60)
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
    doc2.close()
    con.commit()
    con.close()
    print(f'  已重建 {name}')

for f in sorted(os.listdir(SRC)):
    if not f.lower().endswith('.pdf'):
        continue
    m = re.match(r'^(\d+)\.(\d+)', f)
    if not m:
        continue
    name = f'{m.group(1)}.{m.group(2)}周测'
    date_str = f'2026-{int(m.group(1)):02d}-{int(m.group(2)):02d}'
    fix_book(os.path.join(SRC, f), name, date_str)
print('DONE')
