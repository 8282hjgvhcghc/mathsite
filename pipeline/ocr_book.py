"""线代做题本全量 OCR：渲染每页 + rapidocr 识别，保存每页文本行与坐标 JSON。"""
import sys, io, os, json, time, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import pypdfium2 as pdfium
import numpy as np
from rapidocr_onnxruntime import RapidOCR

BOOK = "linear_algebra"
PDF = r"D:\QQ Download\27邂逅遗憾线代思维课-做题本（数二三）（标准版）.pdf"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", f"ocr_{BOOK}.json")
SCALE = 2.0

def main():
    engine = RapidOCR()
    doc = pdfium.PdfDocument(PDF)
    total = len(doc)
    result = {"book": BOOK, "pdf": PDF, "scale": SCALE, "pages": []}
    t0 = time.time()
    for i in range(total):
        page = doc[i]
        bmp = page.render(scale=SCALE)
        img = bmp.to_pil()
        res, _ = engine(np.array(img))
        lines = []
        for box, text, conf in (res or []):
            ys = [p[1] for p in box]
            xs = [p[0] for p in box]
            lines.append({
                "text": text,
                "conf": round(float(conf), 3),
                "x0": round(min(xs), 1), "x1": round(max(xs), 1),
                "y0": round(min(ys), 1), "y1": round(max(ys), 1),
            })
        lines.sort(key=lambda l: (l["y0"], l["x0"]))
        result["pages"].append({"page": i + 1, "w": img.width, "h": img.height, "lines": lines})
        el = time.time() - t0
        print(f"[{i+1}/{total}] {el:.0f}s done", flush=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print("SAVED:", OUT, flush=True)

if __name__ == "__main__":
    main()
