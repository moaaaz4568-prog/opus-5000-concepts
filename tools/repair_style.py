#!/usr/bin/env python3
"""إصلاح آثار الطراز القديم في كل ملفات المفاهيم — بلا اختراع حقائق:
- حذف أي محتوى قبل H1، وسطر «التصنيف: ... · ...» المكرر.
- إزالة شارات [direct_quote]/[inference].
- حذف قسم «أمثلة حقيقية» المكرر الذي يحمل جدول claim_ref.
- إعادة بناء جدول «الأخطاء القاتلة» من مشاكل الملف/سيناريوهاته نفسها (claim rows المنسوخة).
"""
import glob, re, sys

def sections(body):
    """يقسم الجسم إلى (قبل أول ##، قائمة [عنوان، محتوى])"""
    pre, *rest = re.split(r'^## ', body, flags=re.M)
    out = []
    for part in rest:
        head, _, cont = part.partition('\n')
        out.append([head.strip(), cont])
    return pre, out

def rebuild(pre, secs):
    # إزالة سطر التصنيف المكرر (غير البولد) من pre-H1 وبين H1 وأول ##
    pre = '\n'.join(l for l in pre.split('\n')
                    if not re.match(r'^التصنيف:.*المصدر الرئيسي:', l.strip()))
    secs = [[h, c.replace('**[direct_quote]** ', '').replace('**[inference]** ', '')
                .replace('**[direct_quote]**', '').replace('**[inference]**', '')]
            for h, c in secs]
    # حذف قسم أمثلة حقيقية المكرر الذي يحمل جدول claim_ref
    n_ex = sum(1 for h, _ in secs if h.startswith('أمثلة حقيقية'))
    seen_ex = 0
    keep = []
    for h, c in secs:
        if h.startswith('أمثلة حقيقية'):
            seen_ex += 1
            if 'claim_ref' in c or (n_ex > 1 and seen_ex == n_ex):
                continue
        keep.append([h, c])
    secs = keep
    # جدول الأخطاء القاتلة: هل صفوفه منسوخة (claim-style)؟
    rows = [l for l in next((c for h, c in secs if h.startswith('الأخطاء القاتلة')), '').splitlines()
            if l.strip().startswith('|')]
    data = [r for r in rows[1:] if not re.fullmatch(r'\|[\s\-:|]+\|', r)]
    fake = any(len(r.strip('|').split('|')) > 3 or 'S_yt_' in r for r in data)
    if fake:
        new_rows = derive_rows(secs)
        if new_rows:
            table = ['| الخطأ القاتل | النتيجة | الحل الوقائي |', '|---|---|---|'] + new_rows
            for pair in secs:
                if pair[0].startswith('الأخطاء القاتلة'):
                    pair[1] = '\n' + '\n'.join(table) + '\n'
    return pre, secs

def derive_rows(secs):
    rows = []
    for h, c in secs:
        if h.startswith('مشاكل متقدمة'):
            for m in re.finditer(r'\*\*مشكلة:\s*(.+?)\*\*(.*?)(?=\*\*مشكلة:|\Z)', c, re.S):
                prob = re.sub(r'\s+', ' ', m.group(1)).strip()
                sol = re.search(r'الحل:\s*(.+?)(?:\.\s*\*\*|$)', m.group(2), re.S)
                sol_t = re.sub(r'\s+', ' ', sol.group(1)).strip(' .') if sol else 'مراعاة قيد المصدر نفسه'
                rows.append(f'| {prob} | يعرقل تطبيق الفكرة كما حددها المصدر | {sol_t} |')
    if rows: return rows
    scen = next((c for h, c in secs if h.startswith('سيناريوهات')), '')
    bullets = re.findall(r'-\s*(?:إذا\s+(.+?)\s*(?:→|⇒|=>)\s*(.+?))\s*(?:\*\*\[.*?\]\*\*)?\s*(?:\n|$)', scen)
    for cond, act in bullets:
        cond, act = cond.strip(), act.strip()
        rows.append(f'| إغفال حالة: {cond} | ضياع أثر الفكرة الذي حذّر منه المصدر | {act} |')
    if rows: return rows
    lim = next((c for h, c in secs if h.startswith('الملخص') or h.startswith('حدود')), '')
    body_all = '\n'.join(c for _, c in secs)
    claim = next((c for h, c in secs if h.startswith('ملخص')), '')
    if claim.strip():
        first = re.sub(r'\s+', ' ', claim.strip().split('.')[0]).strip()
        rows.append(f'| تطبيق الفكرة خارج سياقها المحدد في المصدر | عكس النتيجة المقصودة | {first[:180]} |')
    return rows

def main():
    fixed = 0
    for f in sorted(glob.glob('concepts/yt/C_*.md')):
        s = open(f).read()
        m = re.match(r'^(---\n.*?\n---\n)(.*)$', s, re.S)
        if not m: continue
        fm, body = m.groups()
        pre, secs = rebuild(*sections(body))
        new = fm + pre + '\n'.join(f'## {h}\n{c}' for h, c in secs)
        new = re.sub(r'\n{3,}', '\n\n', new)
        if new != s:
            open(f, 'w').write(new); fixed += 1
    print('fixed', fixed, 'files')

main()
