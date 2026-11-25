#!/usr/bin/env python3
"""فاحص آلي لملفات المفاهيم C_<CODE>_NN.md — طراز ويكي معاذ القديمة العميقة (حرفيًا)."""
import re, sys
from pathlib import Path

# ترتيب معاذ المُلزم: H1 ثم التصنيف ثم المصدر الرئيسي ثم ## ملخص
# ثم أقسام مكونات/بنية (مرنة العنوان)، ثم الخطوات/البروتوكول، ثم الأخطاء القاتلة كجدول،
# ثم ## التعميق: لماذا يعمل ... (ويشمل الآلية/سيناريوهات/بروتوكول مفصل/مشاكل متقدمة/أمثلة حقيقية)،
# ثم ## المصطلحات المرتبطة في النهاية.
FM_FIELDS = ["type","name","created","updated","deepened","deepener","tags","related","sources","entities"]
LEAK = re.compile(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af\u0400-\u04ff]')
EMOJI_NUM = re.compile(r'^\s*[0-9]*[\u2000-\u330e\U0001F000-\U0001FAFF\u2600-\u27BF]\s')

def words(text: str) -> int:
    return len([w for w in re.split(r'\s+', text.strip()) if w])

def norm(s: str) -> str:
    return re.sub(r'\s+', ' ', s).strip()

def check_concept(path: Path, sources: dict) -> list:
    errs = []
    text = path.read_text(encoding='utf-8')
    m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
    if not m: return ['NO_FRONTMATTER']
    fm_block, body = m.group(1), text[m.end():]
    # frontmatter: الحقول العشرة فقط — منعًا باتًا لغيرها (ومنها concept_id)
    keys = [l.split(':')[0] for l in fm_block.splitlines() if l.strip() and not l.startswith(' ')]
    if sorted(keys) != sorted(FM_FIELDS): errs.append('FM_FIELDS:' + ','.join(keys))
    m_id = re.fullmatch(r'C_(.+)_([0-9]{2})', path.stem)
    if not m_id: return errs + ['BAD_FILENAME']
    code = m_id.group(1)
    if not re.search(r'^sources:.*S_yt_' + code, fm_block, re.M): errs.append('NO_SOURCE_REF')
    fm = dict(re.findall(r'^(\w+):\s*(.*)$', fm_block, re.M))
    # 1) H1 أول محتوى بعد الـfrontmatter: أسطر فارغة فقط مسموحة قبله
    h1_m = re.search(r'^# \S', body, re.M)
    if not h1_m:
        return errs + ['NO_H1']
    pre = body[:h1_m.start()]
    if norm(pre.replace('\n', ' ')): errs.append('CONTENT_BEFORE_H1')
    # 2/3) **التصنيف:** ثم **المصدر الرئيسي:** بعد H1 وقبل أول ##
    post = re.split(r'^## ', body, maxsplit=1, flags=re.M)[0][h1_m.start():]
    if '**التصنيف:**' not in post: errs.append('NO_CLASSIFICATION_BOLD')
    if '**المصدر الرئيسي:**' not in post: errs.append('NO_MAIN_SOURCE_BOLD')
    # 5) الأقسام بالترتيب
    h2 = [re.sub(r'[\u200b-\u200f\u202a-\u202e\ufeff\u00ad]', '', l)[3:].lstrip().strip() for l in body.splitlines() if l.startswith('## ')]
    def idx(pfx): return next((i for i,h in enumerate(h2) if h.startswith(pfx)), -1)
    i_sum = idx('ملخص')
    # قسم البنية/المكونات: أي قسم H2 بعد ملخص (الترتيب هو الملزم حسب توجيه معاذ)
    i_struct = next((i for i,h in enumerate(h2) if i != i_sum and i > 0), -1)
    i_fatal = next((i for i,h in enumerate(h2) if 'الأخطاء القاتلة' in h), -1)
    i_deep = next((i for i,h in enumerate(h2) if 'التعميق: لماذا' in h), -1)
    i_terms = next((i for i,h in enumerate(h2) if 'المصطلحات المرتبطة' in h), -1)
    if i_sum != 0: errs.append('H2_ORDER:ملخص ليس أول قسم')
    if i_struct == -1: errs.append('H2_ORDER:لا قسم مكونات/بنية/بروتوكول')
    if i_fatal == -1: errs.append('NO_FATAL_ERRORS_TABLE_SECTION')
    if i_deep == -1: errs.append('NO_DEEPENING_SECTION')
    if i_terms == -1: errs.append('NO_LINKED_TERMS_SECTION')
    if -1 in (i_sum,i_struct,i_fatal,i_deep,i_terms): return errs
    if not (i_sum < i_struct < i_fatal < i_deep < i_terms):
        if i_deep < i_fatal: errs.append('DEEPENING_BEFORE_FATAL_ERRORS')
        errs.append('H2_ORDER:' + ';'.join(h2))
    # جدول داخل الأخطاء القاتلة — وصفوفه حقيقية لا منسوخة من قسم آخر
    parts = re.split(r'^## ', body, flags=re.M)
    fatal_sec = next((p for p in parts if p.startswith('الأخطاء القاتلة')), '')
    if not fatal_sec.strip('|').strip() or '|' not in fatal_sec:
        errs.append('FATAL_ERRORS_NOT_TABLE')
    else:
        rows = [norm(l) for l in fatal_sec.splitlines() if l.strip().startswith('|')]
        rows = [r for r in rows if not re.fullmatch(r'\|[\s\-:|]+\|', r)]
        data_rows = rows[1:]  # بعد صف العناوين
        before_fatal = body.split('## الأخطاء القاتلة', 1)[0]
        for r in data_rows:
            if r and r in norm(before_fatal):
                errs.append('FATAL_ROWS_COPIED_FROM_OTHER_SECTION'); break
    # 8) التعميق يشمل العناصر الداخلية
    _dl = next((i for i,l in enumerate(body.splitlines()) if 'التعميق: لماذا' in l), None)
    deep = '\n'.join(body.splitlines()[_dl:]) if _dl is not None else ''
    for req,tag in [('الآلية','DEEP_NO_MECHANISM'),('سيناريو','DEEP_NO_SCENARIO'),('مشاكل متقدمة','DEEP_NO_ADVANCED'),('أمثلة حقيقية','DEEP_NO_EXAMPLES')]:
        if req not in deep and req not in body: errs.append(tag)
    # 9) المصطلحات المرتبطة آخر قسم
    if h2[-1] != 'المصطلحات المرتبطة': errs.append('LINKED_TERMS_NOT_LAST')
    # related فارغة مع وجود روابط مفاهيم في المصطلحات المرتبطة = تناقض
    related_raw = fm.get('related', '[]').strip('[] ').strip()
    terms_sec = next((p for p in parts if p.startswith('المصطلحات المرتبطة')), '')
    term_links = re.findall(r'\[\[C_\S+?\]\]', terms_sec)
    if not related_raw and term_links: errs.append('RELATED_EMPTY_BUT_TERMS_LINKS')
    # الممنوعات منعًا باتًا
    if 'سجل الأدلة' in body: errs.append('FORBIDDEN_EVIDENCE_LOG')
    if re.search(r'\bCL_', body + fm_block): errs.append('FORBIDDEN_CL_REFS')
    if 'claim_refs' in fm_block: errs.append('FORBIDDEN_CLAIM_REFS')
    for l in body.splitlines():
        if EMOJI_NUM.search(l): errs.append('FORBIDDEN_EMOJI_NUMBERED'); break
    if LEAK.search(text): errs.append('CHAR_LEAK')
    wc = words(re.sub(r'\|.*\|', ' ', body))
    if wc < 250: errs.append(f'WORDS_{wc}')
    src = sources.get(code)
    if src is None: errs.append('NO_SOURCE_FILE')
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
