# -*- coding: utf-8 -*-
"""파넬티아 번역 TSV 만들기(2026-11-01, 실크 외전 mk_tsv 를 옮김) → my files/tsv/ — 18KB 단위(자투리 1/3 미만은 앞 파일에 합침)
  pt_###.tsv = MES 문자열(같은 글 하나로, 위치 = 처음 파일:16진(×같은 글 수) · 끝 = 뒤 제어(0C 대사 끝·13 쪽 넘김·00/02 메뉴·0D/0A/15 변수 끼움 조각))
  JP 토큰: ／ = 게임 줄바꿈(％) — 조각 문장(변수 앞뒤)은 앞뒤 줄과 이어 읽을 것
  python tools/mk_tsv.py"""
import csv, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIMIT = 18 * 1024
OUT = os.path.join(ROOT, 'my files', 'tsv')


def write(prefix, lines):
    head = '번호\t위치\tJP\tKO\n'; chunks = [[]]; size = len(head.encode())
    for ln in lines:
        b = len(ln.encode())
        if chunks[-1] and size + b > LIMIT: chunks.append([]); size = len(head.encode())
        chunks[-1].append(ln); size += b
    if len(chunks) > 1 and sum(len(l.encode()) for l in chunks[-1]) < LIMIT // 3:
        last = chunks.pop(); chunks[-1] += last                           # ★pop 먼저(chunks[-2] += chunks.pop() 은 pop 뒤 엉뚱한 칸을 덮음 — 2026-11-01)
    for i, c in enumerate(chunks):
        p = os.path.join(OUT, '%s_%03d.tsv' % (prefix, i + 1))
        open(p, 'w', encoding='utf-8', newline='\n').write(head + ''.join(c))
        print(os.path.basename(p), len(c), '줄', os.path.getsize(p), 'B')


def main():
    sys.stdout.reconfigure(encoding='utf-8'); os.makedirs(OUT, exist_ok=True)
    rows = list(csv.DictReader(open(os.path.join(ROOT, 'work', 'text', 'script.tsv'), encoding='utf-8'), delimiter='\t', quoting=csv.QUOTE_NONE))
    cnt = {}
    for r in rows:
        k = r['같은글'] or r['ID']; cnt[k] = cnt.get(k, 0) + 1
    uniq = [r for r in rows if not r['같은글']]
    import re
    late = [r for r in uniq if re.fullmatch('[一-龠●ー々]+', r['JP'])]           # 2026-11-01 뒤늦게 찾은 한자만 이름 14개 — 하스피가 pt_* 번역 중이라 번호 그대로 두고 Claude 가 따로(work/text/ko_extra.tsv)
    uniq = [r for r in uniq if r not in late]
    open(os.path.join(ROOT, 'work', 'text', 'late_names.tsv'), 'w', encoding='utf-8', newline='\n').write('ID\tJP\n' + ''.join('%s\t%s\n' % (r['ID'], r['JP']) for r in late))
    write('pt', ['%05d\t%s(×%d)\t%s\t\n' % (n + 1, r['ID'], cnt[r['ID']], r['JP']) for n, r in enumerate(uniq)])


if __name__ == '__main__':
    main()
