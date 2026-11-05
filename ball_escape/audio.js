/*
 * Audio-Synthese (Node) aus dem Event-Log der Simulation -> WAV (48 kHz, Stereo, 16 bit).
 * Alles synthetisch erzeugt = keine Musiklizenz, kein Copyright-Claim.
 *
 * Modus "layers" (Standard): Der Song läuft ab dem ersten Ringbruch im Takt. Jeder Ring schaltet ein
 * Instrument frei (arrangement.js), beim letzten Ring spielt alles. Vor dem ersten freigeschalteten
 * Melodie-Instrument spielt jeder Aufprall die nächste Melodie-Note, danach einen leisen Akkordton.
 * Modus "bounce": nur Aufprall-Noten (Marimba) + Glasbruch, wie die klassischen Ball-Videos.
 */
'use strict';

const Arrangement = require('./arrangement');

const SR = 48000;
const TAU = Math.PI * 2;

function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const hz = (midi) => 440 * Math.pow(2, (midi - 69) / 12);
const lpCoef = (fc) => 1 - Math.exp((-TAU * Math.min(fc, SR * 0.45)) / SR);

class Bus {
  constructor(n) {
    this.L = new Float32Array(n);
    this.R = new Float32Array(n);
  }
  add(start, data, gain, pan) {
    // data: Float32Array (mono) oder [L, R]
    const stereo = Array.isArray(data);
    const p = Math.max(-1, Math.min(1, pan || 0));
    const gl = Math.cos(((p + 1) * Math.PI) / 4) * Math.SQRT2 * gain;
    const gr = Math.sin(((p + 1) * Math.PI) / 4) * Math.SQRT2 * gain;
    const s0 = Math.round(start * SR);
    const a = stereo ? data[0] : data;
    const b = stereo ? data[1] : data;
    const n = Math.min(a.length, this.L.length - s0);
    for (let i = Math.max(0, -s0); i < n; i++) {
      this.L[s0 + i] += a[i] * gl;
      this.R[s0 + i] += b[i] * gr;
    }
  }
}

/* ---------------- Instrumente ---------------- */

function env(t, dur, att, rel) {
  if (t < att) return t / att;
  if (t > dur) return Math.max(0, 1 - (t - dur) / rel);
  return 1;
}

function marimba(freq, vel) {
  const dur = Math.min(1.8, 0.6 + 260 / freq);
  const n = Math.floor(dur * SR);
  const out = new Float32Array(n);
  const tau1 = Math.min(0.9, 0.32 * Math.sqrt(440 / freq) + 0.12);
  for (let i = 0; i < n; i++) {
    const t = i / SR;
    const att = Math.min(1, t / 0.0025);
    out[i] = att * vel * (
      Math.exp(-t / tau1) * Math.sin(TAU * freq * t) +
      0.28 * Math.exp(-t / 0.07) * Math.sin(TAU * freq * 3.98 * t) +
      0.1 * Math.exp(-t / 0.014) * Math.sin(TAU * freq * 9.92 * t) +
      0.12 * Math.exp(-t / (tau1 * 1.6)) * Math.sin(TAU * freq * 2.0 * t));
  }
  return out;
}

function kick() {
  const n = Math.floor(0.45 * SR);
  const out = new Float32Array(n);
  let ph = 0;
  const rng = mulberry32(7);
  for (let i = 0; i < n; i++) {
    const t = i / SR;
    const f = 48 + 110 * Math.exp(-t / 0.035);
    ph += (TAU * f) / SR;
    out[i] = Math.sin(ph) * Math.exp(-t / 0.28) + 0.12 * (rng() * 2 - 1) * Math.exp(-t / 0.003);
  }
  return out;
}

function noiseHit(seed, dur, decay, hpA, lpFc) {
  const n = Math.floor(dur * SR);
  const out = new Float32Array(n);
  const rng = mulberry32(seed);
  let hp = 0;
  let prev = 0;
  let lp = 0;
  const a = lpFc ? lpCoef(lpFc) : 1;
  for (let i = 0; i < n; i++) {
    const t = i / SR;
    const x = rng() * 2 - 1;
    hp = hpA * (hp + x - prev);
    prev = x;
    lp += a * (hp - lp);
    out[i] = lp * Math.exp(-t / decay);
  }
  return out;
}

function clap() {
  const n = Math.floor(0.3 * SR);
  const out = new Float32Array(n);
  const rng = mulberry32(11);
  let lp1 = 0;
  let lp2 = 0;
  const a1 = lpCoef(2400);
  const a2 = lpCoef(700);
  for (let i = 0; i < n; i++) {
    const t = i / SR;
    const x = rng() * 2 - 1;
    lp1 += a1 * (x - lp1);
    lp2 += a2 * (x - lp2);
    const bp = lp1 - lp2;
    let e = Math.exp(-t / 0.11);
    for (const o of [0, 0.011, 0.022]) if (t >= o && t < o + 0.01) e = Math.max(e, Math.exp(-(t - o) / 0.004) * 1.3);
    out[i] = bp * e * 2.2;
  }
  return out;
}

function crash() {
  return noiseHit(23, 2.2, 0.7, 0.55, 9000);
}

function saw(ph) {
  return 2 * (ph - Math.floor(ph)) - 1;
}

function bass(freq, dur) {
  const total = dur + 0.03;
  const n = Math.floor(total * SR);
  const out = new Float32Array(n);
  let ph = 0;
  let l1 = 0;
  let l2 = 0;
  for (let i = 0; i < n; i++) {
    const t = i / SR;
    ph += freq / SR;
    const a = lpCoef(260 + 1100 * Math.exp(-t / 0.06));
    const x = saw(ph) * 0.7 + Math.sin(TAU * ph) * 0.6;
    l1 += a * (x - l1);
    l2 += a * (l1 - l2);
    out[i] = l2 * env(t, dur, 0.003, 0.03);
  }
  return out;
}

function sub(freq, dur) {
  const n = Math.floor((dur + 0.06) * SR);
  const out = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const t = i / SR;
    out[i] = Math.sin(TAU * freq * t) * env(t, dur, 0.02, 0.06);
  }
  return out;
}

function supersaw(freq, dur, opts) {
  const { att, rel, cutoff, detunes, cutEnv } = opts;
  const n = Math.floor((dur + rel) * SR);
  const L = new Float32Array(n);
  const R = new Float32Array(n);
  const phL = detunes.map((_, k) => (k * 0.37) % 1);
  const phR = detunes.map((_, k) => (k * 0.61) % 1);
  const fL = detunes.map((c) => freq * Math.pow(2, c / 1200));
  const fR = detunes.map((c) => freq * Math.pow(2, -c / 1200));
  let a1 = 0, a2 = 0, b1 = 0, b2 = 0;
  for (let i = 0; i < n; i++) {
    const t = i / SR;
    const a = lpCoef(cutoff + (cutEnv || 0) * Math.exp(-t / 0.12));
    let xl = 0;
    let xr = 0;
    for (let k = 0; k < detunes.length; k++) {
      phL[k] += fL[k] / SR;
      phR[k] += fR[k] / SR;
      xl += saw(phL[k]);
      xr += saw(phR[k]);
    }
    a1 += a * (xl - a1); a2 += a * (a1 - a2);
    b1 += a * (xr - b1); b2 += a * (b1 - b2);
    const e = env(t, dur, att, rel) / detunes.length;
    L[i] = a2 * e;
    R[i] = b2 * e;
  }
  return [L, R];
}

function lead(freq, dur) {
  const total = dur + 0.08;
  const n = Math.floor(total * SR);
  const L = new Float32Array(n);
  const R = new Float32Array(n);
  let p1 = 0, p2 = 0, p3 = 0;
  let l1 = 0, l2 = 0, r1 = 0, r2 = 0;
  for (let i = 0; i < n; i++) {
    const t = i / SR;
    const vib = 1 + (t > 0.18 ? 0.004 * Math.sin(TAU * 5.5 * t) : 0);
    p1 += (freq * vib * 1.004) / SR;
    p2 += (freq * vib * 0.996) / SR;
    p3 += (freq * vib * 0.5) / SR;
    const sq = (p3 % 1) < 0.5 ? 0.35 : -0.35;
    const a = lpCoef(1500 + 3800 * Math.exp(-t / 0.12));
    const xl = saw(p1) + sq;
    const xr = saw(p2) + sq;
    l1 += a * (xl - l1); l2 += a * (l1 - l2);
    r1 += a * (xr - r1); r2 += a * (r1 - r2);
    const e = env(t, Math.max(0.03, dur - 0.02), 0.006, 0.08);
    L[i] = l2 * e * 0.5;
    R[i] = r2 * e * 0.5;
  }
  return [L, R];
}

function pluck(freq, dur, seed) {
  // Karplus-Strong
  const total = Math.min(1.6, dur + 0.5);
  const n = Math.floor(total * SR);
  const out = new Float32Array(n);
  const N = Math.max(2, Math.round(SR / freq));
  const buf = new Float32Array(N);
  const rng = mulberry32(seed);
  let lp = 0;
  for (let i = 0; i < N; i++) {
    lp += 0.5 * (rng() * 2 - 1 - lp);
    buf[i] = lp;
  }
  const damp = 0.996;
  for (let i = 0; i < n; i++) {
    const j = i % N;
    const y = buf[j];
    buf[j] = 0.5 * (y + buf[(j + 1) % N]) * damp;
    const t = i / SR;
    out[i] = y * (t > dur + 0.35 ? Math.max(0, 1 - (t - dur - 0.35) / 0.15) : 1) * 1.6;
  }
  return out;
}

function bell(freq, dur) {
  const total = Math.min(2.0, dur + 0.9);
  const n = Math.floor(total * SR);
  const out = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const t = i / SR;
    const idx = 2.2 * Math.exp(-t / 0.25);
    out[i] = Math.sin(TAU * freq * t + idx * Math.sin(TAU * freq * 3.5 * t)) * Math.exp(-t / 0.6) * Math.min(1, t / 0.002);
  }
  return out;
}

function arpNote(freq, dur) {
  const total = dur + 0.12;
  const n = Math.floor(total * SR);
  const out = new Float32Array(n);
  let ph = 0;
  let l1 = 0;
  let l2 = 0;
  for (let i = 0; i < n; i++) {
    const t = i / SR;
    ph += freq / SR;
    const x = (ph % 1) < 0.3 ? 1 : -1;
    const a = lpCoef(900 + 3500 * Math.exp(-t / 0.05));
    l1 += a * (x - l1);
    l2 += a * (l1 - l2);
    out[i] = l2 * Math.exp(-t / 0.11) * Math.min(1, t / 0.002);
  }
  return out;
}

function stab(freq) {
  return supersaw(freq, 0.09, { att: 0.002, rel: 0.09, cutoff: 1300, cutEnv: 2500, detunes: [-12, 0, 12] });
}

function glass(ringIdx, rng, big) {
  const dur = big ? 2.6 : 1.0;
  const n = Math.floor(dur * SR);
  const out = new Float32Array(n);
  const base = 1300 + ringIdx * 85;
  const ratios = [1, 2.32, 4.25, 6.63, 8.9];
  const phases = ratios.map(() => rng() * TAU);
  let hpPrev = 0;
  let hpOut = 0;
  let lp = 0;
  for (let i = 0; i < n; i++) {
    const t = i / SR;
    const noise = rng() * 2 - 1;
    hpOut = 0.97 * (hpOut + noise - hpPrev);
    hpPrev = noise;
    lp += 0.08 * (noise - lp);
    let s = hpOut * Math.exp(-t / (big ? 0.35 : 0.11)) * 0.55;
    for (let k = 0; k < ratios.length; k++) {
      s += (0.22 / (k + 1)) * Math.exp(-t / (0.5 / (k * 0.6 + 1))) * Math.sin(TAU * base * ratios[k] * t + phases[k]);
    }
    s += 0.5 * Math.exp(-t / 0.09) * Math.sin(TAU * 95 * t);
    if (big) {
      const f = 30 + 80 * Math.exp(-t / 0.25);
      s += 1.1 * Math.exp(-t / 0.9) * Math.sin(TAU * f * t);
      s += 0.6 * lp * Math.exp(-t / 0.7);
    }
    out[i] = s * Math.min(1, t / 0.001);
  }
  return out;
}

/* Freeverb (Jezar) vereinfacht – gibt das Hallsignal zurück */
function reverb(inL, inR, len) {
  const scale = SR / 44100;
  const combs = [1116, 1188, 1277, 1356, 1422, 1491, 1557, 1617].map((x) => Math.round(x * scale));
  const aps = [556, 441, 341, 225].map((x) => Math.round(x * scale));
  const spread = Math.round(23 * scale);
  const fb = 0.84;
  const damp = 0.25;
  const n = len || inL.length;
  function chan(off) {
    const out = new Float32Array(n);
    const cb = combs.map((c) => ({ buf: new Float32Array(c + off), i: 0, store: 0 }));
    const ab = aps.map((a) => ({ buf: new Float32Array(a + off), i: 0 }));
    for (let k = 0; k < n; k++) {
      const x = (inL[k] + inR[k]) * 0.5 * 0.015;
      let s = 0;
      for (const c of cb) {
        const y = c.buf[c.i];
        c.store = y * (1 - damp) + c.store * damp;
        c.buf[c.i] = x + c.store * fb;
        if (++c.i >= c.buf.length) c.i = 0;
        s += y;
      }
      for (const a of ab) {
        const y = a.buf[a.i];
        a.buf[a.i] = s + y * 0.5;
        if (++a.i >= a.buf.length) a.i = 0;
        s = y - s;
      }
      out[k] = s * 3;
    }
    return out;
  }
  return [chan(0), chan(spread)];
}

/* ---------------- Mix ---------------- */

// Pegel, Panorama und Hall-Anteil je Instrument
const MIX = {
  kick: { gain: 0.78, pan: 0, send: 0, duck: false },
  clap: { gain: 0.45, pan: 0, send: 0.25, duck: false },
  hats: { gain: 0.16, pan: 0.25, send: 0, duck: false },
  openhat: { gain: 0.14, pan: -0.25, send: 0.1, duck: false },
  shaker: { gain: 0.07, pan: 0.45, send: 0, duck: false },
  bass: { gain: 0.42, pan: 0, send: 0, duck: true },
  sub: { gain: 0.38, pan: 0, send: 0, duck: true },
  pad: { gain: 0.2, pan: 0, send: 0.6, duck: true },
  arp: { gain: 0.14, pan: -0.35, send: 0.4, duck: true },
  stab: { gain: 0.12, pan: 0.3, send: 0.35, duck: true },
  pluck: { gain: 0.42, pan: 0.15, send: 0.35, duck: false },
  lead: { gain: 0.24, pan: 0, send: 0.3, duck: false },
  bell: { gain: 0.16, pan: 0.35, send: 0.5, duck: false },
  harmony: { gain: 0.13, pan: -0.3, send: 0.35, duck: false },
};

function renderInst(e, cache) {
  const f = e.midi != null ? hz(e.midi) : 0;
  const key = e.inst + ':' + (e.midi == null ? '' : e.midi) + ':' + e.dur.toFixed(3);
  if (cache.has(key)) return cache.get(key);
  let buf;
  switch (e.inst) {
    case 'kick': buf = kick(); break;
    case 'clap': buf = clap(); break;
    case 'hats': buf = noiseHit(3, 0.08, 0.03, 0.5, 12000); break;
    case 'openhat': buf = noiseHit(5, 0.35, 0.16, 0.5, 11000); break;
    case 'shaker': buf = noiseHit(9, 0.06, 0.018, 0.45, 9000); break;
    case 'bass': buf = bass(f, e.dur); break;
    case 'sub': buf = sub(f, e.dur); break;
    case 'pad': buf = supersaw(f, e.dur, { att: 0.25, rel: 0.45, cutoff: 1300, detunes: [-11, -4, 4, 11] }); break;
    case 'arp': buf = arpNote(f, e.dur); break;
    case 'stab': buf = stab(f); break;
    case 'pluck': buf = pluck(f, e.dur, e.midi * 31); break;
    case 'lead': case 'harmony': buf = lead(f, e.dur); break;
    case 'bell': buf = bell(f, e.dur); break;
    default: return null;
  }
  cache.set(key, buf);
  return buf;
}

function sliceFrom(buf, skipSec) {
  const s = Math.round(skipSec * SR);
  if (Array.isArray(buf)) return [buf[0].subarray(s), buf[1].subarray(s)];
  return buf.subarray(s);
}

function renderAudio(events, durationSec, opts) {
  opts = opts || {};
  const n = Math.ceil(durationSec * SR);
  const dry = new Bus(n);
  const send = new Bus(n);
  const duck = new Bus(n);
  const duckSend = new Bus(n);
  const rng = mulberry32((opts.seed || 1) * 7919);
  const width = opts.width || 1080;
  const song = opts.song || null;
  const layered = !!song && opts.music !== 'bounce';
  const breaks = events.filter((e) => e.type === 'break');
  const songStart = layered && breaks.length ? breaks[0].vt : null;
  const unlock = layered ? Arrangement.unlockTimes(breaks.map((b) => b.vt), opts.rings || breaks.length) : null;
  const melodyUnlock = unlock ? Math.min(unlock[1], unlock[7]) : Infinity;
  const cache = new Map();
  const kickTimes = [];

  // 1) Song-Layer
  if (songStart != null) {
    const plan = Arrangement.schedule(song, songStart, durationSec);
    const SUSTAIN = { pad: 1, sub: 1, lead: 1, harmony: 1, bell: 1, pluck: 1 };
    for (const e of plan) {
      const u = unlock[e.layer];
      if (e.t + e.dur <= u) continue;
      let skip = 0;
      if (e.t < u - 1e-4) {
        if (!SUSTAIN[e.inst]) continue;
        skip = u - e.t; // gehaltene Töne setzen genau beim Ringbruch ein
      }
      const buf = renderInst(e, cache);
      if (!buf) continue;
      const m = MIX[e.inst];
      const data = skip ? sliceFrom(buf, skip) : buf;
      const t = e.t + skip;
      const g = m.gain * e.vel;
      (m.duck ? duck : dry).add(t, data, g, m.pan);
      if (m.send) (m.duck ? duckSend : send).add(t, data, g * m.send, m.pan);
      if (e.inst === 'kick') kickTimes.push(t);
    }
  }

  // 2) Aufprall-Noten + Glasbruch
  for (const e of events) {
    const pan = Math.max(-0.7, Math.min(0.7, ((e.x || width / 2) / width) * 2 - 1)) * 0.6;
    if (e.type === 'note') {
      if (layered && e.vt >= melodyUnlock) {
        // Melodie läuft schon im Song -> Aufprall = leiser Akkordton (immer harmonisch)
        const c = Arrangement.chordAt(song, songStart, e.vt);
        const tones = Arrangement.chordTones(c, 84);
        const m = tones[Math.floor(rng() * tones.length)];
        const key = 'tick' + m;
        if (!cache.has(key)) cache.set(key, bell(hz(m), 0.05));
        dry.add(e.vt, cache.get(key), 0.07 * e.vel, pan);
        send.add(e.vt, cache.get(key), 0.05 * e.vel, pan);
      } else {
        const key = 'mar' + e.midi;
        if (!cache.has(key)) cache.set(key, marimba(hz(e.midi), 1));
        dry.add(e.vt, cache.get(key), 0.42 * e.vel, pan);
        send.add(e.vt, cache.get(key), 0.25 * e.vel, pan);
      }
    } else if (e.type === 'break') {
      const g = glass(e.ring, rng, e.final);
      const gain = layered ? (e.final ? 0.6 : 0.3) : e.final ? 0.75 : 0.42;
      dry.add(e.vt, g, gain, pan * 0.5);
      send.add(e.vt, g, gain * 0.5, pan * 0.5);
      if (e.final) {
        if (layered) {
          const c = crash();
          dry.add(e.vt, c, 0.35, 0.2);
          send.add(e.vt, c, 0.2, 0.2);
        } else {
          const chord = opts.chord || [0, 3, 7];
          const tonic = opts.tonic != null ? opts.tonic : 59;
          for (const iv of chord) for (const oct of [12, 24]) send.add(e.vt + 0.02, marimba(hz(tonic + iv + oct), 1), 0.3, (rng() - 0.5) * 0.8);
        }
      }
    }
  }
  if (!layered && opts.loopChimeAt != null) {
    const tonic = opts.tonic != null ? opts.tonic : 59;
    dry.add(opts.loopChimeAt, marimba(hz(tonic + 12), 1), 0.25, 0);
    dry.add(opts.loopChimeAt + 0.18, marimba(hz(tonic + 19), 1), 0.2, 0.2);
  }

  // 3) Sidechain: Bass/Flächen pumpen mit der Kick
  if (kickTimes.length) {
    let ki = 0;
    for (let i = 0; i < n; i++) {
      const t = i / SR;
      while (ki + 1 < kickTimes.length && kickTimes[ki + 1] <= t) ki++;
      const dt = t - kickTimes[ki];
      const g = dt >= 0 ? 1 - 0.6 * Math.exp(-dt / 0.1) : 1;
      duck.L[i] *= g; duck.R[i] *= g; duckSend.L[i] *= g; duckSend.R[i] *= g;
    }
  }

  // 4) Hall + Summe
  const L = dry.L;
  const R = dry.R;
  for (let i = 0; i < n; i++) {
    L[i] += duck.L[i];
    R[i] += duck.R[i];
    send.L[i] += duckSend.L[i];
    send.R[i] += duckSend.R[i];
  }
  const [wl, wr] = reverb(send.L, send.R, n);
  const wet = opts.reverb != null ? opts.reverb / 0.22 : 1;
  for (let i = 0; i < n; i++) {
    L[i] += wl[i] * wet * 0.66;
    R[i] += wr[i] * wet * 0.66;
  }

  // 5) Pegel: 99,5-%-Perzentil auf ~0.5, Spitzen weich begrenzen, Ausblenden für den Loop
  const sample = [];
  for (let i = 0; i < n; i += 37) sample.push(Math.abs(L[i]), Math.abs(R[i]));
  sample.sort((a, b) => a - b);
  const p = sample[Math.floor(sample.length * 0.995)] || 1;
  const g = 0.5 / Math.max(p, 1e-6);
  const fadeLen = Math.floor((layered ? opts.fadeOut || 2.0 : 0.05) * SR);
  for (let i = 0; i < n; i++) {
    const f = i > n - fadeLen ? Math.pow((n - i) / fadeLen, 1.5) : 1;
    L[i] = Math.tanh(L[i] * g * 1.3) * 0.92 * f;
    R[i] = Math.tanh(R[i] * g * 1.3) * 0.92 * f;
  }
  return { L, R, sampleRate: SR };
}

function toWav({ L, R, sampleRate }) {
  const n = L.length;
  const buf = Buffer.alloc(44 + n * 4);
  buf.write('RIFF', 0);
  buf.writeUInt32LE(36 + n * 4, 4);
  buf.write('WAVE', 8);
  buf.write('fmt ', 12);
  buf.writeUInt32LE(16, 16);
  buf.writeUInt16LE(1, 20);
  buf.writeUInt16LE(2, 22);
  buf.writeUInt32LE(sampleRate, 24);
  buf.writeUInt32LE(sampleRate * 4, 28);
  buf.writeUInt16LE(4, 32);
  buf.writeUInt16LE(16, 34);
  buf.write('data', 36);
  buf.writeUInt32LE(n * 4, 40);
  for (let i = 0; i < n; i++) {
    buf.writeInt16LE(Math.max(-32768, Math.min(32767, Math.round(L[i] * 32767))), 44 + i * 4);
    buf.writeInt16LE(Math.max(-32768, Math.min(32767, Math.round(R[i] * 32767))), 46 + i * 4);
  }
  return buf;
}

module.exports = { renderAudio, toWav, SR };
