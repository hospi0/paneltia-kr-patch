# -*- coding: utf-8 -*-
r"""대사 평문 훑기(2026-10-26) — SJIS 2바이트 + ASCII(@ 제어 코드) 가 NUL 로 끝나는 문자열 중 가나가 2자 이상인 것.
  python tools/textscan.py → 파일별 문자열·글자 수 + 중복 뺀 합계, work/text_all.tsv(파일·위치·문자열)"""
import collections, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAT = re.compile(rb'(?:[\x81-\x9f\xe0-\xef][\x40-\x7e\x80-\xfc]|[\x20-\x7e]|\x0a)+(?=\x00)')
KANA = re.compile(r'[ぁ-んァ-ヶ]')


def strings(d):
    for m in PAT.finditer(d):
        try:
            t = m.group().decode('cp932')
        except UnicodeDecodeError:
            continue
        body = re.sub(r'@V[0-9a-z]+_|@[a-zA-Z][0-9]?', '', t)
        if len(KANA.findall(body)) >= 2 and len(re.findall(r'[ -~]', body)) <= len(body) * 0.5:
            yield m.start(), t, body


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    rows = []; per = collections.Counter(); perc = collections.Counter(); uniq = {}
    for dp, _, fn in os.walk(os.path.join(ROOT, 'work', 'arc')):
        for f in fn:
            if f.endswith('.WAV'): continue
            p = os.path.join(dp, f); rel = os.path.relpath(p, os.path.join(ROOT, 'work', 'arc')).replace(os.sep, '/')
            for o, t, body in strings(open(p, 'rb').read()):
                rows.append((rel, o, t)); per[rel] += 1; perc[rel] += len(body); uniq.setdefault(t, len(body))
    for k, v in per.most_common(70):
        print('%-28s %5d %7d' % (k, v, perc[k]))
    print('전체 %d 문자열 %d 자 · 중복 뺀 %d 문자열 %d 자' % (len(rows), sum(perc.values()), len(uniq), sum(uniq.values())))
    open(os.path.join(ROOT, 'work', 'text_all.tsv'), 'w', encoding='utf-8').write(''.join('%s\t0x%X\t%s\n' % (a, b, c.replace('\n', '\n')) for a, b, c in rows))
