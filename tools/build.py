# -*- coding: utf-8 -*-
r"""파넬티아 넣기 빌더(2026-11-01) — 번역 TSV → work/build/*.MES · KANJI.FON
  번역: work/text/ko_script.tsv(tools/merge_ko.py 결과, JP·KO) — JP 로 맞춤(같은 글은 모든 파일에 같은 번역)
  문장 경계: tools/extract.records(= tools/mes.runs) · 문자열 사이 바이트코드는 그대로 복사(길이 바뀌어도 됨 — PoC 2026-11-01 실기)
  글자: 파일마다 원래 128자 표는 그대로 둔다(경계 밖 미추출 문자열 보호) — 표에 있는 글자는 1바이트, 나머지는 2바이트(SJIS 첫 바이트 −0x20)
        ⇒ 2바이트 글자는 SJIS 첫 바이트 0x81~0x9F 만 가능 · 한글 = KANJI.FON 빈 한자 칸(48~62구 먼저, 그다음 16~47구)에 Galmuri14(16×16)
        반각 부호·공백 → 전각(！？，．～ 공백 → 　) · 부호 뒤 공백 지움(전프로젝트 규칙)
  ★쓰는 순간 막음: 글꼴·인코딩에 없는 글자(빌드 실패) · ／ 개수는 달라도 됨(줄 폭 18자 넘으면 경고 목록)
  MES 크기: 적재 버퍼 MES_LIMIT 넘으면 실패
  python tools/build.py [--test]   (--test = 가나·한자를 «가나다…» 시험 음절로, 같은 글자 수 → 용량·글꼴 칸 검산)"""
import csv, glob, os, re, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE)
import mes, bdf, smallfont, opsub
from extract import ORDER
DISC = os.path.join(ROOT, 'work', 'disc0'); OUT = os.path.join(ROOT, 'work', 'build')
GALMURI14 = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri14.bdf'
MES_LIMIT = 0x10000                       # MES 버퍼 0x060B0000(A.BIN 초기화 0x0600984C 가 구조체 +0x18C 에 저장) · 다음 구역 0x060C0000(0x060097DA → 0x0604BE34) ⇒ 64KB
LINE = 17                                 # 대사 창 한 줄 글자 수(원문 명시 줄 17자 207·18자 2 — 18자면 마지막 글자가 접힘, 2026-10-31 실기)
TO_FULL = {'!': '！', '?': '？', ',': '，', '.': '．', '~': '～', ' ': '　', ':': '：', '(': '（', ')': '）', '-': 'ー', '/': '／',
           '%': '％', '+': '＋', '…': '…'}
TO_FULL.update({chr(0x30 + i): chr(0xFF10 + i) for i in range(10)})
TO_FULL.update({chr(0x41 + i): chr(0xFF21 + i) for i in range(26)})
TO_FULL.update({chr(0x61 + i): chr(0xFF41 + i) for i in range(26)})
PUNCT = '!?,.~:;！？，．～：；、。…‥'
TEST_SYL = '가나다라마바사아자차카타파하거너더러머버서어저처커터퍼허'


def jis_sjis(ku, ten):
    return bytes([ku + 0xA0, ten + 0xA0]).decode('euc_jp').encode('cp932')


def load_ko(test):
    src = list(csv.DictReader(open(os.path.join(ROOT, 'work', 'text', 'script.tsv'), encoding='utf-8'), delimiter='\t', quoting=csv.QUOTE_NONE))
    jps = sorted(set(r['JP'] for r in src))
    if test:
        return {j: ''.join(TEST_SYL[i % len(TEST_SYL)] if re.match('[ぁ-んァ-ヶ一-龠]', c) else c for i, c in enumerate(j)) for j in jps}
    ko = {}
    files = [os.path.join(ROOT, 'work', 'text', 'ko_script.tsv')]       # ★병합·검사 결과(tools/merge_ko.py — my files/파넬티아번역 + ko_extra, 이름 통일·줄 나눔)
    if not os.path.exists(files[0]): sys.exit('⛔ work/text/ko_script.tsv 없음 — 먼저 kiwi-venv python tools/merge_ko.py')
    for f in files:
        for r in csv.DictReader(open(f, encoding='utf-8-sig'), delimiter='\t', quoting=csv.QUOTE_NONE):
            k = (r.get('KO') or '').strip(' \t\r\n')   # 전각 공백(줄맞춤)은 남김 - str.strip() 은 U+3000 도 지움(2026-10-31)
            if k and r.get('JP'): ko[r['JP']] = k
    return ko


def dots(m):
    n = m.group(0).count('.') + 3 * m.group(0).count('…')
    return '‥' if n == 2 else '…' * max(1, round(n / 3))                 # 점 수를 3 단위로 맞춤(섞으면 점 간격이 들쭉날쭉)


# 말줄임 점(2026-10-31 하스피 «새로 그려»): «...»가 칸마다 점 하나씩 벌어져 보임 → 점 2개 이상 줄은 …(점 3)·‥(점 2) 칸으로 묶음
#  JP 원문은 … ‥ 를 안 씀(0회) → 두 칸 그림을 바닥 점으로 새로 그림(．와 같은 2×2 점, y 12~13, x 간격 5)
DOT_GLYPH = {'…': (1, 6, 11), '‥': (3, 9)}


def dot_glyph(xs):
    rows = [0] * 16
    for x in xs:
        for y in (12, 13): rows[y] |= 0xC000 >> x
    return b''.join(struct.pack('>H', r) for r in rows)


def tidy(s):
    s = re.sub(r'[.…]{2,}|…', dots, s)                                     # 말줄임 묶기(점 수 그대로)
    s = re.sub('([%s]) +' % re.escape(PUNCT), r'\1', s)                   # 부호 뒤 공백 지움
    return ''.join(TO_FULL.get(c, c) for c in s).replace('／', '％')


def glyph(f, ch, top):
    pts, w = f.draw(ch); rows = [0] * 16
    for x, y in pts:
        yy = y - top + 1
        assert 0 <= yy < 16 and 0 <= x < 16, ('글자 칸 밖', ch, x, yy)
        rows[yy] |= 0x8000 >> x
    return b''.join(struct.pack('>H', r) for r in rows)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    test = '--test' in sys.argv
    ko = load_ko(test)
    # 1) 파일별 문자열 → 최종 글
    plan = {}; final_text = []; wide = []
    for nm in ORDER:
        d = open(os.path.join(DISC, nm + '.MES'), 'rb').read(); n, t = mes.table(d)
        segs = []
        for a, s, e in mes.runs(d):
            jp = s.replace('％', '／')
            if jp in ko:
                k = tidy(ko[jp]); segs.append((a, e, k)); final_text.append(k)
                if d[e] in (0x0C, 0x13) and any(len(l) > LINE for l in k.split('％')): wide.append('%s:%X %s' % (nm, a, k))
            else: final_text.append(s)
        if nm == 'RESET' and not test:                                    # 오프닝 음성 자막(tools/opsub.py)
            for at, k in opsub.inserts(d):
                if isinstance(k, bytes): segs.append((at, at, k)); continue  # 명령 바이트 그대로
                k = tidy(k); segs.append((at, at, '' + k)); final_text.append(k)
            segs += opsub.ends(d)                                          # 오프닝 «Z[1]/Z[2] = -1(목록 끝)» → -2(숨김)
            segs.sort(key=lambda x: x[0])
        plan[nm] = (d, n, t, segs)
    for nm, (d, n, t, segs) in plan.items(): final_text.append(t)  # 표 글자도 «쓰는 글자»
    # 2) 한글 칸 배정
    used = set(''.join(final_text))
    hang = sorted(c for c in used if '가' <= c <= '힣')
    free = []
    for ku in list(range(48, 63)) + list(range(16, 48)):
        for ten in range(1, 95):
            try: sj = jis_sjis(ku, ten); c = sj.decode('cp932')
            except UnicodeDecodeError: continue
            if sj[0] <= 0x9F and c not in used: free.append((ku, ten, sj))
    if len(hang) > len(free): sys.exit('⛔ 한글 칸 모자람 %d > %d' % (len(hang), len(free)))
    slot = dict(zip(hang, free))
    # 3) 글꼴
    fon = bytearray(open(os.path.join(DISC, 'KANJI.FON'), 'rb').read()); f = bdf.Font(GALMURI14)
    top = min(y for c in '가각힣맑앙' for x, y in f.draw(c)[0])
    for c, (ku, ten, sj) in slot.items():
        g = (ku - 1) * 94 + (ten - 1); fon[g * 32:g * 32 + 32] = glyph(f, c, top)
    for c, xs in DOT_GLYPH.items():
        e = c.encode('euc_jp'); g = (e[0] - 0xA1) * 94 + (e[1] - 0xA1); fon[g * 32:g * 32 + 32] = dot_glyph(xs)
    os.makedirs(OUT, exist_ok=True)
    for p in glob.glob(os.path.join(OUT, '*')): os.remove(p)
    open(os.path.join(OUT, 'KANJI.FON'), 'wb').write(fon)
    # 4) MES
    bad = []; sizes = []; outs = {}
    for nm, (d, n, t, segs) in plan.items():
        tix = {c: 0x80 + i for i, c in enumerate(t)}
        def enc(s):
            b = b''
            for c in s:
                if c < ' ': b += bytes([ord(c)]); continue                 # 명령 바이트(오프닝 자막 17)
                if c in tix: b += bytes([tix[c]])
                elif c in slot: sj = slot[c][2]; b += bytes([sj[0] - 0x20, sj[1]])
                else:
                    try: sj = c.encode('cp932')
                    except UnicodeEncodeError: bad.append((nm, c, s)); continue
                    if len(sj) != 2 or not 0x81 <= sj[0] <= 0x9F: bad.append((nm, c, s)); continue
                    b += bytes([sj[0] - 0x20, sj[1]])
            return b
        out = bytearray(d[:n]); k = n
        for a, e, s in segs: out += d[k:a] + (s if isinstance(s, bytes) else enc(s)); k = e
        out += d[k:]
        if not segs: continue
        outs[nm + '.MES'] = bytes(out)
    if bad: sys.exit('⛔ 인코딩 안 되는 글자 %d\n' % len(bad) + '\n'.join('%s «%s» %s' % b for b in bad[:20]))
    # 5) 작은(8×8) 글꼴 — tools/smallfont.py (A.BIN 변환 블록·글자 목록, MES 두 번째 등록 반복문·작은 문자열, FONT.B8)
    sp = smallfont.apply(outs, lambda nm: open(os.path.join(DISC, nm), 'rb').read())
    print('작은 글꼴: 음절 %d (칸 %d)' % (len(sp.syl), smallfont.NCELL - len(smallfont.FIXED)))
    for nm, b in outs.items():
        open(os.path.join(OUT, nm), 'wb').write(b)
        if nm.endswith('.MES'): sizes.append((nm[:-4], len(open(os.path.join(DISC, nm), 'rb').read()), len(b)))
    over = [x for x in sizes if x[2] > MES_LIMIT]
    big = max(sizes, key=lambda x: x[2]) if sizes else None
    print('번역 %d / %d 문장 · 한글 %d자(빈 칸 %d 중) · MES %d개' % (len(ko), len(set(r for r in ko)), len(hang), len(free), len(sizes)))
    if big: print('가장 큰 MES %s %d → %d B (한계 %d)' % (big + (MES_LIMIT,)))
    for nm, a, b in sorted(sizes, key=lambda x: -x[2])[:5]: print('  %-10s %6d → %6d (+%d)' % (nm, a, b, b - a))
    if wide: print('⚠️줄 폭 %d자 넘는 문장 %d (work/text/wide.txt)' % (LINE, len(wide)))
    open(os.path.join(ROOT, 'work', 'text', 'wide.txt'), 'w', encoding='utf-8').write('\n'.join(wide))
    if over: sys.exit('⛔ MES 적재 한계 넘침 %s' % over)


if __name__ == '__main__':
    main()
