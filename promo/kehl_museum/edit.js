// Kehl Event — "Kunst, die man essen kann." Kampagnenfilm, Catering im August-Macke-Haus Bonn.
// Idee: Das Buffet wird wie eine Ausstellung inszeniert. Galeriewand, Rahmen, Spot, Museumsschild (Werkangaben = Speisekarte).
// 30 s = 12 Takte @ 96 BPM, Loop. Satz-Loop: "Kehl Event —" -> "Kunst, die man essen kann."
// Kehl Event hat keine feste Karte: Menü und Cocktails werden für jeden Kunden individuell zusammengestellt.
// Die Gerichte stammen aus dem Menü DIESES Abends. Übergänge: Push-Through in den Rahmen (Speed-Ramp), Lichtschwenk, Whip, Iris aus dem Glasrand (Match-Cut),
// Zoom-Through, Katalogseite schiebt sich ins Bild, Licht aus. Fakten nur aus Speisekarte und Location-Tag.
const BPM_ = 96, BEAT = 60 / BPM_, at = b => b * BEAT;
const ORANGE = '#e8853a', WALL = '#e9e4dc', PAPER = '#efe7da', KI = '#0f0d0b', KC = '#f3ede4', CARD = '#f7f3ec', GREY = '#77706a';

function fit(str, fontFn, maxSize, maxW) { const w = measure(str, fontFn(100)); return Math.min(maxSize, 100 * maxW / w); }
const PG = 'contrast(1.08) saturate(0.95) brightness(1.07) sepia(0.08)';
const ph = (im, X, Y, w, h, o = {}) => photo(im, X, Y, w, h, { grade: PG, ...o });
const lerp = (a, b, u) => a + (b - a) * u;

// ---------- Kamera, Unschärfe, Mapping ----------
function cam(k, px, py, tx, ty) { x.translate(tx, ty); x.scale(k, k); x.translate(-px, -py); }
let TMP = null;
function zoomBlur(amt, cx = W / 2, cy = H / 2) {           // weiche radiale Bewegungsunschärfe (iterativ, 32 Samples)
  if (amt < .01) return;
  if (!TMP) { TMP = document.createElement('canvas'); TMP.width = W * K; TMP.height = H * K; }
  const t = TMP.getContext('2d'); t.setTransform(1, 0, 0, 1, 0, 0); t.globalAlpha = 1; t.drawImage(buf, 0, 0);
  const PX = cx * K, PY = cy * K, WW = W * K, HH = H * K;
  for (let s = amt * .16; s > .002; s /= 2) { t.globalAlpha = .5; t.drawImage(TMP, PX - PX * (1 + s), PY - PY * (1 + s), WW * (1 + s), HH * (1 + s)); }
  t.globalAlpha = 1; x.save(); x.filter = 'none'; x.globalAlpha = 1; x.drawImage(TMP, 0, 0, W, H); x.restore();
}
// Bildkoordinate (u,v in 0..1) -> Bildschirmposition für ein randloses photo() mit zoom/fx/fy (wie engine.photo)
function toScreen(im, z, fx, fy, u, v) {
  const iw = im.width, ih = im.height, M = 24;
  let s = Math.max(W / iw, H / ih) * z; s = Math.max(s, (W + 2 * M) / iw, (H + 2 * M) / ih);
  const dw = iw * s, dh = ih * s;
  let ix = W / 2 - fx * dw, iy = H / 2 - fy * dh;
  ix = Math.min(-M, Math.max(W - dw + M, ix)); iy = Math.min(-M, Math.max(H - dh + M, iy));
  return [ix + u * dw, iy + v * dh];
}

// ---------- Galerie ----------
function wall(spot = 1, cy = H * .42) {
  fill(WALL);
  const g = x.createRadialGradient(W / 2, cy, 0, W / 2, cy, H * .62);
  g.addColorStop(0, `rgba(255,246,228,${.55 * spot})`); g.addColorStop(.55, 'rgba(255,240,215,0)'); g.addColorStop(1, `rgba(40,30,20,${.42 - .1 * spot})`);
  x.fillStyle = g; x.fillRect(0, 0, W, H);
}
// Bilderrahmen: schwarze Leiste + Passepartout, physischer Schatten; inner = Bildfläche
function frame(X, Y, w, h, k, drawInner) {
  const mat = w * .085, bar = Math.max(5, w * .022);
  x.save();
  x.shadowColor = 'rgba(35,24,14,.38)'; x.shadowBlur = 46 * K * k; x.shadowOffsetY = 26 * K * k; x.shadowOffsetX = 6 * K * k;
  x.fillStyle = '#16120f'; x.fillRect(X - mat - bar, Y - mat - bar, w + 2 * (mat + bar), h + 2 * (mat + bar));
  x.restore();
  fill('#faf7f1', X - mat, Y - mat, w + 2 * mat, h + 2 * mat);
  x.save(); x.strokeStyle = 'rgba(0,0,0,.18)'; x.lineWidth = 1.2; x.strokeRect(X - .5, Y - .5, w + 1, h + 1); x.restore();
  drawInner(X, Y, w, h);
}
// Museumsschild (Werkangaben). p = Einblendung 0..1, lines erscheinen mit Masken-Reveal ab t0
function card(X, Y, no, title, mat, l, t0 = 0, o = {}) {
  const w = (o.w || 560) * S, h = 216 * S, p = o.instant ? 1 : outExpo(cl((l - t0) / .7));
  if (p <= 0) return;
  x.save(); x.beginPath(); x.rect(X, Y, w * p, h); x.clip();
  x.save(); x.shadowColor = 'rgba(0,0,0,.28)'; x.shadowBlur = 24 * K; x.shadowOffsetY = 8 * K; fill(CARD, X, Y, w, h); x.restore();
  fill(ORANGE, X, Y, 6 * S, h);
  x.restore();
  const lt = o.textAt ?? t0 + .15, px = X + 36 * S;
  line(o.label || 'KEHL EVENT', px, Y + 52 * S, F.label(17 * S, GREY), lt, l, { d: .5 });
  if (no) line(no, X + w - 30 * S, Y + 52 * S, F.label(17 * S, GREY), lt, l, { d: .5, align: 'right' });
  const ts = fit(title, v => F.serif(v, KI), 66 * S, w - 72 * S);
  line(title, px, Y + 128 * S, F.serif(ts, KI), lt + .06, l, { d: .55 });
  line(mat, px, Y + 178 * S, F.body(24 * S, '#4a443e'), lt + .12, l, { d: .55 });
}
const CARD_X = () => L, CARD_Y = () => B0 - 216 * S - (FEED ? 0 : 10);

// ---------- 1  Hook: das Buffet hängt als Bild an der Wand, Push-Through in den Rahmen ----------
const HOOKF = () => FEED ? .36 : .40, BUF = { im: 'buffet', z: 1.08, fx: .42, fy: .62 };
function hookLayout() { const fw = W * HOOKF(), fh = H * HOOKF(), top = T0 + 120 * S; return { fw, fh, X: (W - fw) / 2, Y: top, cy: top + fh / 2 }; }
function gallery(l, t) {
  const g = hookLayout(), rs = at(5), re = at(8);
  const u = cl((l - rs) / (re - rs)), e = Math.pow(u, 2.6);
  const k0 = 1 + .018 * Math.min(l, rs), k = lerp(k0, 1 / HOOKF(), e);
  x.save(); cam(k, W / 2, g.cy, W / 2, lerp(g.cy, H / 2, e));
  wall(1, g.cy);
  frame(g.X, g.Y, g.fw, g.fh, k, (X, Y, w, h) => ph(I[BUF.im], X, Y, w, h, { zoom: BUF.z, fx: BUF.fx, fy: BUF.fy }));
  line('KEHL EVENT  ·  AUGUST-MACKE-HAUS BONN', W / 2, T0 + 40 * S, F.label(22 * S, KI), 0, l, { instant: true, align: 'center', alpha: .7 });
  const ty = g.Y + g.fh + (FEED ? 205 : 175) * S;
  pop('Kunst,', W / 2, ty, F.serif(150 * S, KI), l, { baseline: 'alphabetic' });
  if (l >= BEAT) pop('die man essen kann.', W / 2, ty + 92 * S, F.sans(66 * S, KI), l - BEAT, { baseline: 'alphabetic' });
  x.restore();
  zoomBlur(Math.pow(u, 3) * 2.6, W / 2, H / 2);
}

// ---------- 2  Das Buffet, randlos (Ramp läuft aus) ----------
function buffetShot(l, t) {
  const z = BUF.z * (1 + .1 * outExpo(cl(l / .9)) + .012 * l);
  ph(I[BUF.im], 0, 0, W, H, { zoom: z, fx: BUF.fx, fy: BUF.fy, ...hh(t, cl(l / .8)) });
  topShade(); shade(H * .55, .55);
  zoomBlur((1 - outCubic(cl(l / .4))) * 2.6);
  card(CARD_X(), CARD_Y(), '', 'Das Buffet', 'Ausgestellt im August-Macke-Haus', l, BEAT);
}

// ---------- 3  Sechs Werke ----------
const DISH = [
  { n: 'Roggenschnittchen', m: 'Roggenbrot, Brie, Pfeffersalami', im: 'platters', z: 1.5, fx: .22, fy: .82 },
  { n: 'Partyfrikadelle', m: 'In Sweet-Chili-Dip', im: 'glasses', z: 1.6, fx: .2, fy: .82 },
  { n: 'Kartoffelsalat', m: 'Kartoffel, Essig & Öl', im: 'menu', z: 1.5, fx: .3, fy: .78, iris: [.28, .77] },
  { n: 'Süßkartoffelsalat', m: 'Süßkartoffel, Ahornsirup', im: 'glasses', z: 1.9, fx: .6, fy: .6, iris: [.67, .64] },
  { n: 'Obstsalat', m: 'Frisches Obst, in Honig mariniert', im: 'buffet', z: 1.6, fx: .42, fy: .7 },
  { n: 'Mousse au chocolat', m: 'Schokolade, Chilifäden', im: 'buffet', z: 1.9, fx: .76, fy: .88 },
];
const DL = at(2);
function dishImg(i, l, t) {           // nur das Bild (ohne Schild), inkl. Zoom-Through-Rampen
  const d = DISH[i]; let z = d.z * (1 + .045 * l);
  if (i === 3) z *= 1 + 1.4 * Math.pow(cl((l - (DL - .32)) / .32), 3);      // rast hinein ...
  if (i === 4) z *= 1 + .45 * (1 - outExpo(cl(l / .5)));                     // ... und landet im nächsten Bild
  ph(I[d.im], 0, 0, W, H, { zoom: z, fx: d.fx, fy: d.fy, ...hh(t, .7) });
  topShade(); shade(H * .58, .5);
}
function sweep(l, drawA, drawB, d = .55) {   // Lichtschwenk: diagonale Lichtkante deckt B auf
  const p = cl(l / d); if (p >= 1) { drawB(); return; }
  drawA(); if (p <= 0) return;
  const tilt = W * .35, bx = lerp(-tilt, W + tilt, inCubic(p) * .35 + outCubic(p) * .65);
  x.save(); x.beginPath(); x.moveTo(-10, 0); x.lineTo(bx + tilt, 0); x.lineTo(bx - tilt, H); x.lineTo(-10, H); x.closePath(); x.clip(); drawB(); x.restore();
  x.save(); x.globalCompositeOperation = 'screen';
  const nx = 1, ny = (2 * tilt) / H, len = Math.hypot(nx * H, 2 * tilt);
  const g = x.createLinearGradient(bx - 160, H / 2, bx + 160, H / 2);
  g.addColorStop(0, 'rgba(255,214,160,0)'); g.addColorStop(.5, `rgba(255,228,190,${.85 * Math.sin(Math.PI * p)})`); g.addColorStop(1, 'rgba(255,214,160,0)');
  x.fillStyle = g; x.beginPath(); x.moveTo(bx + tilt - 160, 0); x.lineTo(bx + tilt + 160, 0); x.lineTo(bx - tilt + 160, H); x.lineTo(bx - tilt - 160, H); x.closePath(); x.fill();
  x.restore();
}
function iris(l, drawA, drawB, cx, cy, d = .5) {   // Kreis öffnet sich aus dem Glasrand
  const p = cl(l / d); if (p >= 1) { drawB(); return; }
  drawA(); if (p <= 0) return;
  const e = p < .5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2, r = 40 + e * Math.hypot(W, H);
  x.save(); x.beginPath(); x.arc(cx, cy, r, 0, Math.PI * 2); x.clip(); drawB(); x.restore();
  x.save(); x.strokeStyle = `rgba(255,236,210,${.8 * (1 - p)})`; x.lineWidth = 4; x.beginPath(); x.arc(cx, cy, r, 0, Math.PI * 2); x.stroke(); x.restore();
}
const dish = i => (l, t) => {
  const d = DISH[i], A = () => i === 0 ? buffetShot(l + at(4), t) : dishImg(i - 1, l + DL, t), B = () => dishImg(i, l, t);
  if (i === 0 || i === 5) sweep(l, A, B);
  else if (d.iris) { const [cx, cy] = toScreen(I[d.im], d.z, d.fx, d.fy, d.iris[0], d.iris[1]); iris(l, A, B, cx, cy, .6); }
  else B();
  if (i === 4) zoomBlur((1 - outCubic(cl(l / .35))) * 2.6);
  if (i === 3) zoomBlur(Math.pow(cl((l - (DL - .32)) / .32), 3) * 2.6);
  // Schild bleibt stehen, nur die Angaben wechseln
  card(CARD_X(), CARD_Y(), `NO. 0${i + 1} / 06`, d.n, d.m, l, 0, { instant: true, textAt: .04, label: 'NUR FÜR DIESEN ABEND' });
};

// ---------- 4  Katalog (Break): die Seite schiebt sich ins Bild ----------
const MENU = [['01', 'Ihr erzählt.', 'Anlass, Gäste, Geschmack.'], ['02', 'Wir komponieren.', 'Euer Menü. Eure Cocktails.'], ['03', 'Ihr genießt.', 'Ein Unikat, nur für euch.']];
function catalogPage(l) {
  fill(PAPER); x.save(); x.translate(0, FEED ? 0 : 130);
  line('KEINE STANDARDKARTE', L, T0 + 60 * S, F.label(22 * S, ORANGE), .25, l);
  line('Jedes Menü', L, T0 + 200 * S, F.serif(130 * S, KI), .32, l);
  line('ein Unikat.', L, T0 + 325 * S, F.serif(130 * S, ORANGE), .4, l);
  const y0 = T0 + 420 * S, RH = 210 * S;
  MENU.forEach((r, i) => {
    const st = (i + 1) * BEAT - .05, y = y0 + i * RH;
    rule(L, y, W - L, st, l, 'rgba(15,13,11,.25)');
    line(r[0], L, y + 145 * S, F.serif(110 * S, ORANGE), st + .05, l);
    line(r[1], L + 170 * S, y + 102 * S, F.sans(fit(r[1], v => F.sans(v), 70 * S, W - 2 * L - 170 * S), KI), st + .1, l);
    line(r[2], L + 170 * S, y + 160 * S, F.body(34 * S, '#4a443e'), st + .18, l);
  });
  rule(L, y0 + 3 * RH, W - L, 3 * BEAT + .3, l, 'rgba(15,13,11,.25)');
  x.restore();
}
function catalog(l, t) {
  const p = outExpo(cl(l / .55));
  if (p < 1) { dishImg(5, l + DL, t); card(CARD_X(), CARD_Y(), 'NO. 06 / 06', DISH[5].n, DISH[5].m, 9, 0, { instant: true, label: 'NUR FÜR DIESEN ABEND' }); }
  const y = H * (1 - p);
  x.save(); x.beginPath(); x.rect(0, y, W, H); x.clip(); x.translate(0, y * .35); catalogPage(l); x.restore();
  if (p < 1) { const g = x.createLinearGradient(0, y - 40, 0, y); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,.35)'); x.fillStyle = g; x.fillRect(0, y - 40, W, 40); }
}

// ---------- 5  Drop: "Ausgestellt. Aufgegessen." 8 Schnitte auf halbe Beats ----------
const MONT = [['buffet', 1.3, .3, .62], ['glasses', 2.0, .25, .8], ['platters', 2.1, .2, .86], ['menu', 1.8, .45, .78],
  ['buffet', 2.2, .75, .9], ['glasses', 2.1, .62, .6], ['staff', 1.6, .5, .78], ['buffet', 1.9, .45, .7]];
function montage(l, t) {
  const hb = BEAT / 2, i = Math.min(7, Math.floor(l / hb)), li = l - i * hb, [n, z, fx, fy] = MONT[i];
  ph(I[n], 0, 0, W, H, { zoom: z * (1 + .14 * Math.exp(-li * 11)) * (1 + .05 * li), fx, fy, ...hh(t, 1.2) });
  fill('rgba(10,8,6,.25)'); shade(H * .35, .85);
  const cy = FEED ? H * .62 : H * .64;
  if (l < at(2)) pop('Ausgestellt.', W / 2, cy, F.serif(fit('Ausgestellt.', v => F.serif(v), 190 * S, W - 2 * L), KC), l);
  else pop('Aufgegessen.', W / 2, cy, F.sans(fit('Aufgegessen.', v => F.sans(v), 140 * S, W - 2 * L), KC), l - at(2));
}

// ---------- 6  Der Gastgeber ----------
function curator(l, t) {
  ph(I.staff, 0, 0, W, H, { zoom: (1.1 + .025 * l) * (1 + .1 * Math.exp(-l * 10)), fx: .42, fy: FEED ? .3 : .24, ...hh(t) });
  fill('rgba(10,8,6,.16)'); topShade(); shade(H * .4, .98);
  const y = FEED ? H * .78 : B0 - 40 * S;
  line('KURATIERT VON', L, y - 190 * S, F.label(24 * S, ORANGE), .1, l);
  line('Kehl Event.', L, y, F.serif(fit('Kehl Event.', v => F.serif(v), 190 * S, W - 2 * L - 60), KC), .2, l);
}

// ---------- 7  CTA: Teamfoto, Kamera zieht aus dem Bild zurück an die Wand ----------
function ctaLayout() { const fw = W * (FEED ? .34 : .46), fh = fw * 4 / 3, top = T0 + 70 * S; return { fw, fh, X: (W - fw) / 2, Y: top, cy: top + fh / 2 }; }
function cta(l, t) {
  const g = ctaLayout(), p = outExpo(cl(l / 1.3)), kS = Math.max(W / g.fw, H / g.fh) * 1.02, k = lerp(kS, 1, p);
  x.save(); cam(k, W / 2, g.cy, W / 2, lerp(H / 2, g.cy, p));
  wall(1, g.cy);
  frame(g.X, g.Y, g.fw, g.fh, k, (X, Y, w, h) => ph(I.team, X, Y, w, h, { zoom: 1.02, fx: .5, fy: .5 }));
  x.restore();
  zoomBlur((1 - outCubic(cl(l / .5))) * 2.4, W / 2, H / 2);
  const ty = g.Y + g.fh + (FEED ? 190 : 200) * S;
  line('Ihr Event.', W / 2, ty, F.serif(140 * S, KI), 1.0, l, { align: 'center' });
  line('Unser Werk.', W / 2, ty + 100 * S, F.sans(84 * S, KI), 1.0 + BEAT, l, { align: 'center' });
  if (l >= at(4)) {
    const ls = l - at(4), sc = (1 + .06 * (1 - outExpo(cl(ls / .35)))) * (1 + .03 * Math.exp(-(ls % BEAT) * 10));
    const f = F.sans(52 * S, KI), tw = measure('kehl-event.de', f), pw = tw + 100 * S, ph = 104 * S, cy = ty + 210 * S;
    x.save(); x.translate(W / 2, cy); x.scale(sc, sc); x.beginPath(); x.roundRect(-pw / 2, -ph / 2, pw, ph, ph / 2); x.fillStyle = ORANGE; x.fill();
    setFont(f); x.fillStyle = KI; x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText('kehl-event.de', 0, 4 * S); x.restore();
  }
  line('MENÜ & COCKTAILS NACH WUNSCH  ·  JETZT ANFRAGEN', W / 2, ty + (FEED ? 300 : 315) * S, F.label(20 * S, KI), at(5), l, { align: 'center', alpha: .7 });
}

// ---------- 8  Licht aus, Endkarte ----------
function endCard(l, t) {
  const off = outCubic(cl(l / .3));
  if (off < 1) { cta(l + at(8), t); fill(`rgba(8,6,5,${off})`); }
  if (l < .3) return;
  const ll = l - .3, cy = H * (FEED ? .48 : .46);
  const sp = outCubic(cl(ll / .6));                       // Spot geht auf
  const g = x.createRadialGradient(W / 2, cy - 60 * S, 0, W / 2, cy - 60 * S, H * .45);
  g.addColorStop(0, `rgba(255,238,212,${.12 * sp})`); g.addColorStop(1, 'rgba(255,238,212,0)'); x.fillStyle = g; x.fillRect(0, 0, W, H);
  const push = 1 + .012 * ll + .07 * inCubic((l - at(3)) / BEAT);
  x.save(); x.translate(W / 2, cy); x.scale(push, push); x.translate(-W / 2, -cy);
  const lp = outExpo(cl(ll / .9)), R = 112 * S, ly = cy - 190 * S + (1 - lp) * 24;
  x.save(); x.globalAlpha = lp; x.beginPath(); x.arc(W / 2, ly, R, 0, Math.PI * 2); x.clip(); x.drawImage(I.logo, 34, 32, 232, 232, W / 2 - R, ly - R, 2 * R, 2 * R); x.restore();
  x.save(); x.globalAlpha = lp * .35; x.strokeStyle = KC; x.lineWidth = 1.5; x.beginPath(); x.arc(W / 2, ly, R + 16, 0, Math.PI * 2); x.stroke(); x.restore();
  line('Kehl Event —', W / 2, cy + 95 * S, F.serif(170 * S), .15, ll, { align: 'center' });
  line('CATERING & MOBILE BARS  ·  BONN', W / 2, cy + 180 * S, F.label(23 * S), BEAT, ll, { align: 'center', alpha: .75 });
  x.restore();
}

const shots = [
  { a: 0, b: at(8), f: gallery },
  { a: at(8), b: at(12), f: buffetShot },
  ...[0, 1, 2, 3, 4, 5].map(i => ({ a: at(12 + 2 * i), b: at(14 + 2 * i), f: dish(i) })),
  { a: at(24), b: at(28), f: catalog },
  { a: at(28), b: at(32), f: montage },
  { a: at(32), b: at(36), f: curator },
  { a: at(36), b: at(44), f: cta },
  { a: at(44), b: at(48), f: endCard },
];
window.EDIT = {
  dur: at(48), loop: true, accent: ORANGE,
  assets: Object.fromEntries(['staff', 'buffet', 'platters', 'menu', 'glasses', 'team', 'logo'].map(n => [n, `img/${n}.jpg`])),
  shots,
  fx: [
    { type: 'flash', t: 0, a: .3 },
    { type: 'whip', t: at(14), w: .11 },
    { type: 'flash', t: at(28), a: .5 },
    { type: 'flash', t: at(30), a: .35 },
    { type: 'flash', t: at(32), a: .25 },
  ],
};
