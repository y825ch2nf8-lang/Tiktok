// "Verkaufstricks" — bright explainer, cut to the voice: every scene starts with its spoken sentence (cues.js).
// Look: paper background, ink type, one sale-red accent; price tags, a price-history chart, pop captions.
// Engine helpers (line, fill, F, L, T0, W, H, x, ...) are globals from ../engine/engine.js; use them only inside functions.
const RED = '#ff3d2e', PAPER = '#f4efe6', K_INK = '#121110', K_CREAM = '#f6f1e8';
const TXW = 846, LEAD = window.LEAD, PH = window.PHRASES.map(p => ({ a: p[0] + LEAD, b: p[1] + LEAD, str: p[2], sc: p[3] }));
const CUT = [0, 1, 2, 3, 4, 5, 6].map(k => k === 0 ? 0 : PH.find(p => p.sc === k).a - .12);       // scene starts
const ph = i => PH[i].a;                                                                           // cue = start of phrase i

function fit(str, fontFn, maxSize, maxW) { const w = measure(str, fontFn(100)); return Math.min(maxSize, 100 * maxW / w); }
const P = (t, t0, d = .35) => outExpo(cl((t - t0) / d));
function slam(str, X, Y, f, dt, rot = 0, amp = .16, align = 'left') {
  if (dt < 0) return; const k = Math.exp(-dt * 16), w = measure(str, f), cx = align === 'center' ? X : X + w / 2, cy = Y - f.size * .3;
  x.save(); x.translate(cx, cy); x.rotate(rot * k); x.scale(1 + amp * k, 1 + amp * k); setFont(f); x.textAlign = 'center'; x.textBaseline = 'alphabetic'; x.fillStyle = f.color; x.fillText(str, 0, f.size * .3); x.restore();
}
function text(str, X, Y, f, align = 'left') { setFont(f); x.fillStyle = f.color; x.textAlign = align; x.textBaseline = 'alphabetic'; x.fillText(str, X, Y); }
function strike(X, Y, w, p, lw = 16, col = RED) { if (p <= 0) return; x.save(); x.strokeStyle = col; x.lineWidth = lw; x.lineCap = 'round'; x.beginPath(); x.moveTo(X, Y + 18); x.lineTo(X + w * p, Y + 18 - 46 * p); x.stroke(); x.restore(); }
function label(str, t0, t, col = RED) { line(str, L, T0 + 40, F.label(24, col), t0, t, { d: .45 }); }
function shake(dt, amp = 14) { const s = Math.exp(-Math.max(0, dt) * 11) * amp; x.translate(Math.sin(dt * 97) * s, Math.cos(dt * 83) * s); }

// 0 — hook: full-bleed red "−50 %", then hard cut to paper where the number gets struck through
function sHook(l, t) {
  const cutB = ph(1) - .1;
  if (t < cutB) {
    fill(RED, -60, -60, W + 120, H + 120); x.save(); shake(l);
    text('VERKAUFSTRICKS  ·  FOLGE 01', L, T0 + 40, F.label(24, K_INK));
    slam('−50 %', L, 900, F.sans(fit('−50 %', v => F.sans(v), 400, TXW), K_CREAM), l, -.04, .12);
    slam('?', L + 560, 1330, F.serif(420, K_INK), l - .75, .1, .3);
    x.restore();
  } else {
    const d = t - cutB; fill(PAPER); x.save(); shake(d);
    text('VERKAUFSTRICKS  ·  FOLGE 01', L, T0 + 40, F.label(24, RED));
    const f = F.sans(250, K_INK); text('−50 %', L, 640, f); strike(L - 10, 560, measure('−50 %', f) + 20, P(d, .1, .3), 24);
    slam('Dieser Rabatt', L, 860, F.sans(fit('Dieser Rabatt', v => F.sans(v), 150, TXW), K_INK), d, 0, .1);
    slam('ist oft', L, 1010, F.sans(150, K_INK), d - .45, 0, .1);
    slam('gar keiner.', L, 1210, F.serif(fit('gar keiner.', v => F.serif(v), 250, TXW), RED), d - .8, -.02, .14);
    x.restore();
  }
}
// 1 — the trick: the struck-through price is the UVP
function sTrick(l, t) {
  fill(PAPER); label('DER TRICK', 0, l);
  const f = F.sans(300, K_INK), w = measure('129 €', f), X = L, Y = 720, d1 = t - ph(3);
  slam('129 €', X, Y, f, l - .1, 0, .1); strike(X - 14, Y - 110, w + 28, P(l, .5, .35), 26);
  if (d1 > .9) {                                           // arrow + box "UVP" pointing at the struck price
    const p = P(d1, .9, .3), ax = X + 100;
    x.save(); x.globalAlpha = Math.min(1, p * 2); x.strokeStyle = K_INK; x.lineWidth = 8; x.lineCap = 'round'; x.lineJoin = 'round';
    x.beginPath(); x.moveTo(ax, 880); x.lineTo(ax, 880 - 90 * p); x.moveTo(ax - 26, 880 - 90 * p + 30); x.lineTo(ax, 880 - 90 * p); x.lineTo(ax + 26, 880 - 90 * p + 30); x.stroke();
    const ff = F.sans(104, K_CREAM), ww = measure('UVP', ff) + 72; x.translate(X, 900); fill(K_INK, 0, 0, ww * p, 132); if (p > .7) text('UVP', 36, 102, ff); x.restore();
  }
  const d2 = t - ph(4);
  line('= unverbindliche Preisempfehlung', L, 1130, F.body(fit('= unverbindliche Preisempfehlung', v => F.body(v), 54, TXW), K_INK), 0, d2 + .1, { d: .45 });
  if (d2 > 1.0) slam('Zahlt kaum jemand.', L, 1250, F.serif(fit('Zahlt kaum jemand.', v => F.serif(v), 130, TXW), RED), d2 - 1.0, -.015, .12);
}
// 2 — example price tag: UVP 129 struck, 79 big, badge −39 %
function tag(t, uvpT, nowT, badgeT, badge) {
  const X = L, Y = 420, w = TXW, h = 640;
  fill('#ffffff', X, Y, w, h); x.save(); x.strokeStyle = K_INK; x.lineWidth = 6; x.strokeRect(X, Y, w, h); x.restore();
  text('KOPFHÖRER', X + 44, Y + 84, F.label(26, K_INK)); fill(K_INK, X + 44, Y + 112, w - 88, 3);
  if (t > uvpT) { const f = F.sans(92, 'rgba(18,17,16,.55)'), s = 'UVP 129 €'; slam(s, X + 44, Y + 250, f, t - uvpT, 0, .1); strike(X + 34, Y + 205, measure(s, f) + 20, P(t, uvpT + .35, .3), 12); }
  if (t > nowT) slam('79 €', X + 44, Y + 520, F.sans(300, RED), t - nowT, -.02, .16);
  if (t > badgeT) {
    const k = Math.exp(-(t - badgeT) * 14), r = 150; x.save(); x.translate(X + w - 110, Y + 60); x.rotate(.18 + .3 * k); x.scale(1 + .5 * k, 1 + .5 * k);
    x.beginPath(); x.arc(0, 0, r, 0, 7); x.fillStyle = badge.col; x.fill(); text(badge.str, 0, 30, F.sans(88, badge.fg), 'center'); x.restore();
  }
}
function sExample(l, t) {
  fill(PAPER); label('BEISPIEL', 0, l, K_INK);
  tag(t, ph(6), ph(7), ph(8) + .5, { str: '−39 %', col: K_INK, fg: K_CREAM });
}
// 3 — price history: the real price was 84, the UVP line floats far above
function sChart(l, t) {
  fill(PAPER); label('PREISVERLAUF  ·  LETZTE 8 WOCHEN', 0, l, K_INK);
  const X0 = L + 10, X1 = L + TXW - 120, Y0 = 1020, Yt = 430, vals = [86, 85, 86, 84, 84, 85, 84, 79];
  const yv = v => Y0 - (v - 70) / (135 - 70) * (Y0 - Yt), xi = i => X0 + (X1 - X0) * i / (vals.length - 1);
  x.save(); x.strokeStyle = 'rgba(18,17,16,.18)'; x.lineWidth = 2; for (const g of [80, 100, 120]) { x.beginPath(); x.moveTo(X0, yv(g)); x.lineTo(X1 + 110, yv(g)); x.stroke(); text(g + ' €', X1 + 110, yv(g) - 10, F.label(20, 'rgba(18,17,16,.5)'), 'right'); }
  x.setLineDash([16, 12]); x.strokeStyle = K_INK; x.lineWidth = 4; x.beginPath(); x.moveTo(X0, yv(129)); x.lineTo(X0 + (X1 + 110 - X0) * P(l, .1, .6), yv(129)); x.stroke(); x.setLineDash([]);
  text('UVP 129 €', X0, yv(129) - 22, F.sans(40, K_INK));
  const p = cl((l - .3) / 1.6) * (vals.length - 1); x.strokeStyle = RED; x.lineWidth = 12; x.lineJoin = 'round'; x.lineCap = 'round'; x.beginPath();
  for (let i = 0; i <= Math.floor(p); i++) i ? x.lineTo(xi(i), yv(vals[i])) : x.moveTo(xi(0), yv(vals[0]));
  const fi = Math.floor(p), fr = p - fi; if (fi < vals.length - 1) x.lineTo(xi(fi) + (xi(fi + 1) - xi(fi)) * fr, yv(vals[fi]) + (yv(vals[fi + 1]) - yv(vals[fi])) * fr); x.stroke();
  const dot = (i, str, dy, t0, al = 'center', dx = 0) => { const q = P(l, t0, .3); if (q <= 0) return; x.beginPath(); x.arc(xi(i), yv(vals[i]), 20 * q, 0, 7); x.fillStyle = K_INK; x.fill(); x.globalAlpha = q; text(str, xi(i) + dx, yv(vals[i]) + dy, F.sans(46, K_INK), al); x.globalAlpha = 1; };
  dot(3, 'vor 4 Wochen: 84 €', -44, 1.2); dot(7, 'heute: 79 €', 86, 2.1, 'right', 24);
  x.restore();
  const d = t - ph(10);
  if (d > 0) {
    const k = Math.exp(-d * 14); x.save(); x.translate(L + TXW / 2, 1175); x.scale(1 + .12 * k, 1 + .12 * k); fill(RED, -TXW / 2, -75, TXW, 150);
    text('Echte Ersparnis:', -TXW / 2 + 36, 22, F.sans(62, K_INK));
    if (t > ph(11)) { const k2 = Math.exp(-(t - ph(11)) * 14); x.translate(TXW / 2 - 150, 0); x.scale(1 + .4 * k2, 1 + .4 * k2); text('5 €', 0, 38, F.sans(118, K_CREAM), 'center'); }
    x.restore();
  }
}
// 4 — the study number, counting up on a dark frame
function sStat(l, t) {
  fill(K_INK); label('BLACK FRIDAY 2024  ·  10.000 PRODUKTE', 0, l);
  const end = PH[12].b - .9, n = Math.round(7 * cl((t - (ph(12) + 1.2)) / Math.max(.5, end - ph(12) - 1.2)) * 10) / 10, done = t >= end;
  line('Echte Ersparnis', L, 520, F.sans(fit('Echte Ersparnis', v => F.sans(v), 120, TXW), K_CREAM), .1, l);
  line('im Schnitt:', L, 650, F.serif(150, K_CREAM), .3, l);
  const f = F.sans(430, RED), s = (done ? '7' : n.toFixed(1).replace('.', ',')) + ' %', k = done ? Math.exp(-(t - end) * 14) : 0;
  x.save(); x.translate(L, 1080); x.scale(1 + .1 * k, 1 + .1 * k); text(s, 0, 0, F.sans(fit(s, v => F.sans(v), 430, TXW), RED)); x.restore();
  line('QUELLE: IDEALO-PREISSTUDIE  ·  VERGLEICH MIT DEM VORMONAT', L, 1200, F.label(fit('QUELLE: IDEALO-PREISSTUDIE  ·  VERGLEICH MIT DEM VORMONAT', v => F.label(v), 21, TXW), 'rgba(246,241,232,.7)'), 1.6, l);
}
// 5 — what to do
function sTip(l, t) {
  fill(RED, -60, -60, W + 120, H + 120); x.save(); shake(l, 10); label('SO FÄLLST DU NICHT DRAUF REIN', 0, l, K_INK);
  slam('Erst', L, 640, F.sans(200, K_INK), t - ph(14), 0, .12);
  slam('Preisverlauf', L, 820, F.sans(fit('Preisverlauf', v => F.sans(v), 200, TXW), K_CREAM), t - ph(14) - .25, 0, .12);
  slam('checken.', L, 1000, F.sans(fit('checken.', v => F.sans(v), 200, TXW), K_CREAM), t - ph(14) - .7, 0, .12);
  slam('Dann kaufen.', L, 1220, F.serif(fit('Dann kaufen.', v => F.serif(v), 230, TXW), K_INK), t - ph(15), -.02, .16);
  x.restore();
}
// 6 — call to action
function sCta(l) {
  fill(PAPER); const push = 1 + .012 * l; x.save(); x.translate(W / 2, H * .45); x.scale(push, push); x.translate(-W / 2, -H * .45);
  text('VERKAUFSTRICKS  ·  FOLGE 01', L, T0 + 40, F.label(24, RED));
  line('Nicht reinfallen.', L, 760, F.serif(fit('Nicht reinfallen.', v => F.serif(v), 200, TXW), K_INK), .05, l);
  line('Folge für mehr', L, 910, F.sans(110, K_INK), .25, l);
  if (l > .5) { const f = F.sans(92, K_CREAM), s = 'Verkaufstricks', w = measure(s, f) + 80, k = Math.exp(-(l - .5) * 14); x.save(); x.translate(L + w / 2, 1040); x.scale(1 + .1 * k, 1 + .1 * k); fill(RED, -w / 2, -70, w, 140); text(s, 0, 32, f, 'center'); x.restore(); }
  x.restore();
}
// captions: spoken words, 1-3 at a time, numbers in red (skipped on the hook and CTA, which already show their words)
const WEIGHT = { '129': 21, '79,': 15, '39': 14, '84': 14, '2024': 25, '7': 6, '5': 4, '50': 7, 'UVP': 9 };
const CAPS = (() => {
  const out = [];
  for (const p of PH) {
    if (p.sc === 0 || p.sc === 6 || p.sc === 5) continue;
    const chunks = []; let cur = [];
    for (const w of p.str.split(' ')) { if (cur.length && (cur.join(' ') + ' ' + w).length > 16) { chunks.push(cur); cur = []; } cur.push(w); if (cur.length >= 3 || /[.?!:,]$/.test(w)) { chunks.push(cur); cur = []; } }
    if (cur.length) chunks.push(cur);
    const wt = c => c.reduce((n, w) => n + (WEIGHT[w] ?? w.length) + 1, 0), tot = chunks.reduce((n, c) => n + wt(c), 0); let acc = 0;
    chunks.forEach((c, i) => { const a = p.a + (p.b - p.a) * acc / tot; acc += wt(c); out.push({ a: a - .04, b: i === chunks.length - 1 ? p.b + .12 : p.a + (p.b - p.a) * acc / tot - .04, str: c.join(' ').replace(/[.,:]$/, '').replace(' Euro', ' €').replace(' Prozent', ' %') }); });
  }
  return out;
})();
function captions(t, dark) {
  const c = CAPS.find(c => t >= c.a && t < c.b); if (!c) return;
  const cf = v => ({ font: `800 ${v}px "Inter Tight"`, size: v, track: v * .012 }), f = cf(fit(c.str, cf, 92, TXW - 60)), k = Math.exp(-(t - c.a) * 22);
  x.save(); x.translate(L + TXW / 2, 1372); x.scale(1 + .16 * k, 1 + .16 * k); setFont(f); x.textAlign = 'center'; x.textBaseline = 'middle'; x.lineJoin = 'round';
  x.strokeStyle = K_INK; x.lineWidth = f.size * .17; x.strokeText(c.str, 0, 0); x.fillStyle = /\d/.test(c.str) ? '#ffd84a' : '#ffffff'; x.fillText(c.str, 0, 0); x.restore();
}
function bar(t, col) { fill(col, 0, 246, W * (t / window.DUR), 7); }

const SC = [sHook, sTrick, sExample, sChart, sStat, sTip, sCta], BARCOL = [K_INK, RED, RED, RED, RED, K_INK, RED];
window.EDIT = {
  dur: window.DUR, loop: true, accent: RED, grain: .14, vignette: .07, assets: {},
  shots: SC.map((f, k) => ({ a: CUT[k], b: k < 6 ? CUT[k + 1] : window.DUR, f: (l, t) => { f(l, t); captions(t); bar(t, k === 0 && t < ph(1) - .1 ? K_INK : BARCOL[k]); } })),
  fx: [{ type: 'flash', t: 0, a: .2 }, { type: 'whip', t: CUT[2], w: .08 }, { type: 'flash', t: CUT[4], a: .25 }, { type: 'whip', t: CUT[5], w: .08, dir: -1 }],
};
