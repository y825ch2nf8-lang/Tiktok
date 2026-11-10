// "KI im Alltag" — explainer template, 21.6 s = 9 bars @ 100 BPM, one video per entry in topics.js (?topic=0..9).
// Hook (4 beats) -> Schritt 1: Material (6) -> Schritt 2: Prompt wird getippt (10) -> Schritt 3: Ergebnis (10) -> CTA (6).
// Engine helpers (line, pop, rule, fill, F, S, L, T0, B0, W, H, x, ...) are globals from ../engine/engine.js
// and may only be used inside functions (this file loads first).
const BEAT = 60 / 100, at = b => b * BEAT;
const TI = Math.max(0, Math.min(window.TOPICS.length - 1, +(new URLSearchParams(location.search).get('topic') || 0)));
const TP = window.TOPICS[TI], NO = String(TI + 1).padStart(2, '0');
const LIME = '#d9f24a', PAPER = '#efe6d8', K_INK = '#0f0d0b', K_CREAM = '#f3ede4';
const TXW = 846;                                   // usable text width (right 150 px stay free for the TikTok buttons)

function fit(str, fontFn, maxSize, maxW) { const w = measure(str, fontFn(100)); return Math.min(maxSize, 100 * maxW / w); }
function wrapText(str, f, maxW) {
  const out = []; let cur = '';
  for (const w of str.split(' ')) { const tryL = cur ? cur + ' ' + w : w; if (cur && measure(tryL, f) > maxW) { out.push(cur); cur = w; } else cur = tryL; }
  if (cur) out.push(cur); return out;
}

// ---------------- line-art plates (unit box ~600x600, centred on 0,0) ----------------
const P = (l, t0, d) => outExpo(cl((l - t0) / d));
function txt(s, X, Y, px, col, align = 'left', w = 800) { setFont({ font: `${w} ${px}px "Inter Tight"`, track: px * .04 }); x.fillStyle = col; x.textAlign = align; x.textBaseline = 'middle'; x.fillText(s, X, Y); }
function rr(X, Y, w, h, r) { x.beginPath(); x.roundRect(X, Y, w, h, r); }
function ln(x0, y0, x1, y1) { x.beginPath(); x.moveTo(x0, y0); x.lineTo(x1, y1); x.stroke(); }
function sheet(c, bg, rows, skip = []) {              // paper with text lines; returns the row y positions
  rr(-190, -250, 380, 500, 6); x.fillStyle = bg; x.fill(); x.stroke();
  const ys = []; for (let i = 0; i < rows; i++) { const y = -120 + i * 58; ys.push(y); if (!skip.includes(i)) { x.save(); x.globalAlpha = .55; x.lineWidth = 5; ln(-140, y, i % 3 === 2 ? 60 : 140, y); x.restore(); } }
  return ys;
}
const ART = {
  tv(l, c, a, bg) {
    rr(-290, -210, 580, 350, 10); x.fillStyle = bg; x.fill(); x.stroke();
    ln(0, 140, 0, 190); ln(-120, 192, 120, 192);
    for (let i = 0; i < 5; i++) {
      const y = -165 + i * 58;
      if (i === 3) { const p = P(l, .35, .5); x.fillStyle = a; x.fillRect(-262, y - 22, 250 * p, 44); if (p > .6) txt('DATENSCHUTZ', -250, y + 1, 24, K_INK); }
      else { x.save(); x.globalAlpha = .55; x.lineWidth = 5; ln(-250, y, i % 2 ? -90 : -40, y); x.restore(); }
    }
    x.save(); x.lineWidth = 5; x.strokeRect(40, -175, 215, 150); txt('WERBUNG', 147, -100, 27, c, 'center'); x.restore();
    const s = P(l, .9, .45); if (s > 0) { x.save(); x.strokeStyle = a; x.lineWidth = 14; ln(30, -15, 30 + 235 * s, -15 - 170 * s); x.restore(); }
  },
  letter(l, c, a, bg) {
    sheet(c, bg, 5);
    x.save(); x.lineWidth = 5; ln(-140, -205, -40, -205); ln(-140, -180, -70, -180); x.restore();
    const p = P(l, .45, .4), sc = 1.6 - .6 * p;
    if (p > 0) { x.save(); x.translate(105, 165); x.rotate(-.22); x.scale(sc, sc); x.globalAlpha = p; x.beginPath(); x.arc(0, 0, 62, 0, 7); x.fillStyle = a; x.fill(); x.stroke(); txt('FRIST', 0, 2, 27, K_INK, 'center'); x.restore(); }
  },
  abo(l, c, a, bg) {
    sheet(c, bg, 5, [0]);
    txt('ABO', -140, -190, 54, c); txt('29,90 € / MONAT', -140, -118, 25, c);
    const s = P(l, .6, .5); if (s > 0) { x.save(); x.strokeStyle = a; x.lineWidth = 20; ln(-220, 200, -220 + 440 * s, 200 - 400 * s); x.restore(); }
  },
  fridge(l, c, a, bg) {
    rr(-180, -270, 360, 540, 16); x.fillStyle = bg; x.fill(); x.stroke();
    ln(-180, -90, 180, -90); ln(-180, 90, 180, 90);
    const drop = (i) => (1 - P(l, .25 + i * .14, .45)) * -50, al = i => P(l, .25 + i * .14, .3);
    x.save(); x.lineWidth = 5;
    x.globalAlpha = al(0); x.strokeRect(-120, -190 + drop(0), 50, 100); x.strokeRect(-106, -222 + drop(0), 22, 32);
    x.globalAlpha = al(1); x.beginPath(); x.arc(60, -130 + drop(1), 40, 0, 7); x.fillStyle = a; x.fill(); x.stroke();
    x.globalAlpha = al(2); x.strokeRect(-130, 10 + drop(2), 120, 80);
    x.globalAlpha = al(3); for (const ex of [50, 105]) { x.beginPath(); x.ellipse(ex, 58 + drop(3), 22, 30, 0, 0, 7); x.stroke(); }
    x.globalAlpha = al(4); x.beginPath(); x.moveTo(-110, 240 + drop(4)); x.lineTo(-60, 150 + drop(4)); x.lineTo(40, 150 + drop(4)); x.lineTo(90, 240 + drop(4)); x.stroke();
    x.restore();
  },
  bill(l, c, a, bg) {
    const p = P(l, .5, .5);
    rr(-190, -250, 380, 500, 6); x.fillStyle = bg; x.fill(); x.stroke();
    txt('RECHNUNG', -140, -195, 30, c);
    for (let i = 0; i < 5; i++) {
      const y = -120 + i * 62;
      if (i === 2) { x.fillStyle = a; x.fillRect(-165, y - 26, 330 * p, 52); if (p > .6) { txt('ABO-EXTRA', -150, y + 1, 24, K_INK); txt('+ 4,99 €', 150, y + 1, 24, K_INK, 'right'); } }
      else { x.save(); x.globalAlpha = .55; x.lineWidth = 5; ln(-140, y, 10, y); ln(90, y, 140, y); x.restore(); }
    }
    x.save(); x.lineWidth = 5; ln(-140, 205, 140, 205); x.restore();
  },
  washer(l, c, a, bg) {
    rr(-220, -270, 440, 540, 14); x.fillStyle = bg; x.fill(); x.stroke();
    ln(-220, -160, 220, -160);
    const on = (l % .6) < .36;
    x.fillStyle = on ? a : bg; x.fillRect(-180, -245, 170, 62); x.save(); x.lineWidth = 5; x.strokeRect(-180, -245, 170, 62); x.restore();
    if (on) txt('E18', -95, -213, 38, K_INK, 'center');
    x.beginPath(); x.arc(140, -214, 30, 0, 7); x.stroke(); x.save(); x.lineWidth = 5; ln(140, -214, 140 + 22 * Math.cos(l * 1.2), -214 + 22 * Math.sin(l * 1.2)); x.restore();
    x.beginPath(); x.arc(0, 60, 165, 0, 7); x.stroke();
    x.save(); x.lineWidth = 5; x.beginPath(); x.arc(0, 60, 118, 0, 7); x.stroke(); x.globalAlpha = .55; x.beginPath(); x.arc(0, 60, 82, .5, 2.2); x.stroke(); x.restore();
  },
  phone(l, c, a, bg) {
    rr(-170, -290, 340, 580, 34); x.fillStyle = bg; x.fill(); x.stroke();
    x.save(); x.lineWidth = 5; ln(-40, -252, 40, -252); x.restore();
    ['TRACKING', 'WERBUNG', 'STANDORT'].forEach((s, i) => {
      const y = -130 + i * 125, p = P(l, .45 + i * .32, .3), kx = 110 - 46 * p;
      txt(s, -130, y, 25, c);
      rr(40, y - 27, 96, 54, 27); x.fillStyle = p < .5 ? a : bg; x.fill(); x.save(); x.lineWidth = 5; x.stroke(); x.restore();
      x.beginPath(); x.arc(kx, y, 17, 0, 7); x.fillStyle = p < .5 ? K_INK : c; x.fill();
      x.save(); x.globalAlpha = .3; x.lineWidth = 3; ln(-130, y + 62, 136, y + 62); x.restore();
    });
  },
  board(l, c, a, bg) {
    rr(-290, -200, 580, 400, 8); x.fillStyle = bg; x.fill(); x.stroke();
    txt('ABFLUG', -255, -150, 27, c); x.save(); x.lineWidth = 5; ln(-290, -110, 290, -110); x.restore();
    [['LH 402', '10:15', 'PÜNKTLICH'], ['EW 9461', '10:40', '+ 3:20'], ['FR 1178', '11:05', 'PÜNKTLICH']].forEach((r, i) => {
      const y = -50 + i * 90;
      txt(r[0], -255, y, 31, c); txt(r[1], -60, y, 31, c);
      if (i === 1) { const p = P(l, .5, .45); x.fillStyle = a; x.fillRect(60, y - 31, 200 * p, 62); if (p > .6) txt(r[2], 160, y + 1, 31, K_INK, 'center'); }
      else { x.save(); x.globalAlpha = .5; txt(r[2], 260, y, 22, c, 'right', 600); x.restore(); }
    });
  },
  contract(l, c, a, bg) {
    const ys = sheet(c, bg, 5, [2]);
    txt('VERTRAG', -140, -195, 30, c);
    const p = P(l, .5, .5); x.fillStyle = a; x.fillRect(-160, ys[2] - 26, 320 * p, 52); if (p > .6) txt('§ 7  KÜNDIGUNG', -145, ys[2] + 1, 25, K_INK);
    x.save(); x.lineWidth = 5; x.beginPath(); x.moveTo(-10, 205);
    const sp = P(l, 1.0, .7); for (let u = 0; u <= sp; u += .02) x.lineTo(-10 + u * 150, 205 - Math.sin(u * 15) * 20 * (1 - u * .5)); x.stroke(); x.restore();
    const mx = 150 - 40 * Math.sin(l * 1.3), my = ys[2] + 12 * Math.cos(l * 1.1);
    x.beginPath(); x.arc(mx, my, 62, 0, 7); x.stroke(); ln(mx + 46, my + 46, mx + 112, my + 112);
  },
  tag(l, c, a, bg) {
    x.save(); x.rotate(-.16 + .03 * Math.sin(l * 1.6));
    x.beginPath(); x.moveTo(-280, 0); x.lineTo(-170, -130); x.lineTo(270, -130); x.lineTo(270, 130); x.lineTo(-170, 130); x.closePath(); x.fillStyle = bg; x.fill(); x.stroke();
    x.beginPath(); x.arc(-185, 0, 22, 0, 7); x.stroke();
    txt('79,99 €', 60, -8, 86, c, 'center'); x.save(); x.globalAlpha = .55; txt('STATT 129 €', 60, 72, 24, c, 'center', 600); x.restore();
    x.restore();
    const p = P(l, .55, .4); if (p > 0) { const sc = 1.5 - .5 * p; x.save(); x.translate(215, -175); x.scale(sc, sc); x.globalAlpha = p; x.beginPath(); x.arc(0, 0, 66, 0, 7); x.fillStyle = a; x.fill(); x.stroke(); txt('?', 0, 4, 80, K_INK, 'center'); x.restore(); }
  },
};
function art(cx, cy, k, l, c, a, bg) {
  x.save(); x.translate(cx, cy); x.scale(k, k); x.strokeStyle = c; x.lineWidth = 7; x.lineJoin = 'round'; x.lineCap = 'round';
  ART[TP.art](l, c, a, bg); x.restore();
}

// ---------------- shots ----------------
function slam(str, X, Y, f, li, rot = 0, amp = .16) {              // word hits the frame: overshoot scale + tiny rotation, settles in ~0.2 s
  const k = Math.exp(-li * 16), sc = 1 + amp * k, w = measure(str, f), cx = X + w / 2, cy = Y - f.size * .3;   // scales around its own centre so it never leaves the frame
  x.save(); x.translate(cx, cy); x.rotate(rot * k); x.scale(sc, sc); setFont(f); x.textAlign = 'center'; x.textBaseline = 'alphabetic'; x.fillStyle = f.color; x.fillText(str, 0, f.size * .3); x.restore();
}
// Hook: one hard cut per beat. Beat 0 = full-bleed lime with a giant ink line (frame 0 already carries the message),
// beat 1 = inverted, beat 2 = payoff line in serif, beat 3 = promise ("3 Schritte") + plate.
function hook(l, t) {
  const i = Math.min(3, Math.floor(l / BEAT)), li = l - i * BEAT, h = TP.hook;
  const shake = Math.exp(-li * 11) * 16, push = 1 + .02 * li;
  x.save(); x.translate(W / 2 + Math.sin(l * 97) * shake, H / 2 + Math.cos(l * 83) * shake); x.scale(push, push); x.translate(-W / 2, -H / 2);
  const big = (str, serif) => fit(str, v => serif ? F.serif(v) : F.sans(v), serif ? 300 : 250, TXW);
  if (i === 0) {
    fill(LIME, -60, -60, W + 120, H + 120);
    line(`KI IM ALLTAG  ·  TRICK ${NO}`, L, T0 + 40, F.label(24, K_INK), 0, l, { instant: true });
    slam(h[0], L, 900, F.sans(big(h[0]), K_INK), li, -.03, .1);
    fill(K_INK, L, 960, TXW * outExpo(cl(li / .35)), 10);
    art(L + 300, 1262, .62, l, K_INK, PAPER, LIME);
  } else {
    line(`KI IM ALLTAG  ·  TRICK ${NO}`, L, T0 + 40, F.label(24, ACC), 0, l, { instant: true });
    if (i === 1) {
      x.save(); x.globalAlpha = .45; setFont(F.sans(fit(h[0], v => F.sans(v), 96, TXW))); x.fillStyle = CREAM; x.textAlign = 'left'; x.textBaseline = 'alphabetic'; x.fillText(h[0], L, 660); x.restore();
      slam(h[1], L, 900, F.sans(big(h[1])), li, .03);
      art(L + 300, 1262, .62, l, CREAM, ACC, INK);
    } else {
      const s0 = fit(h[0], v => F.sans(v), 110, TXW), s1 = fit(h[1], v => F.sans(v), 110, TXW);
      setFont(F.sans(s0)); x.fillStyle = CREAM; x.textAlign = 'left'; x.textBaseline = 'alphabetic'; x.fillText(h[0], L, 520);
      setFont(F.sans(s1)); x.fillText(h[1], L, 640);
      const l2 = l - 2 * BEAT;
      slam(h[2], L, 880, F.serif(big(h[2], true), ACC), l2, -.025);
      if (i === 3) {
        const p = outExpo(cl(li / .3)), txt_ = 'SO GEHT’S IN 3 SCHRITTEN', f = F.label(27, K_INK), tw = measure(txt_, f) + 56;
        x.save(); x.beginPath(); x.rect(L, 960, tw * p, 76); x.clip(); fill(ACC, L, 960, tw, 76);
        setFont(f); x.fillStyle = K_INK; x.textAlign = 'left'; x.textBaseline = 'middle'; x.fillText(txt_, L + 28, 999); x.restore();
      }
      art(L + 300, 1262, .62, l, CREAM, ACC, INK);
    }
  }
  x.restore();
}
// retention bar: thin progress line across the top of the safe area
function bar(t, col) { fill(col, 0, 246, W * (t / at(36)), 7); }
function corners(X, Y, w, h, len, col, lw) {
  x.save(); x.strokeStyle = col; x.lineWidth = lw; x.lineCap = 'square';
  for (const [cx, cy, sx, sy] of [[X, Y, 1, 1], [X + w, Y, -1, 1], [X, Y + h, 1, -1], [X + w, Y + h, -1, -1]]) { x.beginPath(); x.moveTo(cx + sx * len, cy); x.lineTo(cx, cy); x.lineTo(cx, cy + sy * len); x.stroke(); }
  x.restore();
}
function step1(l, t) {
  const h = 1010, snap = 2 * BEAT, d = hh(t, .7);
  fill(PAPER, 0, 0, W, h);
  const z = l < snap ? 1.12 + l * .03 : 1.2 + .1 * Math.exp(-(l - snap) * 9) + (l - snap) * .012;   // punch-in when the photo is taken
  x.save(); x.beginPath(); x.rect(0, 0, W, h); x.clip();
  art(W / 2 + d.dx, 560 + d.dy, z, l, INK, LIME, PAPER);
  const m = l < snap ? 150 - 22 * outExpo(cl(l / .5)) : 128, cw = W - 2 * m;                          // viewfinder
  corners(m, 560 - cw * .55, cw, cw * 1.1, 70, INK, 5);
  if (l < snap) { x.fillStyle = INK; x.globalAlpha = .5 + .5 * Math.sin(l * 14); x.beginPath(); x.arc(m + 34, 560 - cw * .55 + 34, 9, 0, 7); x.fill(); x.globalAlpha = 1; }
  else { x.fillStyle = `rgba(255,252,244,${Math.exp(-(l - snap) * 9)})`; x.fillRect(0, 0, W, h); }
  x.restore();
  const ly = h + 84;
  line('SCHRITT 01', L, ly, F.label(24, ACC), 0, l, { d: .5 });
  line('01 / 03', L + TXW, ly, F.label(24), 0, l, { instant: true, align: 'right', alpha: .7 });
  line(TP.s1[0], L, ly + 135, F.sans(fit(TP.s1[0], v => F.sans(v), 100, TXW)), .05, l, { d: .55 });
  line(TP.s1[1], L, ly + 215, F.label(fit(TP.s1[1], v => F.label(v), 23, TXW)), snap + .05, l, { d: .55, alpha: .78 });
}
function step2(l) {
  fill(LIME);
  line('SCHRITT 02', L, T0 + 40, F.label(24, K_INK), 0, l, { d: .5 });
  line('02 / 03', L + TXW, T0 + 40, F.label(24, K_INK), 0, l, { instant: true, align: 'right', alpha: .7 });
  line('Das fragst du', L, T0 + 180, F.sans(88, K_INK), .05, l, { d: .55 });
  line('die KI:', L, T0 + 285, F.serif(120, K_INK), .14, l, { d: .55 });
  rule(L, T0 + 345, L + TXW, .3, l, K_INK, 2);
  // the prompt types itself; size chosen so it never needs more than 6 lines
  const full = '„' + TP.prompt + '“';
  let sz = 118, lines; do { lines = wrapText(full, F.serif(sz, K_INK), TXW); sz -= 3; } while (lines.length * sz * 1.16 > 660); sz += 3;
  const f = F.serif(sz, K_INK), lh = sz * 1.16, t0 = 1 * BEAT, tEnd = 6.2 * BEAT;
  const n = Math.floor(cl((l - t0) / (tEnd - t0)) * full.length);
  let left = n, y = T0 + 345 + lh * 1.05, cx = L, cy = y;
  setFont(f); x.fillStyle = K_INK; x.textAlign = 'left'; x.textBaseline = 'alphabetic';
  for (const s of lines) {
    const part = s.slice(0, Math.max(0, left)); if (part) { setFont(f); x.fillStyle = K_INK; x.textAlign = 'left'; x.textBaseline = 'alphabetic'; x.fillText(part, L, y); cx = L + x.measureText(part).width; cy = y; }
    left -= s.length + 1; if (left < 0) break; y += lh;
  }
  if (l >= t0 - .3 && (n < full.length || (l % .7) < .4)) { x.fillStyle = K_INK; x.fillRect(cx + 6, cy - sz * .72, 5, sz * .86); }
  const by = B0 - 20;
  if (l >= tEnd + .15) { rule(L, by - 70, L + TXW, tEnd + .15, l, K_INK, 2); line('PROMPT KOPIEREN  ·  VIDEO SPEICHERN', L, by, F.label(24, K_INK), tEnd + .25, l, { d: .55 }); }
}
function step3(l) {
  x.save(); x.translate(0, -l * 5 + 40);
  line('SCHRITT 03', L, T0 + 40, F.label(24, ACC), .02, l);
  line('03 / 03', L + TXW, T0 + 40, F.label(24), 0, l, { instant: true, align: 'right', alpha: .7 });
  line('Das bekommst du.', L, T0 + 205, F.serif(fit('Das bekommst du.', v => F.serif(v), 150, TXW)), .1, l);
  const y0 = T0 + 290, RH = 205;
  TP.res.forEach((r, i) => {
    const st = (i + 1) * BEAT - .1, y = y0 + i * RH;
    rule(L, y, L + TXW, st, l);
    line('0' + (i + 1), L, y + 132, F.serif(110, ACC), st + .05, l);
    line(r, L + 165, y + 122, F.sans(fit(r, v => F.sans(v), 62, TXW - 165)), st + .1, l);
  });
  rule(L, y0 + 3 * RH, L + TXW, 3 * BEAT + .3, l);
  if (TP.note) line(TP.note, L, y0 + 3 * RH + 70, F.label(fit(TP.note, v => F.label(v), 22, TXW)), 4.5 * BEAT, l, { alpha: .7 });
  x.restore();
}
function cta(l, t) {
  const d = hh(t, .8), push = 1 + .012 * l + .07 * inCubic((l - 5 * BEAT) / BEAT);
  x.save(); x.translate(W / 2, H * .46); x.scale(push, push); x.translate(-W / 2, -H * .46);
  art(W / 2 - 40 + d.dx, 610 + d.dy, .82, 9, CREAM, ACC, INK);
  line(`KI IM ALLTAG  ·  TRICK ${NO}`, L, T0 + 40, F.label(24, ACC), 0, l, { instant: true });
  line("Probier's aus.", L, 1090, F.serif(190), .05, l);
  line('Folge für mehr', L, 1225, F.sans(104), BEAT - .05, l);
  if (l >= 2 * BEAT) {
    const ls = l - 2 * BEAT, sc = (1 + .06 * (1 - outExpo(cl(ls / .35)))) * (1 + .025 * Math.exp(-(ls % BEAT) * 10));
    const f = F.sans(86, K_INK), tw = measure('KI-Tricks', f), pw = tw + 90, ph = 132, cy = 1345;
    x.save(); x.translate(L + pw / 2, cy); x.scale(sc, sc); x.fillStyle = ACC; x.fillRect(-pw / 2, -ph / 2, pw, ph);
    setFont(f); x.fillStyle = K_INK; x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText('KI-Tricks', 0, 5); x.restore();
  }
  x.restore();
}

window.EDIT = {
  dur: at(36), loop: true, accent: LIME, grain: .22, assets: {},
  shots: [
    { a: 0, b: at(4), f: (l, t) => { hook(l, t); bar(t, t < BEAT ? K_INK : LIME); } },
    { a: at(4), b: at(10), f: (l, t) => { step1(l, t); bar(t, K_INK); } },
    { a: at(10), b: at(20), f: (l, t) => { step2(l, t); bar(t, K_INK); } },
    { a: at(20), b: at(30), f: (l, t) => { step3(l, t); bar(t, LIME); } },
    { a: at(30), b: at(36), f: (l, t) => { cta(l, t); bar(t, LIME); } },
  ],
  fx: [
    { type: 'flash', t: 0, a: .22 },
    { type: 'flash', t: at(1), a: .3 },
    { type: 'flash', t: at(2), a: .4 },
    { type: 'whip', t: at(10), w: .1 },
    { type: 'whip', t: at(20), w: .1, dir: -1 },
    { type: 'leak', t: at(30) },
  ],
};
