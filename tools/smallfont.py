# -*- coding: utf-8 -*-
r"""파넬티아 작은(8×8) 글꼴 한글화(2026-11-01, 정적 분석 docs/00_초기조사.md «작은 글꼴»)
  원본 구조: MES 안 `06 «반각 1바이트 문자열» 06` → 인터프리터 0x0600C34E~: 0x20 = x+8, 0x40(@) = 모드 뒤집기(문자열 시작 모드 0),
             그 밖 = 112자 목록(A.BIN 0x0602FADA)에서 위치 idx → (모드1 이고 48≤idx≤102 면 +64) → 패턴 = idx+0x32
             패턴 0x32~0xDD(172칸) = FONT.B8 시트 칸 I(x=(I%16)*8, y=(I/16)*8) — MES 머리 스크립트 반복문이 등록(J=50, I≠172)
  바꾸는 것:
   ① A.BIN 0x0600C412~0x0600C435(36 B): «모드1 이면 idx+=110 · idx≥172 면 idx+=5» (패턴 0xDE~0xE2 = 화살표 등 피함)
   ② A.BIN 0x0602FADA 112자 목록 = 새 코드표
   ③ MES 마다 두 번째 등록 반복문(J=55, I=172~221, y+32 → 시트 14~17행, 패턴 0xE3~0x114 — 23개 스테이트 모두 빈 번호)
   ④ 작은 글꼴 문자열 → 한글 코드(work/text/small_ko_v2.tsv, 원래 바이트로 맞춤) — max(원래 길이, 15) 넘으면 실패
   ⑤ FONT.B8: 칸 0~9 숫자 · 10~15 D J L R V X · 16 - · 17 / (원래 그림 복사) · 18~221 한글(Galmuri7, 색 15)
  칸 = 모드0 코드 L[i] → 칸 i(0~111) · 모드1 코드 L[i] → 칸 i+110(112~221 쓰임)"""
import csv, os, re, struct, sys, unicodedata, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE)
import bdf
DISC = os.path.join(ROOT, 'work', 'disc0')
ABIN = 0x06008000
LIST_AT = 0x0602FADA
BLOCK_AT = 0x0600C412
BLOCK2_AT = 0x0600C684                  # 두 번째 같은 꼴(상태 화면 등, 2026-10-31)
GALMURI7 = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri7.bdf'
FIXED = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'E', 'L', 'P', 'V', 'X', '-', '/']   # 2026-10-31: D J R 뺌(김특DX·에테르JR → 김특대·에테르소) · E P 넣음(상태 «EXP»)
NCELL = 222
# 글자 아닌 그림 칸 — 원래 그림 그대로(2026-10-31 저장 화면 창 틀이 한글로 깨짐: 틀 스프라이트 = 칸 39~47 타일)
#  36 ▶ · 37 = · 38/108~111/167~171 다른 숫자 0~9(y+1) · 39~47 창 틀 조각
PROTECT = set(range(36, 48)) | set(range(108, 112)) | set(range(167, 172))
SMALL = re.compile(rb'\x06([^\x00-\x1f\x06]{1,16})\x06')

# ① 변환 블록(원본 바이트 검산 후 덮음)
BLOCK_ORIG = None   # 처음 실행 때 채움(아래 patch_abin 에서 원본 36 B 길이·명령 검사)
BLOCK_NEW = [0x61F2,  # mov.l @r15,r1        ; 모드
             0x90A3,  # mov.w @(0x600C55E),r0 ; =0x15C
             0x03FE,  # mov.l @(r0,r15),r3   ; idx
             0x4110,  # dt r1                ; 모드==1 → T
             0x8B00,  # bf +0
             0x736E,  # add #110,r3
             0xE256,  # mov #86,r2
             0x4200,  # shll r2              ; 172
             0x3322,  # cmp/hs r2,r3         ; idx>=172
             0x8B00,  # bf +0
             0x7305,  # add #5,r3
             0x0F36,  # mov.l r3,@(r0,r15)
             0x0009, 0x0009, 0x0009, 0x0009, 0x0009, 0x0009]


def is_small(s):
    return re.search(rb'[\xa1-\xdf]', s) is not None


def kana(s):
    """원래 작은 글꼴 바이트 → 읽기용 가나(small_ko*.tsv 의 JP 열과 같은 규칙)"""
    o = ''; hira = False
    for b in s:
        if b == 0x40: hira = not hira; continue
        c = unicodedata.normalize('NFKC', bytes([b]).decode('cp932'))
        if hira and 'ァ' <= c <= 'ヶ': c = chr(ord(c) - 0x60)
        o += c
    return unicodedata.normalize('NFKC', o)


def load_map():
    m = {}
    for r in csv.DictReader(open(os.path.join(ROOT, 'work', 'text', 'small_ko_v2.tsv'), encoding='utf-8'), delimiter='\t', quoting=csv.QUOTE_NONE):
        m[r['JP'].strip(' ')] = r['KO'].strip(' ')
    return m


class Plan:
    def __init__(self, kos):
        syl = collections.Counter(c for k in kos for c in k if '가' <= c <= '힣')
        order = [c for c, n in syl.most_common()]
        free = [c for c in range(len(FIXED), NCELL) if c not in PROTECT]   # 한글 칸(그림 칸 PROTECT 빼고)
        if len(order) > len(free): sys.exit('⛔ 작은 글꼴 음절 %d > 칸 %d' % (len(order), len(free)))
        self.cell = {c: i for i, c in enumerate(FIXED)}
        for k, c in enumerate(order):
            self.cell[c] = free[k]
        # 0xDE·0xDF 뺌: 게임은 «다음 바이트가 ﾞ/ﾟ 면 x 안 넘김»(0x0600C51C) — 한글 코드로 쓰면 앞 글자와 겹침(2026-10-31)
        pool = [b for b in range(0xA1, 0xDE)] + [b for b in range(0x21, 0x7F) if chr(b) not in FIXED and b != 0x40]
        self.L = [ord(c) for c in FIXED] + pool[:112 - len(FIXED)]
        assert len(set(self.L)) == 112 and 0x40 not in self.L and 0x20 not in self.L and 0x06 not in self.L
        self.syl = order

    def encode(self, s):
        out = bytearray(); mode = 0
        for c in s:
            if c == ' ': out.append(0x20); continue
            if c not in self.cell: raise KeyError(c)
            cl = self.cell[c]
            want = 0 if cl < 112 else 1
            if want != mode: out.append(0x40); mode = want
            out.append(self.L[cl] if want == 0 else self.L[cl - 110])
        return bytes(out)


def loop2(mes):
    """원래 등록 반복문 바로 뒤에 넣을 두 번째 반복문"""
    a = mes.find(b'\x0c\x4a\x07\xcb\x03\x0c\x49\x30\x03\x04\x10\x0f\x49\x08\x0b\xc3\x34\x21\x28\x03\x01')
    if a < 0: return None, None
    e = mes.find(b'\x0c\x49\x49\x31\x20\x03\x00', a) + 7
    orig = mes[a:e]
    new = orig.replace(b'\x0c\x4a\x07\xcb\x03', b'\x0c\x4a\x07\xdf\x03', 1)                       # J = 55
    new = new.replace(b'\x0c\x49\x30\x03', b'\x0c\x49\x08\x0b\xb3\x03', 1)                       # I = 172
    new = new.replace(b'\x08\x0b\xc3\x34\x21\x28', b'\x08\x0f\x7b\x28', 1)                       # I != 222
    y1, y2 = b'\x49\x07\x43\x23\x38\x22\x03', b'\x49\x07\x43\x23\x38\x22\x37\x20\x03'
    assert new.count(y1) == 1 and new.count(y2) == 1, '반복문 꼴 다름'
    new = new.replace(y2, y2[:-1] + b'\x07\x83\x20\x03').replace(y1, y1[:-1] + b'\x07\x83\x20\x03')   # y += 32
    return e, new


def patch_mes(d, plan, m, bad):
    e, l2 = loop2(d)
    out = bytearray(); k = 0
    for mt in SMALL.finditer(d):
        s = mt.group(1)
        if not is_small(s):
            if s.strip(b' ') == b'EXP':                                   # 상태 화면 «EXP» — 영문도 새 코드표로(원래 바이트면 «사X0», 2026-10-31 실기)
                out += d[k:mt.start(1)] + plan.encode(s.decode()); k = mt.end(1)
            continue
        jp = kana(s).strip(' ')
        if jp not in m: bad.append(('번역 없음', jp)); continue
        ko = m[jp]
        lead = len(s) - len(s.lstrip(b' '))                               # 줄 맞춤 공백은 원래대로(앞 그대로, 뒤는 원래 길이까지 채움)
        try: nb = b' ' * lead + plan.encode(ko)
        except KeyError as x: bad.append(('글자', jp, str(x))); continue
        if len(nb) > max(len(s), 15): bad.append(('길이', jp, ko, len(s), len(nb))); continue   # 램 이름 칸 16 B(0x060A9F80~) — MES 길이는 자유, @ 전환 바이트 때문에 원래보다 길 수 있음
        vis = lambda x: len(x) - x.count(b'@') - x.count(0xDE) - x.count(0xDF)   # ﾞﾟ 도 자리 안 차지(앞 글자에 겹침, 0x0600C51C) · 찍히는 폭(@ = 모드 전환, 자리 안 차지) — 수치·장비 이름이 라벨 폭 바로 뒤에 찍힘(2026-10-31 실기: 바이트 길이로 맞춰 줄 어긋남)
        if s.endswith(b' '):
            if vis(nb) > vis(s): bad.append(('폭', jp, ko, vis(s), vis(nb))); continue
            nb += b' ' * (vis(s) - vis(nb))
        out += d[k:mt.start(1)] + nb; k = mt.end(1)
    out += d[k:]
    d = bytes(out)
    if l2:
        e2, _ = loop2(d)                                                  # 문자열 바꾼 뒤 위치 다시
        d = d[:e2] + l2 + d[e2:]
    return d


def patch_abin(d, plan):
    d = bytearray(d)
    o = BLOCK_AT - ABIN
    orig = struct.unpack_from('>18H', d, o)
    assert orig[0] == 0x60F2 or orig[:1] == (0x60F2,), ('변환 블록 원본 다름', hex(orig[0]))
    struct.pack_into('>18H', d, o, *BLOCK_NEW)
    # 2026-10-31 실기: 상태 화면·소지금(«D력»·«JL력»·«04») = 같은 꼴의 두 번째 변환 블록 0x0600C684~(36 B, 바깥 분기 없음) — 0x15C 리터럴만 0x0600C7DC
    o2 = BLOCK2_AT - ABIN
    orig2 = struct.unpack_from('>18H', d, o2)
    assert orig2[0] == 0x60F2 and orig2[4] == 0x90A6, ('두 번째 변환 블록 원본 다름', [hex(x) for x in orig2[:4]])
    struct.pack_into('>18H', d, o2, *([BLOCK_NEW[0], 0x90A9] + BLOCK_NEW[2:]))
    lo = LIST_AT - ABIN
    assert d[lo:lo + 16] == b'0123456789ABCDEF', '112자 목록 원본 다름'
    d[lo:lo + 112] = bytes(plan.L)
    return bytes(d)


def cell_xy(c):
    return (c % 16) * 8, (c // 16) * 8 + (32 if c >= 172 else 0)


def sheet(plan):
    f = bytearray(open(os.path.join(DISC, 'FONT.B8'), 'rb').read()); W = 320
    src = {}
    for i, ch in enumerate(open(os.path.join(DISC, 'A.BIN'), 'rb').read()[LIST_AT - ABIN:LIST_AT - ABIN + 112].decode('latin1')):
        src.setdefault(ch, i)                                             # 첫 자리(«0»은 0번 = 밝은 0 · 38번 = 흐린 0 — 마지막 걸 잡아 0 이 흐렸음, 2026-10-31)
    def get(c):
        x, y = c % 16 * 8, c // 16 * 8
        return [f[(y + j) * W + x:(y + j) * W + x + 8] for j in range(8)]
    fixed_px = {i: get(src[ch]) for i, ch in enumerate(FIXED)}
    for c in range(NCELL):                                                # 지우기(그림 칸은 그대로)
        if c in PROTECT: continue
        x, y = cell_xy(c)
        for j in range(8): f[(y + j) * W + x:(y + j) * W + x + 8] = bytes(8)
    for i, rows in fixed_px.items():
        x, y = cell_xy(i)
        for j in range(8): f[(y + j) * W + x:(y + j) * W + x + 8] = rows[j]
    g = bdf.Font(GALMURI7)
    for ch, c in plan.cell.items():
        if c < len(FIXED): continue
        x, y = cell_xy(c)
        for px, py in g.draw(ch)[0]:
            yy = py - 2 + 1                                               # Galmuri7 한글 y 2~8 → 1~7
            assert 0 <= px < 8 and 0 <= yy < 8, (ch, px, yy)
            f[(y + yy) * W + x + px] = 15
    return bytes(f)


def apply(new, read):
    """build.py 에서: new = {파일이름: 바이트} (MES 는 이름.MES), read(이름) = 원본/현재 바이트"""
    m = load_map()
    plan = Plan(m.values())
    bad = []
    for nm in [x for x in os.listdir(DISC) if x.endswith('.MES') and x != 'STAFF.MES' and x != 'MACHI.MES']:
        d = new.get(nm) or read(nm)
        new[nm] = patch_mes(d, plan, m, bad)
    if bad: sys.exit('⛔ 작은 글꼴 %d\n' % len(bad) + '\n'.join(map(str, bad[:20])))
    new['A.BIN'] = patch_abin(read('A.BIN'), plan)
    new['FONT.B8'] = sheet(plan)
    return plan
