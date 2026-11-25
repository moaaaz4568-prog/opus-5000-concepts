#!/usr/bin/env python3
"""تحدّث حالة المصادر في MANIFEST_5000.json بحسب الملفات الموجودة في concepts/yt."""
import json, re
from pathlib import Path

m = json.load(open('MANIFEST_5000.json'))
done_codes = {p.stem.split('_')[1] for p in Path('concepts/yt').glob('C_*.md')}
n = 0
for it in m['items']:
    if it['status'] == 'pending' and it['code'] in done_codes:
        it['status'] = 'done'
        it['concept_files'] = sorted(p.name for p in Path('concepts/yt').glob(f"C_{it['code']}_*.md"))
        n += 1
json.dump(m, open('MANIFEST_5000.json', 'w'), ensure_ascii=False, indent=2)
print(f'marked {n} sources done; total done =', sum(1 for i in m['items'] if i['status'] == 'done'))
