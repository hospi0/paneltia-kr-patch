# -*- coding: utf-8 -*-
r"""오프닝 음성 자막(2026-10-31) — RESET.MES 스크립트에 대사 문장을 끼움(어셈블리 훅 없음)
  게임 안 음성 대사 장면(MACHI3 등)의 꼴을 흉내: `04 25 06 «음성.aif» 06 …재생 대기 반복문… 04 24 38 03` 바로 뒤에 `17 «글»`
  (17 = 음성 대사 장면에서 글 앞에 오는 명령 — 추출기가 놓쳤던 «앞 바이트 17» 대사들과 같은 꼴)
  번역: work/voice/opening_ko.tsv (no·voice·JP·KO) — build.py 가 segs 에 (자리, 자리, '\x17' + 글) 로 넣음
  ⏳시험: 17 이 버튼을 기다리는지·창 없이 어디에 찍히는지·다음 조각 전에 지워지는지 실기 확인"""
import csv, os, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAIL = b'\x04\x24\x38\x03'
# 대사 창 글자 그림 열기(2026-10-31 2차 — 1차 «17 글»만은 실기에서 안 보임: 오프닝엔 글자 그림 객체가 없음)
#  START.MES 세이브 화면·MACHI 음성 대사 장면이 대사마다 되풀이하는 두 문장 그대로:
#  0c 4a … = J(그림 번호) 대입 · 04 1a 34 … = 함수 1A(4, J, x 24, y 160, 295, 207, 320) 글자 그림 272×48 만들기(지움)
#  0d 5a 07 57 38 22 … = 객체 21번(Z[21*8]) 에 그 그림 표시 — 오프닝 그림은 객체 0·1 번
OPEN_A = bytes.fromhex('0c4a080f8b03' '041a3403024a030207630302080b83030208139f0302080f3f030208170303')
OPEN_B = bytes.fromhex('0d5a0757382203080f8b03020763030208 0b830302093fffff0302093fffff0302350302300302300 3'.replace(' ', ''))
# 3차(2026-10-31): Z 객체 표에서 그림 번호 -1(ffff) = 목록 끝 · -2(fffe) = 숨김(건너뜀) — 오프닝은 Z[0] 그림 + Z[1] = -1 로 끝내서
#  Z[21] 자막까지 안 감(2차 실기 «아예 안 뜸», 스테이트 opsub_test2: Z[21] 들어가 있으나 VDP1 엔 그림 1장)
#  → 자막 객체를 Z[3] 에 · Z[2] = -2 · Z[4] = -1(끝) · 오프닝 구간의 «Z[1]/Z[2] = -1» 을 -2 로(같은 길이 제자리)
Z = lambda k: bytes([0x0d, 0x5a, 0x30 + k, 0x38, 0x22, 0x03])
NEG1, NEG2 = bytes.fromhex('093fffff'), bytes.fromhex('093ffffb')
OPEN_B3 = OPEN_B.replace(bytes.fromhex('0d5a0757382203'), Z(3), 1)
OPEN = OPEN_A + OPEN_B3
# 4차(2026-10-31, 3차 실기: 첫 화면에 옛 객체 Z[2]… 가 그려져 깨짐 · 자막 자리엔 검은 상자만(글 안 찍힘))
#  ① «Z[1]/Z[2] = -1» 자리마다 Z[k..3] = -2, Z[4] = -1 로 늘려 씀(옛 객체 안 그림, 장면 바뀌면 자막 Z[3] 도 숨김)
#  ② 글 앞에 MES 첫머리 대사 준비 꼴 그대로: 0d 40 3d … = @[13] 글 영역(24,160~295,208) · 18 08 0b 1f 03 — 그다음 17 «글»
TEXT_PREP = bytes.fromhex('0d403d030763030208' '0b830302' '08139f03' '02080f43' '03' '18080b1f03')


def load():
    p = os.path.join(ROOT, 'work', 'voice', 'opening_ko.tsv')
    return {r['voice']: r['KO'] for r in csv.DictReader(open(p, encoding='utf-8'), delimiter='\t', quoting=csv.QUOTE_NONE) if r['KO'].strip()}


def inserts(d):
    """RESET.MES 원본 바이트 → [(자리, 한글 글)] (자리 = 재생 대기 뒤 04 24 38 03 끝)"""
    ko = load(); out = []
    for m in re.finditer(rb'\x04\x25\x06(op[a-z0-9_]+)\.aif\x06', d):
        v = m.group(1).decode()
        if v not in ko: continue
        e = d.find(TAIL, m.end())
        nxt = d.find(b'\x04\x25\x06', m.end())
        assert e > 0 and (nxt < 0 or e < nxt) and d[e - 2:e] == b'\x03\x00', ('재생 대기 꼴 다름', v, hex(m.start()))   # 대기 반복문 끝 03 00
        # 6차 순서: 대사 준비 → 17 글 → 함수 1A(4) = 쌓인 글을 그림 226 에 찍기 → Z[3] 표시 → 재생
        #  (5차 «상자 → 글 → 재생» 은 여전히 한 토막 밀림: 1A(4) 가 «앞서 쌓인 글»을 찍는 것 — 게임 대사 장면도 글 뒤에 1A(4))
        out.append((m.start(), TEXT_PREP))
        out.append((m.start(), ko[v]))
        out.append((m.start(), OPEN))
    assert len(out) == 3 * len(ko), ('자막 수 ≠ 음성 수', len(out), len(ko))
    return out


def ends(d):
    """오프닝 구간(첫 opa1a 재생 ~ 마지막 opb9 재생 대기 끝)의 «Z[1]/Z[2] = -1» 자리 → [(자리, 끝, -2 바이트)]"""
    a = d.rfind(Z(0), 0, d.find(b'\x04\x25\x06opa1a.aif')); b = d.find(TAIL, d.find(b'\x04\x25\x06opb9.aif')) + len(TAIL)
    loops = []                                                            # 음성 재생 ~ 재생 대기 끝(이 안의 쓰기는 자막 Z[3] 을 남김 — 7차, opa3a1 그림 흔들기 반복문)
    for m in re.finditer(rb'\x04\x25\x06op[a-z0-9_]+\.aif\x06', d): loops.append((m.start(), d.find(TAIL, m.end())))
    out = []
    for k in (1, 2):
        pat = Z(k) + NEG1
        i = d.find(pat, a)
        while 0 <= i < b:
            keep = any(s < i < e for s, e in loops)
            rep = b''.join(Z(j) + NEG2 + b'\x03' for j in range(k, 4) if not (keep and j == 3)) + Z(4) + NEG1   # 원래 뒤 03 은 그대로 남음
            out.append((i, i + len(pat), rep)); i = d.find(pat, i + 1)
    # 7차: opb9(«이렇게 케룬은…» 나레이션) 바로 앞 페이드아웃 04 16 33 03 을 재생 대기 뒤로 미룸 — 원래는 꺼진 화면에서 나레이션(자막 안 보임)
    p = d.find(b'\x04\x25\x06opb9.aif'); f = p - 4
    assert d[f:p] == FADE_OUT, ('opb9 앞 페이드아웃 꼴 다름', d[f - 8:p].hex())
    out.append((f, p, b''))
    out.append((b, b, FADE_OUT))
    return out


FADE_OUT = b'\x04\x16\x33\x03'
