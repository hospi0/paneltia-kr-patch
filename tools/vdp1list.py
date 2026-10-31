# -*- coding: utf-8 -*-
r"""VDP1 명령표 훑기(call/return 따라감) — 소드앤소서리 스테이트(VDP1 VRAM 은 LE u16 → swap)
  python tools/vdp1list.py work/mem/<이름> [최소폭] [png 폴더]  → 스프라이트(cmd0~2) 목록, png 폴더 주면 텍스처를 CRAM 색으로 저장"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import vdp1cmd


def walk(v):
    out = []; i = 0; stack = []; n = 0
    while n < 4000:
        n += 1
        c = struct.unpack_from('>16H', v, i * 32)
        if c[0] & 0x8000: break
        jp = (c[0] >> 12) & 7; cmd = c[0] & 0xF
        if not (jp & 4) and cmd in (0, 1, 2):
            out.append(dict(i=i, cmd=cmd, pmod=c[2], colr=c[3], srca=c[4] * 8, w=((c[5] >> 8) & 0x3F) * 8, h=c[5] & 0xFF,
                            x=struct.unpack('>h', struct.pack('>H', c[6]))[0], y=struct.unpack('>h', struct.pack('>H', c[7]))[0]))
        j = jp & 3
        if j == 0: i += 1
        elif j == 1: i = c[1] // 4
        elif j == 2: stack.append(i + 1); i = c[1] // 4
        else: i = stack.pop() if stack else i + 1
    return out


def texture(v, cram, s):
    from PIL import Image
    w, h = s['w'], s['h']; mode = (s['pmod'] >> 3) & 7
    im = Image.new('RGBA', (max(w, 1), max(h, 1)))
    def c15(u): return ((u & 31) * 8, ((u >> 5) & 31) * 8, ((u >> 10) & 31) * 8, 255 if u else 0)
    for y in range(h):
        for x in range(w):
            if mode in (0, 1):
                b = v[s['srca'] + (y * w + x) // 2]; p = (b >> 4) if x % 2 == 0 else b & 15
                if mode == 0: u = struct.unpack_from('>H', cram, (((s["colr"] & ~15) + p) % 2048) * 2)[0] if p else 0
                else: u = struct.unpack_from('>H', v, s['colr'] * 8 + p * 2)[0] if p else 0
            elif mode in (2, 3, 4):
                p = v[s['srca'] + y * w + x]; u = struct.unpack_from('>H', cram, (((s["colr"] & ~255) + p) % 2048) * 2)[0] if p else 0
            else:
                u = struct.unpack_from('>H', v, s['srca'] + (y * w + x) * 2)[0]; u = u if u & 0x8000 else 0
            im.putpixel((x, y), c15(u))
    return im


if __name__ == '__main__':
    d = sys.argv[1]; mw = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    v = vdp1cmd.load(d); cram = open(os.path.join(d, 'CRAM.bin'), 'rb').read()
    png = sys.argv[3] if len(sys.argv) > 3 else None
    if png: os.makedirs(png, exist_ok=True)
    for s in walk(v):
        if s['w'] < mw: continue
        print('%4d cmd%d pmod %04x colr %04x srca %05x %3dx%-3d at (%d,%d)' % (s['i'], s['cmd'], s['pmod'], s['colr'], s['srca'], s['w'], s['h'], s['x'], s['y']))
        if png: texture(v, cram, s).save(os.path.join(png, '%04d_%05x_%dx%d.png' % (s['i'], s['srca'], s['w'], s['h'])))
