"""按手稿小标题重建分类：章（手稿 L0）→ 节（手稿 L1），题目按 P 页码归入节。"""
import sys, io, json, re, sqlite3
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = r'D:\408\mathsite'
toc = json.load(open(BASE + r'\data\linear_toc.json', encoding='utf-8'))

FIX = {'2.11': 46, '5.15': 194, '6.9': 228, '3.6': 104, '3.13': 109,
       '3.20': 118, '3.31': 133, '6.17': 235, '2.44': 78, '6.23': 241}

# 手稿章（L0）
chapters = [t for t in toc if t['level'] == 0]
# 手稿节（L1）
sections = [t for t in toc if t['level'] == 1]

def page_of(num, text):
    if num in FIX:
        return FIX[num]
    m = re.findall(r'[(（]\s*P\s*(\d{1,3})\s*[)）]', text)
    return int(m[-1]) if m else None

def section_of(p):
    best = None
    for s in sections:
        if s['print_page'] <= p:
            best = s
    return best

con = sqlite3.connect(BASE + r'\data\math.db')
rows = con.execute("SELECT id, num, cnum, text FROM questions WHERE subject_id=1 ORDER BY cnum, qnum, sub").fetchall()

# 重建章节表（用手稿完整章名）
con.execute("DELETE FROM chapters WHERE subject_id=1")
chap_map = {}  # cnum -> chapter_id
for c in chapters:
    m = re.match(r'^第([零一二三四五六七八九十]+)章', c['title'])
    cnum = None
    if m:
        cn = {'零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
        for ch in m.group(1):
            cnum = cn.get(ch, 0) if cnum is None else cnum * 10 + cn.get(ch, 0)
    title = c['title'].strip()
    cur = con.execute("INSERT INTO chapters (subject_id, num, title) VALUES (1, ?, ?)", (cnum, title))
    if cnum is not None:
        chap_map[cnum] = cur.lastrowid

# 建 sections 表
con.execute("""CREATE TABLE IF NOT EXISTS sections (
    id INTEGER PRIMARY KEY, subject_id INTEGER, chapter_id INTEGER,
    num TEXT, title TEXT, UNIQUE(subject_id, num))""")
con.execute("DELETE FROM sections WHERE subject_id=1")

sec_map = {}  # (title) -> section_id
for s in sections:
    m = re.match(r'^(\d+\.\d+)', s['title'])
    num = m.group(1) if m else '补'
    # 节所属章
    cnum = int(num.split('.')[0]) if m else 5
    cid = chap_map.get(cnum)
    title = s['title'].strip()
    cur = con.execute("INSERT INTO sections (subject_id, chapter_id, num, title) VALUES (1, ?, ?, ?)",
                      (cid, num, title))
    sec_map[num] = cur.lastrowid

# 更新 questions 的 chapter_id + section_id
if 'section_id' not in [r[1] for r in con.execute("PRAGMA table_info(questions)")]:
    con.execute("ALTER TABLE questions ADD COLUMN section_id INTEGER")
    con.commit()

stats = {}
for qid, num, cnum, text in rows:
    p = page_of(num, text)
    sec = section_of(p)
    sec_num = None
    if sec:
        m = re.match(r'^(\d+\.\d+)', sec['title'])
        sec_num = m.group(1) if m else '补'
    new_cid = chap_map.get(cnum)
    new_sid = sec_map.get(sec_num)
    con.execute("UPDATE questions SET chapter_id=?, section_id=? WHERE id=?", (new_cid, new_sid, qid))
    key = sec['title'] if sec else '(未映射)'
    stats[key] = stats.get(key, 0) + 1

con.commit()

# 输出分布
print('=== 节分布（章 → 节：题数）===')
cur_ch = None
for s in sections:
    m = re.match(r'^(\d+\.\d+)', s['title'])
    num = m.group(1) if m else '补'
    cnum = int(num.split('.')[0]) if m else 5
    if cnum != cur_ch:
        print(f'\n【第{cnum}章】')
        cur_ch = cnum
    print(f'  {s["title"]}: {stats.get(s["title"], 0)} 题')

# 校验
total = sum(stats.values())
print(f'\n总映射题数: {total} (应为 228)')
con.close()
