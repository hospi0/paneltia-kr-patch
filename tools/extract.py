# -*- coding: utf-8 -*-
r"""파넬티아 대사·문자열 추출(2026-11-01) → work/text/script.tsv
  ID = 파일:16진 시작 · 끝 = 문자열 뒤 제어 바이트(0C 대사 끝 · 13 쪽 넘김(13 33) · 00/02 메뉴·이름 · 0D/0A/15/04 변수 끼움 조각)
  JP 표시: ％(게임 줄바꿈) → ／ · 같은 글은 처음 것 하나(같은글 = 처음 ID)
  ⛔STAFF.MES(스태프 롤)는 뺌 — 하스피 허락 전 손대지 않음
  경계는 tools/mes.py 휴리스틱(바이트코드 해석 전) — 실기에서 원문이 보이면 여기부터 의심
  python tools/extract.py"""
import glob, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE)
import mes
DISC = os.path.join(ROOT, 'work', 'disc0')
ORDER = ['START', 'MACHI1', 'MACHI2', 'MACHI3', 'MACHI4', 'MACHI5', 'MACHI6', 'MACHI7', 'MACHI8', 'MACHI9', 'FIELD', 'DUN', 'BOSS',
         'BUKI1', 'BUKI2', 'YADOYA', 'YADOYA2', 'SAKABA', 'PANEYA', 'JIJI', 'MAPEDIT', 'MAPEDIT1', 'RESET', 'CLEAR']


def records():
    for nm in ORDER:
        d = open(os.path.join(DISC, nm + '.MES'), 'rb').read()
        for a, s, e in mes.runs(d):
            yield '%s:%X' % (nm, a), s.replace('％', '／'), '%02X' % d[e], e - a


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    left = sorted(set(os.path.basename(f)[:-4] for f in glob.glob(os.path.join(DISC, '*.MES'))) - set(ORDER) - {'STAFF', 'MACHI'})
    assert not left, left
    first = {}; n = 0; chars = 0
    with open(os.path.join(ROOT, 'work', 'text', 'script.tsv'), 'w', encoding='utf-8', newline='\n') as o:
        o.write('ID\t같은글\t끝\t바이트\tJP\n')
        for i, jp, end, nb in records():
            dup = first.get(jp, '')
            if not dup: first[jp] = i; chars += len(jp.replace('／', ''))
            o.write('%s\t%s\t%s\t%d\t%s\n' % (i, dup, end, nb, jp)); n += 1
    print('기록 %d · 고유 %d · 고유 글자 %d' % (n, len(first), chars))


if __name__ == '__main__':
    main()
