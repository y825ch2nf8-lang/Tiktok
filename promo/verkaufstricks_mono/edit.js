// "Verkaufstricks", mono style (user reference, Nov 2026): pure black / pure white, hard inversions, one thought per frame,
// centred grotesk type that appears word by word with the voice (blur-in + small rise), minimal data graphics
// (rolling counter, glowing line chart, 10x10 grid). No accent colour, no grain, no captions: the type IS the caption.
// Cut to the voice: one shot per spoken phrase (cues.js). Engine helpers are globals; use them only inside functions.
const BLK = '#000000', WHT = '#ffffff', G1 = '#8c8c8c', G2 = '#a3a3a3', CX = 507, TXW = 846;
const LEAD = window.LEAD, PH = window.PHRASES.map(p => ({ a: p[0] + LEAD, b: p[1] + LEAD, str: p[2] }));
const WEIGHT = { '129': 21, '79,': 15, '39': 14, '84': 14, '2024': 25, '7': 6, '5': 4, '50': 7, 'UVP': 9, 'UVP,': 9 };
// time each word of phrase i is spoken (spread by length; numbers weighted by how long they take to say)
const wts = i => { const ws = PH[i].str.split(' '), wt = w => (WEIGHT[w] ?? w.length) + 1, tot = ws.reduce((n, w) => n + wt(w), 0); let acc = 0; return ws.map(w => { const t = PH[i].a + (PH[i].b - PH[i].a) * acc / tot; acc += wt(w); return t; }); };
const WT = PH.map((_, i) => wts(i));
const B = (s, c) => ({ font: `800 ${s}px "Inter Tight"`, size: s, color: c, track: -s * .03 });
const M = (s, c) => ({ font: `500 ${s}px "Inter Tight"`, size: s, color: c, track: -s * .012 });
function fit(str, fontFn, maxSize, maxW = TXW) { const w = measure(str, fontFn(100)); return Math.min(maxSize, 100 * maxW / w); }
// a word arrives: out of blur, rising a little
function win(str, X, Y, f, dt, align = 'left') {
  if (dt < 0) return; const p = outExpo(cl(dt / .42)), b = (1 - p) * 18 * K;
  x.save(); x.globalAlpha = cl(dt / .1); x.filter = b > .4 ? `blur(${b}px)` : 'none'; setFont(f); x.fillStyle = f.color; x.textAlign = align; x.textBaseline = 'alphabetic'; x.fillText(str, X, Y + (1 - p) * 24); x.restore();
}
// centred row of words, each with its own font and start time; the row keeps its final layout from the first word on
function row(t, Y, parts) {
  let tot = 0; parts.forEach((p, i) => { p.w = measure(p.s, p.f); tot += p.w + (i ? p.f.size * .24 : 0); });
  let X = CX - tot / 2; parts.forEach((p, i) => { if (i) X += p.f.size * .24; win(p.s, X, Y, p.f, t - p.at); X += p.w; });
}
const big = (str, Y, f, dt) => win(str, CX, Y, f, dt, 'center');
function settle(str, Y, f, l) { const k = Math.exp(-l * 14); x.save(); x.translate(CX, Y - f.size * .32); x.scale(1 + .08 * k, 1 + .08 * k); setFont(f); x.fillStyle = f.color; x.textAlign = 'center'; x.textBaseline = 'alphabetic'; x.fillText(str, 0, f.size * .32); x.restore(); }
const drift = l => { x.translate(CX, 900); x.scale(1 + .012 * l, 1 + .012 * l); x.translate(-CX, -900); };   // slow push-in on every shot

const SHOTS = [
  // 0 "Minus 50 Prozent?" — frame 0 is sharp: the number is there before the thumb moves on
  { bg: WHT, f: (l, t) => { big('Black Friday', 640, M(56, G1), l - .05); settle('−50 %', 980, B(fit('−50 %', v => B(v), 400), BLK), l); } },
  // 1 "Dieser Rabatt ist oft gar keiner."
  { bg: BLK, f: (l, t) => { const w = WT[1]; row(t, 700, [{ s: 'Dieser', at: w[0], f: B(130, WHT) }, { s: 'Rabatt', at: w[1], f: B(130, WHT) }]); row(t, 850, [{ s: 'ist', at: w[2], f: M(110, G2) }, { s: 'oft', at: w[3], f: M(110, G2) }, { s: 'gar', at: w[4], f: M(110, G2) }]); big('keiner.', 1090, B(250, WHT), t - w[5]); } },
  // 2 "Der Trick:"
  { bg: WHT, f: (l, t) => row(t, 960, [{ s: 'Der', at: WT[2][0], f: M(170, G1) }, { s: 'Trick', at: WT[2][1], f: B(210, BLK) }]) },
  // 3 "Der durchgestrichene Preis ist oft die UVP,"
  { bg: BLK, f: (l, t) => {
    const w = WT[3]; row(t, 610, [{ s: 'Der', at: w[0], f: M(58, G2) }, { s: 'durchgestrichene', at: w[1], f: M(58, G2) }, { s: 'Preis', at: w[2], f: M(58, G2) }]);
    const f = B(300, '#6f6f6f'); big('129 €', 930, f, l - .05); const ww = measure('129 €', f), p = outExpo(cl((t - w[1]) / .4));
    if (p > 0) { x.save(); x.strokeStyle = WHT; x.lineWidth = 12; x.lineCap = 'round'; x.shadowColor = WHT; x.shadowBlur = 18 * K; x.beginPath(); x.moveTo(CX - ww / 2 - 20, 850); x.lineTo(CX - ww / 2 - 20 + (ww + 40) * p, 850 - 30 * p); x.stroke(); x.restore(); }
    row(t, 1160, [{ s: 'ist', at: w[3], f: M(84, G2) }, { s: 'oft', at: w[4], f: M(84, G2) }, { s: 'die', at: w[5], f: M(84, G2) }, { s: 'UVP', at: w[6], f: B(150, WHT) }]);
  } },
  // 4 "eine Preisempfehlung, die im Laden kaum jemand bezahlt."
  { bg: WHT, f: (l, t) => { const w = WT[4]; row(t, 640, [{ s: 'eine', at: w[0], f: M(66, G1) }, { s: 'Preisempfehlung,', at: w[1], f: M(66, G1) }]); row(t, 820, [{ s: 'die', at: w[2], f: M(110, G1) }, { s: 'im', at: w[3], f: M(110, G1) }, { s: 'Laden', at: w[4], f: M(110, G1) }]); row(t, 1010, [{ s: 'kaum', at: w[5], f: B(138, BLK) }, { s: 'jemand', at: w[6], f: B(138, BLK) }]); big('bezahlt.', 1210, B(190, BLK), t - w[7]); } },
  // 5 "Beispiel:"
  { bg: BLK, f: (l, t) => big('Beispiel', 990, B(fit('Beispiel', v => B(v), 230), WHT), l - .02) },
  // 6 "UVP 129 Euro," — the number rolls up
  { bg: WHT, f: (l, t) => { const w = WT[6], n = Math.round(129 * outCubic((t - w[1]) / .9)); big('UVP', 690, M(90, G1), t - w[0]); if (t >= w[1]) settle(n + ' €', 1010, B(330, BLK), t - w[1] - .9 < 0 ? 9 : t - w[1] - .9); } },
  // 7 "jetzt 79,"
  { bg: BLK, f: (l, t) => {
    const w = WT[7], f = M(90, '#6f6f6f'), ww = measure('129 €', f); big('129 €', 600, f, l); x.save(); x.strokeStyle = G2; x.lineWidth = 5; x.beginPath(); x.moveTo(CX - ww / 2 - 10, 572); x.lineTo(CX - ww / 2 - 10 + (ww + 20) * outExpo(cl(l / .3)), 572); x.stroke(); x.restore();
    big('jetzt', 760, M(90, G2), t - w[0]); if (t >= w[1]) settle('79 €', 1110, B(fit('79 €', v => B(v), 420), WHT), t - w[1]);
  } },
  // 8 "sieht aus wie minus 39 Prozent."
  { bg: WHT, f: (l, t) => { const w = WT[8]; row(t, 700, [{ s: 'sieht', at: w[0], f: M(84, G1) }, { s: 'aus', at: w[1], f: M(84, G1) }, { s: 'wie', at: w[2], f: M(84, G1) }]); if (t >= w[3]) settle('−39 %', 1040, B(fit('−39 %', v => B(v), 380), BLK), t - w[3]); } },
  // 9 "Vor vier Wochen kostete das Ding aber 84 Euro," — glowing price line, the UVP floats far above it
  { bg: BLK, f: (l, t) => {
    const w = WT[9]; row(t, 470, [{ s: 'Vor', at: w[0], f: M(70, G2) }, { s: 'vier', at: w[1], f: B(70, WHT) }, { s: 'Wochen', at: w[2], f: B(70, WHT) }]);
    const X0 = 110, X1 = 900, Y0 = 1010, Yt = 600, vals = [86, 85, 86, 84, 84, 85, 84, 79], yv = v => Y0 - (v - 70) / 65 * (Y0 - Yt), xi = i => X0 + (X1 - X0) * i / 7;
    x.save(); x.setLineDash([14, 12]); x.strokeStyle = '#5a5a5a'; x.lineWidth = 3; x.beginPath(); x.moveTo(X0, yv(129)); x.lineTo(X0 + (X1 - X0) * outExpo(cl(l / .6)), yv(129)); x.stroke(); x.setLineDash([]);
    setFont(M(34, G1)); x.fillStyle = G1; x.textAlign = 'left'; x.fillText('UVP 129 €', X0, yv(129) - 18);
    const p = cl((l - .25) / 1.7) * 7, fi = Math.floor(p), fr = p - fi; x.strokeStyle = WHT; x.lineWidth = 9; x.lineJoin = 'round'; x.lineCap = 'round'; x.shadowColor = WHT; x.shadowBlur = 26 * K; x.beginPath();
    for (let i = 0; i <= fi; i++) i ? x.lineTo(xi(i), yv(vals[i])) : x.moveTo(xi(0), yv(vals[0]));
    let hx = xi(fi), hy = yv(vals[fi]); if (fi < 7) { hx += (xi(fi + 1) - xi(fi)) * fr; hy += (yv(vals[fi + 1]) - yv(vals[fi])) * fr; x.lineTo(hx, hy); } x.stroke();
    x.beginPath(); x.arc(hx, hy, 11, 0, 7); x.fillStyle = WHT; x.fill(); x.restore();
    if (p >= 7) { setFont(M(34, G1)); x.fillStyle = G1; x.textAlign = 'right'; x.fillText('heute 79 €', X1, yv(79) + 60); }
    if (t >= w[7]) settle('84 €', 1300, B(230, WHT), t - w[7]);
  } },
  // 10+11 "echte Ersparnis: 5 Euro."
  { bg: WHT, span: 2, f: (l, t) => { const w = WT[10]; row(t, 700, [{ s: 'echte', at: w[0], f: M(96, G1) }, { s: 'Ersparnis', at: w[1], f: B(96, BLK) }]); if (t >= PH[11].a) settle('5 €', 1130, B(460, BLK), t - PH[11].a); } },
  // 12 "Laut Idealo lag die echte Ersparnis am Black Friday 2024 im Schnitt bei nur 7 Prozent." — 100 squares, 7 light up
  { bg: BLK, f: (l, t) => {
    const w = WT[12]; row(t, 450, [{ s: 'Black', at: w[7], f: M(64, G2) }, { s: 'Friday', at: w[8], f: M(64, G2) }, { s: '2024', at: w[9], f: B(64, WHT) }]);
    const cell = 46, gap = 9, n = 10, G = n * cell + (n - 1) * gap, gx = CX - G / 2, gy = 530, hit = t >= w[14];
    for (let i = 0; i < 100; i++) { const a = cl((l - .1 - i * .012) / .25); if (a <= 0) continue; const on = hit && i < 7, k = on ? Math.exp(-(t - w[14] - i * .05) * 10) : 0;
      x.save(); x.globalAlpha = a; x.fillStyle = on && t - w[14] >= i * .05 ? WHT : '#262626'; if (on) { x.shadowColor = WHT; x.shadowBlur = 16 * K; } const s = cell * (1 + .25 * Math.max(0, k));
      x.fillRect(gx + (i % n) * (cell + gap) + (cell - s) / 2, gy + Math.floor(i / n) * (cell + gap) + (cell - s) / 2, s, s); x.restore(); }
    row(t, 1180, [{ s: 'im', at: w[10], f: M(70, G2) }, { s: 'Schnitt', at: w[11], f: M(70, G2) }, { s: 'nur', at: w[13], f: M(70, G2) }]);
    if (hit) settle('7 %', 1400, B(250, WHT), t - w[14]);
    win('Quelle: idealo-Preisstudie, 10.000 Produkte, Vergleich mit dem Vormonat', CX, 1470, M(25, '#7a7a7a'), l - 1.2, 'center');
  } },
  // 13 "Also:"
  { bg: WHT, f: (l, t) => big('Also', 990, B(260, BLK), l - .02) },
  // 14 "Erst den Preisverlauf checken,"
  { bg: BLK, f: (l, t) => { const w = WT[14]; row(t, 760, [{ s: 'Erst', at: w[0], f: M(120, G2) }, { s: 'den', at: w[1], f: M(120, G2) }]); big('Preisverlauf', 950, B(fit('Preisverlauf', v => B(v), 190), WHT), t - w[2]); big('checken', 1130, B(170, WHT), t - w[3]); } },
  // 15 "dann kaufen."
  { bg: WHT, f: (l, t) => row(t, 990, [{ s: 'dann', at: WT[15][0], f: M(150, G1) }, { s: 'kaufen.', at: WT[15][1], f: B(170, BLK) }]) },
  // 16 "Folg mir für mehr Verkaufstricks."
  { bg: BLK, f: (l, t) => { const w = WT[16]; row(t, 840, [{ s: 'Folg', at: w[0], f: M(84, G2) }, { s: 'mir', at: w[1], f: M(84, G2) }, { s: 'für', at: w[2], f: M(84, G2) }, { s: 'mehr', at: w[3], f: M(84, G2) }]); big('Verkaufstricks', 1010, B(fit('Verkaufstricks', v => B(v), 150), WHT), t - w[4]); } },
];
const shots = []; let pi = 0;
SHOTS.forEach(s => { const a = pi === 0 ? 0 : PH[pi].a - .08; const fn = s.f, bg = s.bg; shots.push({ a, f: (l, t) => { fill(bg, -40, -40, W + 80, H + 80); x.save(); drift(l); fn(l, t); x.restore(); } }); pi += s.span || 1; });
shots.forEach((s, i) => s.b = i < shots.length - 1 ? shots[i + 1].a : window.DUR);
window.EDIT = { dur: window.DUR, loop: true, accent: WHT, grain: 0, vignette: 0, assets: {}, shots, fx: [] };
