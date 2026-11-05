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

  let o, tl, cv, ctx, scale;
  let bloomQ, bloomQctx, bloomH, bloomHctx;
  let rng, particles, shards, popups, ringFlash, trails, shake, flashUntil;
  let lastEvents = [];
  let song = null;
  let songStart = -1;
  let spriteCache = {};
  let fontsReady = false;

  const fmt = (n) => n.toLocaleString('de-DE');
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

  async function loadFonts() {
    if (fontsReady) return;
    const faces = [
      new FontFace('Montserrat Black', 'url(fonts/Montserrat-Black.ttf)'),
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
    song = o.song && o.music !== 'bounce' && window.Melodies ? window.Melodies.compile(o.song) : null;
    songStart = -1;
    return { fps: o.fps, seed: o.seed, rings: o.rings, mode: o.mode };
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
    if (songStart < 0) songStart = vt;
    const added = song ? window.Arrangement.layersForRing(ev.ring, o.rings).map((l) => l.label) : [];
    popups.push({
      label: added.length ? '+ ' + added.join(' + ') + (ev.final ? ' = ganzer Song!' : '') : null,
      text: o.mode === 'double' ? '×2' : '+2',
      t0: vt,
      hue,
      big: ev.final,
    });
    shake = { t0: vt, dur: ev.final ? 0.35 : 0.12, amp: ev.final ? 16 : 6 };
    if (ev.final) flashUntil = tl.frame + 3;
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

  function drawBalls(vt) {
    const balls = tl.sim.balls;
    const br = tl.sim.br;
    const n = balls.length;
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
    ctx.globalAlpha = 0.9;
    ctx.drawImage(bloomQ, 0, 0, cv.width, cv.height);
    ctx.globalAlpha = 0.55;
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

  function hookLines() {
    if (o.hook) return o.hook.split('|');
    return [`Kann der Ball ${o.rings} Ringe`, 'zerstören?'];
  }

  function subLine() {
    if (o.subline != null) return o.subline;
    if (song) return o.mode === 'double' ? 'Jeder Ring: Bälle ×2 & ein neues Instrument' : 'Jeder Ring: +2 Bälle & ein neues Instrument';
    return o.mode === 'double' ? 'Bälle verdoppeln sich bei jedem Ring' : '+2 Bälle bei jedem Entkommen';
  }

  function drawText(vt, alphaHook, alphaHud) {
    const lines = hookLines();
    if (alphaHook > 0) {
      ctx.globalAlpha = alphaHook;
      lines.forEach((ln, i) => outlinedText(ln, 540, 215 + i * 88, FONT_HOOK, 82, 900));
      outlinedText(subLine(), 540, 215 + lines.length * 88 - 18, FONT_HOOK, 40, 860, '#FFD60A', 9);
      ctx.globalAlpha = 1;
    }
    if (alphaHud > 0) {
      ctx.globalAlpha = alphaHud;
      const sim = tl.sim;
      outlinedText(`Bälle: ${fmt(sim.balls.length && sim.cur < sim.rings.length ? sim.balls.length : lastBallCount())}`, 540, 1462, FONT_MONO, 60, 860, '#fff', 10);
      outlinedText(`Ringe übrig: ${sim.ringsLeft}/${o.rings}`, 540, 1522, FONT_MONO, 38, 860, '#9FB3C8', 8);
      ctx.globalAlpha = 1;
    }
  }

  function lastBallCount() {
    const br = tl.log.filter((e) => e.type === 'break').pop();
    return br ? br.balls : 1;
  }

  function drawPopups(vt) {
    for (const p of popups) {
      const age = vt - p.t0;
      const dur = p.big ? 0.55 : 0.7;
      if (age < 0 || age > (p.label ? (p.big ? 2.7 : 1.5) : dur)) continue;
      const f = Math.min(1, age / dur);
      const size = (p.big ? 170 : 110) * (0.8 + 0.6 * ease(f));
      ctx.globalAlpha = 1 - f * f;
      ctx.font = `${size}px ${FONT_HOOK}`;
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
        const la = clamp(1 - (age - (p.big ? 2.2 : 1.0)) / 0.5, 0, 1) * clamp(age / 0.12, 0, 1);
        if (la > 0) {
          ctx.globalAlpha = la;
          ctx.textBaseline = 'alphabetic';
          outlinedText(p.label, o.cx, p.big ? o.cy - 300 : o.cy + 110, FONT_HOOK, p.big ? 58 : 54, 880, p.big ? '#FFD60A' : '#fff', 10);
        }
      }
    }
    ctx.globalAlpha = 1;
    popups = popups.filter((p) => vt - p.t0 < 3);
  }

  function drawOutroCard(since, untilEnd) {
    // Großer End-Zähler + Teil-2-Teaser
    const a = clamp((since - 0.6) / 0.4, 0, 1) * clamp((untilEnd - 2.4) / 0.4, 0, 1);
    if (a <= 0) return;
    const n = lastBallCount();
    const pop = 0.85 + 0.15 * ease((since - 0.6) / 0.35);
    ctx.save();
    ctx.globalAlpha = a;
    ctx.translate(540, 860);
    ctx.scale(pop, pop);
    ctx.textAlign = 'center';
    ctx.textBaseline = 'alphabetic';
    ctx.lineJoin = 'round';
    fitFont(fmt(n), FONT_HOOK, 230, 860);
    ctx.shadowColor = 'hsl(48,100%,55%)';
    ctx.shadowBlur = 40;
    ctx.lineWidth = 14;
    ctx.strokeStyle = '#000';
    ctx.strokeText(fmt(n), 0, 0);
    ctx.fillStyle = '#FFD60A';
    ctx.fillText(fmt(n), 0, 0);
    ctx.shadowBlur = 0;
    outlinedText('BÄLLE!', 0, 120, FONT_HOOK, 100, 860);
    ctx.restore();
    const b = clamp((since - 1.5) / 0.4, 0, 1) * clamp((untilEnd - 2.4) / 0.4, 0, 1);
    if (b > 0) {
      ctx.globalAlpha = b;
      const teaser = o.teaser != null ? o.teaser : `Teil 2: ${o.rings * 2} Ringe`;
      outlinedText(teaser, 540, 1130, FONT_HOOK, 64, 880, '#fff', 10);
      outlinedText('Folgen, um es zu sehen!', 540, 1200, FONT_HOOK, 42, 880, '#FFD60A', 8);
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

    // Szene (mit Screen-Shake)
    let sx = 0;
    let sy = 0;
    if (shake.t0 >= 0 && vt - shake.t0 < shake.dur) {
      const p = 1 - (vt - shake.t0) / shake.dur;
      sx = (rng() * 2 - 1) * shake.amp * p * p;
      sy = (rng() * 2 - 1) * shake.amp * p * p;
    }
    ctx.setTransform(scale, 0, 0, scale, sx * scale, sy * scale);

    let grow = null;
    if (since >= 0 && untilEnd <= 2.4) {
      const t = 2.4 - untilEnd; // 0..2.4
      grow = (i) => (t - (i / Math.max(1, o.rings - 1)) * 0.9) / 0.6;
    }
    drawRings(vt, grow);
    drawFx();
    if (since < 0 || untilEnd > 2.4) drawBalls(vt);
    if (grow) {
      // Startball erscheint wieder in der Mitte -> nahtloser Loop
      const a = clamp((2.4 - untilEnd - 1.0) / 0.5, 0, 1);
      if (a > 0) {
        const br = o.ballR;
        ctx.globalAlpha = a;
        ctx.globalCompositeOperation = 'lighter';
        ctx.drawImage(glowSprite(ringHue(0, 0)), o.cx - br * 2.1, o.cy - br * 2.1, br * 4.2, br * 4.2);
        ctx.globalCompositeOperation = 'source-over';
        ctx.fillStyle = '#fff';
        ctx.beginPath();
        ctx.arc(o.cx, o.cy, br * 0.92, 0, TAU);
        ctx.fill();
        ctx.globalAlpha = 1;
      }
    }

    bloom();

    // Text (ohne Bloom, ohne Shake)
    ctx.setTransform(scale, 0, 0, scale, 0, 0);
    drawPopups(vt);
    let hookA = 1;
    let hudA = 1;
    if (since >= 0) {
      const fadeOut = 1 - clamp((since - 0.3) / 0.4, 0, 1);
      const fadeIn = clamp((2.0 - untilEnd) / 0.6, 0, 1);
      hookA = Math.max(fadeOut, fadeIn);
      hudA = Math.max(fadeOut, fadeIn);
    }
    drawOutroCard(since, untilEnd);
    if (since >= 0 && untilEnd < 2.0) {
      // Loop-Ende: HUD zeigt wieder den Startzustand
      ctx.globalAlpha = hudA;
      outlinedText('Bälle: 1', 540, 1462, FONT_MONO, 60, 860, '#fff', 10);
      outlinedText(`Ringe übrig: ${o.rings}/${o.rings}`, 540, 1522, FONT_MONO, 38, 860, '#9FB3C8', 8);
      ctx.globalAlpha = 1;
      drawText(vt, hookA, 0);
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
    s.events = t.log.map((e) => ({ type: e.type, vt: e.vt, midi: e.midi, vel: e.vel, x: e.x, ring: e.ring, final: e.final, balls: e.balls }));
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
