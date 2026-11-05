// Kehl Event — business loop (27.5 s = 11 bars @ 96 BPM).
// Sentence loop: ends on "Kehl Event —" and cuts on the downbeat into "Die Bar kommt zu dir."
// Engine helpers (photo, line, pop, rule, shutter, F, S, L, T0, B0, W, H, ...) are globals from ../engine/engine.js
// and may only be used inside functions (this file loads first).
const BPM_ = 96, BEAT = 60 / BPM_, BARLEN = 4 * BEAT;
const WINE = '#3b1416', PLATE = '#efe6d8', ORANGE = '#e8853a';

// fit a single line into maxW by shrinking the font size
function fit(str, fontFn, maxSize, maxW) { const w = measure(str, fontFn(100)); return Math.min(maxSize, 100 * maxW / w); }

// ---------------- motion-graphic plates ----------------
function coffeePlate(X, Y, w, h, l) {
  fill(PLATE, X, Y, w, h);
  const k = h / 800, cx = X + w / 2, cy = Y + h * .6;
  x.save(); x.lineWidth = 7 * k; x.strokeStyle = INK; x.lineJoin = 'round'; x.lineCap = 'round';
  x.beginPath(); x.ellipse(cx, cy + 150 * k, 240 * k, 36 * k, 0, 0, Math.PI * 2); x.fillStyle = '#e4d8c4'; x.fill(); x.stroke();
  x.beginPath(); x.moveTo(cx - 175 * k, cy - 80 * k); x.lineTo(cx - 135 * k, cy + 105 * k);
  x.quadraticCurveTo(cx, cy + 150 * k, cx + 135 * k, cy + 105 * k); x.lineTo(cx + 175 * k, cy - 80 * k); x.closePath();
  x.fillStyle = PLATE; x.fill(); x.stroke();
  x.beginPath(); x.arc(cx + 190 * k, cy + 5 * k, 52 * k, -1.25, 1.25); x.stroke();
  x.beginPath(); x.ellipse(cx, cy - 80 * k, 175 * k, 27 * k, 0, 0, Math.PI * 2); x.fillStyle = '#5a3418'; x.fill(); x.stroke();
  x.beginPath(); x.ellipse(cx - 20 * k, cy - 84 * k, 60 * k, 8 * k, 0, 0, Math.PI * 2); x.fillStyle = 'rgba(214,160,110,.7)'; x.fill();
  const p = outExpo(cl(l / .9));
  [-60, 0, 60].forEach((bx, i) => {
    x.beginPath();
    for (let s = 0; s <= p; s += .02) {
      const yy = cy - 125 * k - s * 300 * k, xx = cx + bx * k + Math.sin(s * 7 + l * 5 + i * 2) * 24 * k * (s + .25);
      s === 0 ? x.moveTo(xx, yy) : x.lineTo(xx, yy);
    }
    x.globalAlpha = .55; x.lineWidth = 6 * k; x.stroke(); x.globalAlpha = 1;
  });
  x.restore();
}
function glassPlate(X, Y, w, h, l) {
  fill(WINE, X, Y, w, h);
  const k = h / 800, cx = X + w / 2, ty = Y + h * .2, bot = ty + 330 * k;
  const bowl = () => { x.beginPath(); x.moveTo(cx - 150 * k, ty); x.bezierCurveTo(cx - 195 * k, ty + 180 * k, cx - 120 * k, bot, cx, bot); x.bezierCurveTo(cx + 120 * k, bot, cx + 195 * k, ty + 180 * k, cx + 150 * k, ty); };
  const p = outCubic(l / 1.0), level = bot - 250 * k * p;
  x.save(); bowl(); x.closePath(); x.clip();
  const g = x.createLinearGradient(0, level, 0, bot); g.addColorStop(0, '#ff9a3c'); g.addColorStop(1, '#e8471c'); x.fillStyle = g;
  x.beginPath(); x.moveTo(cx - 220 * k, bot + 10);
  for (let xx = -220; xx <= 220; xx += 8) x.lineTo(cx + xx * k, level + Math.sin(xx * .05 + l * 9) * (3 + 7 * (1 - p)) * k);
  x.lineTo(cx + 220 * k, bot + 10); x.closePath(); x.fill();
  for (let i = 0; i < 14; i++) {
    const span = Math.max(1, (bot - level)), yy = bot - ((l * 140 * k + i * 41 * k) % span), xx = cx + Math.sin(i * 12.9) * 95 * k;
    x.beginPath(); x.arc(xx, yy, (3 + (i % 3) * 2) * k, 0, Math.PI * 2); x.fillStyle = 'rgba(255,240,220,.55)'; x.fill();
  }
  x.restore();
  x.save(); x.strokeStyle = CREAM; x.lineWidth = 6 * k; x.lineCap = 'round';
  bowl(); x.stroke();
  x.beginPath(); x.moveTo(cx, bot); x.lineTo(cx, ty + 520 * k); x.stroke();
  x.beginPath(); x.ellipse(cx, ty + 522 * k, 110 * k, 16 * k, 0, 0, Math.PI * 2); x.stroke();
  const sp = outExpo(prog(l, .45, .6));                      // orange slice drops onto the rim
  if (sp > 0) {
    const ox = cx + 125 * k, oy = ty - 10 * k - (1 - sp) * 160 * k;
    x.beginPath(); x.arc(ox, oy, 62 * k, 0, Math.PI * 2); x.fillStyle = '#ffb347'; x.fill(); x.stroke();
    x.lineWidth = 3 * k; for (let a = 0; a < 8; a++) { x.beginPath(); x.moveTo(ox, oy); x.lineTo(ox + Math.cos(a * Math.PI / 4) * 54 * k, oy + Math.sin(a * Math.PI / 4) * 54 * k); x.stroke(); }
  }
  x.restore();
}
function ginPlate(X, Y, w, h, l) {
  fill(ORANGE, X, Y, w, h);
  const cx = X + w / 2, cy = Y + h / 2, r = Math.min(w, h) * .3;
  circleImg(I.gin, cx, cy, r, 'contrast(1.12) brightness(1.02)');
  x.save(); x.strokeStyle = INK; x.lineWidth = 2; x.beginPath(); x.arc(cx, cy, r + 18 * S, 0, Math.PI * 2); x.stroke(); x.restore();
  ringText("KEHL'S GIN · GERMAN DRY GIN · KEHL'S GIN · GERMAN DRY GIN · ", cx, cy, r + 58 * S, -Math.PI / 2 + l * .45, F.label(25 * S, INK));
}

// ---------------- shots ----------------
function hook(l) {
  const y1 = FEED ? 540 : 770;
  line('MOBILE BARS & CATERING  ·  RHEINLAND', L, T0 + 40 * S, F.label(24 * S, ACC), 0, l, { instant: true });
  pop('Die Bar', L, y1, F.sans(200 * S), l, { align: 'left', baseline: 'alphabetic' });
  if (l >= BEAT) pop('kommt', L, y1 + 195 * S, F.sans(200 * S), l - BEAT, { align: 'left', baseline: 'alphabetic' });
  if (l >= 2 * BEAT) pop('zu dir.', L, y1 + 425 * S, F.serif(255 * S, ACC), l - 2 * BEAT, { align: 'left', baseline: 'alphabetic' });
}
function container(l, t) {
  const Y = T0 + 110 * S, h = FEED ? 520 : 660;
  line('THE BAR CONTAINER', L, T0 + 40 * S, F.label(24 * S, ACC), 0, l, { d: .5 });
  shutter(0, Y, W, h, 0, l, () => photo(I.container, 0, Y, W, h, { zoom: 1.04 + l * .02, ...hh(t, .5) }), .7);
  const y = Y + h + 140 * S;
  line('Aufklappen.', L, y, F.sans(96 * S), 1 * BEAT - .05, l, { d: .55 });
  line('Ausschenken.', L, y + 118 * S, F.sans(96 * S), 2 * BEAT - .05, l, { d: .55 });
  line('Anstoßen.', L, y + 245 * S, F.serif(128 * S, ACC), 3 * BEAT - .05, l, { d: .55 });
}
const K_INK = '#0f0d0b', K_CREAM = '#f3ede4';
const OCC = [['Firmenfeier.', ORANGE, K_INK, 'sans'], ['Hochzeit.', PLATE, K_INK, 'serif'], ['Geburtstag.', K_INK, K_CREAM, 'sans'], ['Messe.', WINE, K_CREAM, 'serif']];
const occasion = i => (l) => {
  const [word, bg, fg, style] = OCC[i];
  fill(bg);
  const cy = H * .5;
  setFont(F.label(24 * S)); x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillStyle = fg; x.globalAlpha = .7; x.fillText('FÜR JEDEN ANLASS', W / 2, cy - 200 * S); x.globalAlpha = 1;
  pop(word, W / 2, cy, style === 'serif' ? F.serif(185 * S, fg) : F.sans(132 * S, fg), l);
  setFont(F.label(22 * S)); x.textAlign = 'center'; x.fillStyle = fg; x.globalAlpha = .7; x.fillText(`0${i + 1} — 04`, W / 2, cy + 160 * S); x.globalAlpha = 1;
};
const SERV = [
  { n: 'Mobile Bars', sub: 'INKL. BAR-CONTAINER', plate: (X, Y, w, h, l, t) => photo(I.container, X, Y, w, h, { zoom: 1.2 + l * .05, fx: .45, fy: .45, ...hh(t, .6) }) },
  { n: 'Cocktail-Catering', sub: 'COCKTAILS & LONGDRINKS', plate: (X, Y, w, h, l, t) => photo(I.shelf, X, Y, w, h, { zoom: 1.04 + l * .05, fx: .55, fy: .4, ...hh(t, .6) }) },
  { n: 'Barista-Catering', sub: 'KAFFEESPEZIALITÄTEN VOR ORT', plate: (X, Y, w, h, l) => coffeePlate(X, Y, w, h, l) },
  { n: 'Food & BBQ', sub: 'CATERING FÜR FIRMENFEIERN', plate: (X, Y, w, h, l, t) => photo(I.food, X, Y, w, h, { zoom: 1.04 + l * .05, fx: .45, fy: .55, ...hh(t, .6) }) },
  { n: 'Cocktail-Workshops', sub: 'SELBST MIXEN, GEMEINSAM FEIERN', plate: (X, Y, w, h, l) => glassPlate(X, Y, w, h, l) },
  { n: "Kehl's Gin", sub: 'UNSER GERMAN DRY GIN', plate: (X, Y, w, h, l) => ginPlate(X, Y, w, h, l) },
];
const service = i => (l, t) => {
  const s = SERV[i], Y = FEED ? T0 + 100 * S : 0, h = FEED ? 780 : 1130;
  const ly = FEED ? T0 + 40 * S : h + 82;                       // reel: image bleeds from the top, labels sit under it
  s.plate(0, Y, W, h, l, t);
  if (!FEED) topShade();
  line('WAS WIR MITBRINGEN', L, ly, F.label(24 * S, ACC), 0, l, { instant: i > 0, d: .5 });
  line(`0${i + 1} / 06`, W - L, ly, F.label(24 * S), 0, l, { instant: true, align: 'right', alpha: .7 });
  const sz = fit(s.n, v => F.sans(v), 104 * S, W - 2 * L - 90);
  const ny = FEED ? Y + h + 150 * S : h + 212;
  line(s.n, L, ny, F.sans(sz), .03, l, { d: .55 });
  line(s.sub, L, ny + 78 * S, F.label(23 * S), .12, l, { d: .55, alpha: .75 });
};
const STEPS = [['01', 'Anfragen', 'Datum, Ort & Gästezahl.'], ['02', 'Planen', 'Bar, Drinks & Food nach Wunsch.'], ['03', 'Feiern', 'Wir schenken aus. Ihr genießt.']];
function steps(l) {
  x.save(); x.translate(0, -l * 6 * S + (FEED ? 60 : 110));
  line("SO EINFACH GEHT'S", L, T0 + 40 * S, F.label(24 * S, ACC), .02, l);
  line('In drei Schritten.', L, T0 + 210 * S, F.serif(150 * S), .1, l);
  const y0 = T0 + 300 * S, RH = 230 * S;
  STEPS.forEach((r, i) => {
    const st = (i + 1) * BEAT - .1, y = y0 + i * RH;
    rule(L, y, W - L, st, l);
    line(r[0], L, y + 150 * S, F.serif(118 * S, ACC), st + .05, l);
    line(r[1], L + 175 * S, y + 108 * S, F.sans(78 * S), st + .1, l);
    line(r[2], L + 175 * S, y + 170 * S, F.body(36 * S, 'rgba(243,237,228,.72)'), st + .18, l);
  });
  rule(L, y0 + 3 * RH, W - L, 3 * BEAT + .3, l);
  x.restore();
}
function vibe(l, t) {
  const h = FEED ? 720 : 1080;
  photo(I.party, 0, 0, W, h, { zoom: 1.12 - l * .03, fx: .5, fy: .55, grade: GRADE + ' blur(0.8px)', ...hh(t, 1.1) });
  topShade();
  line('FIRMENFEIERN  ·  HOCHZEITEN  ·  EVENTS', L, h + 95 * S, F.label(23 * S, ACC), .05, l);
  line('Ihr feiert.', L, h + 245 * S, F.serif(160 * S), .15, l);
  line('Wir machen die Bar.', L, h + 352 * S, F.sans(76 * S), .3, l);
}
function cta(l, t) {
  x.save(); x.globalAlpha = .3; photo(I.container, 0, 0, W, H, { zoom: 1.3, grade: GRADE + ' blur(14px) brightness(.6)' }); x.restore();
  fill('rgba(15,13,11,.72)');
  const Y0 = T0 + (FEED ? 160 : 200) * S;
  line('DEIN EVENT IM RHEINLAND', L, Y0, F.label(24 * S, ACC), .02, l);
  line('Deine Feier.', L, Y0 + 200 * S, F.serif(195 * S), .12, l);
  line('Unsere Bar.', L, Y0 + 355 * S, F.sans(150 * S), .28, l);
  rule(L, Y0 + 430 * S, L + 120 * S, 2 * BEAT - .1, l, ACC, 3);
  line('Jetzt unverbindlich anfragen:', L, Y0 + 520 * S, F.body(44 * S), 2 * BEAT, l);
  if (l >= 3 * BEAT) {
    const ls = l - 3 * BEAT, beatPhase = ls % BEAT;
    const sc = (1 + .06 * (1 - outExpo(cl(ls / .35)))) * (1 + .03 * Math.exp(-beatPhase * 10));
    const f = F.sans(60 * S, INK), tw = measure('kehl-event.de', f), pw = tw + 110 * S, ph = 124 * S, cy = Y0 + 660 * S;
    x.save(); x.translate(L + pw / 2, cy); x.scale(sc, sc);
    x.beginPath(); x.roundRect(-pw / 2, -ph / 2, pw, ph, ph / 2); x.fillStyle = ACC; x.fill();
    setFont(f); x.fillStyle = INK; x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText('kehl-event.de', 0, 4 * S); x.restore();
  }
  line('@KEHL_EVENT  ·  LINK IM PROFIL', L, Y0 + 830 * S, F.label(24 * S), 5 * BEAT, l, { alpha: .75 });
}
function endCard(l) {
  const cy = H * (FEED ? .48 : .46);
  const push = 1 + .012 * l + .07 * inCubic((l - 3 * BEAT) / BEAT);   // accelerates into the loop cut
  x.save(); x.translate(W / 2, cy); x.scale(push, push); x.translate(-W / 2, -cy);
  const lp = outExpo(cl(l / .9)), R = 112 * S, ly = cy - 190 * S + (1 - lp) * 24;
  x.save(); x.globalAlpha = lp; x.beginPath(); x.arc(W / 2, ly, R, 0, Math.PI * 2); x.clip(); x.drawImage(I.logo, 34, 32, 232, 232, W / 2 - R, ly - R, 2 * R, 2 * R); x.restore();
  x.save(); x.globalAlpha = lp * .35; x.strokeStyle = CREAM; x.lineWidth = 1.5; x.beginPath(); x.arc(W / 2, ly, R + 16, 0, Math.PI * 2); x.stroke(); x.restore();
  line('Kehl Event —', W / 2, cy + 95 * S, F.serif(170 * S), .15, l, { align: 'center' });
  line('MOBILE BARS & CATERING  ·  BONN', W / 2, cy + 180 * S, F.label(23 * S), BEAT, l, { align: 'center', alpha: .75 });
  x.restore();
}

const at = b => b * BEAT;
const shots = [
  { a: 0, b: at(3), f: hook },
  { a: at(3), b: at(8), f: container },
  ...[0, 1, 2, 3].map(i => ({ a: at(8 + i), b: at(9 + i), f: occasion(i) })),
  ...[0, 1, 2, 3, 4, 5].map(i => ({ a: at(12 + 2 * i), b: at(14 + 2 * i), f: service(i) })),
  { a: at(24), b: at(28), f: steps },
  { a: at(28), b: at(32), f: vibe },
  { a: at(32), b: at(40), f: cta },
  { a: at(40), b: at(44), f: endCard },
];
window.EDIT = {
  dur: at(44), loop: true, accent: ORANGE,
  assets: { container: 'img/container.jpg', shelf: 'img/shelf.jpg', food: 'img/food.jpg', party: 'img/party.jpg', gin: 'img/gin.jpg', logo: 'img/logo.jpg' },
  shots,
  fx: [
    { type: 'flash', t: 0, a: .35 },
    { type: 'leak', t: at(12) },
    ...[14, 16, 18, 20, 22].map(b => ({ type: 'whip', t: at(b), w: .1 })),
    { type: 'flash', t: at(28), a: .45 },
    { type: 'leak', t: at(32) },
  ],
};
