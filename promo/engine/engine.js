// promo engine — editorial, beat-locked promo videos rendered from a <canvas>.
// A project page defines window.EDIT (see promo/kehl_event/edit.js) and includes this file.
// Rendering is deterministic: render(t) draws the frame at time t; prepare(t) seeks video clips.
'use strict';

// ---------- format (9:16 reel/story/tiktok, 4:5 feed via ?feed) ----------
const FEED = new URLSearchParams(location.search).has('feed');
const W = 1080, H = FEED ? 1350 : 1920;
const S = FEED ? .82 : 1;                         // type scale
const L = FEED ? 72 : 84;                         // left margin
const T0 = FEED ? 70 : 270, B0 = FEED ? H - 80 : 1450; // text-safe band (clear of platform UI)
const INK = '#0f0d0b', CREAM = '#f3ede4';
let ACC = '#f2a65a';
const GRADE = 'contrast(1.08) saturate(0.88) brightness(0.93) sepia(0.10)';

// K = backing-store scale: layout stays in 1080-wide units, pixels are K times denser (K=2 -> 4K)
const K = +(new URLSearchParams(location.search).get('k') || 1);
const main = document.getElementById('c'); main.width = W * K; main.height = H * K; main.style.width = W + 'px'; main.style.height = H + 'px';
const m = main.getContext('2d'); m.setTransform(K, 0, 0, K, 0, 0);
const buf = document.createElement('canvas'); buf.width = W * K; buf.height = H * K;
const x = buf.getContext('2d'); x.setTransform(K, 0, 0, K, 0, 0);
x.imageSmoothingQuality = 'high'; m.imageSmoothingQuality = 'high';
const kf = f => f.replace(/blur\(([\d.]+)px\)/g, (_, v) => `blur(${v * K}px)`);   // canvas filter lengths are device pixels
const I = {};                                     // loaded images / video elements

// ---------- math ----------
const cl = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
const outExpo = t => t >= 1 ? 1 : 1 - Math.pow(2, -10 * t);
const outCubic = t => 1 - Math.pow(1 - cl(t), 3);
const inCubic = t => Math.pow(cl(t), 3);
const prog = (l, t0, d) => cl((l - t0) / d);
// subtle handheld drift
const hh = (t, k = 1) => ({ dx: k * (Math.sin(t * .9 + 1) * 5 + Math.sin(t * 2.3) * 2.2), dy: k * (Math.cos(t * .7) * 6 + Math.sin(t * 1.7 + 2) * 2.4), rot: k * Math.sin(t * .5) * .0022 });

// ---------- drawing ----------
// cover-fit an image/video into a rect; fx/fy = focus point (0..1), zoom >= 1, margins hide drift edges
function photo(im, X, Y, w, h, o = {}) {
  const iw = im.videoWidth || im.width, ih = im.videoHeight || im.height;
  const z = o.zoom || 1, fx = o.fx ?? .5, fy = o.fy ?? .5, M = 24;
  let s = Math.max(w / iw, h / ih) * z;
  s = Math.max(s, (w + 2 * M) / iw, (h + 2 * M) / ih);
  const dw = iw * s, dh = ih * s;
  let ix = X + w / 2 - fx * dw, iy = Y + h / 2 - fy * dh;
  ix = Math.min(X - M, Math.max(X + w - dw + M, ix)); iy = Math.min(Y - M, Math.max(Y + h - dh + M, iy));
  x.save(); x.beginPath(); x.rect(X, Y, w, h); x.clip();
  x.translate(X + w / 2 + (o.dx || 0), Y + h / 2 + (o.dy || 0)); x.rotate(o.rot || 0); x.translate(-(X + w / 2), -(Y + h / 2));
  x.filter = kf(o.grade || GRADE); x.drawImage(im, ix, iy, dw, dh); x.restore();
}
function fill(c, X = 0, Y = 0, w = W, h = H) { x.fillStyle = c; x.fillRect(X, Y, w, h); }
function shade(y0, a) {
  const g = x.createLinearGradient(0, y0, 0, H);
  g.addColorStop(0, 'rgba(10,8,6,0)'); g.addColorStop(.45, `rgba(10,8,6,${a * .82})`); g.addColorStop(1, `rgba(10,8,6,${a})`);
  x.fillStyle = g; x.fillRect(0, y0, W, H - y0);
}
function topShade() { const g = x.createLinearGradient(0, 0, 0, H * .22); g.addColorStop(0, 'rgba(10,8,6,.45)'); g.addColorStop(1, 'rgba(10,8,6,0)'); x.fillStyle = g; x.fillRect(0, 0, W, H * .22); }

// type system: serif italic for emotion, tight grotesk for facts, tracked caps for labels
const F = {
  serif: (s, c = CREAM) => ({ font: `italic 400 ${s}px "Instrument Serif"`, size: s, color: c, track: -s * .01 }),
  sans: (s, c = CREAM, w = 800) => ({ font: `${w} ${s}px "Inter Tight"`, size: s, color: c, track: -s * .035 }),
  body: (s, c = CREAM) => ({ font: `500 ${s}px "Inter Tight"`, size: s, color: c, track: -s * .01 }),
  label: (s, c = CREAM) => ({ font: `600 ${s}px "Inter Tight"`, size: s, color: c, track: s * .22 }),
};
function setFont(f) { x.font = f.font; x.letterSpacing = (f.track || 0) + 'px'; }
function measure(str, f) { setFont(f); return x.measureText(str).width; }
// masked line reveal: the line rises out of an invisible slot. t0 = local start, l = local time.
function line(str, X, Y, f, t0, l, o = {}) {
  if (l < t0) return;
  const p = o.instant ? 1 : outExpo(cl((l - t0) / (o.d || .8)));
  setFont(f); x.textBaseline = 'alphabetic'; x.textAlign = 'left';
  const w = x.measureText(str).width;
  const lx = o.align === 'center' ? X - w / 2 : o.align === 'right' ? X - w : X;
  x.save(); x.beginPath(); x.rect(lx - 40, Y - f.size * 1.02, w + 80, f.size * 1.34); x.clip();
  x.globalAlpha *= (o.alpha ?? 1) * Math.min(1, p * 1.8); x.fillStyle = f.color;
  x.fillText(str, lx, Y + (1 - p) * f.size * 1.15); x.restore();
}
// hard "pop" for kinetic words cut on the beat (no fade, tiny scale settle)
function pop(str, X, Y, f, l, o = {}) {
  const sc = 1 + .05 * (1 - outExpo(cl(l / .3)));
  x.save(); x.translate(X, Y); x.scale(sc, sc); setFont(f); x.textAlign = o.align || 'center'; x.textBaseline = o.baseline || 'middle';
  x.fillStyle = f.color; x.fillText(str, 0, 0); x.restore();
}
function rule(x0, y, x1, t0, l, col = 'rgba(243,237,228,.28)', lw = 1.5) {
  if (l < t0) return; const p = outExpo(cl((l - t0) / .9));
  x.strokeStyle = col; x.lineWidth = lw; x.beginPath(); x.moveTo(x0, y); x.lineTo(x0 + (x1 - x0) * p, y); x.stroke();
}
// rectangular plate revealed by a top-down "shutter" wipe with a thin light edge
function shutter(X, Y, w, h, t0, l, drawFn, d = .8) {
  const p = outExpo(prog(l, t0, d)); if (p <= 0) return;
  x.save(); x.beginPath(); x.rect(X, Y, w, h * p); x.clip(); drawFn(); x.restore();
  if (p < .995) { x.fillStyle = `rgba(255,236,210,${.8 * (1 - p)})`; x.fillRect(X, Y + h * p - 2, w, 3); }
}
function circleImg(im, cx, cy, r, grade) {
  x.save(); x.beginPath(); x.arc(cx, cy, r, 0, Math.PI * 2); x.clip();
  x.filter = kf(grade || GRADE); const iw = im.width, ih = im.height, s = 2 * r / Math.min(iw, ih);
  x.drawImage(im, cx - iw * s / 2, cy - ih * s / 2, iw * s, ih * s); x.restore();
}
// text set on a circle (rotating badge ring)
function ringText(str, cx, cy, r, rot, f) {
  setFont(f); x.fillStyle = f.color; x.textAlign = 'center'; x.textBaseline = 'middle';
  const chars = [...str], step = (Math.PI * 2) / chars.length;
  chars.forEach((ch, i) => { const a = rot + i * step; x.save(); x.translate(cx + Math.cos(a) * r, cy + Math.sin(a) * r); x.rotate(a + Math.PI / 2); x.fillText(ch, 0, 0); x.restore(); });
}

// ---------- finishing passes (operate on main canvas m) ----------
const grains = [...Array(6)].map(() => {
  const c = document.createElement('canvas'); c.width = W * K / 2; c.height = H * K / 2; const g = c.getContext('2d');
  const d = g.createImageData(c.width, c.height);
  for (let i = 0; i < d.data.length; i += 4) { const v = 128 + (Math.random() + Math.random() - 1) * 70; d.data[i] = d.data[i + 1] = d.data[i + 2] = v; d.data[i + 3] = 255; }
  g.putImageData(d, 0, 0); return c;
});
function whip(t, tc, w, dir = 1) { // directional motion-blur push across a cut
  const before = t < tc, p = before ? (t - (tc - w)) / w : 1 - (t - tc) / w, e = p * p * p;
  const off = (before ? -1 : 1) * dir * e * W * .55, spread = e * 300, n = 12;
  m.fillStyle = INK; m.fillRect(0, 0, W, H);
  for (let i = 0; i < n; i++) { m.globalAlpha = 1 / (i + 1); m.drawImage(buf, off + spread * (i / (n - 1) - .5), 0, W, H); }
  m.globalAlpha = 1;
}
function leak(dt) { // warm light leak; dt = time relative to the cut it sits on
  const p = (dt + .35) / .95; if (p <= 0 || p >= 1) return; const k = Math.pow(Math.sin(Math.PI * p), 1.4);
  m.save(); m.globalCompositeOperation = 'screen';
  const g1 = m.createRadialGradient(W * (1.15 - p * .9), H * .3, 0, W * (1.15 - p * .9), H * .3, H * .75);
  g1.addColorStop(0, `rgba(255,120,45,${.9 * k})`); g1.addColorStop(1, 'rgba(255,120,45,0)'); m.fillStyle = g1; m.fillRect(0, 0, W, H);
  const g2 = m.createRadialGradient(W * (-.15 + p * .7), H * .78, 0, W * (-.15 + p * .7), H * .78, H * .5);
  g2.addColorStop(0, `rgba(255,200,110,${.65 * k})`); g2.addColorStop(1, 'rgba(255,200,110,0)'); m.fillStyle = g2; m.fillRect(0, 0, W, H);
  m.fillStyle = `rgba(255,150,70,${.18 * k})`; m.fillRect(0, 0, W, H); m.restore();
}
function flash(dt, a = .45) { if (dt >= 0 && dt < .35) { m.fillStyle = `rgba(255,248,235,${a * Math.exp(-dt * 12)})`; m.fillRect(0, 0, W, H); } }

// ---------- timeline ----------
const E = window.EDIT;
const DUR = E.dur;
const wrap = t => E.loop ? ((t % DUR) + DUR) % DUR : t;
const rel = (t, tc) => { let d = t - tc; if (E.loop) { d = ((d + DUR / 2) % DUR + DUR) % DUR - DUR / 2; } return d; };
function shotAt(t) { return E.shots.find(s => t >= s.a && t < s.b) || E.shots[E.shots.length - 1]; }
function drawShot(t) {
  t = wrap(t); x.save(); x.filter = 'none'; x.globalAlpha = 1; fill(INK);
  const s = shotAt(t); s.f(t - s.a, t); x.restore();
}
function render(t) {
  let whipped = false;
  for (const fx of E.fx || []) if (fx.type === 'whip') {
    const d = rel(t, fx.t), w = fx.w || .12;
    if (Math.abs(d) < w) { drawShot(t); whip(fx.t + d, fx.t, w, fx.dir || 1); whipped = true; break; }
  }
  if (!whipped) { drawShot(t); m.globalAlpha = 1; m.drawImage(buf, 0, 0, W, H); }
  for (const fx of E.fx || []) {
    if (fx.type === 'flash') flash(rel(t, fx.t), fx.a);
    if (fx.type === 'leak') leak(rel(t, fx.t));
  }
  const v = m.createRadialGradient(W / 2, H / 2, H * .32, W / 2, H / 2, H * .78);
  v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, `rgba(0,0,0,${E.vignette ?? .42})`); m.fillStyle = v; m.fillRect(0, 0, W, H);
  m.save(); m.globalCompositeOperation = 'overlay'; m.globalAlpha = E.grain ?? .42; m.drawImage(grains[Math.round(t * 30) % 6], 0, 0, W, H); m.restore();
  if (!E.loop) { const fd = Math.max(1 - t / .15, 1 - (DUR - t) / .7, 0); if (fd > 0) { m.fillStyle = `rgba(0,0,0,${cl(fd)})`; m.fillRect(0, 0, W, H); } }
}
// seek every clip used by the active shot: media: [{name, from (s), speed}]
async function prepare(t) {
  t = wrap(t); const s = shotAt(t);
  await Promise.all((s.media || []).map(md => new Promise(res => {
    const v = I[md.name]; const target = (md.from || 0) + (t - s.a) * (md.speed || 1);
    if (Math.abs(v.currentTime - target) < 1e-3 && v.readyState >= 2) return res();
    v.addEventListener('seeked', () => res(), { once: true }); v.currentTime = Math.min(target, v.duration - .05);
  })));
}

window.DUR = DUR; window.render = render; window.prepare = prepare;
window.ready = (async () => {
  if (E.accent) ACC = E.accent;
  await Promise.all(Object.entries(E.assets).map(([n, src]) => new Promise((res, rej) => {
    if (/\.(mp4|webm|mov)$/i.test(src)) {
      const v = document.createElement('video'); v.muted = true; v.preload = 'auto'; v.src = src; I[n] = v;
      v.addEventListener('loadeddata', res, { once: true }); v.addEventListener('error', () => rej(new Error('video ' + src)), { once: true });
    } else { const i = new Image(); i.onload = () => { I[n] = i; res(); }; i.onerror = () => rej(new Error('image ' + src)); i.src = src; }
  })));
  await Promise.all(['italic 400 40px "Instrument Serif"', '500 40px "Inter Tight"', '600 40px "Inter Tight"', '800 40px "Inter Tight"'].map(f => document.fonts.load(f, 'Aäß—·')));
  if (E.init) E.init();
  await prepare(0); render(0); return true;
})();
