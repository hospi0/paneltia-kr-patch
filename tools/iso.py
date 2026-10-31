# -*- coding: utf-8 -*-
r"""파넬티아 트랙 1 파일 바꿔 넣기(2026-11-01, 다이노 아일랜드 tools/iso.py 를 옮김 — 같은 배치).
  원본: 파일이 LBA 순으로 빈틈없이 이어지고 마지막 진짜 파일(SUGA.AN2)이 LBA 30251 에서 끝, 뒤 150섹터 = 뒷간격(0), 트랙 1 = 30,401섹터.
        ★/SEGACDDA(LBA 30551, 1.2 MB)는 트랙 2(오디오) 자리를 가리키는 기록 → 트랙 1 이 늘면 같은 만큼 옮긴다.
        PVD 볼륨 크기 = 31,151(= SEGACDDA 끝) → 같이 늘린다.
  규칙: 새 파일이 원래 섹터 수 안이면 제자리(남는 곳 0), 넘치면 파일 영역 끝(30251 부터)에 차례로 붙이고 그 뒤 뒷간격 150섹터.
        디렉터리 기록 LBA·크기(양 엔디안), 쓴 섹터는 헤더·EDC/ECC 새로(유나 리믹스 iso.sector).
        트랙 2 는 cue 에서 따로 파일(.bin)이라 트랙 1 이 늘어도 cue 는 그대로.
  from iso import patch; patch(dst, {'/MACHI1.MES': bytes, ...})"""
import importlib.util, os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import disc

_sp = importlib.util.spec_from_file_location('yuna_iso', r'C:\claude\project\yunaremix-kr-patch\tools\iso.py')
_y = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(_y)
sector = _y.sector
FILES_END = 30251; GAP = 150; TRACK = 30401; AUDIO_REC = '/SEGACDDA'


def records(f):
    """(경로, 디렉터리 섹터 LBA, 기록 자리, LBA, 크기)"""
    pvd = disc.sec(f, 16); out = []
    def walk(lba, size, pre):
        for k in range((size + 2047) // 2048):
            d = disc.sec(f, lba + k); i = 0
            while i < 2048 and d[i]:
                L = d[i]; nm = d[i + 33:i + 33 + d[i + 32]]
                if nm not in (b'\0', b'\1'):
                    n = nm.decode('latin1').split(';')[0]
                    el, sz, fl = struct.unpack_from('<I', d, i + 2)[0], struct.unpack_from('<I', d, i + 10)[0], d[i + 25]
                    if fl & 2: walk(el, sz, pre + n + '/')
                    else: out.append((pre + n, lba + k, i, el, sz))
                i += L
    walk(struct.unpack_from('<I', pvd, 156 + 2)[0], struct.unpack_from('<I', pvd, 156 + 10)[0], '/')
    return out


def patch(dst, files, log=print):
    src = disc.bin_path(0)
    f = open(src, 'rb'); recs = {r[0]: r for r in records(f)}
    assert os.path.getsize(src) == TRACK * 2352
    last = max(r[3] + (r[4] + 2047) // 2048 for r in recs.values() if r[0] != AUDIO_REC)
    assert last == FILES_END, ('파일 영역 끝이 다름', last)
    plan = {}; cur = FILES_END
    for name, data in sorted(files.items()):
        _, dl, di, lba, size = recs[name]
        if (len(data) + 2047) // 2048 <= (size + 2047) // 2048: plan[name] = lba
        else: plan[name] = cur; cur += (len(data) + 2047) // 2048
    grow = cur - FILES_END; newsec = TRACK + grow
    with open(dst, 'wb') as o:
        f.seek(0); left = FILES_END * 2352
        while left:
            b = f.read(min(left, 1 << 24)); o.write(b); left -= len(b)
        for lba in range(FILES_END, newsec): o.write(sector(lba, bytes(2048)))   # 새 자리 + 뒷간격(0, 헤더 새로)
    with open(dst, 'r+b') as o:
        for name, data in files.items():
            lba = plan[name]; _, dl, di, olba, osize = recs[name]
            n = max((len(data) + 2047) // 2048, (osize + 2047) // 2048 if lba == olba else 0)
            for k in range(n):
                o.seek((lba + k) * 2352); o.write(sector(lba + k, data[k * 2048:(k + 1) * 2048].ljust(2048, b'\0')))
        dirs = {}
        def setrec(name, lba, size):
            _, dl, di, _, _ = recs[name]
            if dl not in dirs: o.seek(dl * 2352 + 16); dirs[dl] = bytearray(o.read(2048))
            d = dirs[dl]
            struct.pack_into('<I', d, di + 2, lba); struct.pack_into('>I', d, di + 6, lba)
            struct.pack_into('<I', d, di + 10, size); struct.pack_into('>I', d, di + 14, size)
        for name, data in files.items(): setrec(name, plan[name], len(data))
        if grow:
            _, _, _, tl, ts = recs[AUDIO_REC]; setrec(AUDIO_REC, tl + grow, ts)
        for dl, d in dirs.items(): o.seek(dl * 2352); o.write(sector(dl, bytes(d)))
        if grow:
            o.seek(16 * 2352 + 16); p = bytearray(o.read(2048))
            v = struct.unpack_from('<I', p, 80)[0] + grow
            struct.pack_into('<I', p, 80, v); struct.pack_into('>I', p, 84, v)
            o.seek(16 * 2352); o.write(sector(16, bytes(p)))
    for name, data in files.items():
        assert disc.read(name, dst) == data, name
    moved = sorted(n for n in files if plan[n] != recs[n][3])
    log('트랙 1: %d → %d섹터(+%d) · 바뀐 파일 %d(제자리 %d · 끝으로 옮김 %d)' % (TRACK, newsec, grow, len(files), len(files) - len(moved), len(moved)))
    return grow
