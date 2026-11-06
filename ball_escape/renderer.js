/*
 * Renderer (Browser, Canvas 2D) für die Ball-Escape-Simulation.
 * Stil #1 "Neon Rainbow Rings on Black": schwarzer Hintergrund, Regenbogen-Ringe mit Glow,
 * weißer Ball mit Trail, Splitter + Funken beim Zerbrechen, Bloom, Screen-Shake, Zähler.
 *
 * API (window.BE):
 *   BE.setup(opts)        -> { totalFrames, fps, ... }   (startet Timeline + Renderer neu)
 *   BE.renderFrame(k)     -> zeichnet Frame k (sequenziell), gibt JPEG-DataURL zurück wenn opts.capture
 *   BE.simulate(opts)     -> Events + Länge ohne Zeichnen (für Audio)
 *   BE.findSeed(opts)     -> Seed-Suche (siehe sim.js)
 */
(function () {
  'use strict';
  const { Timeline, findSeed, resolve, mulberry32, TAU } = window.BallSim;

  const W = 1080;
  const H = 1920;
  const FONT_HOOK = '"Montserrat Black", "Montserrat", "Arial Black", sans-serif';
  const FONT_MONO = '"JetBrains Mono", "Consolas", monospace';
  const FONT_IT = '"Montserrat BlackItalic", "Montserrat Black", "Arial Black", sans-serif';

  // Texte (Großbuchstaben, kurz – wie die erfolgreichsten Accounts der Nische)
  const TEXT = {
    de: {
      qRings: (n) => `KANN DER BALL ${n} RINGE ZERSTÖREN?`,
      qBox: 'WIE SCHNELL ERKENNST DU DEN SONG?',
      qBoxAsmr: (n) => `SCHAFFT ER ${n} BÄLLE?`,
      ruleRings: (song, dbl) => (dbl ? '×2 BÄLLE' : '+2 BÄLLE') + (song ? ' & 1 INSTRUMENT PRO RING' : ' BEI JEDEM RING'),
      ruleBox: '+2 BÄLLE BEI JEDEM ENTKOMMEN',
      balls: 'BÄLLE', rings: 'RINGE', goal: 'ZIEL', ballsBang: 'BÄLLE!', fullSong: ' = GANZER SONG!',
      teaserRings: (n) => `TEIL 2: ${n} RINGE`, teaserBox: (n) => `TEIL 2: ${n} BÄLLE`, follow: 'FOLGEN, UM ES ZU SEHEN!',
      layers: {},
    },
    en: {
      qRings: (n) => `CAN THE BALL BREAK ${n} RINGS?`,
      qBox: 'HOW FAST CAN YOU GUESS THE SONG?',
      qBoxAsmr: (n) => `CAN IT REACH ${n} BALLS?`,
      ruleRings: (song, dbl) => (dbl ? '×2 BALLS' : '+2 BALLS') + (song ? ' & 1 INSTRUMENT PER RING' : ' EACH RING'),
      ruleBox: '+2 BALLS EACH ESCAPE',
      balls: 'BALLS', rings: 'RINGS', goal: 'GOAL', ballsBang: 'BALLS!', fullSong: ' = FULL SONG!',
      teaserRings: (n) => `PART 2: ${n} RINGS`, teaserBox: (n) => `PART 2: ${n} BALLS`, follow: 'FOLLOW FOR PART 2!',
      layers: { kick: 'Beat', pluck: 'Melody', bass: 'Bass', hats: 'Hi-Hats', pad: 'Synth Pads', clap: 'Clap', arp: 'Arpeggio',
        lead: 'Lead Synth', bell: 'Bells', perc: 'Percussion', stabs: 'Sub & Stabs', harmony: 'Harmony' },
    },
  };

  let o, tl, cv, ctx, scale;
  let bloomQ, bloomQctx, bloomH, bloomHctx;
  let rng, particles, shards, popups, ringFlash, trails, shake, flashUntil;
  let lastEvents = [];
  let song = null;
  let songStart = -1;
  let spriteCache = {};
  let skinCache = {};
  let stars = null;
  let initBall = null;
  let T = TEXT.de;
  let fontsReady = false;

  const fmt = (n) => n.toLocaleString(T === TEXT.en ? 'en-US' : 'de-DE');
  const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
  const ease = (x) => 1 - Math.pow(1 - clamp(x, 0, 1), 3);
  const ringHue = (i, vt) => (i * 30 + vt * 20) % 360;

  function canvas(w, h) {
    const c = document.createElement('canvas');
    c.width = w;
    c.height = h;
    return c;
  }

  function glowSprite(hue) {
    const key = Math.round(hue / 10) % 36;
    if (spriteCache[key]) return spriteCache[key];
    const s = 64;
    const c = canvas(s, s);
    const g = c.getContext('2d');
    const gr = g.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2);
    gr.addColorStop(0, 'rgba(255,255,255,1)');
    gr.addColorStop(0.28, 'rgba(255,255,255,1)');
    gr.addColorStop(0.36, `hsla(${key * 10},100%,65%,0.95)`);
    gr.addColorStop(0.6, `hsla(${key * 10},100%,55%,0.35)`);
    gr.addColorStop(1, `hsla(${key * 10},100%,50%,0)`);
    g.fillStyle = gr;
    g.fillRect(0, 0, s, s);
    return (spriteCache[key] = c);
  }

  /* Figuren statt einfacher Bälle (selbst gezeichnet, keine fremden Bilder) */
  function skinSprite(kind, variant) {
    const key = kind + variant;
    if (skinCache[key]) return skinCache[key];
    const S = 128;
    const c = canvas(S, S);
    const g = c.getContext('2d');
    const m = S / 2;
    if (kind === 'smiley') {
      const gr = g.createRadialGradient(m - 14, m - 18, 6, m, m, 58);
      gr.addColorStop(0, '#FFF59A');
      gr.addColorStop(0.55, '#FFD60A');
      gr.addColorStop(1, '#E59A00');
      g.fillStyle = gr;
      g.beginPath(); g.arc(m, m, 58, 0, TAU); g.fill();
      g.fillStyle = '#2B1A00';
      for (const dx of [-19, 19]) { g.beginPath(); g.ellipse(m + dx, m - 14, 7, 12, 0, 0, TAU); g.fill(); }
      g.strokeStyle = '#2B1A00'; g.lineWidth = 8; g.lineCap = 'round';
      g.beginPath(); g.arc(m, m + 2, 32, 0.18 * Math.PI, 0.82 * Math.PI); g.stroke();
    } else if (kind === 'cat') {
      const fur = [['#FFFFFF', '#D9D9E0'], ['#FFB65C', '#E07B1F'], ['#A7A9B4', '#6E7180'], ['#3A3A44', '#1E1E26']][variant % 4];
      const gr = g.createRadialGradient(m - 10, m - 6, 6, m, m + 8, 56);
      gr.addColorStop(0, fur[0]); gr.addColorStop(1, fur[1]);
      g.fillStyle = gr;
      g.beginPath(); g.moveTo(m - 48, m - 8); g.lineTo(m - 44, m - 60); g.lineTo(m - 10, m - 40); g.closePath(); g.fill();
      g.beginPath(); g.moveTo(m + 48, m - 8); g.lineTo(m + 44, m - 60); g.lineTo(m + 10, m - 40); g.closePath(); g.fill();
      g.beginPath(); g.arc(m, m + 8, 50, 0, TAU); g.fill();
      g.fillStyle = '#FF9EB5';
      g.beginPath(); g.moveTo(m - 40, m - 18); g.lineTo(m - 38, m - 46); g.lineTo(m - 18, m - 34); g.closePath(); g.fill();
      g.beginPath(); g.moveTo(m + 40, m - 18); g.lineTo(m + 38, m - 46); g.lineTo(m + 18, m - 34); g.closePath(); g.fill();
      const eye = variant % 4 === 3 ? '#B8F55A' : '#1A1A22';
      for (const dx of [-18, 18]) {
        g.fillStyle = eye; g.beginPath(); g.ellipse(m + dx, m + 2, 8, 11, 0, 0, TAU); g.fill();
        g.fillStyle = '#fff'; g.beginPath(); g.arc(m + dx + 3, m - 3, 3, 0, TAU); g.fill();
      }
      g.fillStyle = '#FF7A9A'; g.beginPath(); g.moveTo(m - 6, m + 16); g.lineTo(m + 6, m + 16); g.lineTo(m, m + 23); g.closePath(); g.fill();
      g.strokeStyle = variant % 4 === 3 ? '#ccc' : '#444'; g.lineWidth = 2;
      for (const sgn of [-1, 1]) for (const dy of [-4, 4]) { g.beginPath(); g.moveTo(m + sgn * 14, m + 22); g.lineTo(m + sgn * 46, m + 18 + dy * 2); g.stroke(); }
    } else if (kind === 'faces') {
      // Gesichter mit Ausdruck (eigene Zeichnung): erschrocken, lachend, cool, wütend, verliebt
      const v = variant % 5;
      const base = v === 3 ? ['#FFB0A0', '#FF6B4A', '#D9342B'] : ['#FFF59A', '#FFD60A', '#E59A00'];
      const gr = g.createRadialGradient(m - 14, m - 18, 6, m, m, 58);
      gr.addColorStop(0, base[0]); gr.addColorStop(0.55, base[1]); gr.addColorStop(1, base[2]);
      g.fillStyle = gr; g.beginPath(); g.arc(m, m, 58, 0, TAU); g.fill();
      const ink = '#2B1A00';
      g.fillStyle = ink; g.strokeStyle = ink; g.lineCap = 'round';
      if (v === 0) { // erschrocken
        for (const dx of [-20, 20]) { g.fillStyle = '#fff'; g.beginPath(); g.arc(m + dx, m - 12, 13, 0, TAU); g.fill(); g.fillStyle = ink; g.beginPath(); g.arc(m + dx, m - 10, 6, 0, TAU); g.fill(); }
        g.beginPath(); g.ellipse(m, m + 26, 11, 15, 0, 0, TAU); g.fill();
      } else if (v === 1) { // lachend
        g.lineWidth = 7;
        for (const dx of [-20, 20]) { g.beginPath(); g.arc(m + dx, m - 8, 10, Math.PI * 1.1, Math.PI * 1.9); g.stroke(); }
        g.beginPath(); g.arc(m, m + 6, 30, 0, Math.PI); g.closePath(); g.fill();
        g.fillStyle = '#FF7A9A'; g.beginPath(); g.arc(m, m + 26, 12, 0, Math.PI); g.fill();
      } else if (v === 2) { // cool mit Sonnenbrille
        g.fillRect(m - 44, m - 22, 88, 8);
        for (const dx of [-21, 21]) { g.beginPath(); g.ellipse(m + dx, m - 12, 18, 13, 0, 0, TAU); g.fill(); }
        g.lineWidth = 7; g.beginPath(); g.arc(m + 6, m + 14, 22, 0.15 * Math.PI, 0.6 * Math.PI); g.stroke();
      } else if (v === 3) { // wütend
        g.lineWidth = 7;
        g.beginPath(); g.moveTo(m - 34, m - 30); g.lineTo(m - 10, m - 18); g.stroke();
        g.beginPath(); g.moveTo(m + 34, m - 30); g.lineTo(m + 10, m - 18); g.stroke();
        for (const dx of [-20, 20]) { g.beginPath(); g.arc(m + dx, m - 6, 6, 0, TAU); g.fill(); }
        g.beginPath(); g.arc(m, m + 38, 20, 1.15 * Math.PI, 1.85 * Math.PI); g.stroke();
      } else { // verliebt
        g.fillStyle = '#E8173A';
        for (const dx of [-21, 21]) {
          const x = m + dx, y = m - 12;
          g.beginPath(); g.moveTo(x, y + 12); g.bezierCurveTo(x - 20, y - 2, x - 9, y - 16, x, y - 5); g.bezierCurveTo(x + 9, y - 16, x + 20, y - 2, x, y + 12); g.fill();
        }
        g.lineWidth = 7; g.beginPath(); g.arc(m, m + 6, 26, 0.15 * Math.PI, 0.85 * Math.PI); g.stroke();
      }
    } else if (kind === 'egg') {
      const gr = g.createRadialGradient(m - 14, m - 20, 4, m, m + 6, 60);
      gr.addColorStop(0, '#FFFDF5'); gr.addColorStop(0.6, '#F6E7C8'); gr.addColorStop(1, '#D9BF8C');
      g.fillStyle = gr;
      g.beginPath(); g.ellipse(m, m + 4, 44, 58, 0, 0, TAU); g.fill();
      g.fillStyle = 'rgba(255,255,255,0.7)'; g.beginPath(); g.ellipse(m - 16, m - 24, 8, 14, -0.4, 0, TAU); g.fill();
    }
    return (skinCache[key] = c);
  }

  function drawStars(vt) {
    if (!stars) {
      const r = mulberry32(4242);
      stars = [];
      for (let i = 0; i < 160; i++) stars.push({ x: r() * W, y: r() * H, s: 0.8 + r() * 1.8, ph: r() * TAU, sp: 0.6 + r() * 1.6 });
    }
    ctx.fillStyle = '#fff';
    for (const st of stars) {
      ctx.globalAlpha = 0.12 + 0.18 * (0.5 + 0.5 * Math.sin(vt * st.sp + st.ph));
      ctx.fillRect(st.x - st.s / 2, st.y - st.s / 2, st.s, st.s);
    }
    ctx.globalAlpha = 1;
  }

  async function loadFonts() {
    if (fontsReady) return;
    const faces = [
      new FontFace('Montserrat Black', 'url(fonts/Montserrat-Black.ttf)'),
      new FontFace('Montserrat BlackItalic', 'url(fonts/Montserrat-BlackItalic.ttf)'),
      new FontFace('JetBrains Mono', 'url(fonts/JetBrainsMono-Bold.ttf)', { weight: '700' }),
    ];
    for (const f of faces) {
      try {
        document.fonts.add(await f.load());
      } catch (e) {
        console.warn('Font nicht geladen:', f.family, e);
      }
    }
    fontsReady = true;
  }

  function setup(opts) {
    o = resolve(opts);
    tl = new Timeline(o);
    scale = o.renderScale || 1;
    cv = document.getElementById('stage');
    cv.width = Math.round(W * scale);
    cv.height = Math.round(H * scale);
    ctx = cv.getContext('2d');
    bloomQ = canvas(Math.round(cv.width / 4), Math.round(cv.height / 4));
    bloomQctx = bloomQ.getContext('2d');
    bloomH = canvas(Math.round(cv.width / 2), Math.round(cv.height / 2));
    bloomHctx = bloomH.getContext('2d');
    rng = mulberry32(((o.seed >>> 0) ^ 0x9e3779b9) >>> 0);
    particles = [];
    shards = [];
    popups = [];
    ringFlash = new Float32Array(o.rings);
    trails = new Map();
    shake = { t0: -1, dur: 0, amp: 0 };
    flashUntil = -1;
    song = o.song && o.music !== 'bounce' && o.music !== 'asmr' && window.Melodies ? window.Melodies.compile(o.song) : null;
    songStart = -1;
    T = TEXT[o.lang] || TEXT.de;
    if (!o.skin) o.skin = 'smiley';
    const b0 = tl.sim.balls[0];
    initBall = { x: b0.x, y: b0.y, id: b0.id, born: 0 };
    return { fps: o.fps, seed: o.seed, rings: o.rings, mode: o.mode, scene: o.scene };
  }

  /* ---------- Effekte ---------- */

  function spawnBreakFx(ev, vt) {
    const sim = tl.sim;
    const ring = sim.rings[ev.ring];
    const hue = ringHue(ring.i, vt);
    const gc = sim.gapCenter(ring, sim.t);
    const span = TAU - 2 * ring.half;
    const pieces = ev.final ? 28 : 18;
    for (let k = 0; k < pieces; k++) {
      const a0 = gc + ring.half + (span * k) / pieces;
      const a1 = a0 + span / pieces;
      const am = (a0 + a1) / 2;
      const sp = 180 + rng() * (ev.final ? 650 : 320);
      shards.push({
        x: o.cx + Math.cos(am) * ring.r,
        y: o.cy + Math.sin(am) * ring.r,
        vx: Math.cos(am) * sp - Math.sin(am) * ring.omega * ring.r,
        vy: Math.sin(am) * sp + Math.cos(am) * ring.omega * ring.r,
        rot: am + Math.PI / 2,
        vr: (rng() - 0.5) * 10,
        len: ring.r * (a1 - a0) * 0.9,
        hue,
        life: 0,
        maxLife: 1.1 + rng() * 0.6,
      });
    }
    const n = ev.final ? 220 : 60;
    for (let k = 0; k < n; k++) {
      const a = rng() * TAU;
      const sp = (2 + rng() * 6) * 60 * (ev.final ? 1.8 : 1);
      const onRing = rng() < 0.5;
      const ra = rng() * TAU;
      particles.push({
        x: onRing ? o.cx + Math.cos(ra) * ring.r : ev.x,
        y: onRing ? o.cy + Math.sin(ra) * ring.r : ev.y,
        vx: Math.cos(a) * sp,
        vy: Math.sin(a) * sp,
        size: 2 + rng() * 3,
        hue: (hue + (rng() - 0.5) * 40 + 360) % 360,
        life: 0,
        maxLife: 0.6 + rng() * 0.4,
      });
    }
    shake = { t0: vt, dur: ev.final ? 0.35 : 0.12, amp: ev.final ? 16 : 6 };
    if (ev.final) flashUntil = tl.frame + 3;
    if (o.scene === 'box') return;
    if (songStart < 0) songStart = vt;
    const added = song ? window.Arrangement.layersForRing(ev.ring, o.rings).map(layerLabel) : [];
    popups.push({
      label: added.length ? '+ ' + added.join(' + ') + (ev.final ? T.fullSong : '') : null,
      text: o.mode === 'double' ? '×2' : '+2',
      t0: vt,
      hue,
      big: ev.final,
    });
  }

  const layerLabel = (l) => T.layers[l.id] || l.label;

  function spawnStageFx(ev, vt) {
    // Box-Szene: Meilenstein erreicht -> neues Instrument
    if (songStart < 0) songStart = vt;
    if (!song) {
      // ASMR: Meilenstein = Level-up (passt zum "Ding"-Sound)
      if (o.music === 'asmr') popups.push({ label: ev.final ? 'LEVEL MAX!' : `LEVEL ${ev.k + 1}`, text: null, t0: vt, hue: ringHue(0, vt), big: ev.final, stage: true });
      return;
    }
    const l = window.Arrangement.LAYERS[ev.k];
    popups.push({ label: '+ ' + layerLabel(l) + (ev.final ? T.fullSong : ''), text: null, t0: vt, hue: ringHue(0, vt), big: ev.final, stage: true });
  }

  function spawnEscapeFx(ev, vt) {
    if (popups.filter((p) => p.small).length >= 6) return;
    popups.push({ small: true, text: '+2', x: clamp(ev.x, 80, W - 160), y: clamp(ev.y, 120, H - 420), t0: vt, hue: ringHue(0, vt) });
  }

  function spawnNoteFx(ev) {
    if (ev.ring < ringFlash.length) ringFlash[ev.ring] = 1;
    if (tl.sim.balls.length > 40) return;
    const vt = ev.vt;
    for (let k = 0; k < 5; k++) {
      const a = rng() * TAU;
      const sp = 60 + rng() * 160;
      particles.push({
        x: ev.x,
        y: ev.y,
        vx: Math.cos(a) * sp,
        vy: Math.sin(a) * sp,
        size: 1.5 + rng() * 1.5,
        hue: ringHue(ev.ring, vt),
        life: 0,
        maxLife: 0.35 + rng() * 0.25,
      });
    }
  }

  function updateFx(dt) {
    const g = 540;
    for (const p of particles) {
      p.vy += g * dt;
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      p.vx *= 0.995;
      p.life += dt;
    }
    particles = particles.filter((p) => p.life < p.maxLife);
    for (const s of shards) {
      s.vy += 900 * dt;
      s.x += s.vx * dt;
      s.y += s.vy * dt;
      s.rot += s.vr * dt;
      s.life += dt;
    }
    shards = shards.filter((s) => s.life < s.maxLife);
    for (let i = 0; i < ringFlash.length; i++) ringFlash[i] *= 0.86;
  }

  /* ---------- Zeichnen ---------- */

  /** 1 direkt auf einem Kick-Schlag, klingt schnell ab (Ringe pulsieren im Takt). */
  function beatPulse(vt) {
    if (!song || songStart < 0 || vt < songStart) return 0;
    const bs = 60 / song.bpm;
    const pos = ((vt - songStart) / bs) % song.meter;
    let best = Infinity;
    for (const p of song.drums.kick) {
      let d = pos - p;
      if (d < 0) d += song.meter;
      best = Math.min(best, d);
    }
    return Math.exp(-(best * bs) / 0.11);
  }

  function drawRings(vt, grow) {
    const sim = tl.sim;
    ctx.lineCap = 'round';
    for (const ring of sim.rings) {
      let alive = ring.alive;
      let gc = sim.gapCenter(ring, sim.t);
      let k = 1;
      if (grow) {
        // Outro: Ringe wachsen in Startposition nach (Loop zum ersten Frame)
        const p = ease(grow(ring.i));
        if (p <= 0) continue;
        alive = true;
        k = p;
        gc = ring.gc0;
      }
      if (!alive) continue;
      const f = Math.max(ringFlash[ring.i] || 0, grow ? 0 : beatPulse(vt) * 0.8);
      const hue = grow ? ringHue(ring.i, 0) : ringHue(ring.i, vt);
      ctx.strokeStyle = `hsl(${hue},100%,${60 + 25 * f}%)`;
      ctx.lineWidth = o.stroke + 4 * f;
      ctx.beginPath();
      ctx.arc(o.cx, o.cy, ring.r * k, gc + ring.half, gc + TAU - ring.half);
      ctx.stroke();
    }
  }

  /* Fäden: von jedem Aufprallpunkt (dreht mit dem Ring) zur Figur. Neue Fäden leuchten kurz auf. */
  function drawThreads() {
    const sim = tl.sim;
    const balls = sim.balls;
    const n = balls.length || 1;
    const budget = Math.max(3, Math.min(o.maxAnchors, Math.floor(3200 / n)));
    const t = sim.t;
    const fresh = [];
    ctx.lineCap = 'round';
    ctx.beginPath();
    for (const b of balls) {
      const an = b.anchors;
      if (!an || !an.length || b.dead) continue;
      for (let k = Math.max(0, an.length - budget); k < an.length; k++) {
        const A = an[k];
        const ring = sim.rings[A.ring];
        const ang = A.a + ring.omega * t;
        const x = o.cx + Math.cos(ang) * A.r;
        const y = o.cy + Math.sin(ang) * A.r;
        if (t - A.t < 0.3) fresh.push(x, y, b.x, b.y, t - A.t);
        else {
          ctx.moveTo(x, y);
          ctx.lineTo(b.x, b.y);
        }
      }
    }
    ctx.strokeStyle = 'rgba(255,255,255,' + (n > 200 ? 0.28 : n > 40 ? 0.4 : 0.6) + ')';
    ctx.lineWidth = n > 200 ? 1 : 1.5;
    ctx.stroke();
    for (let i = 0; i < fresh.length; i += 5) {
      const f = 1 - fresh[i + 4] / 0.3;
      ctx.strokeStyle = `rgba(255,255,255,${0.5 + 0.5 * f})`;
      ctx.lineWidth = 1.5 + 2 * f;
      ctx.beginPath();
      ctx.moveTo(fresh[i], fresh[i + 1]);
      ctx.lineTo(fresh[i + 2], fresh[i + 3]);
      ctx.stroke();
    }
  }

  function drawSkinBall(b, br, vt) {
    const spr = skinSprite(o.skin, b.id % (o.skin === 'faces' ? 5 : 4));
    const s = br * 2.25;
    const spin = (((b.id * 7) % 9) - 4) * 0.35;
    const a = b.id * 1.7 + vt * spin;
    ctx.save();
    ctx.translate(b.x, b.y);
    ctx.rotate(a);
    ctx.drawImage(spr, -s / 2, -s / 2, s, s);
    ctx.restore();
  }

  function drawBalls(vt) {
    const balls = tl.sim.balls;
    const br = tl.sim.br;
    const n = balls.length;
    if (o.skin !== 'neon') {
      const t = tl.sim.t;
      for (const b of balls) {
        if (b.dead) continue;
        if (b.out && tl.finalFrame < 0) {
          // entkommene Figuren blenden schnell aus (kein Gewusel über dem Hook)
          const a = 1 - (t - b.outT) / 0.6;
          if (a <= 0) continue;
          ctx.globalAlpha = a;
          drawSkinBall(b, br, vt);
          ctx.globalAlpha = 1;
        } else drawSkinBall(b, br, vt);
      }
      return;
    }
    const trailLen = n <= 3 ? 22 : n <= 9 ? 14 : n <= 40 ? 7 : 0;
    ctx.globalCompositeOperation = 'lighter';
    for (const b of balls) {
      if (b.dead) continue;
      const hue = (b.born * 30 + vt * 20 + ((b.id * 47) % 50)) % 360;
      if (trailLen) {
        let tr = trails.get(b.id);
        if (!tr) trails.set(b.id, (tr = []));
        tr.unshift(b.x, b.y);
        if (tr.length > trailLen * 2) tr.length = trailLen * 2;
        const m = tr.length / 2;
        for (let k = m - 1; k >= 1; k--) {
          const f = k / trailLen;
          ctx.globalAlpha = 0.6 * (1 - f);
          ctx.fillStyle = `hsl(${hue},100%,60%)`;
          ctx.beginPath();
          ctx.arc(tr[2 * k], tr[2 * k + 1], br * (1 - 0.7 * f), 0, TAU);
          ctx.fill();
        }
        ctx.globalAlpha = 1;
      }
      const spr = glowSprite(hue);
      const s = br * (n > 40 ? 3.2 : 4.2);
      ctx.drawImage(spr, b.x - s / 2, b.y - s / 2, s, s);
    }
    ctx.globalCompositeOperation = 'source-over';
    if (n <= 40) {
      for (const b of balls) {
        if (b.dead) continue;
        ctx.fillStyle = '#ffffff';
        ctx.beginPath();
        ctx.arc(b.x, b.y, br * 0.92, 0, TAU);
        ctx.fill();
      }
    }
    if (trails.size > n * 2 + 50) {
      const alive = new Set(balls.map((b) => b.id));
      for (const id of trails.keys()) if (!alive.has(id)) trails.delete(id);
    }
  }

  function drawFx() {
    ctx.globalCompositeOperation = 'lighter';
    ctx.lineCap = 'round';
    for (const s of shards) {
      const a = 1 - s.life / s.maxLife;
      ctx.globalAlpha = a;
      ctx.strokeStyle = `hsl(${s.hue},100%,62%)`;
      ctx.lineWidth = o.stroke;
      const dx = (Math.cos(s.rot) * s.len) / 2;
      const dy = (Math.sin(s.rot) * s.len) / 2;
      ctx.beginPath();
      ctx.moveTo(s.x - dx, s.y - dy);
      ctx.lineTo(s.x + dx, s.y + dy);
      ctx.stroke();
    }
    for (const p of particles) {
      const a = 1 - p.life / p.maxLife;
      ctx.globalAlpha = a;
      ctx.fillStyle = `hsl(${p.hue},100%,${65 + 20 * a}%)`;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size * (0.5 + 0.5 * a), 0, TAU);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = 'source-over';
  }

  function bloom() {
    // Szene verkleinern + weichzeichnen + additiv zurück: billiger, schöner Glow
    bloomQctx.globalCompositeOperation = 'copy';
    bloomQctx.filter = 'blur(5px)';
    bloomQctx.drawImage(cv, 0, 0, bloomQ.width, bloomQ.height);
    bloomQctx.filter = 'none';
    bloomHctx.globalCompositeOperation = 'copy';
    bloomHctx.filter = 'blur(3px)';
    bloomHctx.drawImage(cv, 0, 0, bloomH.width, bloomH.height);
    bloomHctx.filter = 'none';
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.imageSmoothingQuality = 'high';
    ctx.globalCompositeOperation = 'lighter';
    const soft = o.skin && o.skin !== 'neon'; // Figuren: weniger Glow, damit Gesichter erkennbar bleiben
    ctx.globalAlpha = soft ? 0.4 : 0.9;
    ctx.drawImage(bloomQ, 0, 0, cv.width, cv.height);
    ctx.globalAlpha = soft ? 0.2 : 0.55;
    ctx.drawImage(bloomH, 0, 0, cv.width, cv.height);
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = 'source-over';
  }

  function fitFont(text, family, size, maxW) {
    ctx.font = `${size}px ${family}`;
    const w = ctx.measureText(text).width;
    if (w > maxW) {
      size = Math.floor((size * maxW) / w);
      ctx.font = `${size}px ${family}`;
    }
    return size;
  }

  function outlinedText(text, x, y, family, size, maxW, fill, strokeW) {
    fitFont(text, family, size, maxW);
    ctx.textAlign = 'center';
    ctx.textBaseline = 'alphabetic';
    ctx.lineJoin = 'round';
    ctx.lineWidth = strokeW || 12;
    ctx.strokeStyle = '#000';
    ctx.strokeText(text, x, y);
    ctx.fillStyle = fill || '#fff';
    ctx.fillText(text, x, y);
  }

  function wrapLines(text, family, size, maxW) {
    ctx.font = `${size}px ${family}`;
    const words = text.split(' ');
    const lines = [];
    let cur = '';
    for (const w of words) {
      const test = cur ? cur + ' ' + w : w;
      if (cur && ctx.measureText(test).width > maxW) {
        lines.push(cur);
        cur = w;
      } else cur = test;
    }
    if (cur) lines.push(cur);
    return lines;
  }

  function hookLines() {
    if (o.hook) return o.hook.split('|');
    const q = o.scene === 'box' ? (o.music === 'asmr' && o.asmr !== 'dropmelody' ? T.qBoxAsmr(fmt(o.goal)) : T.qBox) : T.qRings(o.rings);
    return wrapLines(q, FONT_IT, 64, 900);
  }

  function ruleText() {
    if (o.subline != null) return o.subline;
    return o.scene === 'box' ? T.ruleBox : T.ruleRings(!!song, o.mode === 'double');
  }

  function drawHeader(alpha) {
    if (alpha <= 0) return;
    ctx.globalAlpha = alpha;
    const lines = hookLines();
    // erste Zeile ab y≈290: darüber liegt in der TikTok-App die Such-/Tab-Leiste
    const top = (o.scene === 'box' ? 246 : 226) + (2 - lines.length) * 36;
    lines.forEach((ln, i) => outlinedText(ln, 540, top + 64 + i * 72, FONT_IT, 64, 920, '#fff', 10));
    // Regel als weißes Label (gut lesbar, sofort verständlich)
    const rule = ruleText();
    if (rule) {
      const y = top + 64 + lines.length * 72 + 4;
      const size = fitFont(rule, FONT_IT, 40, 820);
      const w = ctx.measureText(rule).width + 44;
      ctx.fillStyle = '#fff';
      ctx.fillRect(540 - w / 2, y - size * 0.95, w, size * 1.3);
      ctx.fillStyle = '#000';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'alphabetic';
      ctx.fillText(rule, 540, y);
    }
    ctx.globalAlpha = 1;
  }

  function hudCount() {
    const sim = tl.sim;
    if (tl.finalFrame >= 0) return lastBallCount();
    return o.scene === 'box' ? sim.inside : sim.balls.length;
  }

  function drawHud(alpha, startState) {
    if (alpha <= 0) return;
    ctx.globalAlpha = alpha;
    const sim = tl.sim;
    const n = startState ? 1 : hudCount();
    outlinedText(`${T.balls}: ${fmt(n)}`, 540, 1458, FONT_IT, 66, 860, '#fff', 10);
    const second = o.scene === 'box'
      ? `${T.goal}: ${fmt(o.goal)}`
      : `${T.rings}: ${startState ? o.rings : sim.ringsLeft}/${o.rings}`;
    outlinedText(second, 540, 1518, FONT_IT, 34, 860, '#9FB3C8', 8);
    ctx.globalAlpha = 1;
  }

  function drawText(vt, alphaHook, alphaHud) {
    drawHeader(alphaHook);
    drawHud(alphaHud, false);
  }

  function lastBallCount() {
    const br = tl.log.filter((e) => e.type === 'break').pop();
    return br ? br.balls : 1;
  }

  function drawPopups(vt) {
    for (const p of popups) {
      const age = vt - p.t0;
      if (p.small) {
        if (age < 0 || age > 0.8) continue;
        ctx.globalAlpha = 1 - (age / 0.8) ** 2;
        outlinedText(p.text, p.x, p.y - 80 * ease(age / 0.8), FONT_IT, 52, 300, `hsl(${p.hue},100%,72%)`, 9);
        continue;
      }
      const dur = p.big ? 0.55 : 0.7;
      if (age < 0 || age > (p.label ? (p.big ? 2.7 : 1.5) : dur)) continue;
      const f = Math.min(1, age / dur);
      const size = (p.big ? 170 : 110) * (0.8 + 0.6 * ease(f));
      ctx.globalAlpha = p.text ? 1 - f * f : 0;
      ctx.font = `${size}px ${FONT_IT}`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.lineJoin = 'round';
      ctx.lineWidth = 10;
      ctx.strokeStyle = '#000';
      ctx.strokeText(p.text, o.cx, o.cy);
      ctx.fillStyle = `hsl(${p.hue},100%,70%)`;
      ctx.fillText(p.text, o.cx, o.cy);
      if (p.label) {
        // Instrument bleibt länger stehen als das "+2"
        const la = clamp(1 - (age - (p.big ? (o.loop === 'seamless' ? 0.9 : 2.2) : 1.0)) / 0.4, 0, 1) * clamp(age / 0.12, 0, 1);
        if (la > 0) {
          ctx.globalAlpha = la;
          ctx.textBaseline = 'alphabetic';
          const ly = p.big ? o.cy - 300 : p.stage ? o.cy + 20 : o.cy + 110;
          outlinedText(p.label.toUpperCase(), o.cx, ly, FONT_IT, p.big ? 56 : 54, 880, p.big ? '#FFD60A' : '#fff', 11);
        }
      }
    }
    ctx.globalAlpha = 1;
    popups = popups.filter((p) => vt - p.t0 < (p.small ? 0.8 : 3));
  }

  function drawOutroCard(since, untilEnd) {
    if (o.loop === 'seamless') return; // nahtloser Loop: keine Schlusstafel, direkt zurück zum Start
    // Großer End-Zähler + Teil-2-Teaser
    const a = clamp((since - 0.6) / 0.4, 0, 1) * clamp((untilEnd - 2.4) / 0.4, 0, 1);
    if (a <= 0) return;
    const n = lastBallCount();
    const pop = 0.85 + 0.15 * ease((since - 0.6) / 0.35);
    ctx.save();
    ctx.globalAlpha = a;
    ctx.translate(540, o.cy - 20);
    ctx.scale(pop, pop);
    ctx.textAlign = 'center';
    ctx.textBaseline = 'alphabetic';
    ctx.lineJoin = 'round';
    fitFont(fmt(n), FONT_IT, 230, 860);
    ctx.shadowColor = 'hsl(48,100%,55%)';
    ctx.shadowBlur = 40;
    ctx.lineWidth = 14;
    ctx.strokeStyle = '#000';
    ctx.strokeText(fmt(n), 0, 0);
    ctx.fillStyle = '#FFD60A';
    ctx.fillText(fmt(n), 0, 0);
    ctx.shadowBlur = 0;
    outlinedText(T.ballsBang, 0, 120, FONT_IT, 100, 860);
    ctx.restore();
    const b = clamp((since - 1.5) / 0.4, 0, 1) * clamp((untilEnd - 2.4) / 0.4, 0, 1);
    if (b > 0) {
      ctx.globalAlpha = b;
      const teaser = o.teaser != null ? o.teaser : o.scene === 'box' ? T.teaserBox(fmt(o.goal * 10)) : T.teaserRings(o.rings * 2);
      outlinedText(teaser, 540, 1130, FONT_IT, 64, 880, '#fff', 10);
      outlinedText(T.follow, 540, 1200, FONT_IT, 42, 880, '#FFD60A', 8);
      ctx.globalAlpha = 1;
    }
  }

  function renderFrame(k) {
    while (tl.frame < k) {
      const evs = tl.step();
      const vt = tl.frame / o.fps;
      for (const ev of evs) {
        if (ev.type === 'break') spawnBreakFx(ev, vt);
        else if (ev.type === 'note') spawnNoteFx(ev);
        else if (ev.type === 'stage') spawnStageFx(ev, vt);
        else if (ev.type === 'escape' && tl.sim.inside < 150) spawnEscapeFx(ev, vt);
      }
      lastEvents = evs;
      updateFx(tl.timeScale(tl.frame) / o.fps);
    }
    const vt = k / o.fps;
    const total = Number.isFinite(tl.totalFrames) ? tl.totalFrames : Infinity;
    const finalF = tl.finalFrame;
    const since = finalF >= 0 ? (k - finalF) / o.fps : -1;
    const untilEnd = (total - k) / o.fps;

    // Hintergrund
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = 'source-over';
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, cv.width, cv.height);
    const vg = ctx.createRadialGradient(cv.width * 0.48, cv.height * 0.46, cv.width * 0.3, cv.width * 0.5, cv.height * 0.5, cv.height * 0.62);
    vg.addColorStop(0, 'rgba(5,7,13,0)');
    vg.addColorStop(1, 'rgba(5,7,13,1)');
    ctx.fillStyle = vg;
    ctx.fillRect(0, 0, cv.width, cv.height);
    ctx.setTransform(scale, 0, 0, scale, 0, 0);
    drawStars(vt);

    // Szene (mit Screen-Shake)
    let sx = 0;
    let sy = 0;
    if (shake.t0 >= 0 && vt - shake.t0 < shake.dur) {
      const p = 1 - (vt - shake.t0) / shake.dur;
      sx = (rng() * 2 - 1) * shake.amp * p * p;
      sy = (rng() * 2 - 1) * shake.amp * p * p;
    }
    ctx.setTransform(scale, 0, 0, scale, sx * scale, sy * scale);

    const seamless = o.loop === 'seamless';
    const G = seamless ? 1.3 : 2.4; // Dauer: Arena wächst zurück in den Startzustand
    let grow = null;
    if (since >= 0 && untilEnd <= G) {
      const t = G - untilEnd;
      grow = (i) => (t - (i / Math.max(1, o.rings - 1)) * (G * 0.375)) / (G * 0.25);
    }
    if (o.threads && !grow) drawThreads();
    drawRings(vt, grow);
    drawFx();
    if (since < 0 || untilEnd > G) drawBalls(vt);
    if (grow) {
      // Startball erscheint wieder in der Mitte -> nahtloser Loop
      const a = clamp((G - untilEnd - G * 0.42) / (G * 0.2), 0, 1);
      if (a > 0) {
        const br = o.ballR;
        ctx.globalAlpha = a;
        if (o.skin !== 'neon') {
          drawSkinBall(initBall, br, 0);
        } else {
          ctx.globalCompositeOperation = 'lighter';
          ctx.drawImage(glowSprite(ringHue(0, 0)), initBall.x - br * 2.1, initBall.y - br * 2.1, br * 4.2, br * 4.2);
          ctx.globalCompositeOperation = 'source-over';
          ctx.fillStyle = '#fff';
          ctx.beginPath();
          ctx.arc(initBall.x, initBall.y, br * 0.92, 0, TAU);
          ctx.fill();
        }
        ctx.globalAlpha = 1;
      }
    }

    bloom();

    // Text (ohne Bloom, ohne Shake)
    ctx.setTransform(scale, 0, 0, scale, 0, 0);
    if (o.watermark) {
      ctx.globalAlpha = 0.22;
      ctx.font = `44px ${FONT_HOOK}`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = '#fff';
      ctx.fillText(o.watermark, o.cx, o.cy);
      ctx.globalAlpha = 1;
    }
    drawPopups(vt);
    let hookA = 1;
    let hudA = 1;
    if (since >= 0 && !seamless) {
      const fadeOut = 1 - clamp((since - 0.3) / 0.4, 0, 1);
      const fadeIn = clamp((2.0 - untilEnd) / 0.6, 0, 1);
      hookA = Math.max(fadeOut, fadeIn);
      hudA = Math.max(fadeOut, fadeIn);
    }
    drawOutroCard(since, untilEnd);
    if (since >= 0 && untilEnd < (seamless ? 0.45 : 2.0)) {
      // Loop-Ende: HUD zeigt wieder den Startzustand
      drawHud(hudA, true);
      drawHeader(hookA);
    } else {
      drawText(vt, hookA, hudA);
    }

    // Weißer Blitz beim finalen Ring
    if (finalF >= 0 && k >= finalF && k < flashUntil) {
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.globalAlpha = 1 - (k - finalF) / 3.5;
      ctx.fillStyle = '#fff';
      ctx.fillRect(0, 0, cv.width, cv.height);
      ctx.globalAlpha = 1;
    }

    if (o.capture) return cv.toDataURL('image/jpeg', o.jpegQuality || 0.95);
    return lastEvents;
  }

  function simulate(opts) {
    const t = new Timeline(opts);
    const s = t.runHeadless();
    s.events = t.log.map((e) => ({ type: e.type, vt: e.vt, midi: e.midi, vel: e.vel, x: e.x, ring: e.ring, final: e.final, balls: e.balls, k: e.k, len: e.len }));
    s.fps = t.o.fps;
    return s;
  }

  window.BE = {
    loadFonts,
    setup,
    renderFrame,
    simulate,
    findSeed,
    info: () => ({ frame: tl.frame, totalFrames: tl.totalFrames, finalFrame: tl.finalFrame, balls: tl.sim.balls.length, breaks: tl.log.filter((e) => e.type === 'break').map((e) => e.frame) }),
    get timeline() {
      return tl;
    },
  };
})();
