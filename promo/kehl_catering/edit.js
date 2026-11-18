// Kehl Event — Catering-Recap aus dem August-Macke-Haus Bonn (27.5 s = 11 bars @ 96 BPM, Loop).
// Satz-Loop: Endkarte "Kehl Event —" schneidet auf die Eins in "Catering im Museum."
// Fakten nur aus dem Material: Speisekarte (Roggenschnittchen, Gläschen, Dessert) und Location-Tag August-Macke-Haus.
// Engine-Helfer sind Globals aus ../engine/engine.js und nur innerhalb von Funktionen benutzbar.
const BPM_ = 96, BEAT = 60 / BPM_;
const WINE = '#3b1416', PLATE = '#efe6d8', ORANGE = '#e8853a', K_INK = '#0f0d0b', K_CREAM = '#f3ede4';

function fit(str, fontFn, maxSize, maxW) { const w = measure(str, fontFn(100)); return Math.min(maxSize, 100 * maxW / w); }

// ---------------- Einstellungen ----------------
function hook(l, t) {
  // Mitarbeiter mit Daumen hoch über dem Text, Platte darunter
  photo(I.staff, 0, 0, W, H, { zoom: 1.1 + l * .03, fx: .42, fy: FEED ? .3 : .22, ...hh(t) });
  fill('rgba(10,8,6,.18)'); topShade(); shade(H * .44, .94);
  const y1 = FEED ? 860 : 1100;
  line('KEHL EVENT  ·  AUGUST-MACKE-HAUS BONN', L, T0 + 40 * S, F.label(24 * S, ACC), 0, l, { instant: true });
  pop('Catering', L, y1, F.sans(170 * S), l, { align: 'left', baseline: 'alphabetic' });
  if (l >= BEAT) pop('im', L, y1 + 165 * S, F.sans(170 * S), l - BEAT, { align: 'left', baseline: 'alphabetic' });
  if (l >= 2 * BEAT) pop('Museum.', L, y1 + 360 * S, F.serif(215 * S, ACC), l - 2 * BEAT, { align: 'left', baseline: 'alphabetic' });
}
function buffet(l, t) {
  const Y = T0 + 110 * S, h = FEED ? 520 : 660;
  line('DAS BUFFET', L, T0 + 40 * S, F.label(24 * S, ACC), 0, l, { d: .5 });
  // Tilt von der Decke runter aufs Buffet
  shutter(0, Y, W, h, 0, l, () => photo(I.buffet, 0, Y, W, h, { zoom: 1.12 + l * .02, fx: .45, fy: .5 + l * .035, ...hh(t, .5) }), .7);
  const y = Y + h + 140 * S;
  line('Anrichten.', L, y, F.sans(96 * S), 1 * BEAT - .05, l, { d: .55 });
  line('Servieren.', L, y + 118 * S, F.sans(96 * S), 2 * BEAT - .05, l, { d: .55 });
  line('Genießen.', L, y + 245 * S, F.serif(128 * S, ACC), 3 * BEAT - .05, l, { d: .55 });
}
const WORDS = [['Herzhaft.', ORANGE, K_INK, 'sans'], ['Frisch.', PLATE, K_INK, 'serif'], ['Im Glas.', K_INK, K_CREAM, 'sans'], ['Süß.', WINE, K_CREAM, 'serif']];
const word = i => (l) => {
  const [wd, bg, fg, style] = WORDS[i]; fill(bg);
  const cy = H * .5;
  setFont(F.label(24 * S)); x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillStyle = fg; x.globalAlpha = .7; x.fillText('AUF DEM BUFFET', W / 2, cy - 200 * S); x.globalAlpha = 1;
  pop(wd, W / 2, cy, style === 'serif' ? F.serif(185 * S, fg) : F.sans(132 * S, fg), l);
  setFont(F.label(22 * S)); x.textAlign = 'center'; x.fillStyle = fg; x.globalAlpha = .7; x.fillText(`0${i + 1} — 04`, W / 2, cy + 160 * S); x.globalAlpha = 1;
};
// Gerichte von der Speisekarte, jedes mit eigenem Ausschnitt
const DISH = [
  { n: 'Roggenschnittchen', sub: 'BRIE  ·  PFEFFERSALAMI  ·  LEBERWURST', im: 'platters', z: 1.45, fx: .22, fy: .8 },
  { n: 'Partyfrikadelle', sub: 'IN SWEET-CHILI-DIP', im: 'glasses', z: 1.5, fx: .2, fy: .8 },
  { n: 'Kartoffelsalat', sub: 'IN ESSIG & ÖL', im: 'menu', z: 1.35, fx: .32, fy: .8 },
  { n: 'Süßkartoffelsalat', sub: 'MIT AHORNSIRUP', im: 'glasses', z: 1.7, fx: .58, fy: .6 },
  { n: 'Obstsalat', sub: 'IN HONIG MARINIERT', im: 'buffet', z: 1.5, fx: .42, fy: .7 },
  { n: 'Mousse au chocolat', sub: 'MIT CHILIFÄDEN', im: 'buffet', z: 1.75, fx: .74, fy: .9 },
];
const dish = i => (l, t) => {
  const s = DISH[i], Y = FEED ? T0 + 100 * S : 0, h = FEED ? 780 : 1130;
  const ly = FEED ? T0 + 40 * S : h + 82;
  photo(I[s.im], 0, Y, W, h, { zoom: s.z + l * .05, fx: s.fx, fy: s.fy, ...hh(t, .6) });
  if (!FEED) topShade();
  line('AUF DER KARTE', L, ly, F.label(24 * S, ACC), 0, l, { instant: i > 0, d: .5 });
  line(`0${i + 1} / 06`, W - L, ly, F.label(24 * S), 0, l, { instant: true, align: 'right', alpha: .7 });
  const sz = fit(s.n, v => F.sans(v), 104 * S, W - 2 * L - 90);
  const ny = FEED ? Y + h + 150 * S : h + 212;
  line(s.n, L, ny, F.sans(sz), .03, l, { d: .55 });
  line(s.sub, L, ny + 78 * S, F.label(23 * S), .12, l, { d: .55, alpha: .75 });
};
const MENU = [['01', 'Schnittchen', 'Roggenbrot mit Brie, Salami & mehr.'], ['02', 'Gläschen', 'Salate, Frikadellen, Lachs-Röllchen.'], ['03', 'Dessert', 'Obstsalat & Mousse au chocolat.']];
function menuCard(l) {
  x.save(); x.translate(0, -l * 6 * S + (FEED ? 60 : 110));
  line('DIE KARTE DES ABENDS', L, T0 + 40 * S, F.label(24 * S, ACC), .02, l);
  line('Für jeden was.', L, T0 + 210 * S, F.serif(150 * S), .1, l);
  const y0 = T0 + 300 * S, RH = 230 * S;
  MENU.forEach((r, i) => {
    const st = (i + 1) * BEAT - .1, y = y0 + i * RH;
    rule(L, y, W - L, st, l);
    line(r[0], L, y + 150 * S, F.serif(118 * S, ACC), st + .05, l);
    line(r[1], L + 175 * S, y + 108 * S, F.sans(78 * S), st + .1, l);
    line(r[2], L + 175 * S, y + 170 * S, F.body(36 * S, 'rgba(243,237,228,.72)'), st + .18, l);
  });
  rule(L, y0 + 3 * RH, W - L, 3 * BEAT + .3, l);
  x.restore();
}
// 4 randlose Schnitte auf dem Beat, Text bleibt stehen
const VIBE = [['buffet', 1.06, .35, .78], ['platters', 1.35, .2, .7], ['glasses', 1.12, .45, .8], ['menu', 1.1, .4, .75]];
function vibe(l, t) {
  const i = Math.min(3, Math.floor(l / BEAT)), li = l - i * BEAT, [n, z0, fx, fy] = VIBE[i];
  let z = z0 + li * .06; if (i === 0) z *= 1 + .12 * Math.exp(-li * 10);
  photo(I[n], 0, 0, W, H, { zoom: z, fx, fy, ...hh(t, 1.1) });
  topShade(); shade(H * .36, .92);
  const y2 = B0 - 30 * S, y1 = y2 - 120 * S, yl = y1 - 178 * S;
  line('CATERING  ·  BARS  ·  EVENTS', L, yl, F.label(23 * S, ACC), .05, l);
  line('Ihr feiert.', L, y1, F.serif(175 * S), .12, l);
  line('Wir machen das Buffet.', L, y2, F.sans(fit('Wir machen das Buffet.', v => F.sans(v), 78 * S, W - 2 * L - 60)), .26, l);
}
function cta(l, t) {
  const ph = FEED ? 420 : 760, pb = ph;
  shutter(0, 0, W, ph, 0, l, () => photo(I.team, 0, 0, W, ph, { zoom: 1.04 + l * .015, fx: .5, fy: .5, ...hh(t, .5) }), .7);
  line('CATERING IM RHEINLAND', L, pb + 75 * S, F.label(24 * S, ACC), .05, l);
  line('Dein Event.', L, pb + 250 * S, F.serif(180 * S), .15, l);
  line('Unser Buffet.', L, pb + 380 * S, F.sans(140 * S), .3, l);
  line('JETZT UNVERBINDLICH ANFRAGEN', L, pb + 455 * S, F.label(22 * S), 2 * BEAT, l, { alpha: .8 });
  if (l >= 3 * BEAT) {
    const ls = l - 3 * BEAT, beatPhase = ls % BEAT;
    const sc = (1 + .06 * (1 - outExpo(cl(ls / .35)))) * (1 + .03 * Math.exp(-beatPhase * 10));
    const f = F.sans(58 * S, K_INK), tw = measure('kehl-event.de', f), pw = tw + 110 * S, phh = 116 * S, cy = pb + 545 * S;
    x.save(); x.translate(L + pw / 2, cy); x.scale(sc, sc);
    x.beginPath(); x.roundRect(-pw / 2, -phh / 2, pw, phh, phh / 2); x.fillStyle = ACC; x.fill();
    setFont(f); x.fillStyle = K_INK; x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText('kehl-event.de', 0, 4 * S); x.restore();
  }
  line('@KEHL_EVENT  ·  LINK IM PROFIL', L, pb + 665 * S, F.label(23 * S), 5 * BEAT, l, { alpha: .75 });
}
function endCard(l) {
  const cy = H * (FEED ? .48 : .46);
  const push = 1 + .012 * l + .07 * inCubic((l - 3 * BEAT) / BEAT);
  x.save(); x.translate(W / 2, cy); x.scale(push, push); x.translate(-W / 2, -cy);
  const lp = outExpo(cl(l / .9)), R = 112 * S, ly = cy - 190 * S + (1 - lp) * 24;
  x.save(); x.globalAlpha = lp; x.beginPath(); x.arc(W / 2, ly, R, 0, Math.PI * 2); x.clip(); x.drawImage(I.logo, 34, 32, 232, 232, W / 2 - R, ly - R, 2 * R, 2 * R); x.restore();
  x.save(); x.globalAlpha = lp * .35; x.strokeStyle = CREAM; x.lineWidth = 1.5; x.beginPath(); x.arc(W / 2, ly, R + 16, 0, Math.PI * 2); x.stroke(); x.restore();
  line('Kehl Event —', W / 2, cy + 95 * S, F.serif(170 * S), .15, l, { align: 'center' });
  line('CATERING & MOBILE BARS  ·  BONN', W / 2, cy + 180 * S, F.label(23 * S), BEAT, l, { align: 'center', alpha: .75 });
  x.restore();
}

const at = b => b * BEAT;
const shots = [
  { a: 0, b: at(3), f: hook },
  { a: at(3), b: at(8), f: buffet },
  ...[0, 1, 2, 3].map(i => ({ a: at(8 + i), b: at(9 + i), f: word(i) })),
  ...[0, 1, 2, 3, 4, 5].map(i => ({ a: at(12 + 2 * i), b: at(14 + 2 * i), f: dish(i) })),
  { a: at(24), b: at(28), f: menuCard },
  { a: at(28), b: at(32), f: vibe },
  { a: at(32), b: at(40), f: cta },
  { a: at(40), b: at(44), f: endCard },
];
window.EDIT = {
  dur: at(44), loop: true, accent: ORANGE,
  assets: Object.fromEntries(['staff', 'buffet', 'platters', 'menu', 'glasses', 'team', 'logo'].map(n => [n, `img/${n}.jpg`])),
  shots,
  fx: [
    { type: 'flash', t: 0, a: .35 },
    { type: 'leak', t: at(12) },
    ...[14, 16, 18, 20, 22].map(b => ({ type: 'whip', t: at(b), w: .1 })),
    { type: 'flash', t: at(28), a: .45 },
    { type: 'leak', t: at(32) },
  ],
};
