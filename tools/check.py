#!/usr/bin/env python3
"""فاحص آلي لملفات المفاهيم C_<CODE>_NN.md — طراز ويكي معاذ القديمة العميقة (حرفيًا)."""
import hashlib, json, re, sys, unicodedata
from pathlib import Path

# ترتيب معاذ المُلزم: H1 ثم التصنيف ثم المصدر الرئيسي ثم ## ملخص
# ثم أقسام مكونات/بنية (مرنة العنوان)، ثم الخطوات/البروتوكول، ثم الأخطاء القاتلة كجدول،
# ثم ## التعميق: لماذا تعمل ... (ويشمل الآلية/سيناريوهات/بروتوكول مفصل/مشاكل متقدمة/أمثلة حقيقية)،
# ثم ## المصطلحات المرتبطة في النهاية.
FM_FIELDS = ["type","name","created","updated","deepened","deepener","tags","related","sources","entities"]
LEAK = re.compile(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af\u0400-\u04ff]')
EMOJI_NUM = re.compile(r'^\s*[0-9]*[\u2000-\u330e\U0001F000-\U0001FAFF\u2600-\u27BF]\s')

def words(text: str) -> int:
    return len([w for w in re.split(r'\s+', text.strip()) if w])

def check_concept(path: Path, sources: dict) -> list:
    errs = []
    text = path.read_text(encoding='utf-8')
    m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
    if not m: return ['NO_FRONTMATTER']
    fm_block, body = m.group(1), text[m.end():]
    fm = dict(re.findall(r'^(\w+):\s*(.*)$', fm_block, re.M))
    cid_m = re.search(r'^concept_id:\s*(\S+)', fm_block, re.M)
    if not cid_m: return ['NO_CONCEPT_ID']
    cid = cid_m.group(1)
    if cid != path.stem: errs.append('ID_MISMATCH')
    m_id = re.fullmatch(r'C_(.+)_([0-9]{2})', path.stem)
    if not m_id: return ['BAD_FILENAME']
    code = m_id.group(1)
    # frontmatter: الحقول العشرة فقط — منعًا باتًا لغيرها
    keys = [l.split(':')[0] for l in fm_block.splitlines() if l.strip() and not l.startswith(' ')]
    if sorted(keys) != sorted(FM_FIELDS + ['concept_id']): errs.append('FM_FIELDS:' + ','.join(keys))
    if not re.search(r'^sources:.*S_yt_' + code, fm_block, re.M): errs.append('NO_SOURCE_REF')
    # 1) H1
    if not re.search(r'^# \S', body, re.M): errs.append('NO_H1')
    # 2/3) **التصنيف:** ثم **المصدر الرئيسي:** بعد H1 وقبل أول ##
    pre = re.split(r'^## ', body, maxsplit=1, flags=re.M)[0]
    if '**التصنيف:**' not in pre: errs.append('NO_CLASSIFICATION_BOLD')
    if '**المصدر الرئيسي:**' not in pre: errs.append('NO_MAIN_SOURCE_BOLD')
    # 5) الأقسام بالترتيب
    h2 = [re.sub(r'[\u200b-\u200f\u202a-\u202e\ufeff\u00ad]', '', l)[3:].lstrip().strip() for l in body.splitlines() if l.startswith('## ')]
    def idx(pfx): return next((i for i,h in enumerate(h2) if h.startswith(pfx)), -1)
    i_sum = idx('ملخص')
    # قسم البنية/المكونات: أي قسم H2 بعد ملخص (الترتيب هو الملزم حسب توجيه معاذ)
    i_struct = next((i for i,h in enumerate(h2) if i != i_sum and i > 0), -1)
    i_fatal = next((i for i,h in enumerate(h2) if 'الأخطاء القاتلة' in h), -1)
    i_deep = next((i for i,h in enumerate(h2) if 'التعميق: لماذا تعمل' in h or 'لماذا يعمل' in h), -1)
    i_terms = next((i for i,h in enumerate(h2) if 'المصطلحات المرتبطة' in h), -1)
    if i_sum != 0: errs.append('H2_ORDER:ملخص ليس أول قسم')
    if i_struct == -1: errs.append('H2_ORDER:لا قسم مكونات/بنية/بروتوكول')
    if i_fatal == -1: errs.append('NO_FATAL_ERRORS_TABLE_SECTION')
    if i_deep == -1: errs.append('NO_DEEPENING_SECTION')
    if i_terms == -1: errs.append('NO_LINKED_TERMS_SECTION')
    if -1 in (i_sum,i_struct,i_fatal,i_deep,i_terms): return errs
    if not (i_sum < i_struct < i_fatal < i_deep < i_terms): errs.append('H2_ORDER:' + ';'.join(h2))
    # جدول داخل الأخطاء القاتلة
    sec = body.split('## الأخطاء القاتلة',1)[1] if '## الأخطاء القاتلة' in body else ''
    if not sec.strip('|').strip() or '|' not in sec: errs.append('FATAL_ERRORS_NOT_TABLE')
    # 8) التعميق يشمل العناصر الداخلية
    _dl = next((i for i,l in enumerate(body.splitlines()) if 'التعميق: لماذا تعمل' in l), None)
    deep = '\n'.join(body.splitlines()[_dl:]) if _dl is not None else ''
    # العناصر الداخلية للتعميق تقبل داخل قسم التعميق أو كأقسام شقيقة في الملف (الترتيب هو الملزم)
    for req,tag in [('الآلية','DEEP_NO_MECHANISM'),('سيناريو','DEEP_NO_SCENARIO'),('مشاكل متقدمة','DEEP_NO_ADVANCED'),('أمثلة حقيقية','DEEP_NO_EXAMPLES')]:
        if req not in deep and req not in body: errs.append(tag)
    # 9) المصطلحات المرتبطة آخر قسم
    if h2[-1] != 'المصطلحات المرتبطة': errs.append('LINKED_TERMS_NOT_LAST')
    # الممنوعات منعًا باتًا
    if 'سجل الأدلة' in body: errs.append('FORBIDDEN_EVIDENCE_LOG')
    if re.search(r'\bCL_', body + fm_block): errs.append('FORBIDDEN_CL_REFS')
    if 'claim_refs' in fm_block: errs.append('FORBIDDEN_CLAIM_REFS')
    for i,l in enumerate(body.splitlines()):
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
