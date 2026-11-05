"""Score-driven groove + sound design for promo edits.

usage: python3 promo/engine/music.py <project>/score.json <project>/music.wav

The score locks music to the cut list: same BPM/bars as edit.js, SFX cues at cut times.
loop=true renders two periods and keeps the second, so reverb tails and the end riser
wrap seamlessly into the downbeat at t=0 (perfect Reels/TikTok loop).
"""
import json, sys, wave
import numpy as np

sc = json.load(open(sys.argv[1]))
sr = 44100
BPM = sc['bpm']; B = 60 / BPM; BAR = 4 * B; BARS = sc['bars']
D = BARS * BAR; LOOP = sc.get('loop', False)
PERIODS = 2 if LOOP else 1
TAIL = 0 if LOOP else 2.0
N = int(round(sr * (D * PERIODS + TAIL)))
T = np.arange(N) / sr
rng = np.random.default_rng(sc.get('seed', 11))
mf = lambda m: 440 * 2 ** ((m - 69) / 12)

def bus(): return np.zeros((N, 2))
def add(dst, sig, t0, g=1.0, pan=0.0):
    i = int(round(t0 * sr)); n = min(len(sig), N - i)
    if n <= 0 or i < 0: return
    if sig.ndim == 1:
        dst[i:i+n, 0] += sig[:n] * g * np.sqrt((1 - pan) / 2) * 1.414
        dst[i:i+n, 1] += sig[:n] * g * np.sqrt((1 + pan) / 2) * 1.414
    else:
        dst[i:i+n] += sig[:n] * g

def fft_filter(sig, lo=None, hi=None):
    n = len(sig); X = np.fft.rfft(sig, axis=0); f = np.fft.rfftfreq(n, 1 / sr)
    h = np.ones_like(f)
    if hi: h *= 1 / np.sqrt(1 + (f / hi) ** 4)
    if lo: h *= 1 / np.sqrt(1 + (lo / np.maximum(f, 1e-3)) ** 4)
    return np.fft.irfft(X * (h[:, None] if sig.ndim == 2 else h), n, axis=0)

def lp_var(sig, fc):
    a = 1 - np.exp(-2 * np.pi * np.asarray(fc) / sr); out = np.empty_like(sig)
    for ch in range(sig.shape[1]):
        xx = sig[:, ch]; y1 = y2 = 0.0; o = out[:, ch]
        for k in range(len(xx)):
            ak = a[k]; y1 += ak * (xx[k] - y1); y2 += ak * (y1 - y2); o[k] = y2
    return out

# ---------- instruments ----------
def rhodes(m, dur, vel):
    f = mf(m); n = int(sr * (dur + 1.4)); t = np.arange(n) / sr
    s = np.sin(2*np.pi*f*t + 1.6*np.exp(-t*6)*np.sin(2*np.pi*f*t)) + .16*np.sin(2*np.pi*f*4.02*t)*np.exp(-t*14)
    env = np.minimum(t/.004, 1) * np.exp(-t*.85)
    env = np.where(t > dur, env*np.exp(-(t-dur)*8), env)
    return s * env * vel
def bass(m, dur, vel):
    f = mf(m); n = int(sr*(dur+.3)); t = np.arange(n)/sr
    s = np.sin(2*np.pi*f*t) + .35*np.sin(2*np.pi*2*f*t) + .12*np.sin(2*np.pi*3*f*t)
    env = np.minimum(t/.006, 1) * (.55 + .45*np.exp(-t*4))
    env = np.where(t > dur, env*np.exp(-(t-dur)*25), env)
    return np.tanh(1.6*s*env) * vel
def pluck(m, vel):
    f = mf(m); n = int(sr*1.2); t = np.arange(n)/sr
    tri = 2/np.pi*np.arcsin(np.sin(2*np.pi*f*t))
    return (.6*np.sin(2*np.pi*f*t) + .4*tri) * np.exp(-t*5.5) * np.minimum(t/.003, 1) * vel
def kick():
    n = int(sr*.45); t = np.arange(n)/sr; f = 48 + 95*np.exp(-t*30)
    s = np.sin(2*np.pi*np.cumsum(f)/sr)*np.exp(-t*6.5) + rng.standard_normal(n)*np.exp(-t*400)*.25
    return np.tanh(1.8*s)
def clap():
    n = int(sr*.5); t = np.arange(n)/sr; nz = rng.standard_normal(n)
    env = sum(np.where(t >= d, np.exp(-(t-d)*220), 0) for d in (0, .011, .023)) + np.exp(-t*16)*.55*(t >= .023)
    return fft_filter(nz*env, lo=900, hi=4200) * 1.2
def hat(open_=False):
    n = int(sr*(.35 if open_ else .07)); t = np.arange(n)/sr
    return fft_filter(rng.standard_normal(n), lo=7500) * np.exp(-t*(14 if open_ else 75))
def shaker():
    n = int(sr*.09); t = np.arange(n)/sr
    return fft_filter(rng.standard_normal(n), lo=4500, hi=11000) * np.minimum(t/.012, 1)*np.exp(-t*45)
def noise_sweep(dur, f0, f1, f2=None, shape='swell'):
    n = int(sr*dur); t = np.arange(n)/sr; u = t/dur
    nz = rng.standard_normal((n, 2))
    fc = f0*(f1/f0)**u if f2 is None else np.where(u < .6, f0*(f1/f0)**(u/.6), f1*(f2/f1)**((u-.6)/.4))
    env = u**2.2 if shape == 'swell' else np.sin(np.pi*np.clip(u, 0, 1))**1.6
    return lp_var(nz, fc) * env[:, None]

keys, low, lead, drums, fx = bus(), bus(), bus(), bus(), bus()
kicks = []
CH, RT = sc['chords'], sc['roots']
SW = .028 * (BPM / 90)
drum_mode = sc.get('drums', ['full'] * BARS)
over = {int(k): v for k, v in sc.get('chord_index', {}).items()}
MEL = {int(k): v for k, v in sc.get('melody', {}).items()}

for per in range(PERIODS):
    off = per * D
    for b in range(BARS):
        t0 = off + b * BAR; ci = over.get(b, b % len(CH)); ch = CH[ci]; rt = RT[ci]
        mode = drum_mode[b]
        for (bt, dur, v) in [(0, 1.6, .16), (1.75, .45, .10), (2.5, 1.3, .13)]:
            for k, mm in enumerate(ch): add(keys, rhodes(mm, dur*B, v), t0 + bt*B + k*.012, pan=(k-1.5)*.22)
        if mode != 'none':
            for (bt, dur, d) in [(0, 1.2, 0), (1.75, .4, 12), (2.5, 1.3, 0)]:
                add(low, bass(rt + d, dur*B, .30 if mode != 'break' else .18), t0 + bt*B)
        if mode == 'full':
            for q in (0, 2): add(drums, kick(), t0 + q*B, .62); kicks.append(t0 + q*B)
            if b % 2: add(drums, kick(), t0 + 2.75*B, .30); kicks.append(t0 + 2.75*B)
        if mode in ('full', 'nokick'):
            for q in (1, 3): add(drums, clap(), t0 + q*B + .012, .30)
        if mode != 'none':
            for s16 in range(16):
                tt = t0 + s16*B/4 + (SW if s16 % 2 else 0)
                v = [.55, .18, .35, .2][s16 % 4] * (.55 if mode == 'break' else 1)
                add(drums, hat(), tt, v, pan=.3)
                if s16 % 4 == 2 and mode == 'full': add(drums, shaker(), tt, .22, pan=-.35)
            if mode == 'full' and b % 2 == 0: add(drums, hat(True), t0 + 3.5*B + SW, .12, pan=.3)
        for (bt, mm) in MEL.get(b, []):
            p = pluck(mm, .17)
            add(lead, p, t0 + bt*B, pan=-.2); add(lead, p*.32, t0 + bt*B + .75*B, pan=.45); add(lead, p*.12, t0 + bt*B + 1.5*B, pan=-.5)
    if not LOOP and sc.get('final_chord'):
        for k, mm in enumerate(sc['final_chord']): add(keys, rhodes(mm, 1.6, .15), D + k*.02, pan=(k-2)*.2)

    # ---------- sound design cues (times in seconds within the period) ----------
    for c in sc.get('sfx', []):
        t, typ = c['t'] + off, c['type']
        if typ == 'riser':      # ends exactly on t
            dur = c.get('dur', 1.4); r = noise_sweep(dur, 300, 7000) * .55
            tt = np.arange(len(r))/sr; r[:, 0] += .05*np.sin(2*np.pi*np.cumsum(180+420*(tt/dur)**2)/sr)*(tt/dur)**2
            add(fx, r, t - dur, c.get('g', 1))
        elif typ == 'impact':
            n = int(sr*1.6); tt = np.arange(n)/sr
            boom = np.sin(2*np.pi*np.cumsum(38+30*np.exp(-tt*9))/sr)*np.exp(-tt*2.6) + fft_filter(rng.standard_normal(n), hi=900)*np.exp(-tt*9)*.6
            add(fx, np.tanh(1.4*boom), t, c.get('g', .55))
        elif typ == 'whoosh':   # peaks on t
            dur = c.get('dur', .95); w = noise_sweep(dur, 350, 5200, 700, shape='win')
            w[:, 0] *= np.linspace(1.3, .5, len(w)); w[:, 1] *= np.linspace(.5, 1.3, len(w))
            add(fx, w, t - dur*.55, c.get('g', .5))
        elif typ == 'swish':
            add(fx, noise_sweep(.26, 1500, 9000, 2500, shape='win'), t - .14, c.get('g', .45))
        elif typ == 'reverse':  # swells into t
            add(fx, noise_sweep(c.get('dur', .9), 200, 2500) * .3, t - c.get('dur', .9), c.get('g', 1))
        elif typ == 'tick':
            n = int(sr*.03); tt = np.arange(n)/sr
            add(fx, np.sin(2*np.pi*2400*tt)*np.exp(-tt*180), t, c.get('g', .2))

# sidechain pump
scv = np.ones(N)
for tk in kicks:
    i = int(tk*sr); n = min(int(.45*sr), N-i); tt = np.arange(n)/sr
    scv[i:i+n] = np.minimum(scv[i:i+n], 1 - .42*np.exp(-tt/.11))
keys *= scv[:, None]; low *= scv[:, None]
keys[:, 0] *= 1 + .12*np.sin(2*np.pi*3.8*T); keys[:, 1] *= 1 - .12*np.sin(2*np.pi*3.8*T)
if sc.get('intro_filter_bars') and not LOOP:
    e = sc['intro_filter_bars']*BAR
    keys = lp_var(keys, np.where(T < e, 380*(9000/380)**(T/e), 18000))

def reverb(sig, rt=1.7, pre=.018):
    n = int(sr*rt*1.3); t = np.arange(n)/sr
    ir = fft_filter(rng.standard_normal((n, 2)) * np.exp(-t*6.9/rt)[:, None], hi=5500)
    ir = np.vstack([np.zeros((int(pre*sr), 2)), ir])
    Lf = 1 << int(np.ceil(np.log2(len(sig) + len(ir))))
    out = np.fft.irfft(np.fft.rfft(sig, Lf, axis=0) * np.fft.rfft(ir, Lf, axis=0), Lf, axis=0)[:len(sig)]
    return out / np.abs(out).max() * np.abs(sig).max()

dry = keys + low + lead + drums*.85 + fx*.9
mix = dry + reverb(keys*.30 + lead*.45 + drums*.12 + fx*.25)*.35
mix = fft_filter(mix, lo=32)
if LOOP:
    i0 = int(round(D*sr)); mix = mix[i0:i0 + int(round(D*sr))]
mix = np.tanh(mix / np.abs(mix).max() * 1.6) / np.tanh(1.6)
if not LOOP:
    tt = np.arange(len(mix))/sr; mix *= np.clip((len(mix)/sr - tt)/.9, 0, 1)[:, None]
mix = mix / np.abs(mix).max() * .89
w = wave.open(sys.argv[2], 'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr)
w.writeframes((mix*32767).astype('<i2').tobytes()); w.close()
print(f'wrote {sys.argv[2]}: {len(mix)/sr:.3f}s, {BPM} BPM, {BARS} bars, loop={LOOP}')
