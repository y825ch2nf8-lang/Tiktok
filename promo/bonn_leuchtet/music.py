import numpy as np, wave, sys
sr=44100; D=23.0; N=int(sr*D); out=np.zeros((N,2))
rng=np.random.default_rng(3)
bpm=76; beat=60/bpm; bar=4*beat
f=lambda m:440*2**((m-69)/12)
def add(sig,t0,pan=0.0,g=1.0):
    i=int(t0*sr); n=min(len(sig),N-i)
    if n<=0: return
    out[i:i+n,0]+=sig[:n]*g*(1-pan)/1; out[i:i+n,1]+=sig[:n]*g*(1+pan)/1
def ep(m,dur,vel=1.0):  # soft electric piano
    t=np.arange(int(sr*(dur+1.2)))/sr; fr=f(m)*(1+0.0015*np.sin(2*np.pi*4.5*t))
    s=np.sin(2*np.pi*fr*t)+.35*np.sin(2*np.pi*2*fr*t)*np.exp(-t*3)+.12*np.sin(2*np.pi*3*fr*t)*np.exp(-t*6)
    env=np.minimum(t/0.012,1)*np.exp(-t*1.1); env[t>dur]*=np.exp(-(t[t>dur]-dur)*5)
    return s*env*vel
def kick():
    t=np.arange(int(sr*.35))/sr; return np.sin(2*np.pi*(45+70*np.exp(-t*30))*t)*np.exp(-t*9)
def hat():
    t=np.arange(int(sr*.06))/sr; n=rng.standard_normal(len(t)); n=np.diff(n,prepend=0); return n*np.exp(-t*70)*.25
def snare():
    t=np.arange(int(sr*.25))/sr; n=rng.standard_normal(len(t)); n=np.convolve(n,np.ones(6)/6,'same')
    return (n*np.exp(-t*16)*.5+np.sin(2*np.pi*190*t)*np.exp(-t*25)*.3)
# Fmaj9 - Em7 - Dm9 - Cmaj7
prog=[[53,57,60,64,67],[52,55,59,62],[50,57,60,64],[48,55,59,64]]
bass=[41,40,38,36]
melody=[(0,76),(1.5,74),(2,72),(3,69), (4.5,71),(5,72),(6,74), (8,72),(9.5,69),(10,67), (12.5,71),(13,72),(14,67)]
nb=int(D/bar)+1
for b in range(nb):
    t0=b*bar; ch=prog[b%4]
    for k,m in enumerate(ch): add(ep(m,bar*.9,.13),t0+k*0.025,pan=(k-2)*.15)
    for k,m in enumerate(ch[1:]): add(ep(m+12,beat*.4,.05),t0+2.5*beat+k*.02,pan=.3)
    bt=np.arange(int(sr*bar))/sr; add(np.sin(2*np.pi*f(bass[b%4])*bt)*np.exp(-bt*.6)*np.minimum(bt/.02,1)*.28,t0)
    if b>=1:
        for q in range(4):
            if q in(0,2): add(kick(),t0+q*beat,g=.55)
            if q in(1,3): add(snare(),t0+q*beat+.02,g=.35)
        for e in range(8):
            sw=.06 if e%2 else 0
            add(hat(),t0+e*beat/2+sw,pan=.25,g=.5 if e%2 else .8)
    if b>=2:
        for (bb,m) in melody:
            if int(bb//4)==(b-2)%4: add(ep(m,beat*.8,.09),t0+(bb%4)*beat,pan=-.2)
# warm lowpass + tape wobble-ish, vinyl crackle
from numpy.fft import rfft,irfft
for c in range(2):
    X=rfft(out[:,c]); fr=np.fft.rfftfreq(N,1/sr); X*=1/np.sqrt(1+(fr/3200)**4); out[:,c]=irfft(X,N)
cr=np.zeros(N); idx=rng.integers(0,N,int(D*25)); cr[idx]=rng.uniform(-.3,.3,len(idx)); cr=np.convolve(cr,[1,.6,.3],'same')
out+=cr[:,None]*.05+rng.standard_normal((N,1))*.003
# simple reverb: feedback delays
rev=np.zeros_like(out)
for d,g in [(0.031,.3),(0.047,.25),(0.071,.2),(0.113,.15),(0.167,.1)]:
    k=int(d*sr); rev[k:]+=out[:-k]*g
out+=rev*.6
t=np.arange(N)/sr; out*=np.minimum(t/1.0,1)[:,None]*np.minimum((D-t)/2.0,1)[:,None]
out/=np.abs(out).max()/0.85
w=wave.open(sys.argv[1],'wb');w.setnchannels(2);w.setsampwidth(2);w.setframerate(sr);w.writeframes((out*32767).astype('<i2').tobytes());w.close()
