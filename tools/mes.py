# -*- coding: utf-8 -*-
r"""파넬티아 스토리 .MES 문자열 해독(2026-11-01 조사용, 경계는 휴리스틱 — 바이트코드 해석 전)
  머리: u16 LE = 글자 표 끝(2+2n) · 글자 표 = SJIS n자 · 대사 = 03 뒤 ~ 0C 앞(％ = 줄바꿈) · 메뉴 = 00 끝 · 본문 글자: 0x80+i = 표[i] · 0x40~0x7F 첫 바이트 = SJIS(첫 바이트+0x20, 둘째 그대로)
  python tools/mes.py → work/text/mes_raw.tsv (파일·위치·글자)"""
import glob, os, struct, sys, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def table(d):
    n = struct.unpack('<H', d[:2])[0]
    return n, d[2:n].decode('cp932')


def runs(d):
    n, t = table(d); i = n; out = []
    while i < len(d):
        j = i; s = ''
        while j < len(d):
            b = d[j]
            if b >= 0x80 and b - 0x80 < len(t): s += t[b - 0x80]; j += 1
            elif 0x40 <= b < 0x80 and j + 1 < len(d) and 0x40 <= d[j + 1] <= 0xFC and d[j + 1] != 0x7F:
                try: s += bytes([b + 0x20, d[j + 1]]).decode('cp932'); j += 2
                except UnicodeDecodeError: break
            else: break
        kana = len(re.findall('[ぁ-んァ-ヶー・、。「」！？％…]', s))
        one = d[i - 1] == 1 and j < len(d) and ((d[j] == 0 and re.fullmatch('[一-龠●ー々]+', s)) or (d[j] == 0x0D and re.fullmatch('[一-龠々]{2,}：', s)))   # 한자만 이름(파넬 森·平地…, ●) — 01 뒤 00 끝 (2026-11-01 가나 비율에 걸려 빠졌음) · 01 뒤 «攻撃力：» 꼴 + 0D(수치 끼움) 끝(2026-10-31 실기 미추출)
        if (len(s) >= 2 or one) and j < len(d) and d[j] < 0x40 and d[i - 1] in (0, 1, 2, 3, 0x11, 0x17) and (one or kana >= len(s) * 0.3) and re.search('[ぁ-んァ-ヶ一-龠]', s):   # 2026-10-31 02 = 메뉴 둘째 항목부터 · 17 = 이벤트(음성) 대사 · 11 — 실기 미추출
            out.append((i, s, j)); i = j                                     # 00/01/03 뒤 시작 · 제어 바이트(<0x40: 0C 대사 끝·13·02·00) 앞 끝 — 피연산자 잡음은 가나 비율로 거름
        else: i += 1
    return out


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    os.makedirs(os.path.join(ROOT, 'work', 'text'), exist_ok=True)
    o = open(os.path.join(ROOT, 'work', 'text', 'mes_raw.tsv'), 'w', encoding='utf-8')
    o.write('파일\t위치\t글자\n'); allu = {}; tot = 0
    for f in sorted(glob.glob(os.path.join(ROOT, 'work', 'disc0', '*.MES'))):
        d = open(f, 'rb').read()
        try: r = runs(d)
        except Exception as e: print(os.path.basename(f), e); continue
        for a, s, e in r: o.write('%s\t%X\t%s\n' % (os.path.basename(f), a, s)); allu.setdefault(s, f); tot += len(s)
        print('%-12s 문자열 %5d 글자 %6d' % (os.path.basename(f), len(r), sum(len(s) for a, s, e in r)))
    print('합계 글자 %d · 고유 문자열 %d · 고유 글자 %d' % (tot, len(allu), sum(len(s) for s in allu)))
