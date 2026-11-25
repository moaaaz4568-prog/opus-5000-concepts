#!/usr/bin/env python3
"""فاحص آلي لملفات المفاهيم C_<CODE>_NN.md ضد مصادرها."""
import hashlib, json, re, sys, unicodedata
from pathlib import Path

REQUIRED_H2 = ["التعريف والجوهر","الآلية","الشروط والسياق","الحدود وحالات الفشل",
    "أمثلة موسومة","التوترات والتعارضات","التطبيقات المشروطة","سجل الأدلة والمصادر"]
# الطراز الغني الجديد (توجيه معاذ): ملف مستقل بذاته بملخص وجداول وتعميق
RICH_REQUIRED = ["الملخص التنفيذي","الفكرة في سطر","لماذا يعمل هذا؟ (التعميق)","المصطلحات المرتبطة","حدود الفكرة"]
LEAK = re.compile(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af\u0400-\u04ff]')

def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    s = re.sub(r'[\u200b-\u200f\u2060\ufeff]', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip(' ،.؛:«»"\'\n')

def words(text: str) -> int:
    return len([w for w in re.split(r'\s+', text.strip()) if w])

def check_concept(path: Path, sources: dict) -> list:
    errs = []
    text = path.read_text(encoding='utf-8')
    m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
    if not m: return ['NO_FRONTMATTER']
    fm = m.group(1)
    body = text[m.end():]
    cid_m = re.search(r'^concept_id:\s*(\S+)', fm, re.M)
    if not cid_m: return ['NO_CONCEPT_ID']
    cid = cid_m.group(1)
    if cid != path.stem: errs.append('ID_MISMATCH')
    m_id = re.fullmatch(r'C_(.+)_([0-9]{2})', path.stem)
    if not m_id: return ['BAD_FILENAME']
    code, nn_s = m_id.groups()
    nn = int(nn_s)
    if not (1 <= nn <= 99): errs.append('BAD_NN')
    if not re.search(r'^source_refs:.*S_yt_' + code, fm, re.M): errs.append('NO_SOURCE_REF')
    h2 = [l[3:].strip() for l in body.splitlines() if l.startswith('## ')]
    rich = all(r in h2 for r in RICH_REQUIRED)
    if not rich and h2 != REQUIRED_H2:
        errs.append('H2_SECTIONS:' + ';'.join(h2))
    if rich:
        # الطراز الغني: عنوان H1 وصفي مقبول بدل المعرف، ويجب أن يحوي جداول واقتباسات
        if not re.search(r'^# ', body, re.M): errs.append('NO_H1')
        if '|' not in body: errs.append('NO_TABLE')
    if not ('# ' + cid) in text and not rich: errs.append('NO_H1_ID')
    if LEAK.search(text): errs.append('CHAR_LEAK')
    # word count on body excluding YAML
    wc = words(re.sub(r'\|.*\|', ' ', body))
    if rich and wc < 400: errs.append(f'WORDS_{wc}')
    elif not (250 <= wc <= 900): errs.append(f'WORDS_{wc}')
    # quotes must exist verbatim in source
    quotes = re.findall(r'«([^»]{20,})»', text)
    src = sources.get(code)
    if src is None:
        errs.append('NO_SOURCE_FILE')
    elif not quotes:
        errs.append('NO_QUOTES')
    else:
        nsrc = norm(src)
        for q in quotes:
            if norm(q) not in nsrc:
                errs.append('QUOTE_NOT_VERBATIM:' + q[:40])
    return errs

def main():
    concepts_dir = Path('concepts/yt')
    sources = {}
    for f in Path('sources').rglob('S_yt_*_ar.md'):
        t = f.read_text(encoding='utf-8')
        t = re.sub(r'^---.*?---\n', '', t, flags=re.S)
        m = re.fullmatch(r'S_yt_(.+)_ar', f.stem)
        sources[m.group(1)] = t
    fails = 0
    for p in sorted(concepts_dir.glob('C_*.md')):
        errs = check_concept(p, sources)
        if errs:
            fails += 1
            print(f'{p.name}: {errs}')
    print(f'CHECKED {len(list(concepts_dir.glob("C_*.md")))} concepts, FAILED {fails}')
    sys.exit(1 if fails else 0)

if __name__ == '__main__':
    main()
