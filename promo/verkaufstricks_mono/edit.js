// "Verkaufstricks", mono style (user reference, Nov 2026): pure black / pure white, hard inversions, one thought per frame,
// centred grotesk type that appears word by word with the voice (blur-in + small rise), minimal data graphics
// (rolling counter, glowing line chart, 10x10 grid). No accent colour, no grain, no captions: the type IS the caption.
// Cut to the voice: one shot per spoken phrase (cues.js). Engine helpers are globals; use them only inside functions.
const BLK = '#000000', WHT = '#ffffff', G1 = '#8c8c8c', G2 = '#a3a3a3', CX = 507, TXW = 846;
const LEAD = window.LEAD, PH = {}; window.PHRASES.forEach(p => PH[p[3]] = { a: p[0] + LEAD, b: p[1] + LEAD, str: p[2] });
const WEIGHT = { '129': 21, '79.': 15, '39': 14, '84': 14, '2024': 25, '7': 6, '5': 4, '50': 7, 'UVP': 9, 'UVP.': 9 };
// time each word of a phrase is spoken (spread by length; numbers weighted by how long they take to say)
const WT = {}; for (const id in PH) { const ws = PH[id].str.split(' '), wt = w => (WEIGHT[w] ?? w.length) + 1, tot = ws.reduce((n, w) => n + wt(w), 0); let acc = 0; WT[id] = ws.map(w => { const t = PH[id].a + (PH[id].b - PH[id].a) * acc / tot; acc += wt(w); return t; }); }
const T = id => PH[id].a;
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

const chart = (l, t) => {            // glowing price line; the UVP floats far above it
  const X0 = 110, X1 = 900, Y0 = 1010, Yt = 600, vals = [86, 85, 86, 84, 84, 85, 84, 79], yv = v => Y0 - (v - 70) / 65 * (Y0 - Yt), xi = i => X0 + (X1 - X0) * i / 7;
  x.save(); x.setLineDash([14, 12]); x.strokeStyle = '#5a5a5a'; x.lineWidth = 3; x.beginPath(); x.moveTo(X0, yv(129)); x.lineTo(X0 + (X1 - X0) * outExpo(cl(l / .6)), yv(129)); x.stroke(); x.setLineDash([]);
  setFont(M(34, G1)); x.fillStyle = G1; x.textAlign = 'left'; x.fillText('UVP 129 €', X0, yv(129) - 18);
  const p = cl((l - .2) / 1.3) * 7, fi = Math.floor(p), fr = p - fi; x.strokeStyle = WHT; x.lineWidth = 9; x.lineJoin = 'round'; x.lineCap = 'round'; x.shadowColor = WHT; x.shadowBlur = 26 * K; x.beginPath();
  for (let i = 0; i <= fi; i++) i ? x.lineTo(xi(i), yv(vals[i])) : x.moveTo(xi(0), yv(vals[0]));
  let hx = xi(fi), hy = yv(vals[fi]); if (fi < 7) { hx += (xi(fi + 1) - xi(fi)) * fr; hy += (yv(vals[fi + 1]) - yv(vals[fi])) * fr; x.lineTo(hx, hy); } x.stroke();
  x.beginPath(); x.arc(hx, hy, 11, 0, 7); x.fillStyle = WHT; x.fill(); x.restore();
  if (p >= 7) { setFont(M(34, G1)); x.fillStyle = G1; x.textAlign = 'right'; x.fillText('heute 79 €', X1, yv(79) + 60); }
};
const SHOTS = [
  // "Okay." — like the reference: one small word, sharp on frame 0
  { at: 'okay', bg: WHT, f: (l, t) => settle('okay', 990, B(250, BLK), l) },
  // "Minus 50 Prozent? Glaub ich nicht."
  { at: 'm50', bg: BLK, f: (l, t) => { const w = WT.glaub; settle('−50 %', 930, B(fit('−50 %', v => B(v), 400), WHT), l); row(t, 1150, [{ s: 'Glaub', at: w[0], f: M(110, G2) }, { s: 'ich', at: w[1], f: M(110, G2) }, { s: 'nicht.', at: w[2], f: B(120, WHT) }]); } },
  // "Pass auf."
  { at: 'pass', bg: WHT, f: (l, t) => row(t, 990, [{ s: 'Pass', at: WT.pass[0], f: B(220, BLK) }, { s: 'auf', at: WT.pass[1], f: B(220, BLK) }]) },
  // "Der durchgestrichene Preis ist oft nur die UVP."
  { at: 'trick', bg: BLK, f: (l, t) => {
    const w = WT.trick; row(t, 610, [{ s: 'Der', at: w[0], f: M(58, G2) }, { s: 'durchgestrichene', at: w[1], f: M(58, G2) }, { s: 'Preis', at: w[2], f: M(58, G2) }]);
    const f = B(300, '#6f6f6f'); big('129 €', 930, f, l - .05); const ww = measure('129 €', f), p = outExpo(cl((t - w[1]) / .4));
    if (p > 0) { x.save(); x.strokeStyle = WHT; x.lineWidth = 12; x.lineCap = 'round'; x.shadowColor = WHT; x.shadowBlur = 18 * K; x.beginPath(); x.moveTo(CX - ww / 2 - 20, 850); x.lineTo(CX - ww / 2 - 20 + (ww + 40) * p, 850 - 30 * p); x.stroke(); x.restore(); }
    row(t, 1160, [{ s: 'ist', at: w[3], f: M(80, G2) }, { s: 'oft', at: w[4], f: M(80, G2) }, { s: 'nur', at: w[5], f: M(80, G2) }, { s: 'die', at: w[6], f: M(80, G2) }, { s: 'UVP', at: w[7], f: B(150, WHT) }]);
  } },
  // "Die zahlt eh keiner."
  { at: 'keiner', bg: WHT, f: (l, t) => { const w = WT.keiner; row(t, 800, [{ s: 'Die', at: w[0], f: M(120, G1) }, { s: 'zahlt', at: w[1], f: M(120, G1) }]); row(t, 1040, [{ s: 'eh', at: w[2], f: M(200, G1) }, { s: 'keiner.', at: w[3], f: B(200, BLK) }]); } },
  // "Beispiel: Kopfhörer."
  { at: 'bsp', bg: BLK, f: (l, t) => { big('Beispiel', 760, M(90, G2), l - .02); big('Kopfhörer', 1000, B(fit('Kopfhörer', v => B(v), 200), WHT), t - T('kopf')); } },
  // "UVP 129 Euro." — the number rolls up
  { at: 'uvp', bg: WHT, f: (l, t) => { const a = T('n129'), n = Math.round(129 * outCubic((t - a) / .8)); big('UVP', 690, M(90, G1), l - .02); if (t >= a) settle(n + ' €', 1010, B(330, BLK), t - a - .8 < 0 ? 9 : t - a - .8); } },
  // "Jetzt 79."
  { at: 'jetzt', bg: BLK, f: (l, t) => {
    const f = M(90, '#6f6f6f'), ww = measure('129 €', f); big('129 €', 600, f, 9); x.save(); x.strokeStyle = G2; x.lineWidth = 5; x.beginPath(); x.moveTo(CX - ww / 2 - 10, 572); x.lineTo(CX - ww / 2 - 10 + (ww + 20) * outExpo(cl(l / .3)), 572); x.stroke(); x.restore();
    big('jetzt', 760, M(90, G2), l - .02); if (t >= T('n79')) settle('79 €', 1110, B(fit('79 €', v => B(v), 420), WHT), t - T('n79'));
  } },
  // "Klingt nach minus 39 Prozent."
  { at: 'klingt', bg: WHT, f: (l, t) => { const w = WT.klingt; row(t, 700, [{ s: 'Klingt', at: w[0], f: M(90, G1) }, { s: 'nach', at: w[1], f: M(90, G1) }]); if (t >= w[2]) settle('−39 %', 1040, B(fit('−39 %', v => B(v), 380), BLK), t - w[2]); } },
  // "Vor vier Wochen? 84 Euro."
  { at: 'vor', bg: BLK, f: (l, t) => { const w = WT.vor; row(t, 470, [{ s: 'Vor', at: w[0], f: M(70, G2) }, { s: 'vier', at: w[1], f: B(70, WHT) }, { s: 'Wochen?', at: w[2], f: B(70, WHT) }]); chart(l, t); if (t >= T('n84')) settle('84 €', 1300, B(230, WHT), t - T('n84')); } },
  // the laugh
  { at: 'haha', bg: WHT, f: (l, t) => big('haha', 980, M(110, G1), l - .02) },
  // "Du sparst also 5 Euro."
  { at: 'spar', bg: BLK, f: (l, t) => { const w = WT.spar; row(t, 700, [{ s: 'Du', at: w[0], f: M(96, G2) }, { s: 'sparst', at: w[1], f: B(96, WHT) }, { s: 'also', at: w[2], f: M(96, G2) }]); if (t >= w[3]) settle('5 €', 1130, B(460, WHT), t - w[3]); } },
  // "Und das ist normal."
  { at: 'normal', bg: WHT, f: (l, t) => { const w = WT.normal; row(t, 860, [{ s: 'Und', at: w[0], f: M(110, G1) }, { s: 'das', at: w[1], f: M(110, G1) }, { s: 'ist', at: w[2], f: M(110, G1) }]); big('normal.', 1080, B(230, BLK), t - w[3]); } },
  // "Laut Idealo waren es am Black Friday 2024 im Schnitt nur 7 Prozent." — 100 squares, 7 light up
  { at: 'idealo', bg: BLK, f: (l, t) => {
    const w = WT.idealo, h7 = WT.n7[1]; row(t, 450, [{ s: 'Black', at: w[5], f: M(64, G2) }, { s: 'Friday', at: w[6], f: M(64, G2) }, { s: '2024', at: w[7], f: B(64, WHT) }]);
    const cell = 46, gap = 9, n = 10, G = n * cell + (n - 1) * gap, gx = CX - G / 2, gy = 530, hit = t >= h7;
    for (let i = 0; i < 100; i++) { const a = cl((l - .1 - i * .012) / .25); if (a <= 0) continue; const on = hit && i < 7 && t - h7 >= i * .05, k = on ? Math.exp(-(t - h7 - i * .05) * 10) : 0;
      x.save(); x.globalAlpha = a; x.fillStyle = on ? WHT : '#262626'; if (on) { x.shadowColor = WHT; x.shadowBlur = 16 * K; } const s = cell * (1 + .25 * k);
      x.fillRect(gx + (i % n) * (cell + gap) + (cell - s) / 2, gy + Math.floor(i / n) * (cell + gap) + (cell - s) / 2, s, s); x.restore(); }
    row(t, 1180, [{ s: 'im', at: w[8], f: M(70, G2) }, { s: 'Schnitt', at: w[9], f: M(70, G2) }, { s: 'nur', at: WT.n7[0], f: M(70, G2) }]);
    if (hit) settle('7 %', 1400, B(250, WHT), t - h7);
    win('Quelle: idealo-Preisstudie, 10.000 Produkte, Vergleich mit dem Vormonat', CX, 1470, M(25, '#7a7a7a'), l - 1.2, 'center');
  } },
  // "Also:"
  { at: 'also', bg: WHT, f: (l, t) => big('Also', 990, B(260, BLK), l - .02) },
  // "Erst Preisverlauf checken."
  { at: 'erst', bg: BLK, f: (l, t) => { const w = WT.erst; big('Erst', 760, M(120, G2), t - w[0]); big('Preisverlauf', 950, B(fit('Preisverlauf', v => B(v), 190), WHT), t - w[1]); big('checken.', 1130, B(170, WHT), t - w[2]); } },
  // "Dann kaufen."
  { at: 'dann', bg: WHT, f: (l, t) => row(t, 990, [{ s: 'Dann', at: WT.dann[0], f: M(150, G1) }, { s: 'kaufen.', at: WT.dann[1], f: B(170, BLK) }]) },
  // "Folg mir, wenn du nicht mehr drauf reinfallen willst."
  { at: 'folg', bg: BLK, f: (l, t) => { const w = WT.folg; row(t, 720, [{ s: 'Folg', at: w[0], f: B(170, WHT) }, { s: 'mir,', at: w[1], f: B(170, WHT) }]); row(t, 900, [{ s: 'wenn', at: w[2], f: M(76, G2) }, { s: 'du', at: w[3], f: M(76, G2) }, { s: 'nicht', at: w[4], f: M(76, G2) }, { s: 'mehr', at: w[5], f: M(76, G2) }]); row(t, 1030, [{ s: 'drauf', at: w[6], f: B(100, WHT) }, { s: 'reinfallen', at: w[7], f: B(100, WHT) }]); big('willst.', 1160, M(100, G2), t - w[8]); } },
];
const shots = SHOTS.map((s, i) => ({ a: i === 0 ? 0 : T(s.at) - .08, f: (l, t) => { fill(s.bg, -40, -40, W + 80, H + 80); x.save(); drift(l); s.f(l, t); x.restore(); } }));
shots.forEach((s, i) => s.b = i < shots.length - 1 ? shots[i + 1].a : window.DUR);
window.EDIT = { dur: window.DUR, loop: true, accent: WHT, grain: 0, vignette: 0, assets: {}, shots, fx: [] };
