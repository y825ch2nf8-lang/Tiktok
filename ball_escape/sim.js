/*
 * Ball-Escape – deterministische Physik-Simulation.
 *
 * Fester Zeitschritt (1/240 s), geseedeter PRNG (mulberry32), kein Zufall aus Date/Math.random.
 * Gleicher Seed + gleiche Optionen => exakt gleiches Video. Läuft im Browser (window.BallSim)
 * und in Node (require('./sim.js')).
 *
 * Mechanik: Bälle springen in konzentrischen, rotierenden Ringen mit Lücke. Sobald ein Ball durch
 * die Lücke des innersten Rings entkommt, zerbricht der Ring und die Bälle vermehren sich
 * (mode 'double' = verdoppeln, mode 'plus2' = +2 neue Bälle in der Mitte).
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.BallSim = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const TAU = Math.PI * 2;
  const PHYSICS_HZ = 240;

  function mulberry32(seed) {
    let a = seed >>> 0;
    return function () {
      a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function wrapPi(a) {
    a = (a + Math.PI) % TAU;
    if (a < 0) a += TAU;
    return a - Math.PI;
  }

  const DEFAULTS = {
    seed: 1,
    width: 1080,
    height: 1920,
    cx: 520, // leicht links: rechts liegt die TikTok-Buttonleiste
    cy: 930, // tiefer: oben liegt die TikTok-Such-/Tab-Leiste über dem Hook
    rings: 12,
    innerR: 90,
    outerMax: 464,
    stroke: 5,
    gapStartDeg: 30, // Lücke innerster Ring (auf ~60 s Videolänge abgestimmt)
    gapEndDeg: 5.5, // Lücke äußerster Ring
    omegaMin: 0.4, // rad/s
    omegaMax: 1.2,
    gravity: 800, // px/s²
    ballR: 14,
    ballRMin: 4,
    shrink: 0.88, // Ballradius-Faktor pro Verdopplung
    startSpeed: 500,
    minBounce: 220, // Mindest-Abprallgeschwindigkeit (Ball "stirbt" nie)
    maxSpeed: 2600, // < ballRMin * 240 * ... -> kein Tunneln bei 1/240 s
    mode: 'plus2', // 'plus2' (+2 Bälle je Ring, ~60 s) | 'double' (verdoppeln, kurz & chaotisch)
    maxBalls: 8192,
    fps: 60,
    melody: null, // Array aus MIDI-Noten; jede Kollision spielt die nächste Note
    noteMinGap: 1 / 14, // max. ~14 Noten/s, damit es in der Chaos-Phase nicht übersteuert
    slowmoDur: 1.4, // Zeitlupe nach dem letzten Ring (Videosekunden)
    slowmoScale: 0.35,
    outroDur: 7.0, // Videosekunden nach dem letzten Ring bis Videoende
    maxVideoSec: 120,
    threads: false, // Fäden von jedem Aufprallpunkt zur Figur
    maxAnchors: 50,
  };

  // Voreinstellungen je Modus (überschreibbar). 'double' wächst exponentiell -> kurze Clips.
  const PRESETS = {
    plus2: {},
    double: { gapStartDeg: 34, gapEndDeg: 9, gravity: 1100, minBounce: 260, startSpeed: 600 },
  };

  // Szenen: 'rings' = 12 Ringe zerstören. 'box' = eine Arena mit wandernder Lücke, jedes Entkommen = +2 Bälle,
  // der Zähler wächst exponentiell bis zum Ziel (z. B. 1.000) – wie die erfolgreichsten Accounts der Nische.
  const SCENES = {
    rings: {},
    box: {
      gravity: 0, // drinnen schwerelos: gerade Bahnen, Bälle verteilen sich über die ganze Arena
      fallGravity: 1500, // entkommene Bälle fallen raus
      startSpeed: 620,
      minBounce: 0,
      cy: 950,
      boxR: 430,
      boxGapDeg: 55,
      boxOmega: 0.7,
      goal: 1000,
      ballR: 44, // groß am Anfang, damit die Figur sofort erkennbar ist
      ballRMin: 8,
      maxBalls: 6000,
    },
  };

  // Zusatz-Formate (formats.js): dense, layers, battle, press
  let FORMATS = null;
  try {
    FORMATS = typeof module === 'object' && module.exports ? require('./formats.js') : typeof self !== 'undefined' ? self.BallFormats : null;
  } catch (e) {
    FORMATS = null;
  }
  if (FORMATS) Object.assign(SCENES, FORMATS.PRESETS);

  function resolve(opts) {
    const mode = (opts && opts.mode) || DEFAULTS.mode;
    const scene = (opts && opts.scene) || 'rings';
    return Object.assign({ scene }, DEFAULTS, PRESETS[mode] || {}, SCENES[scene] || {}, opts);
  }

  /** Meilensteine (Ballzahlen), an denen in der Box-Szene je ein Instrument dazukommt. Letzter = Ziel. */
  function milestones(goal, n) {
    const out = [];
    for (let k = 1; k <= n; k++) {
      const m = Math.round(Math.pow(goal, k / n));
      out.push(Math.max(m, (out[out.length - 1] || 1) + 1));
    }
    out[n - 1] = Math.max(goal, out[n - 2] + 1);
    return out;
  }

  class Sim {
    constructor(opts) {
      const o = (this.o = resolve(opts));
      if (FORMATS && FORMATS.has(o.scene)) return FORMATS.create(o);
      this.rng = mulberry32((o.seed >>> 0) || 1);
      this.t = 0;
      this.dt = 1 / PHYSICS_HZ;
      this.events = [];
      this.nextId = 0;
      this.gen = 0;
      this.cur = 0;
      this.lastNoteT = -1;
      this.noteIdx = 0;

      const n = o.rings;
      const step = n > 1 ? Math.min(34, (o.outerMax - o.innerR) / (n - 1)) : 0;
      this.rings = [];
      for (let i = 0; i < n; i++) {
        const f = n > 1 ? i / (n - 1) : 0;
        const gapDeg = o.gapStartDeg + (o.gapEndDeg - o.gapStartDeg) * f;
        const speed = o.omegaMin + this.rng() * (o.omegaMax - o.omegaMin);
        this.rings.push({
          i,
          r: o.innerR + i * step,
          half: (gapDeg * Math.PI) / 360,
          omega: i % 2 === 0 ? speed : -speed,
          gc0: this.rng() * TAU,
          alive: true,
          breakT: null,
        });
      }

      this.balls = [];
      this.br = o.ballR;
      if (o.scene === 'box') {
        this.rings = [{ i: 0, r: o.boxR, half: (o.boxGapDeg * Math.PI) / 360, omega: o.boxOmega, gc0: this.rng() * TAU, alive: true, breakT: null }];
        this.inside = 0;
        this.escapes = 0;
        this.stage = 0;
        this.milestones = milestones(o.goal, 12);
        this.spawnInside();
        return;
      }
      const a = this.rng() * TAU;
      this.addBall(o.cx, o.cy, Math.cos(a) * o.startSpeed, Math.sin(a) * o.startSpeed);
    }

    spawnInside() {
      // zufällige Position im inneren Teil der Arena, zufällige Richtung (keine Durchmesser-Bahnen)
      const o = this.o;
      const a = this.rng() * TAU;
      const rr = Math.sqrt(this.rng()) * o.boxR * 0.55;
      const d = this.rng() * TAU;
      const b = this.addBall(o.cx + Math.cos(a) * rr, o.cy + Math.sin(a) * rr, Math.cos(d) * o.startSpeed, Math.sin(d) * o.startSpeed);
      if (b) this.inside++;
      return b;
    }

    boxRadius() {
      const o = this.o;
      return Math.max(o.ballRMin, Math.min(o.ballR, o.ballR * Math.pow(Math.max(1, this.inside) / 3, -0.3)));
    }

    substepBox() {
      const o = this.o;
      const dt = this.dt;
      this.t += dt;
      const t = this.t;
      const ring = this.rings[0];
      let spawn = 0;
      let anyDead = false;
      const balls = this.balls;
      for (let k = 0; k < balls.length; k++) {
        const b = balls[k];
        const free = b.out || !ring.alive;
        b.vy += (free ? o.fallGravity : o.gravity) * dt;
        b.x += b.vx * dt;
        b.y += b.vy * dt;
        if (free) {
          if (b.y > o.height + 80 || b.y < -400 || b.x < -80 || b.x > o.width + 80) {
            b.dead = true;
            anyDead = true;
          }
          continue;
        }
        if (this.collide(b, ring, t)) {
          b.out = true;
          b.outT = t;
          b.anchors = null; // Fäden reißen beim Entkommen
          this.inside--;
          this.escapes++;
          spawn += 2;
          this.events.push({ type: 'escape', t, x: b.x, y: b.y, balls: this.inside + 2 });
        }
      }
      if (spawn) {
        for (let k = 0; k < spawn; k++) this.spawnInside();
        this.br = this.boxRadius();
        while (this.stage < this.milestones.length && this.inside >= this.milestones[this.stage]) {
          const final = this.stage === this.milestones.length - 1;
          this.events.push({ type: 'stage', t, k: this.stage, balls: this.inside, final });
          this.stage++;
          if (final) {
            ring.alive = false;
            ring.breakT = t;
            this.cur = 1;
            this.snapThreads(0);
            this.gen++;
            this.events.push({ type: 'break', t, ring: 0, x: o.cx, y: o.cy, balls: this.inside, final: true });
            // Finale: alle Bälle explodieren nach außen
            for (const b of balls) {
              if (b.out) continue;
              const dx = b.x - o.cx;
              const dy = b.y - o.cy;
              const d = Math.hypot(dx, dy) || 1;
              b.vx += (dx / d) * 500;
              b.vy += (dy / d) * 500 - 400;
            }
          }
        }
      }
      if (anyDead) this.balls = balls.filter((b) => !b.dead);
    }

    addBall(x, y, vx, vy) {
      if (this.balls.length >= this.o.maxBalls) return null;
      const b = { id: this.nextId++, x, y, vx, vy, born: this.gen, dead: false };
      this.balls.push(b);
      return b;
    }

    get ringsLeft() {
      return this.rings.length - this.cur;
    }

    gapCenter(ring, t) {
      return ring.gc0 + ring.omega * t;
    }

    ballRadius() {
      const o = this.o;
      if (o.mode === 'double') return Math.max(o.ballRMin, o.ballR * Math.pow(o.shrink, this.gen));
      return o.ballR;
    }

    bounce(b, nx, ny, ring, relVx, relVy) {
      // n zeigt von der Wand zum Ball. Elastische Reflexion (relativ zur Wandgeschwindigkeit).
      const o = this.o;
      const vn = relVx * nx + relVy * ny;
      if (vn >= 0) return;
      b.vx -= 2 * vn * nx;
      b.vy -= 2 * vn * ny;
      const out = b.vx * nx + b.vy * ny;
      if (out < o.minBounce) {
        b.vx += (o.minBounce - out) * nx;
        b.vy += (o.minBounce - out) * ny;
      }
      const sp = Math.hypot(b.vx, b.vy);
      if (sp > o.maxSpeed) {
        b.vx *= o.maxSpeed / sp;
        b.vy *= o.maxSpeed / sp;
      }
      // Kontaktpunkt an der Wand (für Fäden + Tonhöhe). Ändert die Physik nicht.
      const px = b.x - nx * this.br;
      const py = b.y - ny * this.br;
      b.len = b.hx == null ? 0 : Math.hypot(px - b.hx, py - b.hy);
      b.hx = px;
      b.hy = py;
      if (o.threads) {
        // Winkel im mitdrehenden System des Rings speichern -> Fäden drehen sich mit der Arena
        if (!b.anchors) b.anchors = [];
        b.anchors.push({ a: Math.atan2(py - o.cy, px - o.cx) - ring.omega * this.t, r: Math.hypot(px - o.cx, py - o.cy), ring: ring.i, t: this.t });
        if (b.anchors.length > o.maxAnchors) b.anchors.shift();
      }
      this.onHit(b, -vn, ring);
    }

    onHit(b, speed, ring) {
      const o = this.o;
      if (!o.melody || !o.melody.length) return;
      if (this.t - this.lastNoteT < o.noteMinGap) return;
      this.lastNoteT = this.t;
      const midi = o.melody[this.noteIdx % o.melody.length];
      this.noteIdx++;
      this.events.push({
        type: 'note',
        t: this.t,
        midi,
        vel: 0.45 + 0.55 * Math.min(1, speed / 1400),
        x: b.x,
        y: b.y,
        ring: ring.i,
        len: b.len || 0,
      });
    }

    collide(b, ring, t) {
      const o = this.o;
      const br = this.br;
      const hs = o.stroke / 2;
      const R = ring.r;
      const dx = b.x - o.cx;
      const dy = b.y - o.cy;
      const d = Math.hypot(dx, dy) || 1e-9;

      if (d > R + hs + br) return true; // komplett draußen => entkommen

      const gc = this.gapCenter(ring, t);
      const rel = wrapPi(Math.atan2(dy, dx) - gc);
      const ux = dx / d;
      const uy = dy / d;

      if (Math.abs(rel) >= ring.half) {
        if (d <= R) {
          const lim = R - hs - br;
          if (d > lim) {
            b.x = o.cx + ux * lim;
            b.y = o.cy + uy * lim;
            this.bounce(b, -ux, -uy, ring, b.vx, b.vy);
          }
        } else {
          const lim = R + hs + br;
          if (d < lim) {
            b.x = o.cx + ux * lim;
            b.y = o.cy + uy * lim;
            this.bounce(b, ux, uy, ring, b.vx, b.vy);
          }
        }
      }

      // Abgerundete Enden der Lücke (bewegen sich mit der Rotation)
      for (let s = -1; s <= 1; s += 2) {
        const a = gc + s * ring.half;
        const px = o.cx + R * Math.cos(a);
        const py = o.cy + R * Math.sin(a);
        const ex = b.x - px;
        const ey = b.y - py;
        const dd = Math.hypot(ex, ey) || 1e-9;
        const lim = hs + br;
        if (dd < lim) {
          const nx = ex / dd;
          const ny = ey / dd;
          b.x = px + nx * lim;
          b.y = py + ny * lim;
          const wvx = -ring.omega * (py - o.cy);
          const wvy = ring.omega * (px - o.cx);
          const rvx = b.vx - wvx;
          const rvy = b.vy - wvy;
          this.bounce(b, nx, ny, ring, rvx, rvy);
        }
      }
      return false;
    }

    snapThreads(ringIdx) {
      for (const b of this.balls) if (b.anchors) b.anchors = b.anchors.filter((an) => an.ring !== ringIdx);
    }

    breakRing(escaper) {
      const o = this.o;
      const ring = this.rings[this.cur];
      this.snapThreads(ring.i);
      ring.alive = false;
      ring.breakT = this.t;
      this.cur++;
      this.gen++;
      const before = this.balls.length;

      if (o.mode === 'double') {
        for (let k = 0; k < before; k++) {
          const b = this.balls[k];
          if (b.dead) continue;
          const th = ((8 + this.rng() * 14) * Math.PI) / 180;
          const c = Math.cos(th);
          const s = Math.sin(th);
          const vx = b.vx;
          const vy = b.vy;
          b.vx = vx * c - vy * s;
          b.vy = vx * s + vy * c;
          this.addBall(b.x, b.y, vx * c + vy * s, -vx * s + vy * c);
        }
      } else {
        for (let k = 0; k < 2; k++) {
          const a = this.rng() * TAU;
          this.addBall(o.cx, o.cy, Math.cos(a) * o.startSpeed, Math.sin(a) * o.startSpeed);
        }
      }
      this.br = this.ballRadius();
      this.events.push({
        type: 'break',
        t: this.t,
        ring: ring.i,
        x: escaper.x,
        y: escaper.y,
        balls: this.balls.length,
        final: this.cur >= this.rings.length,
      });
    }

    substep() {
      if (this.o.scene === 'box') return this.substepBox();
      const o = this.o;
      const dt = this.dt;
      this.t += dt;
      const t = this.t;
      const ring = this.cur < this.rings.length ? this.rings[this.cur] : null;
      let escaper = null;
      const balls = this.balls;
      for (let k = 0; k < balls.length; k++) {
        const b = balls[k];
        b.vy += o.gravity * dt;
        b.x += b.vx * dt;
        b.y += b.vy * dt;
        if (ring) {
          if (this.collide(b, ring, t) && !escaper) escaper = b;
        } else if (b.y > o.height + 80 || b.y < -80 || b.x < -80 || b.x > o.width + 80) {
          b.dead = true;
        }
      }
      if (escaper) this.breakRing(escaper);
      if (!ring && balls.some((b) => b.dead)) this.balls = balls.filter((b) => !b.dead);
    }
  }

  /* Timeline = Regie: Video-Frames, Zeitlupe nach dem Finale, Outro-Länge. */
  class Timeline {
    constructor(opts) {
      this.o = resolve(opts);
      this.sim = new Sim(this.o);
      this.frame = 0;
      this.acc = 0;
      this.finalFrame = -1;
      this.totalFrames = Infinity;
      this.log = [];
      this.stepsPerFrame = PHYSICS_HZ / this.o.fps;
    }

    timeScale(frame) {
      const o = this.o;
      if (this.finalFrame < 0 || frame < this.finalFrame) return 1;
      const s = (frame - this.finalFrame) / o.fps;
      if (s < o.slowmoDur) return o.slowmoScale;
      if (s < o.slowmoDur + 0.5) return o.slowmoScale + ((1 - o.slowmoScale) * (s - o.slowmoDur)) / 0.5;
      return 1;
    }

    /** Einen Videoframe simulieren. Gibt die Events dieses Frames zurück. */
    step() {
      const o = this.o;
      const sim = this.sim;
      const evs = [];
      sim.events = evs;
      this.acc += this.stepsPerFrame * this.timeScale(this.frame + 1);
      while (this.acc >= 1 - 1e-9) {
        this.acc -= 1;
        sim.substep();
      }
      this.frame++;
      for (const ev of evs) {
        ev.frame = this.frame;
        ev.vt = this.frame / o.fps;
        if (ev.type === 'break' && ev.final && this.finalFrame < 0) {
          this.finalFrame = this.frame;
          this.totalFrames = this.frame + Math.round(o.outroDur * o.fps);
        }
      }
      if (evs.length) this.log.push(...evs);
      return evs;
    }

    done() {
      return this.frame >= this.totalFrames || this.frame / this.o.fps > this.o.maxVideoSec;
    }

    /** Komplett ohne Rendering durchrechnen (für Seed-Suche und Audio). */
    runHeadless(stopAfterSec) {
      const limit = (stopAfterSec || this.o.maxVideoSec) * this.o.fps;
      while (!this.done() && this.frame < limit) this.step();
      return this.summary();
    }

    summary() {
      const breaks = this.log.filter((e) => e.type === 'break').map((e) => +e.vt.toFixed(3));
      const stageEv = this.log.filter((e) => e.type === 'stage');
      const stages = this.o.scene !== 'rings' ? stageEv.map((e) => +e.vt.toFixed(3)) : breaks;
      return {
        scene: this.o.scene,
        stages,
        seed: this.o.seed,
        completed: this.finalFrame >= 0,
        finalSec: this.finalFrame >= 0 ? this.finalFrame / this.o.fps : null,
        totalFrames: Number.isFinite(this.totalFrames) ? this.totalFrames : this.frame,
        breaks,
        finalBalls: (this.log.filter((e) => e.type === 'break').pop() || { balls: 1 }).balls,
      };
    }
  }

  /**
   * Sucht einen Seed, bei dem der letzte Ring nahe `target` Sekunden zerbricht
   * und das Tempo stimmt (kein Ring sofort, keine endlos langen Pausen).
   */
  function findSeed(opts) {
    const o = Object.assign({ target: 60, tol: 2, start: 1, tries: 800, minFirst: 2.5, maxFirst: 9, maxGap: 15 }, opts);
    let best = null;
    for (let k = 0; k < o.tries; k++) {
      const seed = o.start + k;
      const tl = new Timeline(Object.assign({}, o, { seed }));
      const s = tl.runHeadless(o.target + o.tol + 1);
      if (!s.completed) continue;
      const st = s.stages;
      const gaps = st.map((b, i) => b - (i ? st[i - 1] : 0));
      const err = Math.abs(s.finalSec - o.target);
      const paced = st[0] >= o.minFirst && st[0] <= o.maxFirst && Math.max(...gaps) <= o.maxGap;
      if (err <= o.tol && paced) return Object.assign(s, { tried: k + 1 });
      const score = err + (paced ? 0 : 5);
      if (!best || score < best.score) best = Object.assign(s, { score, tried: k + 1 });
    }
    return best ? Object.assign(best, { approximate: true }) : null;
  }

  return { Sim, Timeline, findSeed, resolve, milestones, SCENES, mulberry32, DEFAULTS, PRESETS, PHYSICS_HZ, TAU };
});
