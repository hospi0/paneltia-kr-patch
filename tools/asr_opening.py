# -*- coding: utf-8 -*-
r"""오프닝 음성 받아쓰기(2026-10-31, 모노모노 tools/asr_voice.py 꼴) — RESET.MES 가 재생하는 opa*.aif 28조각(스크립트 순서)
  AIF(22,050Hz 모노 16bit BE) → work/voice/wav/NN_이름.wav(듣기용 원래 빠르기) + 16kHz 배열로 위스퍼(★VAD 끔)
  → work/voice/asr.tsv (no·voice·초·start·end·no_speech·JP)
  C:\claude\utils\whisper-venv\Scripts\python.exe tools/asr_opening.py"""
import os, re, struct, sys, wave
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DISC = os.path.join(ROOT, 'work', 'disc0')
HINT = 'ケルン、パネルティア、流れ星の精、ケーモネカ、村長、ルルー。'


def ext80(b):
    e = struct.unpack('>H', b[:2])[0] & 0x7FFF; m = int.from_bytes(b[2:10], 'big'); return m * 2.0 ** (e - 16383 - 63)


def aif(path):
    a = open(path, 'rb').read(); i = a.find(b'COMM')
    ch, fr, bits = struct.unpack('>hIh', a[i + 8:i + 16]); rate = ext80(a[i + 16:i + 26])
    j = a.find(b'SSND'); off = struct.unpack('>I', a[j + 8:j + 12])[0]
    pcm = np.frombuffer(a[j + 16 + off:j + 16 + off + fr * 2], '>i2')
    return pcm, int(rate)


def clips():
    d = open(os.path.join(DISC, 'RESET.MES'), 'rb').read()
    return [m.group(1).decode() for m in re.finditer(rb'\x04\x25\x06(op[a-z0-9_]+\.aif)\x06', d)]


if __name__ == '__main__':
    from faster_whisper import WhisperModel
    wd = os.path.join(ROOT, 'work', 'voice', 'wav'); os.makedirs(wd, exist_ok=True)
    m = WhisperModel('large-v3', device='cuda', compute_type='float16')
    out = open(os.path.join(ROOT, 'work', 'voice', 'asr.tsv'), 'w', encoding='utf-8', newline='\n')
    out.write('no\tvoice\tsec\tstart\tend\tno_speech\tJP\n')
    for k, nm in enumerate(clips(), 1):
        pcm, rate = aif(os.path.join(DISC, nm.upper()))
        w = wave.open(os.path.join(wd, '%02d_%s.wav' % (k, nm[:-4])), 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(pcm.astype('<i2').tobytes()); w.close()
        x = pcm.astype(np.float32) / 32768
        a = np.interp(np.arange(0, len(x) * 16000 // rate) * rate / 16000, np.arange(len(x)), x).astype(np.float32)
        segs, _ = m.transcribe(a, language='ja', vad_filter=False, beam_size=5, initial_prompt=HINT, condition_on_previous_text=False)
        txt = []
        for s in segs:
            out.write('%d\t%s\t%.1f\t%.2f\t%.2f\t%.2f\t%s\n' % (k, nm, len(x) / rate, s.start, s.end, s.no_speech_prob, s.text.strip()))
            txt.append(s.text.strip())
        print('%02d %-10s %4.1f초 %s' % (k, nm, len(x) / rate, ' / '.join(txt)))
    out.close()
