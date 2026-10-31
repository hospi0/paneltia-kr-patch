# -*- coding: utf-8 -*-
r"""파넬티아 PoC(2026-11-01) — «문장 길이를 바꿔도 되는가» + «KANJI.FON 한자 칸 → 한글» 판정
  MACHI1.MES·START.MES 의 모든 문자열(tools/mes.py 경계)을 글자 수 같게 한글로 바꿈 → 1바이트 표 글자가 2바이트가 되어 문자열마다 길이가 늘어남
    («村人「びっくりしたなぁ、もう」» 는 실제 번역 «마을 사람「깜짝 놀랐네, 정말」» — 스샷 4 장면)
    부호(「」、。！？％・ー 공백)는 그대로, 가나·한자는 시험 음절 «가나다라…» 차례
  한글 글자 = Galmuri14(16×16 칸, 칸 고정 폭 → 14px) → KANJI.FON 2수준 한자 칸(JIS 48구~, SJIS 0x989F~) 중 MES 가 안 쓰는 칸
  → work/build/MACHI1.MES·START.MES·KANJI.FON   python tools/poc.py"""
import glob, os, re, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE)
import mes, bdf
DISC = os.path.join(ROOT, 'work', 'disc0'); OUT = os.path.join(ROOT, 'work', 'build')
GALMURI14 = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri14.bdf'
KEEP = set('「」、。！？％・ー　…（）『』：0123456789０１２３４５６７８９')
SYL = '가나다라마바사아자차카타파하거너더러머버서어저처커터퍼허'
REAL = {'村人「びっくりしたなぁ、もう」': '마을 사람「깜짝 놀랐네, 정말」'}


def sjis_of_jis(j):
    """JIS → SJIS (표준 코덱 — 2026-11-01 손 계산식이 짝수 구에서 1 어긋나 글자가 한 칸씩 밀렸음)"""
    return bytes([(j >> 8) | 0x80, (j & 0xFF) | 0x80]).decode('euc_jp').encode('cp932')


def used_chars():
    u = set()
    for f in glob.glob(os.path.join(DISC, '*.MES')):
        d = open(f, 'rb').read()
        try: n, t = mes.table(d)
        except Exception: continue
        u |= set(t)
        for a, s, e in mes.runs(d): u |= set(s)
    return u


def glyph(f, ch, top):
    pts, w = f.draw(ch); rows = [0] * 16
    for x, y in pts:
        yy = y - top + 1
        assert 0 <= yy < 16 and 0 <= x < 16, (ch, x, yy)
        rows[yy] |= 0x8000 >> x
    return b''.join(struct.pack('>H', r) for r in rows)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    os.makedirs(OUT, exist_ok=True)
    used = used_chars()
    free = []
    for ku in range(48, 63):                                              # 2수준 한자 48~62구(MES 2바이트 = SJIS 첫 바이트 0x98~0x9F 범위 안)
        for ten in range(1, 95):
            j = (ku + 0x20) << 8 | (ten + 0x20); sj = sjis_of_jis(j)
            if sj[0] > 0x9F: continue
            try: c = sj.decode('cp932')
            except UnicodeDecodeError: continue
            if c not in used: free.append((ku, ten, sj))
    need = sorted(set(SYL) | set(''.join(REAL.values())) - KEEP - set(' ,'))
    assert len(need) <= len(free)
    slot = {c: free[i] for i, c in enumerate(need)}
    enc = lambda c: bytes([slot[c][2][0] - 0x20, slot[c][2][1]])
    # 글꼴
    fon = bytearray(open(os.path.join(DISC, 'KANJI.FON'), 'rb').read()); f = bdf.Font(GALMURI14)
    top = min(y for c in '가각힣맑앙' for x, y in f.draw(c)[0])
    for c, (ku, ten, sj) in slot.items():
        g = (ku - 1) * 94 + (ten - 1); fon[g * 32:g * 32 + 32] = glyph(f, c, top)
    open(os.path.join(OUT, 'KANJI.FON'), 'wb').write(fon)
    # 문장
    for fn in ('MACHI1.MES', 'START.MES'):
        d = open(os.path.join(DISC, fn), 'rb').read(); n, t = mes.table(d); tix = {c: 0x80 + i for i, c in enumerate(t)}
        def encs(s):
            b = b''
            for c in s:
                if c in slot: b += enc(c)
                elif c == ' ': b += enc('아')[:0] + bytes([0x61, 0x40])       # 전각 공백(SJIS 8140)
                elif c == ',': b += bytes([0x61, 0x43])                       # ，(SJIS 8143)
                elif c in tix: b += bytes([tix[c]])
                else:
                    sj = c.encode('cp932'); assert len(sj) == 2 and sj[0] <= 0x9F, c; b += bytes([sj[0] - 0x20, sj[1]])
            return b
        out = bytearray(); k = n; grow = 0; cnt = 0
        out += d[:n]
        for a, s, e in mes.runs(d):
            out += d[k:a]
            if s in REAL: ko = REAL[s]
            else:
                ko = ''.join(c if c in KEEP else SYL[(i) % len(SYL)] for i, c in enumerate(s))
            nb = encs(ko); out += nb; grow += len(nb) - (e - a); cnt += 1; k = e
        out += d[k:]
        open(os.path.join(OUT, fn), 'wb').write(out)
        print('%s 문자열 %d 바꿈 · %d → %d B (+%d)' % (fn, cnt, len(d), len(out), grow))
    print('한글 칸 %d (빈 2수준 칸 %d 중) · 예: 가 = SJIS %s' % (len(slot), len(free), slot['가'][2].hex()))


if __name__ == '__main__':
    main()
