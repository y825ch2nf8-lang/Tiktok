"""Laid-back 90 BPM groove + sound design, locked to the cut list in anim.html.
usage: python3 music.py out.wav"""
import numpy as np, wave, sys

sr = 44100; D = 23.0; N = int(sr * D)
BPM = 90; B = 60 / BPM; BAR = 4 * B
rng = np.random.default_rng(11)
T = np.arange(N) / sr
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

def lp_var(sig, fc):  # one-pole lowpass with time-varying cutoff (2 poles cascaded)
    a = 1 - np.exp(-2 * np.pi * np.asarray(fc) / sr)
    out = np.empty_like(sig)
    for ch in range(sig.shape[1]):
        x = sig[:, ch]; y1 = y2 = 0.0; o = out[:, ch]
        for k in range(len(x)):
            ak = a[k]; y1 += ak * (x[k] - y1); y2 += ak * (y1 - y2); o[k] = y2
    return out

# ---------------- instruments ----------------
def rhodes(m, dur, vel):
    f = mf(m); n = int(sr * (dur + 1.4)); t = np.arange(n) / sr
    s = np.sin(2*np.pi*f*t + 1.6*np.exp(-t*6)*np.sin(2*np.pi*f*t)) \
        + .16*np.sin(2*np.pi*f*4.02*t)*np.exp(-t*14)
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
    s = (.6*np.sin(2*np.pi*f*t) + .4*tri) * np.exp(-t*5.5) * np.minimum(t/.003, 1)
    return s * vel

def kick():
    n = int(sr*.45); t = np.arange(n)/sr
    f = 48 + 95*np.exp(-t*30); ph = 2*np.pi*np.cumsum(f)/sr
    s = np.sin(ph)*np.exp(-t*6.5) + rng.standard_normal(n)*np.exp(-t*400)*.25
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

# ---------------- arrangement ----------------
CH = [[53,57,60,64], [53,59,64,69], [52,55,59,62], [55,60,64,71]]   # Dm9  G13  Cmaj9  Am9
RT = [38, 43, 36, 45]
MEL = {2: [(.5,76),(1,74),(1.5,76),(2.5,79),(3.25,76)],
       3: [(.5,72),(1,74),(1.5,76),(2.5,69)],
       4: [(.5,76),(1,74),(1.5,72),(2.5,69),(3.25,72)],
       5: [(.5,74),(1.5,71),(2.5,69),(3,67)]}
SW = .028  # swing on off-16ths

keys, low, lead, drums, fx = bus(), bus(), bus(), bus(), bus()
kicks = []
END = 7 * BAR          # 18.67 s: end card, drums drop out
FIN = 8 * BAR          # 21.33 s: final chord

for b in range(8):
    t0 = b * BAR; ch = CH[b % 4]; rt = RT[b % 4]
    for (bt, dur, v) in [(0, 1.6, .16), (1.75, .45, .10), (2.5, 1.3, .13)]:
        for k, mm in enumerate(ch):
            add(keys, rhodes(mm, dur*B, v), t0 + bt*B + k*.012, pan=(k-1.5)*.22)
    if b >= 1:
        for (bt, dur, d) in [(0, 1.2, 0), (1.75, .4, 12), (2.5, 1.3, 0)]:
            add(low, bass(rt + d, dur*B, .30), t0 + bt*B)
    if 1 <= b < 7:
        for q in (0, 2): add(drums, kick(), t0 + q*B, .62); kicks.append(t0 + q*B)
        if b % 2: add(drums, kick(), t0 + 2.75*B, .30); kicks.append(t0 + 2.75*B)
        for q in (1, 3): add(drums, clap(), t0 + q*B + .012, .30)
    if b >= 1 or True:
        for s16 in range(16):
            if b == 0 and s16 < 8: continue
            tt = t0 + s16*B/4 + (SW if s16 % 2 else 0)
            v = [.55, .18, .35, .2][s16 % 4] * (.6 if b == 0 or b >= 7 else 1)
            add(drums, hat(), tt, v, pan=.3)
            if s16 % 4 == 2 and b >= 1: add(drums, shaker(), tt, .22, pan=-.35)
        if 1 <= b < 7 and b % 2 == 0: add(drums, hat(True), t0 + 3.5*B + SW, .12, pan=.3)
    if b in MEL:
        for (bt, mm) in MEL[b]:
            p = pluck(mm, .17)
            add(lead, p, t0 + bt*B, pan=-.2)
            add(lead, p*.32, t0 + bt*B + .75*B, pan=.45)     # dotted-8th echo
            add(lead, p*.12, t0 + bt*B + 1.5*B, pan=-.5)

# final chord (Cmaj9 over C) at 21.33 s
for k, mm in enumerate([52, 55, 59, 62, 67]):
    add(keys, rhodes(mm, 1.6, .15), FIN + k*.02, pan=(k-2)*.2)
add(low, bass(36, 1.2, .26), FIN)

# sidechain pump on keys/bass from kicks
sc = np.ones(N)
for tk in kicks:
    i = int(tk*sr); n = min(int(.45*sr), N-i); tt = np.arange(n)/sr
    sc[i:i+n] = np.minimum(sc[i:i+n], 1 - .42*np.exp(-tt/.11))
keys *= sc[:, None]; low *= sc[:, None]
# tremolo / autopan on keys
keys[:, 0] *= 1 + .12*np.sin(2*np.pi*3.8*T); keys[:, 1] *= 1 - .12*np.sin(2*np.pi*3.8*T)

# ---------------- sound design ----------------
def noise_sweep(dur, f0, f1, f2=None, shape='swell'):
    n = int(sr*dur); t = np.arange(n)/sr; u = t/dur
    nz = rng.standard_normal((n, 2))
    if f2 is None: fc = f0*(f1/f0)**u
    else: fc = np.where(u < .6, f0*(f1/f0)**(u/.6), f1*(f2/f1)**((u-.6)/.4))
    s = lp_var(nz, fc)
    env = u**2.2 if shape == 'swell' else np.sin(np.pi*np.clip(u, 0, 1))**1.6
    return s * env[:, None]

# riser into the drop
r = noise_sweep(1.45, 300, 7000) * .55
tt = np.arange(len(r))/sr; r[:, 0] += .05*np.sin(2*np.pi*np.cumsum(180+420*(tt/1.45)**2)/sr)*(tt/1.45)**2
r[:, 1] += r[:, 0]*0
add(fx, r, 4*B - 1.45)
# impact on the drop (2.67 s)
n = int(sr*1.6); tt = np.arange(n)/sr
boom = np.sin(2*np.pi*np.cumsum(38+30*np.exp(-tt*9))/sr)*np.exp(-tt*2.6) + fft_filter(rng.standard_normal(n), hi=900)*np.exp(-tt*9)*.6
add(fx, np.tanh(1.4*boom), 4*B, .55)
# whooshes on the light leaks, swish on the whip
for tc, dur, g in [(8*B, .95, .5), (24*B, .95, .5)]:
    w = noise_sweep(dur, 350, 5200, 700, shape='win')
    w[:, 0] *= np.linspace(1.3, .5, len(w)); w[:, 1] *= np.linspace(.5, 1.3, len(w))
    add(fx, w, tc - dur*.55, g)
sw = noise_sweep(.26, 1500, 9000, 2500, shape='win')
add(fx, sw, 12*B - .14, .55)
# soft reverse swell into the end card
rv = noise_sweep(.9, 200, 2500) * .3
add(fx, rv, END - .9)

# ---------------- reverb (FFT convolution) ----------------
def reverb(sig, rt=1.7, pre=.018):
    n = int(sr*rt*1.3); t = np.arange(n)/sr
    ir = rng.standard_normal((n, 2)) * np.exp(-t*6.9/rt)[:, None]
    ir = fft_filter(ir, hi=5500); ir = np.vstack([np.zeros((int(pre*sr), 2)), ir])
    L = 1 << int(np.ceil(np.log2(len(sig) + len(ir))))
    out = np.fft.irfft(np.fft.rfft(sig, L, axis=0) * np.fft.rfft(ir, L, axis=0), L, axis=0)[:len(sig)]
    return out / np.abs(out).max() * np.abs(sig).max()

# intro filter: keys + hats open up across bar 0
fc = np.where(T < 4*B, 380*(9000/380)**(T/(4*B)), 18000)
keys = lp_var(keys, fc)
dry = keys*1.0 + low*1.0 + lead*1.0 + drums*.85 + fx*.9
wet = reverb(keys*.30 + lead*.45 + drums*.12 + fx*.25)
mix = dry + wet*.35
mix = fft_filter(mix, lo=32)
mix = np.tanh(mix / np.abs(mix).max() * 1.6) / np.tanh(1.6)
mix *= np.clip((D - T)/.9, 0, 1)[:, None] * np.clip(T/.03, 0, 1)[:, None]
mix = mix / np.abs(mix).max() * .89

w = wave.open(sys.argv[1], 'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr)
w.writeframes((mix*32767).astype('<i2').tobytes()); w.close()
print('ok', D, 's')
