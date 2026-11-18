// Le Shop (Concept Store, Bonn-Poppelsdorf) — Pitch-Demo, Business-Loop 27.5 s = 11 bars @ 96 BPM.
// Kein Fotomaterial verfügbar -> alles als Motion-Graphic in Markenpalette (Strichgrafik, Papier, Salbei).
// Fakten nur aus öffentlichen Quellen: Concept Store, neu seit Anfang September 2026, dritter Le Shop,
// Clemens-August-Str. 39, ca. 90 m², kuratiertes Sortiment, nachhaltige & hochwertige Ware, persönliche Beratung.
// Satz-Loop: Endkarte "Le Shop —" schneidet auf die Eins in "Neu in Poppelsdorf."
const BPM_ = 96, BEAT = 60 / BPM_;
const PAPER = '#efe7da', SAGE = '#a9b78f', FOREST = '#1d2620', CLAY = '#c9876a', DARK = '#0f0d0b', LIGHT = '#f3ede4';

function fit(str, fontFn, maxSize, maxW) { const w = measure(str, fontFn(100)); return Math.min(maxSize, 100 * maxW / w); }
const swing = (t, a = .12, f = 1.6, ph = 0) => Math.sin(t * f + ph) * a;

// ---------------- Strichgrafiken ----------------
// Kleiderbügel: (hx, hy) = Haken-Oberkante, s = Breite in px
function hanger(hx, hy, s, ang, col, lw) {
  x.save(); x.translate(hx, hy); x.rotate(ang); x.strokeStyle = col; x.lineWidth = lw; x.lineCap = 'round'; x.lineJoin = 'round';
  const k = s / 300;
  x.beginPath(); x.arc(0, 22 * k, 22 * k, Math.PI * 1.05, Math.PI * 2.35); x.stroke();     // Haken
  x.beginPath(); x.moveTo(Math.cos(Math.PI * 2.35) * 22 * k, 22 * k + Math.sin(Math.PI * 2.35) * 22 * k);
  x.lineTo(0, 70 * k); x.stroke();                                                           // Hals
  x.beginPath(); x.moveTo(0, 70 * k); x.quadraticCurveTo(-60 * k, 100 * k, -150 * k, 168 * k);
  x.quadraticCurveTo(-158 * k, 178 * k, -140 * k, 180 * k); x.lineTo(140 * k, 180 * k);
  x.quadraticCurveTo(158 * k, 178 * k, 150 * k, 168 * k); x.quadraticCurveTo(60 * k, 100 * k, 0, 70 * k); x.stroke();
  x.restore();
}
// Kleidungsstück am Bügel (einfacher Umriss), Farbe gefüllt
function garment(hx, hy, s, ang, fillC, col, lw, kind) {
  x.save(); x.translate(hx, hy); x.rotate(ang); const k = s / 300;
  x.beginPath();
  if (kind === 'dress') {
    x.moveTo(-70 * k, 120 * k); x.lineTo(-40 * k, 95 * k); x.lineTo(40 * k, 95 * k); x.lineTo(70 * k, 120 * k);
    x.lineTo(60 * k, 230 * k); x.lineTo(130 * k, 470 * k); x.lineTo(-130 * k, 470 * k); x.lineTo(-60 * k, 230 * k); x.closePath();
  } else {
    x.moveTo(-40 * k, 95 * k); x.lineTo(40 * k, 95 * k); x.lineTo(150 * k, 170 * k); x.lineTo(205 * k, 300 * k); x.lineTo(160 * k, 318 * k);
    x.lineTo(118 * k, 230 * k); x.lineTo(118 * k, 420 * k); x.lineTo(-118 * k, 420 * k); x.lineTo(-118 * k, 230 * k);
    x.lineTo(-160 * k, 318 * k); x.lineTo(-205 * k, 300 * k); x.lineTo(-150 * k, 170 * k); x.closePath();
  }
  x.fillStyle = fillC; x.fill(); x.strokeStyle = col; x.lineWidth = lw; x.lineJoin = 'round'; x.stroke();
  x.beginPath(); x.moveTo(-40 * k, 95 * k); x.quadraticCurveTo(0, 135 * k, 40 * k, 95 * k); x.stroke();   // Ausschnitt
  x.restore();
  hanger(hx, hy, s, ang, col, lw);
}

// Schaufenster-Fassade
function storefront(X, Y, w, h, l, t) {
  fill(PAPER, X, Y, w, h);
  const k = h / 800, lw = 5 * k, cx = X + w / 2, fw = 760 * k, fx = cx - fw / 2, top = Y + 95 * k, bot = Y + h - 40 * k;
  x.save(); x.strokeStyle = DARK; x.lineWidth = lw; x.lineJoin = 'round'; x.lineCap = 'round';
  x.strokeRect(fx, top, fw, bot - top);                                                       // Fassade
  // Schild
  const sy = top + 30 * k; x.fillStyle = FOREST; x.fillRect(fx + 60 * k, sy, fw - 120 * k, 92 * k);
  setFont(F.serif(78 * k, LIGHT)); x.fillStyle = LIGHT; x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText('Le Shop', cx, sy + 50 * k);
  // Markise mit Streifen + Bogenkante, fährt aus
  const ay = sy + 120 * k, ap = outExpo(prog(l, .15, .7)), ah = 70 * k * ap, n = 10, sw = fw / n;
  for (let i = 0; i < n; i++) { x.fillStyle = i % 2 ? PAPER : SAGE; x.fillRect(fx + i * sw, ay, sw, ah); }
  x.beginPath(); for (let i = 0; i < n; i++) x.arc(fx + (i + .5) * sw, ay + ah, sw / 2, 0, Math.PI); x.fillStyle = SAGE; x.fill();
  x.strokeRect(fx, ay, fw, ah);
  // Schaufenster
  const wy = ay + 120 * k, ww = 470 * k, wh = bot - wy - 30 * k, wx = fx + 40 * k;
  x.fillStyle = '#e3dccd'; x.fillRect(wx, wy, ww, wh); x.strokeRect(wx, wy, ww, wh);
  x.beginPath(); x.moveTo(wx + 25 * k, wy + 55 * k); x.lineTo(wx + ww - 25 * k, wy + 55 * k); x.stroke();   // Stange
  [['shirt', CLAY], ['dress', SAGE], ['shirt', FOREST]].forEach(([kind, c], i) => {
    const gx = wx + ww * (.22 + i * .28);
    garment(gx, wy + 30 * k, 175 * k, swing(t, .05, 1.3, i * 1.7), c, DARK, lw * .8, kind);
  });
  // Spiegelung
  x.save(); x.globalAlpha = .35; x.fillStyle = '#fff'; x.beginPath(); x.moveTo(wx + ww * .62, wy); x.lineTo(wx + ww * .78, wy); x.lineTo(wx + ww * .48, wy + wh); x.lineTo(wx + ww * .32, wy + wh); x.fill(); x.restore();
  // Tür + Hausnummer
  const dx = wx + ww + 45 * k, dw = fx + fw - 40 * k - dx;
  x.fillStyle = FOREST; x.fillRect(dx, wy, dw, bot - wy); x.strokeRect(dx, wy, dw, bot - wy);
  x.beginPath(); x.arc(dx + dw * .8, wy + (bot - wy) * .55, 7 * k, 0, Math.PI * 2); x.fillStyle = SAGE; x.fill();
  setFont(F.sans(46 * k, LIGHT)); x.fillStyle = LIGHT; x.textAlign = 'center'; x.fillText('39', dx + dw / 2, wy + 60 * k);
  // Gehweg
  x.beginPath(); x.moveTo(X, bot); x.lineTo(X + w, bot); x.stroke();
  x.restore();
}

// Plate 1: Kleiderstange mit kuratierter Auswahl
function railPlate(X, Y, w, h, l, t) {
  fill(PAPER, X, Y, w, h);
  const k = h / 800, ry = Y + 170 * k, lw = 5 * k;
  x.save(); x.strokeStyle = DARK; x.lineWidth = lw; x.lineCap = 'round';
  x.beginPath(); x.moveTo(X + 40 * k, ry); x.lineTo(X + w - 40 * k, ry); x.stroke();
  x.beginPath(); x.moveTo(X + 80 * k, ry); x.lineTo(X + 80 * k, Y + h); x.moveTo(X + w - 80 * k, ry); x.lineTo(X + w - 80 * k, Y + h); x.stroke();
  x.restore();
  const items = [['shirt', SAGE], ['dress', CLAY], ['shirt', LIGHT], ['dress', FOREST], ['shirt', CLAY]];
  // Teile gleiten nacheinander auf die Stange (Beat-Raster)
  items.forEach(([kind, c], i) => {
    const st = i * BEAT * .5, p = outExpo(prog(l, st, .6)); if (p <= 0) return;
    const gx = X + w * (.15 + i * .175) + (1 - p) * w * .5;
    garment(gx, ry - 18 * k, 230 * k, swing(t, .06 * (1 - p) + .025, 1.4, i) - (1 - p) * .25, c, DARK, lw * .8, kind);
  });
}
// Plate 2: Etikett mit Blatt (nachhaltig & hochwertig)
function tagPlate(X, Y, w, h, l, t) {
  fill(FOREST, X, Y, w, h);
  const k = h / 800, cx = X + w / 2, cy = Y + h * .5, p = outExpo(prog(l, 0, .8)), ang = swing(t, .08, 1.5) + (1 - p) * -.4;
  x.save(); x.translate(cx, Y + 90 * k); x.rotate(ang);
  // Faden
  x.strokeStyle = LIGHT; x.lineWidth = 3 * k; x.beginPath(); x.moveTo(0, 0); x.bezierCurveTo(-40 * k, 60 * k, 30 * k, 100 * k, 0, 150 * k); x.stroke();
  // Etikett
  const tw = 330 * k, th = 480 * k, ty = 150 * k;
  x.beginPath(); x.moveTo(0, ty); x.lineTo(tw / 2, ty + 90 * k); x.lineTo(tw / 2, ty + th); x.lineTo(-tw / 2, ty + th); x.lineTo(-tw / 2, ty + 90 * k); x.closePath();
  x.fillStyle = PAPER; x.fill(); x.strokeStyle = DARK; x.lineWidth = 4 * k; x.stroke();
  x.beginPath(); x.arc(0, ty + 70 * k, 16 * k, 0, Math.PI * 2); x.fillStyle = FOREST; x.fill(); x.stroke();
  // Blatt, wächst
  const g = outCubic(prog(l, .35, .9)), ly = ty + 290 * k;
  x.save(); x.translate(0, ly); x.rotate(-.5); x.scale(g, g);
  x.beginPath(); x.moveTo(0, 95 * k); x.bezierCurveTo(-95 * k, 30 * k, -70 * k, -80 * k, 0, -120 * k); x.bezierCurveTo(70 * k, -80 * k, 95 * k, 30 * k, 0, 95 * k);
  x.fillStyle = SAGE; x.fill(); x.strokeStyle = DARK; x.lineWidth = 4 * k; x.stroke();
  x.beginPath(); x.moveTo(0, 125 * k); x.lineTo(0, -95 * k); x.stroke();
  for (let i = 0; i < 4; i++) { const yy = 55 * k - i * 40 * k; x.beginPath(); x.moveTo(0, yy); x.lineTo(-38 * k, yy - 30 * k); x.moveTo(0, yy); x.lineTo(38 * k, yy - 30 * k); x.stroke(); }
  x.restore();
  setFont(F.label(20 * k, DARK)); x.fillStyle = DARK; x.textAlign = 'center'; x.textBaseline = 'middle';
  x.fillText('LE SHOP', 0, ty + th - 60 * k);
  x.restore();
  // rotierender Ring
  ringText('AUSGEWÄHLT · NACHHALTIG · HOCHWERTIG · ', cx, cy + 40 * k, 330 * k, -Math.PI / 2 + l * .35, F.label(24 * k, SAGE));
}
// Plate 3: Beratung (Sprechblasen)
function talkPlate(X, Y, w, h, l, t) {
  fill(CLAY, X, Y, w, h);
  const k = h / 800, lw = 5 * k;
  const bubble = (bx, by, bw, bh, tailLeft, c, st) => {
    const p = outExpo(prog(l, st, .5)); if (p <= 0) return;
    x.save(); x.translate(bx + bw / 2, by + bh); x.scale(p, p); x.translate(-(bx + bw / 2), -(by + bh));
    x.beginPath(); x.roundRect(bx, by, bw, bh, bh / 2);
    const tx = tailLeft ? bx + bw * .22 : bx + bw * .78;
    x.moveTo(tx - 22 * k, by + bh - 4); x.lineTo(tx + (tailLeft ? -30 : 30) * k, by + bh + 50 * k); x.lineTo(tx + 22 * k, by + bh - 4);
    x.fillStyle = c; x.fill(); x.strokeStyle = DARK; x.lineWidth = lw; x.lineJoin = 'round'; x.stroke(); x.restore();
    return p;
  };
  const p1 = bubble(X + 110 * k, Y + 150 * k, 520 * k, 170 * k, true, PAPER, 0);
  if (p1 >= 1) { // Tipp-Punkte
    for (let i = 0; i < 3; i++) { const a = .35 + .65 * Math.max(0, Math.sin(t * 7 - i * .8)); x.globalAlpha = a; x.beginPath(); x.arc(X + 270 * k + i * 100 * k, Y + 235 * k, 20 * k, 0, Math.PI * 2); x.fillStyle = DARK; x.fill(); x.globalAlpha = 1; }
  }
  bubble(X + w - 640 * k, Y + 430 * k, 520 * k, 170 * k, false, FOREST, 2 * BEAT);
  if (l > 2 * BEAT + .2) {   // Herz in der zweiten Blase
    const hp = outExpo(prog(l, 2 * BEAT + .2, .4)), hx = X + w - 380 * k, hy = Y + 515 * k, r = 34 * k * hp * (1 + .06 * Math.exp(-((l - 3 * BEAT + 10) % BEAT) * 8));
    x.save(); x.translate(hx, hy); x.beginPath(); x.moveTo(0, r * 1.1);
    x.bezierCurveTo(-r * 2.2, -r * .2, -r * .9, -r * 1.9, 0, -r * .6); x.bezierCurveTo(r * .9, -r * 1.9, r * 2.2, -r * .2, 0, r * 1.1);
    x.fillStyle = SAGE; x.fill(); x.restore();
  }
}
// Karten-Grafik: Straße + Pin
function mapPlate(X, Y, w, h, l, t) {
  fill(FOREST, X, Y, w, h);
  const k = h / 800;
  x.save(); x.strokeStyle = 'rgba(243,237,228,.16)'; x.lineWidth = 26 * k; x.lineCap = 'round';
  const roads = [[0, .25, 1, .18], [.2, 0, .32, 1], [.72, 0, .62, 1], [0, .82, 1, .9]];
  roads.forEach(([a, b, c, d], i) => { const p = outExpo(prog(l, i * .08, .8)); x.beginPath(); x.moveTo(X + a * w, Y + b * h); x.lineTo(X + (a + (c - a) * p) * w, Y + (b + (d - b) * p) * h); x.stroke(); });
  // Hauptstraße
  const p = outExpo(prog(l, .1, .9)), my = Y + h * .55;
  x.strokeStyle = SAGE; x.lineWidth = 40 * k; x.beginPath(); x.moveTo(X, my + 30 * k); x.lineTo(X + w * p, my - 30 * k); x.stroke();
  x.restore();
  setFont(F.label(22 * k, DARK));
  x.save(); x.translate(X + w * .2, my + 16 * k); x.rotate(-Math.atan2(60 * k, w)); x.fillStyle = DARK; x.textAlign = 'left'; x.textBaseline = 'middle';
  x.globalAlpha = cl((l - .6) / .3); x.fillText('CLEMENS-AUGUST-STR.', 0, 0); x.restore();
  // Pin fällt auf den Beat
  const st = BEAT * 1, pp = prog(l, st, .45), px = X + w * .66, py = my - 12 * k - 30 * k * (.66 - .5) * 2;
  if (l >= st) {
    const bounce = pp < 1 ? (1 - outCubic(pp)) * -260 * k : Math.sin((l - st - .45) * 18) * Math.exp(-(l - st - .45) * 7) * -14 * k;
    const ring = cl((l - st - .4) / 1.2);
    if (ring > 0) { x.save(); x.strokeStyle = SAGE; x.lineWidth = 3 * k; x.globalAlpha = 1 - ring; x.beginPath(); x.ellipse(px, py, 40 * k + ring * 150 * k, (40 * k + ring * 150 * k) * .35, 0, 0, Math.PI * 2); x.stroke(); x.restore(); }
    x.save(); x.translate(px, py + bounce);
    x.beginPath(); x.moveTo(0, 0); x.bezierCurveTo(-30 * k, -60 * k, -70 * k, -95 * k, -70 * k, -140 * k); x.arc(0, -140 * k, 70 * k, Math.PI, 0); x.bezierCurveTo(70 * k, -95 * k, 30 * k, -60 * k, 0, 0);
    x.fillStyle = CLAY; x.fill(); x.strokeStyle = DARK; x.lineWidth = 5 * k; x.stroke();
    setFont(F.sans(54 * k, LIGHT)); x.fillStyle = LIGHT; x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText('39', 0, -138 * k);
    x.restore();
  }
}

// ---------------- Einstellungen ----------------
function hook(l, t) {
  fill(DARK);
  // großer Bügel oben, schwingt aus
  const hs = FEED ? 380 : 560;
  hanger(W * .64, FEED ? 150 : 400, hs, swing(l, .16 * Math.exp(-l * .6) + .02, 3.2, .4), SAGE, 9);
  const y1 = FEED ? 820 : 1060;
  line('CONCEPT STORE  ·  BONN-POPPELSDORF', L, T0 + 40 * S, F.label(24 * S, SAGE), 0, l, { instant: true });
  pop('Neu', L, y1, F.sans(190 * S), l, { align: 'left', baseline: 'alphabetic' });
  if (l >= BEAT) pop('in', L, y1 + 180 * S, F.sans(190 * S), l - BEAT, { align: 'left', baseline: 'alphabetic' });
  if (l >= 2 * BEAT) { const sz = fit('Poppelsdorf.', v => F.serif(v, SAGE), 215 * S, W - 2 * L); pop('Poppelsdorf.', L, y1 + 370 * S, F.serif(sz, SAGE), l - 2 * BEAT, { align: 'left', baseline: 'alphabetic' }); }
}
function store(l, t) {
  const Y = T0 + 110 * S, h = FEED ? 560 : 700;
  line('CLEMENS-AUGUST-STRASSE 39', L, T0 + 40 * S, F.label(24 * S, SAGE), 0, l, { d: .5 });
  shutter(0, Y, W, h, 0, l, () => { x.save(); const z = 1 + l * .012; x.translate(W / 2, Y + h / 2); x.scale(z, z); x.translate(-W / 2, -(Y + h / 2)); storefront(0, Y, W, h, l, t); x.restore(); }, .7);
  const y = Y + h + 140 * S;
  line('Stöbern.', L, y, F.sans(96 * S), 1 * BEAT - .05, l, { d: .55 });
  line('Anprobieren.', L, y + 118 * S, F.sans(96 * S), 2 * BEAT - .05, l, { d: .55 });
  line('Verlieben.', L, y + 248 * S, F.serif(130 * S, SAGE), 3 * BEAT - .05, l, { d: .55 });
}
const WORDS = [['Kuratiert.', SAGE, DARK, 'serif'], ['Nachhaltig.', FOREST, LIGHT, 'sans'], ['Hochwertig.', PAPER, DARK, 'serif'], ['Persönlich.', CLAY, DARK, 'sans']];
const word = i => (l) => {
  const [wd, bg, fg, style] = WORDS[i]; fill(bg);
  const cy = H * .5;
  setFont(F.label(24 * S)); x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillStyle = fg; x.globalAlpha = .7; x.fillText('WAS LE SHOP AUSMACHT', W / 2, cy - 200 * S); x.globalAlpha = 1;
  const f = style === 'serif' ? v => F.serif(v, fg) : v => F.sans(v, fg);
  pop(wd, W / 2, cy, f(fit(wd, f, style === 'serif' ? 185 * S : 132 * S, W - 2 * L)), l);
  setFont(F.label(22 * S)); x.textAlign = 'center'; x.fillStyle = fg; x.globalAlpha = .7; x.fillText(`0${i + 1} — 04`, W / 2, cy + 160 * S); x.globalAlpha = 1;
};
const FEAT = [
  { n: 'Kuratierte Auswahl', sub: 'AUF RUND 90 QUADRATMETERN', plate: railPlate },
  { n: 'Nachhaltig & hochwertig', sub: 'AUSGESUCHTE WARE', plate: tagPlate },
  { n: 'Persönliche Beratung', sub: 'DIREKT IM LADEN', plate: talkPlate },
];
const feature = i => (l, t) => {
  const s = FEAT[i], Y = FEED ? T0 + 100 * S : 0, h = FEED ? 760 : 1130;
  const ly = FEED ? T0 + 40 * S : h + 82;
  x.save(); const z = 1 + l * .01; x.translate(W / 2, Y + h / 2); x.scale(z, z); x.translate(-W / 2, -(Y + h / 2));
  s.plate(0, Y, W, h, l, t); x.restore();
  if (FEED) fill(DARK, 0, 0, W, Y);
  line('IM LADEN', L, ly, F.label(24 * S, SAGE), 0, l, { instant: i > 0, d: .5 });
  line(`0${i + 1} / 03`, W - L, ly, F.label(24 * S), 0, l, { instant: true, align: 'right', alpha: .7 });
  const sz = fit(s.n, v => F.sans(v), 104 * S, W - 2 * L - 40);
  const ny = FEED ? Y + h + 140 * S : h + 212;
  line(s.n, L, ny, F.sans(sz), .03, l, { d: .55 });
  line(s.sub, L, ny + 78 * S, F.label(23 * S), .12, l, { d: .55, alpha: .75 });
};
function find(l, t) {
  const Y = T0 + 110 * S, h = FEED ? 520 : 700;
  line('SO FINDEST DU UNS', L, T0 + 40 * S, F.label(24 * S, SAGE), 0, l, { d: .5 });
  mapPlate(0, Y, W, h, l, t);
  const y = Y + h + 150 * S;
  line('Der dritte Le Shop.', L, y, F.serif(120 * S), .3, l);
  line('Jetzt in Poppelsdorf.', L, y + 120 * S, F.sans(80 * S), 2 * BEAT, l);
}
function drop(l, t) {
  const pi = 1 + .12 * Math.exp(-l * 10) + l * .02, cx = W / 2, cy = FEED ? H * .42 : H * .4;
  fill(PAPER);
  x.save(); x.translate(cx, cy); x.scale(pi, pi); x.translate(-cx, -cy);
  const R = FEED ? 250 : 300;
  x.beginPath(); x.arc(cx, cy, R, 0, Math.PI * 2); x.fillStyle = FOREST; x.fill();
  // Bügel springt pro Beat in eine neue Farbe
  const i = Math.min(3, Math.floor(l / BEAT)), cols = [SAGE, CLAY, LIGHT, SAGE];
  hanger(cx, cy - R * .62, R * 1.15, swing(t, .07, 2.2), cols[i], 9);
  ringText('NEU IN POPPELSDORF · NEU IN POPPELSDORF · ', cx, cy, R + 52, -Math.PI / 2 + l * .5, F.label(26, DARK));
  x.restore();
  const y1 = B0 - 140 * S;
  line('Komm vorbei.', L, y1, F.serif(160 * S, DARK), .1, l);
  line('Schau dich um.', L, y1 + 120 * S, F.sans(84 * S, DARK), 2 * BEAT, l);
}
function cta(l, t) {
  const ph = FEED ? 430 : 760, pb = ph;
  shutter(0, 0, W, ph, 0, l, () => { const z = 1.05 + l * .012; x.save(); x.translate(W / 2, ph / 2); x.scale(z, z); x.translate(-W / 2, -ph / 2); storefront(0, FEED ? -60 : 0, W, FEED ? 560 : ph, 2 + l, t); x.restore(); }, .7);
  line('CONCEPT STORE IN BONN', L, pb + 75 * S, F.label(24 * S, SAGE), .05, l);
  line('Neue Lieblingsteile.', L, pb + 230 * S, F.serif(140 * S), .15, l);
  line('Ganz in der Nähe.', L, pb + 350 * S, F.sans(100 * S), .3, l);
  line('BONN-POPPELSDORF', L, pb + 430 * S, F.label(22 * S), 2 * BEAT, l, { alpha: .8 });
  if (l >= 3 * BEAT) {
    const ls = l - 3 * BEAT, beatPhase = ls % BEAT;
    const sc = (1 + .06 * (1 - outExpo(cl(ls / .35)))) * (1 + .03 * Math.exp(-beatPhase * 10));
    const txt = 'Clemens-August-Str. 39', f = F.sans(54 * S, DARK), tw = measure(txt, f), pw = tw + 100 * S, phh = 112 * S, cy = pb + 525 * S;
    x.save(); x.translate(L + pw / 2, cy); x.scale(sc, sc);
    x.beginPath(); x.roundRect(-pw / 2, -phh / 2, pw, phh, phh / 2); x.fillStyle = SAGE; x.fill();
    setFont(f); x.fillStyle = DARK; x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText(txt, 0, 4 * S); x.restore();
  }
  line('JETZT VORBEISCHAUEN', L, pb + 640 * S, F.label(23 * S), 5 * BEAT, l, { alpha: .75 });
}
function endCard(l, t) {
  const cy = H * (FEED ? .48 : .46);
  const push = 1 + .012 * l + .07 * inCubic((l - 3 * BEAT) / BEAT);
  x.save(); x.translate(W / 2, cy); x.scale(push, push); x.translate(-W / 2, -cy);
  const lp = outExpo(cl(l / .9)), R = 112 * S, ly = cy - 200 * S + (1 - lp) * 24;
  x.save(); x.globalAlpha = lp; x.beginPath(); x.arc(W / 2, ly, R, 0, Math.PI * 2); x.fillStyle = SAGE; x.fill(); x.restore();
  x.save(); x.globalAlpha = lp; hanger(W / 2, ly - R * .62, R * 1.2, swing(t, .05, 2), DARK, 6); x.restore();
  x.save(); x.globalAlpha = lp * .35; x.strokeStyle = LIGHT; x.lineWidth = 1.5; x.beginPath(); x.arc(W / 2, ly, R + 16, 0, Math.PI * 2); x.stroke(); x.restore();
  line('Le Shop —', W / 2, cy + 95 * S, F.serif(170 * S), .15, l, { align: 'center' });
  line('CONCEPT STORE  ·  BONN', W / 2, cy + 180 * S, F.label(23 * S), BEAT, l, { align: 'center', alpha: .75 });
  x.restore();
}

const at = b => b * BEAT;
const shots = [
  { a: 0, b: at(3), f: hook },
  { a: at(3), b: at(8), f: store },
  ...[0, 1, 2, 3].map(i => ({ a: at(8 + i), b: at(9 + i), f: word(i) })),
  ...[0, 1, 2].map(i => ({ a: at(12 + 4 * i), b: at(16 + 4 * i), f: feature(i) })),
  { a: at(24), b: at(28), f: find },
  { a: at(28), b: at(32), f: drop },
  { a: at(32), b: at(40), f: cta },
  { a: at(40), b: at(44), f: endCard },
];
window.EDIT = {
  dur: at(44), loop: true, accent: SAGE,
  assets: {},
  shots,
  fx: [
    { type: 'flash', t: 0, a: .35 },
    { type: 'leak', t: at(12) },
    { type: 'whip', t: at(16), w: .1 },
    { type: 'whip', t: at(20), w: .1 },
    { type: 'flash', t: at(28), a: .45 },
    { type: 'leak', t: at(32) },
  ],
};
