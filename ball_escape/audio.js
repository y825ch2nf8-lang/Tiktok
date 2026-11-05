/*
 * Audio-Synthese (Node) aus dem Event-Log der Simulation -> WAV (48 kHz, Stereo, 16 bit).
 * Alles synthetisch erzeugt = keine Musik-Lizenzen, kein Copyright-Claim.
 *   note  -> Marimba (Grundton + 4. und 10. Partialton, kurzer Anschlag)
 *   break -> Glasbruch (gefiltertes Rauschen + unharmonische Glocke + tiefer Puls)
 *   final -> Boom + Akkord
 * Danach: Freeverb-artiger Hall + weicher Limiter.
 */
'use strict';

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

function addMono(L, R, start, data, gain, pan) {
  const gl = Math.cos(((pan + 1) * Math.PI) / 4) * gain;
  const gr = Math.sin(((pan + 1) * Math.PI) / 4) * gain;
  const s0 = Math.floor(start * SR);
  for (let i = 0; i < data.length; i++) {
    const j = s0 + i;
    if (j < 0 || j >= L.length) continue;
    L[j] += data[i] * gl;
    R[j] += data[i] * gr;
  }
}

function marimba(freq, vel) {
  const dur = Math.min(1.8, 0.6 + 260 / freq);
  const n = Math.floor(dur * SR);
  const out = new Float32Array(n);
  const tau1 = Math.min(0.9, 0.32 * Math.sqrt(440 / freq) + 0.12);
  for (let i = 0; i < n; i++) {
    const t = i / SR;
    const att = Math.min(1, t / 0.0025);
    const fund = Math.exp(-t / tau1) * Math.sin(TAU * freq * t);
    const p4 = 0.28 * Math.exp(-t / 0.07) * Math.sin(TAU * freq * 3.98 * t);
    const p10 = 0.1 * Math.exp(-t / 0.014) * Math.sin(TAU * freq * 9.92 * t);
    const shimmer = 0.12 * Math.exp(-t / (tau1 * 1.6)) * Math.sin(TAU * freq * 2.0 * t);
    out[i] = att * (fund + p4 + p10 + shimmer) * vel;
  }
  return out;
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
    // einfacher Hochpass (Glas-Klirren)
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

/* Freeverb (Jezar) vereinfacht */
function reverb(L, R, wet) {
  const scale = SR / 44100;
  const combs = [1116, 1188, 1277, 1356, 1422, 1491, 1557, 1617].map((x) => Math.round(x * scale));
  const aps = [556, 441, 341, 225].map((x) => Math.round(x * scale));
  const spread = Math.round(23 * scale);
  const fb = 0.84;
  const damp = 0.25;
  function chan(input, off) {
    const out = new Float32Array(input.length);
    const cb = combs.map((c) => ({ buf: new Float32Array(c + off), i: 0, store: 0 }));
    const ab = aps.map((a) => ({ buf: new Float32Array(a + off), i: 0 }));
    for (let n = 0; n < input.length; n++) {
      const x = input[n] * 0.015;
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
      out[n] = s;
    }
    return out;
  }
  const mono = new Float32Array(L.length);
  for (let i = 0; i < L.length; i++) mono[i] = (L[i] + R[i]) * 0.5;
  const wl = chan(mono, 0);
  const wr = chan(mono, spread);
  for (let i = 0; i < L.length; i++) {
    L[i] += wl[i] * wet * 3;
    R[i] += wr[i] * wet * 3;
  }
}

function renderAudio(events, durationSec, opts) {
  opts = opts || {};
  const n = Math.ceil(durationSec * SR);
  const L = new Float32Array(n);
  const R = new Float32Array(n);
  const rng = mulberry32((opts.seed || 1) * 7919);
  const width = opts.width || 1080;
  const chord = opts.chord || [0, 3, 7];
  const tonic = opts.tonic != null ? opts.tonic : 59;
  const noteCache = new Map();

  for (const e of events) {
    const pan = Math.max(-0.7, Math.min(0.7, ((e.x || width / 2) / width) * 2 - 1)) * 0.6;
    if (e.type === 'note') {
      const key = e.midi;
      if (!noteCache.has(key)) noteCache.set(key, marimba(hz(e.midi), 1));
      addMono(L, R, e.vt, noteCache.get(key), 0.42 * e.vel, pan);
    } else if (e.type === 'break') {
      addMono(L, R, e.vt, glass(e.ring, rng, e.final), e.final ? 0.75 : 0.42, pan * 0.5);
      if (e.final) {
        for (const iv of chord) for (const oct of [12, 24]) addMono(L, R, e.vt + 0.02, marimba(hz(tonic + iv + oct), 1), 0.3, (rng() - 0.5) * 0.8);
      }
    }
  }
  // Loop-Akzent am Ende (sanfter Tonika-Ton, wenn die Ringe zurückkommen)
  if (opts.loopChimeAt != null) {
    addMono(L, R, opts.loopChimeAt, marimba(hz(tonic + 12), 1), 0.25, 0);
    addMono(L, R, opts.loopChimeAt + 0.18, marimba(hz(tonic + 19), 1), 0.2, 0.2);
  }

  reverb(L, R, opts.reverb != null ? opts.reverb : 0.22);

  // Pegel: 99,5-%-Perzentil auf ~0.5, Spitzen weich begrenzen
  const sample = [];
  for (let i = 0; i < n; i += 37) sample.push(Math.abs(L[i]), Math.abs(R[i]));
  sample.sort((a, b) => a - b);
  const p = sample[Math.floor(sample.length * 0.995)] || 1;
  const g = 0.5 / Math.max(p, 1e-6);
  const fadeOut = Math.floor(0.05 * SR);
  for (let i = 0; i < n; i++) {
    const f = i > n - fadeOut ? (n - i) / fadeOut : 1;
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
