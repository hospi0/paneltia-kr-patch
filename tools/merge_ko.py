# -*- coding: utf-8 -*-
r"""파넬티아 번역 병합·검사(2026-11-01) — my files/파넬티아번역/*.tsv(하스피, 처음 판 pt 번호) + work/text/ko_extra.tsv → work/text/ko_script.tsv(JP·KO)
  맞추기: JP 원문 그대로(번호 무시) — 원문에 없는 JP·빈 KO 는 목록
  통일(이름·용어): NAMES — 다수 쪽으로(2026-11-01 집계), 작은 글꼴 이름(work/text/small_ko_v2.tsv)도 같은 표기
  부호: 부호 뒤 공백 지움(전프로젝트 규칙) · · → ・ · 반각 ' 짝 → 『』(원문 『』·” 자리) · 앞뒤 공백 지움
  폭: 한 칸 = 한 글자(공백·영숫자도 전각으로 찍힘) · 대사 창 18칸 × 3줄(원문 대사 최대 3줄, 줄 17~18자)
      넘치면 그 문자열 안에서 낱말 단위로 다시 나눔(번역자가 낱말 중간에서 끊은 곳은 Kiwi 로 판정해 붙임) — 줄 수 max(원문, 3)
      그래도 넘치면 목록(쪽을 늘릴 토큰이 없음 — 문장을 줄여야 함, 하스피 확인)
  토큰: 이 게임 문자열 안에는 제어 코드 없음(경계 밖) — ／ 개수는 달라도 됨(창 안이면)
  글자: 빌더가 못 찍는 글자(SJIS 2바이트 0x81~0x9F 밖·한글 아님) 목록
  C:/claude/utils/kiwi-venv/Scripts/python tools/merge_ko.py"""
import csv, glob, os, re, sys, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = 17   # 대사 창 17칸(원문 명시 줄 17자 207 · 18자 2 — 18자 줄은 마지막 글자가 다음 줄로 접혀 쪽이 깨짐, 2026-10-31 실기)
NAMES = [('마을 처녀 티파', '처녀 티파'), ('마을 처녀 안나', '처녀 안나'), ('케른', '케룬'), ('켈른', '케룬'), ('손님1', '손님１'),
         ('수수께끼의 남자', '수수께끼 남자'), ('별똥별의 정령', '별똥별 요정'), ('파넬레스 셉터', '패널레스셉터')]
PUNCT = ',.!?~:;…、。，．！？～：；'
KO_FIX = {   # 18칸 × 3줄에 안 들어가 Claude 가 줄인 문장(2026-11-01, 하스피 확인 필요 — 보고서 «줄임»)
    '青年「興味がありそうだな。／・・・・・・・・・・・・・・・・／バーテンにでもくわしく聞くんだな」': '청년「관심 있어 보이는군.／・・・・・・・・・・・・・・・・／바텐더한테 자세히 물어봐」',
    'ケーモネカ「さすがワシが見込んだ／子だ。ケルン君、商売を一緒に／やらんか？君にはその素質がある」': '케모네카「내 눈이 맞았구나.／케룬 군,같이 장사해 보지／않겠나?자네는 소질이 있어」',
    '店主「じつは、四方を山で囲まれた／岩場には洞窟があり、その奥には／伝説の剣がねむっているとか・・・」': '주인「사방이 산으로 둘러싸인／바위 지대에 동굴이 있고,／그 안에 전설의 검이 있다나…」',
    # 2026-10-31 대사 창 17칸으로 고친 뒤 3줄 넘침 — 하스피 «줄여»
    'おじさん「やっぱり、酔うなら／酒かっくらって気分良く酔いてぇな／今は母ちゃんに止められてるけどな」': '아저씨「취할 거면 역시／술 퍼마시고 기분 좋게／취하고 싶은데 마누라가 말려」',
    '村娘ティファ「ゆっくりお茶の時間も／楽しめないし、お昼寝してても、／ぐらぐらしちゃうと眠れないわ」': '처녀 티파「차 마실 시간도／못 즐기고,낮잠을 자려 해도／흔들려서 잠이 안 와」',
    '謎の男「そうか、頼まれてくれるか。／ではこれで旅の支度を整えるがよい。／私はここで待っているぞ」': '수수께끼 남자「들어주겠나.／그럼 이걸로 채비를 갖추게.／나는 여기서 기다리겠네」',
    '謎の男「なんと！この私の頼みを断る／と申すか！・・うーむ、そこを／なんとか頼まれてはくれまいか」': '수수께끼 남자「뭐라!내 부탁을／거절하겠다고!..으음,제발／들어주지 않겠나」',
    '長老「村に代々伝わる回復の剣を／差し上げよう。これでモンスターを／退治してくれんか？」': '장로「마을의 가보인／회복의 검을 주겠다.이걸로／몬스터를 퇴치해 주겠느냐?」',
    '村娘アンナ「でも、村をもう一つ／大きくしないとパネル屋はないから、／まず村を大きくしてね」': '처녀 안나「하지만 마을을／더 키워야 패널 가게가／생기니까 먼저 키워 주세요」',
    # 2026-10-31 메뉴 창이 원문 길이로 잡혀 긴 항목이 잘림(«처음부터 시작한」) — 하스피 «바꾸는 안으로 다 고쳐»
    '武器を装備する': '무기 장비', 'そうです': '네', 'もう一度': '다시', 'データのロード': '불러오기', '洞窟の作り方': '동굴 만들기',
    'ゲームに戻る': '게임으로', '戦闘なしモード': '전투 없음', '戦闘ありモード': '전투 있음', 'ステージ１へ行く': '스테이지１로',
    'おばちゃん「今いるこの村はね、／『れべるの村』と言って、村の広さが／変わる不思議な村なんだよ」': '아주머니「이 마을은／『레벨의 마을』이라 하는데／크기가 변하는 신기한 마을이야」',
}
_KIWI = None
JOSA = {'만', '에', '에서', '을', '를', '은', '는', '도', '로', '으로', '와', '과', '고', '다고', '라고', '의', '께', '한테', '처럼', '까지', '부터', '보다', '조차', '마저', '이나'}
STANDALONE = {'나', '너', '저', '제', '내', '네', '이건', '이거', '그건', '그거', '이', '그', '저건', '저거'}


def width(s): return len(s)


def tidy(s):
    s = s.strip(' ').replace('·', '・')
    for a, b in NAMES: s = s.replace(a, b)
    if s.count("'") % 2 == 0 and "'" in s:
        n = [0]
        def q(m):
            n[0] += 1; return '『' if n[0] % 2 else '』'
        s = re.sub("'", q, s)
    s = re.sub('([%s]) +' % re.escape(PUNCT), r'\1', s)
    s = '／'.join(l.strip(' ') for l in s.split('／'))
    return s


def glue(a, b):
    """(실크 외전 merge_ko 와 같음) 번역자 줄 끝 a / 다음 줄 b 를 붙일지 — 낱말 중간 끊김"""
    global _KIWI
    m = re.match(r'[가-힣]+', b)
    if not a or not m or a[-1] in ' ／': return False
    b2 = m.group(0)
    if b2 in STANDALONE: return False
    if re.fullmatch('[오아어우으요]+', b2) and re.search(r'[가-힣]$', a): return True
    if b2 in JOSA and (len(b) == len(b2) or not re.match(r'[가-힣]', b[len(b2)])): return True
    if not re.search(r'[가-힣]$', a): return False
    if _KIWI is None:
        from kiwipiepy import Kiwi
        _KIWI = Kiwi()
        for n in ('케룬', '티파', '안나', '로자', '케모네카', '클레어', '티라', '루체', '미샤'): _KIWI.add_user_word(n, 'NNP')
    a2 = re.search(r'[가-힣]+$', a).group(0); L = len(a2)
    alone = _KIWI.tokenize(b2)[0].tag
    tb = [x for x in _KIWI.tokenize(a2 + b2) if x.start == L]
    comb = tb[0].tag if tb else '-'
    return bool(re.match(r'J|E|VCP|XSV|XSA', alone) or re.match(r'XSV|XSA|VCP|E', comb))


def orphan(l):
    return 0 < width(l.rstrip('」』 ')) <= 2 and not re.fullmatch(r'[…」』！？!?、。，,.\s~～・]*', l)


def rewrap(page, maxlines):
    lines = page.split('／')
    ls = [l.strip(' ') for l in lines]
    text = ls[0]
    for l in ls[1:]: text += ('\u200b' if glue(text, l) else ' ') + l
    words = []; soft = set()
    for part in text.split('\u200b'):
        words += re.findall(r'(?:[^\s…・]|[…・]+(?=[…・」』）！？!?、。，]|$))+[…・]*\s*|[…・]+\s*', part)
        soft.add(len(words))
    N = len(words)
    from functools import lru_cache

    @lru_cache(None)
    def go(i, k):
        if i == N: return (0, ())
        if k == 0: return None
        res = None
        for j in range(i + 1, N + 1):
            l = ''.join(words[i:j]).rstrip()
            if width(l) > W: break
            sub = go(j, k - 1)
            if sub is None: continue
            c = ((W - width(l)) ** 2 + (10 ** 6 if j in soft else 0)) if j < N else (10 ** 5 if orphan(l) else 0)
            if res is None or c + sub[0] < res[0]: res = (c + sub[0], (l,) + sub[1])
        return res
    for k in range(1, maxlines + 1):
        r = go(0, k)
        if r: return '／'.join(r[1])
    return None


def encodable(c):
    if '가' <= c <= '힣' or c in ' ／': return True
    try: b = c.encode('cp932')
    except UnicodeEncodeError: return False
    return (len(b) == 2 and 0x81 <= b[0] <= 0x9F) or (len(b) == 1 and 0x20 < b[0] < 0x7F)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    src = list(csv.DictReader(open(os.path.join(ROOT, 'work', 'text', 'script.tsv'), encoding='utf-8'), delimiter='\t', quoting=csv.QUOTE_NONE))
    end = {}
    for r in src: end.setdefault(r['JP'], r['끝'])
    ko = {}; extra = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'my files', '파넬티아번역', '*.tsv'))) + [os.path.join(ROOT, 'work', 'text', 'ko_extra.tsv')]:
        for r in csv.DictReader(open(f, encoding='utf-8-sig'), delimiter='\t', quoting=csv.QUOTE_NONE):
            if r['JP'] not in end: extra.append(r['JP']); continue
            if (r.get('KO') or '').strip(): ko[r['JP']] = r['KO']
    miss = [j for j in end if j not in ko]
    rep = collections.defaultdict(list); final = {}; cnt = collections.Counter()
    for jp, raw in ko.items():
        k = tidy(KO_FIX.get(jp, raw))
        if jp in KO_FIX: rep['줄임(확인 필요)'].append('%s | %s → %s' % (jp, raw, KO_FIX[jp]))
        if k != raw.strip(' '): cnt['통일·부호'] += 1
        bad = [c for c in k if not encodable(c)]
        if bad: rep['못 찍는 글자'].append('%s | %s | %s' % (''.join(sorted(set(bad))), jp, k))
        jl = jp.split('／'); maxl = max(len(jl), 3, -(-len(jp) // W) if len(jl) == 1 else 0)   # 원문 한 줄 긴 안내문(64자)은 게임이 여러 줄로 접음
        jw = max(len(l) for l in jl)
        lim = W                                                           # 원문이 자동 줄바꿈에 맡긴 긴 줄(설명 19~25자)도 18칸에서 직접 나눔(％ = 0x8193 은 같은 출력 함수가 처리, 0x0600C882)
        kl = k.split('／')
        if jp.startswith('　') and k.startswith('　') and len(kl) == len(jl) and all(width(a) <= len(b) for a, b in zip(kl, jl)): pass   # 원문 줄보다 안 넓으면 그대로(전각 공백 줄맞춤 «　×8しばらく…» 19칸 보존, 2026-10-31)
        elif any(width(l) > lim for l in k.split('／')) or len(k.split('／')) > maxl:
            r = rewrap(k, maxl)
            if r is None: rep['넘침(줄이기 필요)'].append('%s | %s' % (jp, k))
            else: k = r; cnt['다시 나눔'] += 1
        elif any(orphan(l) for l in k.split('／')[:-1]):
            r = rewrap(k, maxl)
            if r and r != k: k = r; cnt['한두 글자 줄 정리'] += 1
        final[jp] = k
    # 이름 통일 뒤 남은 갈림(화자 이름)
    nm = collections.defaultdict(collections.Counter)
    for jp, k in final.items():
        a = re.match('^([^「／]{1,10})「', jp); b = re.match('^([^「／]{1,12})「', k)
        if a and b: nm[a.group(1)][b.group(1)] += 1
    for a, c in nm.items():
        if len(c) > 1: rep['화자 이름 갈림'].append('%s %s' % (a, dict(c)))
    with open(os.path.join(ROOT, 'work', 'text', 'ko_script.tsv'), 'w', encoding='utf-8', newline='\n') as o:
        o.write('JP\tKO\n')
        for jp in end:
            if jp in final: o.write('%s\t%s\n' % (jp, final[jp]))
    with open(os.path.join(ROOT, 'work', 'text', 'merge_report.txt'), 'w', encoding='utf-8') as o:
        o.write('번역 %d / %d · 빠짐 %d · 원문에 없는 JP %d\n바뀜 %s\n\n' % (len(final), len(end), len(miss), len(extra), dict(cnt)))
        for j in miss: o.write('빠짐 | %s\n' % j)
        for k, v in rep.items():
            o.write('\n== %s %d\n' % (k, len(v)))
            for x in v: o.write(x + '\n')
    print('번역 %d / %d · 빠짐 %d · 원문에 없는 JP %d · 바뀜 %s' % (len(final), len(end), len(miss), len(extra), dict(cnt)))
    for k, v in rep.items(): print('  %s %d' % (k, len(v)))


if __name__ == '__main__':
    main()
