/*
 * Zusätzliche Formate (eigene Umsetzungen erfolgreicher Nischen-Formate):
 *   dense   – "Schafft der Ball 500 Ringe in 1 Minute?" (dichtes Ringband, Countdown)
 *   layers  – "Was ist ganz unten?" (Ball zerschlägt Schichten, Kamera fährt mit, Auflösung unten)
 *   battle  – "Wer gewinnt?" (4 Teams mit Lebenspunkten, Laser-Linien, Sieger)
 *   press   – "Hydraulische Presse" (Presse zerquetscht Bälle, jeder wird zu 2, bis zum Ziel)
 * Physik deterministisch (fester Zeitschritt, geseedeter Zufall). Läuft in Node und im Browser.
 * Schnittstelle wie Sim in sim.js: substep(), events, balls, t, cur, rings, br.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.BallFormats = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';
  const TAU = Math.PI * 2;
  const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
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
  function milestones(goal, n) {
    const out = [];
    for (let k = 1; k <= n; k++) out.push(Math.max(Math.round(Math.pow(goal, k / n)), (out[k - 2] || 1) + 1));
    out[n - 1] = Math.max(goal, out[n - 2] + 1);
    return out;
  }

  // Voreinstellungen je Format (werden in sim.js resolve() eingemischt)
  const PRESETS = {
    dense: { denseN: 500, denseInner: 110, denseOuter: 470, denseGapDeg: 0, denseOmega: 0.55, gravity: 1100, ballR: 12, startSpeed: 1100, minBounce: 950, breakPerSpeed: 1100, timeLimit: 60, outroDur: 4, cy: 950 },
    layers: { layerN: 240, layerGap: 7, layerTop: 760, boxL: 110, boxRight: 930, gravity: 1800, ballR: 18, startSpeed: 420, bounceMin: 950, breakPerSpeed: 120, outroDur: 4.5 },
    battle: { teams: 4, ballR: 58, startSpeed: 640, gravity: 0, hp: 100, arenaR: 430, outroDur: 4.5, cy: 980 },
    power: { gravity: 2600, ballR: 16, outroDur: 3.5, blockTop: 980, blockBottom: 1560, boxL: 150, boxRight: 930, bounceTop: 560, cy: 1100 },
    tunnel: { tunnelN: 1000, tunnelR0: 140, tunnelStep: 6, tunnelBins: 360, tunnelSpeed: 9, tunnelDepth: [20, 50], tunnelWidth: [18, 22], tunnelClear: 0.65, outroDur: 3.5, cy: 920 },
    press: { goal: 500, arenaR: 430, ballR: 18, ballRMin: 7, startSpeed: 650, gravity: 250, pressOpen: 300, pressH: 420, pressPeriod: 1.2, outroDur: 4, cy: 1000 },
  };

  class Base {
    constructor(o) {
      this.o = o;
      this.rng = mulberry32((o.seed >>> 0) || 1);
      this.t = 0;
      this.dt = 1 / 240;
      this.events = [];
      this.balls = [];
      this.rings = [{ i: 0, r: 0, half: 0, omega: 0, gc0: 0, alive: true }];
      this.cur = 0;
      this.gen = 0;
      this.inside = 1;
      this.br = o.ballR;
      this.lastNoteT = -1;
      this.noteIdx = 0;
      this.stage = 0;
      this.done = false;
      this.nextId = 0;
    }
    get ringsLeft() {
      return 0;
    }
    gapCenter() {
      return 0;
    }
    ball(x, y, vx, vy, extra) {
      const b = Object.assign({ id: this.nextId++, x, y, vx, vy, born: 0, dead: false }, extra || {});
      this.balls.push(b);
      return b;
    }
    note(b, speed, len) {
      const o = this.o;
      if (this.t - this.lastNoteT < o.noteMinGap) return;
      this.lastNoteT = this.t;
      const mel = o.melody && o.melody.length ? o.melody : [72];
      this.events.push({ type: 'note', t: this.t, midi: mel[this.noteIdx++ % mel.length], vel: 0.45 + 0.55 * Math.min(1, speed / 1400), x: b.x, y: b.y, ring: 0, len: len || 300 });
    }
    stageTo(value, max) {
      // 12 Stufen gleichmäßig bis max (für Level-up-Klang und Seed-Tempo)
      while (this.stage < 12 && value >= Math.ceil(((this.stage + 1) * max) / 12)) {
        this.events.push({ type: 'stage', t: this.t, k: this.stage, balls: value, final: this.stage === 11 });
        this.stage++;
      }
    }
    finish(extra) {
      if (this.done) return;
      this.done = true;
      this.finalTime = this.t;
      this.cur = 1;
      this.rings[0].alive = false;
      this.events.push(Object.assign({ type: 'break', t: this.t, ring: 0, x: this.o.cx, y: this.o.cy, balls: this.inside, final: true }, extra || {}));
    }
  }

  /* ---------------- 1) 500 Ringe in 1 Minute ---------------- */
  class Dense extends Base {
    constructor(o) {
      super(o);
      this.n = o.denseN;
      this.half = (o.denseGapDeg * Math.PI) / 360;
      this.gc0 = this.rng() * TAU;
      this.broken = 0;
      this.powerups = [];
      this.nextPU = 2.5 + this.rng() * 1.5;
      const a = this.rng() * TAU;
      this.ball(o.cx, o.cy, Math.cos(a) * o.startSpeed, Math.sin(a) * o.startSpeed, { bigUntil: -1, fastUntil: -1 });
    }
    radius(i) {
      const o = this.o;
      return o.denseInner + (i * (o.denseOuter - o.denseInner)) / (this.n - 1);
    }
    gap(t) {
      return this.gc0 + this.o.denseOmega * t;
    }
    ballR(b) {
      return b.bigUntil > this.t ? this.br * 1.9 : this.br;
    }
    breakOne(b) {
      this.events.push({ type: 'ringbreak', t: this.t, i: this.broken, x: b.x, y: b.y });
      this.broken++;
      this.stageTo(this.broken, this.n);
    }
    spawnPowerup() {
      const o = this.o;
      const kinds = ['x2', 'big', 'fast'];
      const kind = this.balls.length >= 3 ? kinds[1 + Math.floor(this.rng() * 2)] : kinds[Math.floor(this.rng() * 3)];
      const R = this.radius(Math.min(this.broken, this.n - 1)) - 70;
      let x = o.cx;
      let y = o.cy;
      for (let tries = 0; tries < 12; tries++) {
        // nicht direkt beim Ball: der Zuschauer soll sehen, ob er es erwischt
        const a = this.rng() * TAU;
        const r = Math.sqrt(this.rng()) * Math.max(40, R) * 0.85;
        x = o.cx + Math.cos(a) * r;
        y = o.cy + Math.sin(a) * r;
        if (this.balls.every((b) => Math.hypot(b.x - x, b.y - y) > 160)) break;
      }
      this.powerups.push({ kind, x, y, t0: this.t, id: this.nextId++ });
      this.events.push({ type: 'puspawn', t: this.t, kind });
    }
    collect(b, p) {
      const o = this.o;
      if (p.kind === 'x2') {
        this.ball(b.x, b.y, -b.vx * 0.9 + 120, b.vy * 0.9, { bigUntil: -1, fastUntil: -1 });
      } else if (p.kind === 'big') {
        b.bigUntil = this.t + 5;
      } else {
        b.fastUntil = this.t + 5;
        b.vx *= 1.3;
        b.vy *= 1.3;
      }
      this.events.push({ type: 'powerup', t: this.t, kind: p.kind, x: p.x, y: p.y });
      void o;
    }
    substep() {
      const o = this.o;
      this.t += this.dt;
      for (const b of this.balls) {
        b.vy += o.gravity * this.dt;
        b.x += b.vx * this.dt;
        b.y += b.vy * this.dt;
      }
      if (this.done) return;
      // Power-ups erscheinen, verfallen nach 7 s
      if (this.t >= this.nextPU && this.powerups.length < 2) {
        this.spawnPowerup();
        this.nextPU = this.t + 3.5 + this.rng() * 3;
      }
      this.powerups = this.powerups.filter((p) => this.t - p.t0 < 7);
      for (const b of this.balls) {
        const r = this.ballR(b);
        for (const p of this.powerups) {
          if (!p.taken && Math.hypot(b.x - p.x, b.y - p.y) < r + 30) {
            p.taken = true;
            this.collect(b, p);
          }
        }
        if (this.broken >= this.n) continue;
        const dx = b.x - o.cx;
        const dy = b.y - o.cy;
        const d = Math.hypot(dx, dy) || 1e-9;
        const R = this.radius(this.broken);
        if (d + r <= R) continue;
        const ux = dx / d;
        const uy = dy / d;
        b.x = o.cx + ux * (R - r);
        b.y = o.cy + uy * (R - r);
        const vn = b.vx * ux + b.vy * uy;
        if (vn > 0) {
          const fast = b.fastUntil > this.t;
          const minB = o.minBounce * (fast ? 1.3 : 1);
          b.vx -= 2 * vn * ux;
          b.vy -= 2 * vn * uy;
          const out = -(b.vx * ux + b.vy * uy);
          if (out < minB) {
            b.vx -= (minB - out) * ux;
            b.vy -= (minB - out) * uy;
          }
          let k = 1 + Math.floor(vn / o.breakPerSpeed);
          if (fast) k *= 2;
          for (let j = 0; j < k && this.broken < this.n; j++) this.breakOne(b);
          this.note(b, vn, 300);
        }
      }
      this.powerups = this.powerups.filter((p) => !p.taken);
      this.inside = this.broken;
      if (this.broken >= this.n) this.finish({ success: true, time: this.t });
      else if (this.t >= o.timeLimit) this.finish({ success: false, time: o.timeLimit });
    }
  }

  /* ---------------- 2) Was ist ganz unten? ---------------- */
  class Layers extends Base {
    constructor(o) {
      super(o);
      this.broken = 0;
      this.floorY = o.layerTop + o.layerN * o.layerGap + 520;
      this.ball((o.boxL + o.boxRight) / 2, o.layerTop - 420, (this.rng() < 0.5 ? -1 : 1) * o.startSpeed, 0);
    }
    substep() {
      const o = this.o;
      this.t += this.dt;
      const b = this.balls[0];
      if (this.done) return;
      b.vy += o.gravity * this.dt;
      b.x += b.vx * this.dt;
      b.y += b.vy * this.dt;
      if (b.x - this.br < o.boxL) { b.x = o.boxL + this.br; b.vx = Math.abs(b.vx); }
      if (b.x + this.br > o.boxRight) { b.x = o.boxRight - this.br; b.vx = -Math.abs(b.vx); }
      if (this.broken < o.layerN) {
        const yL = o.layerTop + this.broken * o.layerGap;
        if (b.y + this.br > yL && b.vy > 0) {
          const vy = b.vy;
          b.y = yL - this.br;
          const k = 1 + Math.floor(vy / o.breakPerSpeed);
          for (let j = 0; j < k && this.broken < o.layerN; j++) {
            this.events.push({ type: 'layerbreak', t: this.t, i: this.broken, x: b.x });
            this.broken++;
            this.stageTo(this.broken, o.layerN);
          }
          b.vy = -Math.max(o.bounceMin, 0.8 * vy) * (0.95 + 0.1 * this.rng());
          b.vx += (this.rng() - 0.5) * 260;
          b.vx = clamp(b.vx, -700, 700);
          this.note(b, vy, 300);
        }
      } else if (b.y + this.br >= this.floorY) {
        b.y = this.floorY - this.br;
        b.vy = 0;
        b.vx = 0;
        this.finish({ success: true });
      }
      this.inside = this.broken;
    }
  }

  /* ---------------- 3) Wer gewinnt? ---------------- */
  const TEAMS = [
    { name: { de: 'ROT', en: 'RED' }, color: '#FF3B30' },
    { name: { de: 'BLAU', en: 'BLUE' }, color: '#0A84FF' },
    { name: { de: 'GRÜN', en: 'GREEN' }, color: '#34C759' },
    { name: { de: 'GELB', en: 'YELLOW' }, color: '#FFD60A' },
  ];
  class Battle extends Base {
    constructor(o) {
      super(o);
      const n = o.teams;
      for (let k = 0; k < n; k++) {
        const a = (k / n) * TAU + Math.PI / 4;
        const d = this.rng() * TAU;
        this.ball(o.cx + Math.cos(a) * 200, o.cy + Math.sin(a) * 200, Math.cos(d) * o.startSpeed, Math.sin(d) * o.startSpeed, { team: k, hp: o.hp, lasers: [] });
      }
      this.alive = n;
      this.inside = n;
    }
    substep() {
      const o = this.o;
      this.t += this.dt;
      if (this.done) return;
      const R = o.arenaR - this.br;
      const target = o.startSpeed * (1 + this.t / 25); // wird langsam schneller -> Kampf endet sicher
      const live = this.balls.filter((b) => !b.dead);
      for (const b of live) {
        const sp = Math.hypot(b.vx, b.vy) || 1;
        b.vx *= target / sp;
        b.vy *= target / sp;
        b.x += b.vx * this.dt;
        b.y += b.vy * this.dt;
        const dx = b.x - o.cx;
        const dy = b.y - o.cy;
        const d = Math.hypot(dx, dy) || 1e-9;
        if (d > R) {
          const ux = dx / d;
          const uy = dy / d;
          b.x = o.cx + ux * R;
          b.y = o.cy + uy * R;
          const vn = b.vx * ux + b.vy * uy;
          if (vn > 0) {
            b.vx -= 2 * vn * ux;
            b.vy -= 2 * vn * uy;
            b.lasers.push({ x: o.cx + ux * o.arenaR, y: o.cy + uy * o.arenaR, t: this.t });
            if (b.lasers.length > 3) b.lasers.shift();
            this.note(b, vn, 400);
          }
        }
      }
      for (let i = 0; i < live.length; i++) {
        for (let j = i + 1; j < live.length; j++) {
          const a = live[i];
          const c = live[j];
          const dx = c.x - a.x;
          const dy = c.y - a.y;
          const d = Math.hypot(dx, dy) || 1e-9;
          if (d >= 2 * this.br) continue;
          const nx = dx / d;
          const ny = dy / d;
          const over = 2 * this.br - d;
          a.x -= (nx * over) / 2; a.y -= (ny * over) / 2;
          c.x += (nx * over) / 2; c.y += (ny * over) / 2;
          const va = a.vx * nx + a.vy * ny;
          const vc = c.vx * nx + c.vy * ny;
          if (va - vc <= 0) continue;
          a.vx += (vc - va) * nx; a.vy += (vc - va) * ny;
          c.vx += (va - vc) * nx; c.vy += (va - vc) * ny;
          // Wer schneller auf den anderen zufährt, teilt mehr Schaden aus
          const attackerA = Math.abs(va) >= Math.abs(vc);
          const big = 4 + Math.floor(this.rng() * 6);
          const small = 1 + Math.floor(this.rng() * 2);
          const da = attackerA ? small : big;
          const dc = attackerA ? big : small;
          a.hp = Math.max(0, a.hp - da);
          c.hp = Math.max(0, c.hp - dc);
          this.events.push({ type: 'hit', t: this.t, x: (a.x + c.x) / 2, y: (a.y + c.y) / 2, a: a.team, c: c.team, da, dc });
          this.note(a, Math.abs(va - vc), 200);
          for (const b of [a, c]) {
            if (b.hp <= 0 && !b.dead) {
              b.dead = true;
              this.alive--;
              this.inside = this.alive;
              this.events.push({ type: 'ko', t: this.t, team: b.team, x: b.x, y: b.y });
              this.events.push({ type: 'escape', t: this.t, x: b.x, y: b.y, balls: o.teams - this.alive + 1 });
              this.stage = 0;
              this.events.push({ type: 'stage', t: this.t, k: o.teams - this.alive - 1, balls: this.alive, final: false });
            }
          }
        }
      }
      if (this.alive <= 1) {
        const w = this.balls.find((b) => !b.dead);
        this.finish({ winner: w ? w.team : 0, balls: 1 });
      }
    }
  }

  /* ---------------- 4) Hydraulische Presse ---------------- */
  class Press extends Base {
    constructor(o) {
      super(o);
      this.ms = milestones(o.goal, 12);
      this.crushes = 0;
      this.w = o.pressOpen;
      this.wv = 0;
      const a = this.rng() * TAU;
      this.ball(o.cx - 260, o.cy + 40, Math.cos(a) * o.startSpeed, Math.sin(a) * o.startSpeed);
    }
    width(t) {
      const o = this.o;
      const p = (t % o.pressPeriod) / o.pressPeriod;
      if (p < 0.72) return o.pressOpen;
      if (p < 0.8) return o.pressOpen * (1 - (p - 0.72) / 0.08);
      if (p < 0.86) return 0;
      return o.pressOpen * ((p - 0.86) / 0.14);
    }
    radius() {
      const o = this.o;
      return Math.max(o.ballRMin, Math.min(o.ballR, o.ballR * Math.pow(Math.max(1, this.balls.length) / 10, -0.25)));
    }
    substep() {
      const o = this.o;
      this.t += this.dt;
      const w = this.width(this.t);
      this.wv = (w - this.w) / this.dt;
      this.w = w;
      const H2 = o.pressH / 2;
      const PT = 26; // Plattendicke
      const R = o.arenaR - this.br;
      if (this.done) {
        for (const b of this.balls) { b.vy += 1500 * this.dt; b.x += b.vx * this.dt; b.y += b.vy * this.dt; }
        return;
      }
      let spawn = [];
      for (const b of this.balls) {
        if (b.dead) continue;
        b.vy += o.gravity * this.dt; // etwas Schwerkraft: chaotische Bahnen, alle kommen mal in die Presse
        b.x += b.vx * this.dt;
        b.y += b.vy * this.dt;
        const dx = b.x - o.cx;
        const dy = b.y - o.cy;
        // Zerquetscht? (zwischen den Platten, Presse fast zu)
        if (Math.abs(dy) < H2 && Math.abs(dx) < w / 2 + 2 && w < 2 * this.br + 2) {
          b.dead = true;
          this.crushes++;
          spawn.push(b);
          continue;
        }
        // Platten als feste Blöcke links/rechts
        for (const s of [-1, 1]) {
          const x0 = o.cx + s * (w / 2);
          const x1 = o.cx + s * (w / 2 + PT);
          const lo = Math.min(x0, x1);
          const hi = Math.max(x0, x1);
          const qx = clamp(b.x, lo, hi);
          const qy = clamp(b.y, o.cy - H2, o.cy + H2);
          const ex = b.x - qx;
          const ey = b.y - qy;
          const dd = Math.hypot(ex, ey);
          if (dd < this.br) {
            let nx;
            let ny;
            if (dd > 1e-6) { nx = ex / dd; ny = ey / dd; } else { nx = -s; ny = 0; }
            b.x = qx + nx * this.br;
            b.y = qy + ny * this.br;
            const pv = -s * this.wv / 2; // Plattengeschwindigkeit (x)
            const rv = (b.vx - (nx !== 0 ? pv : 0)) * nx + b.vy * ny;
            if (rv < 0) {
              b.vx -= 2 * rv * nx;
              b.vy -= 2 * rv * ny;
              this.note(b, -rv, 200);
            }
          }
        }
        const d = Math.hypot(b.x - o.cx, b.y - o.cy) || 1e-9;
        if (d > R) {
          const ux = (b.x - o.cx) / d;
          const uy = (b.y - o.cy) / d;
          b.x = o.cx + ux * R;
          b.y = o.cy + uy * R;
          const vn = b.vx * ux + b.vy * uy;
          if (vn > 0) {
            b.vx -= 2 * vn * ux;
            b.vy -= 2 * vn * uy;
            this.note(b, vn, 500);
          }
        }
        const sp = Math.hypot(b.vx, b.vy) || 1;
        if (sp > 1400) { b.vx *= 1400 / sp; b.vy *= 1400 / sp; }
        if (sp < 400) { b.vx *= 400 / sp; b.vy *= 400 / sp; }
      }
      if (spawn.length) {
        this.balls = this.balls.filter((b) => !b.dead);
        for (const c of spawn) {
          for (const s of [-1, 1]) {
            const a = (s < 0 ? -Math.PI / 2 : Math.PI / 2) + (this.rng() - 0.5) * 1.2;
            this.ball(o.cx + (this.rng() - 0.5) * 20, o.cy + s * (H2 + this.br + 4), Math.cos(a) * o.startSpeed, Math.sin(a) * o.startSpeed);
          }
          this.events.push({ type: 'escape', t: this.t, x: c.x, y: c.y, balls: this.balls.length });
          this.events.push({ type: 'crush', t: this.t, x: c.x, y: c.y });
        }
        this.br = this.radius();
        this.inside = this.balls.length;
        while (this.stage < 12 && this.inside >= this.ms[this.stage]) {
          this.events.push({ type: 'stage', t: this.t, k: this.stage, balls: this.inside, final: this.stage === 11 });
          this.stage++;
        }
        if (this.inside >= o.goal) {
          for (const b of this.balls) {
            const dx = b.x - o.cx;
            const dy = b.y - o.cy;
            const d = Math.hypot(dx, dy) || 1;
            b.vx = (dx / d) * 900;
            b.vy = (dy / d) * 900 - 500;
          }
          this.finish({ balls: this.inside });
        }
      }
    }
  }

  /* ---------------- 5) Jeder Treffer ×2 Kraft ---------------- */
  const POWER_BLOCKS = [6, 20, 70, 250, 900, 3500, 14000];
  class Power extends Base {
    constructor(o) {
      super(o);
      this.power = 1;
      this.block = 0;
      this.rem = POWER_BLOCKS[0];
      this.ball((o.boxL + o.boxRight) / 2, o.bounceTop, (this.rng() < 0.5 ? -1 : 1) * (220 + this.rng() * 160), 0);
    }
    surface() {
      const o = this.o;
      const size = POWER_BLOCKS[this.block];
      return o.blockTop + (1 - this.rem / size) * (o.blockBottom - o.blockTop);
    }
    substep() {
      const o = this.o;
      this.t += this.dt;
      const b = this.balls[0];
      if (this.done) return;
      b.vy += o.gravity * this.dt;
      b.x += b.vx * this.dt;
      b.y += b.vy * this.dt;
      if (b.x - this.br < o.boxL) { b.x = o.boxL + this.br; b.vx = Math.abs(b.vx); }
      if (b.x + this.br > o.boxRight) { b.x = o.boxRight - this.br; b.vx = -Math.abs(b.vx); }
      const sy = this.surface();
      if (b.y + this.br >= sy && b.vy > 0) {
        b.y = sy - this.br;
        const hit = Math.min(this.power, this.rem);
        this.rem -= hit;
        this.events.push({ type: 'powerhit', t: this.t, x: b.x, y: sy, n: hit, power: this.power, block: this.block });
        this.note(b, b.vy, 300);
        this.power *= 2;
        // immer gleiche Sprunghöhe -> gleichmäßiger Rhythmus
        b.vy = -Math.sqrt(2 * o.gravity * Math.max(120, sy - o.bounceTop));
        b.vx += (this.rng() - 0.5) * 160;
        if (this.rem <= 0) {
          this.events.push({ type: 'stage', t: this.t, k: this.block, balls: this.power, final: false });
          this.block++;
          if (this.block >= POWER_BLOCKS.length) { this.inside = this.power / 2; this.finish({ power: this.power / 2 }); return; }
          this.rem = POWER_BLOCKS[this.block];
          this.events.push({ type: 'newblock', t: this.t, block: this.block });
        }
      }
      this.inside = this.power;
    }
  }

  /* ---------------- 6) Ring-Tunnel: entkommt er jemals? ---------------- */
  class Tunnel extends Base {
    constructor(o) {
      super(o);
      this.n = o.tunnelN;
      this.B = o.tunnelBins;
      this.alive = new Uint8Array(this.n * this.B).fill(1);
      this.count = new Int16Array(this.n).fill(this.B);
      this.passed = 0;
      this.scaleBall();
      const a = this.rng() * TAU;
      this.ball(0, 0, Math.cos(a) * this.speed, Math.sin(a) * this.speed);
    }
    r(i) { return this.o.tunnelR0 + i * this.o.tunnelStep; }
    scaleBall() {
      const h = this.r(Math.min(this.passed, this.n - 1));
      this.br = h * 0.035;
      this.speed = h * this.o.tunnelSpeed;
    }
    carve(j, bin) {
      // zackiger Zacken: breit an der Basis, spitz nach außen
      const o = this.o;
      const D = o.tunnelDepth[0] + Math.floor(this.rng() * o.tunnelDepth[1]);
      const w0 = o.tunnelWidth[0] + this.rng() * o.tunnelWidth[1];
      for (let m = 0; m < D && j + m < this.n; m++) {
        const ring = j + m;
        const w = Math.round(w0 * Math.pow(1 - m / D, 1.5) + this.rng() * 2);
        for (let q = -w; q <= w; q++) {
          const idx = ring * this.B + ((bin + q + this.B * 4) % this.B);
          if (this.alive[idx]) { this.alive[idx] = 0; this.count[ring]--; }
        }
        // halb zerstörte Ringe fallen ganz weg
        if (this.count[ring] > 0 && this.count[ring] < this.B * o.tunnelClear) {
          this.alive.fill(0, ring * this.B, (ring + 1) * this.B);
          this.count[ring] = 0;
        }
      }
      let grew = false;
      while (this.passed < this.n && this.count[this.passed] === 0) { this.passed++; grew = true; }
      if (grew) {
        this.scaleBall();
        const b = this.balls[0];
        const sp = Math.hypot(b.vx, b.vy) || 1;
        b.vx *= this.speed / sp; b.vy *= this.speed / sp;
        this.inside = this.n - this.passed;
        this.stageTo(this.passed, this.n);
        if (this.passed >= this.n) this.finish({ balls: 0 });
      }
    }
    substep() {
      this.t += this.dt;
      const b = this.balls[0];
      b.x += b.vx * this.dt;
      b.y += b.vy * this.dt;
      if (this.done) return;
      const d = Math.hypot(b.x, b.y) || 1e-9;
      const ang = Math.atan2(b.y, b.x);
      const bin = Math.floor(((((ang % TAU) + TAU) % TAU) / TAU) * this.B) % this.B;
      for (let j = this.passed; j < this.n && this.r(j) < d + this.br; j++) {
        if (!this.alive[j * this.B + bin]) continue;
        const ux = b.x / d;
        const uy = b.y / d;
        const vn = b.vx * ux + b.vy * uy;
        const rj = this.r(j);
        b.x = ux * Math.min(d, rj - this.br);
        b.y = uy * Math.min(d, rj - this.br);
        if (vn > 0) {
          b.vx -= 2 * vn * ux; b.vy -= 2 * vn * uy;
          const tw = (this.rng() - 0.5) * 0.6;
          const c = Math.cos(tw);
          const s2 = Math.sin(tw);
          const vx = b.vx;
          b.vx = vx * c - b.vy * s2; b.vy = vx * s2 + b.vy * c;
          this.events.push({ type: 'tunnelhit', t: this.t, x: b.x, y: b.y, j });
          this.note(b, this.speed, 300);
          this.carve(j, bin);
        }
        break;
      }
      this.inside = this.n - this.passed;
    }
  }

  const CLASSES = { dense: Dense, layers: Layers, battle: Battle, press: Press, power: Power, tunnel: Tunnel };

  /* ================= Zeichnen (Browser) ================= */

  function onEvent(ev, fx, sim, o, rng) {
    if (ev.type === 'ringbreak') {
      const r = sim.radius(ev.i);
      const ang = Math.atan2(ev.y - o.cy, ev.x - o.cx);
      for (let k = 0; k < 5; k++) {
        const a = ang + (rng() - 0.5) * 1.4;
        fx.parts.push({ x: o.cx + Math.cos(a) * r, y: o.cy + Math.sin(a) * r, vx: Math.cos(a) * (60 + rng() * 160), vy: Math.sin(a) * (60 + rng() * 160), life: 0, max: 0.6 + rng() * 0.5, col: `hsl(${270 + 50 * (ev.i / sim.n)},90%,70%)`, s: 1.5 + rng() * 2 });
      }
    } else if (ev.type === 'layerbreak') {
      const y = o.layerTop + ev.i * o.layerGap;
      for (let k = 0; k < 6; k++) fx.parts.push({ x: ev.x + (rng() - 0.5) * 140, y, vx: (rng() - 0.5) * 300, vy: -60 - rng() * 220, life: 0, max: 0.5 + rng() * 0.4, col: `hsl(${235 + 85 * (ev.i / o.layerN)},85%,60%)`, s: 2 + rng() * 3, world: true });
    } else if (ev.type === 'hit') {
      fx.floats.push({ x: ev.x, y: ev.y, text: `-${Math.max(ev.da, ev.dc)}`, t0: ev.t, col: '#fff' });
      for (let k = 0; k < 14; k++) { const a = rng() * TAU; fx.parts.push({ x: ev.x, y: ev.y, vx: Math.cos(a) * 300 * rng(), vy: Math.sin(a) * 300 * rng(), life: 0, max: 0.4, col: '#fff', s: 2 }); }
    } else if (ev.type === 'powerhit') {
      const n = Math.min(60, 8 + Math.round(Math.log2(ev.n + 1) * 7));
      for (let k = 0; k < n; k++) fx.parts.push({ x: ev.x + (rng() - 0.5) * 160, y: ev.y, vx: (rng() - 0.5) * 700, vy: -150 - rng() * 900, life: 0, max: 0.6 + rng() * 0.6, col: rng() < 0.5 ? '#FF2E63' : '#FF7A9C', s: 3 + rng() * 4 });
      fx.floats.push({ x: ev.x, y: ev.y - 40, text: `-${ev.n}`, t0: ev.t, col: '#fff' });
      fx.shake = { t0: ev.t, amp: Math.min(18, 3 + Math.log2(ev.n + 1) * 1.4), dur: 0.18 };
    } else if (ev.type === 'newblock') {
      fx.newBlock = ev.t;
      fx.shake = { t0: ev.t, amp: 14, dur: 0.3 };
    } else if (ev.type === 'tunnelhit') {
      for (let k = 0; k < 8; k++) { const a = rng() * TAU; fx.parts.push({ x: ev.x, y: ev.y, vx: Math.cos(a) * 140, vy: Math.sin(a) * 140, life: 0, max: 0.5, col: '#E9E3FF', s: 2, world: true }); }
    } else if (ev.type === 'powerup') {
      const L = { x2: { de: '×2 BALL!', en: '×2 BALL!' }, big: { de: 'GRÖSSER!', en: 'BIGGER!' }, fast: { de: 'SCHNELLER!', en: 'FASTER!' } };
      const col = { x2: '#FF2D95', big: '#34C759', fast: '#FFD60A' }[ev.kind];
      fx.floats.push({ x: o.cx, y: o.cy + 20, text: L[ev.kind][o.lang === 'en' ? 'en' : 'de'], t0: ev.t, col, big: true });
      for (let k = 0; k < 40; k++) { const a = rng() * TAU; const sp = 100 + rng() * 400; fx.parts.push({ x: ev.x, y: ev.y, vx: Math.cos(a) * sp, vy: Math.sin(a) * sp, life: 0, max: 0.6, col, s: 3 }); }
    } else if (ev.type === 'ko') {
      const c = TEAMS[ev.team].color;
      for (let k = 0; k < 80; k++) { const a = rng() * TAU; const sp = 100 + rng() * 600; fx.parts.push({ x: ev.x, y: ev.y, vx: Math.cos(a) * sp, vy: Math.sin(a) * sp, life: 0, max: 0.8 + rng() * 0.5, col: c, s: 2 + rng() * 4 }); }
      fx.shake = { t0: ev.t, amp: 12, dur: 0.3 };
      fx.floats.push({ x: ev.x, y: ev.y - 40, text: 'K.O.!', t0: ev.t, col: c, big: true });
    } else if (ev.type === 'crush') {
      fx.crushFlash = ev.t;
      for (let k = 0; k < 10; k++) fx.parts.push({ x: ev.x, y: ev.y, vx: (rng() - 0.5) * 120, vy: (rng() < 0.5 ? -1 : 1) * (200 + rng() * 300), life: 0, max: 0.35, col: '#9DA8FF', s: 2 });
    } else if (ev.type === 'break' && ev.final) {
      fx.flash = ev.t;
      fx.final = ev;
      fx.shake = { t0: ev.t, amp: 16, dur: 0.4 };
      for (let k = 0; k < 160; k++) { const a = rng() * TAU; const sp = 200 + rng() * 900; fx.parts.push({ x: o.cx, y: o.cy, vx: Math.cos(a) * sp, vy: Math.sin(a) * sp, life: 0, max: 1 + rng() * 0.6, col: `hsl(${rng() * 360},90%,65%)`, s: 2 + rng() * 3, world: o.scene === 'layers' }); }
    }
  }

  function update(fx, dt) {
    for (const p of fx.parts) { p.vy += 500 * dt; p.x += p.vx * dt; p.y += p.vy * dt; p.life += dt; }
    fx.parts = fx.parts.filter((p) => p.life < p.max);
  }

  function background(o) {
    return o.scene === 'layers' ? '#FBF1DF' : null; // null = Standard (dunkel mit Sternen)
  }

  function draw(ctx, sim, vt, o, fx, H) {
    const t = sim.t;
    if (o.scene === 'dense') {
      const gc = sim.gap(t);
      const groups = 24;
      ctx.lineWidth = 1.4;
      for (let g = 0; g < groups; g++) {
        ctx.beginPath();
        for (let i = sim.broken + g; i < sim.n; i += groups) {
          const r = sim.radius(i);
          ctx.moveTo(o.cx + Math.cos(gc + sim.half) * r, o.cy + Math.sin(gc + sim.half) * r);
          ctx.arc(o.cx, o.cy, r, gc + sim.half, gc + TAU - sim.half);
        }
        const f = g / groups;
        ctx.strokeStyle = `hsl(${268 + 52 * f},95%,${g % 2 ? 58 : 70}%)`;
        ctx.stroke();
      }
      drawPowerups(ctx, sim, vt, H);
      sim.balls.forEach((b, i) => drawTrailBall(ctx, sim, fx, b.fastUntil > sim.t ? '#FFD60A' : b.bigUntil > sim.t ? '#5CFF8A' : '#ffffff', i, sim.ballR(b)));
    } else if (o.scene === 'layers') {
      const b = sim.balls[0];
      const target = Math.max(0, b.y - 780);
      fx.cam = fx.cam == null ? target : fx.cam + (target - fx.cam) * 0.12;
      const cam = fx.cam;
      ctx.save();
      ctx.translate(0, -cam);
      // Behälter
      const top = o.layerTop - 40;
      const bottom = sim.floorY;
      ctx.strokeStyle = '#1b1b1b';
      ctx.lineWidth = 5;
      ctx.strokeRect(o.boxL - 6, top, o.boxRight - o.boxL + 12, bottom - top + 6);
      const y0 = Math.max(sim.broken, Math.floor((cam - o.layerTop) / o.layerGap));
      const y1 = Math.min(o.layerN, Math.ceil((cam + 1920 - o.layerTop) / o.layerGap) + 1);
      ctx.lineWidth = o.layerGap * 0.55;
      for (let i = y0; i < y1; i++) {
        const y = o.layerTop + i * o.layerGap;
        ctx.strokeStyle = `hsl(${235 + 85 * (i / o.layerN)},85%,${i % 2 ? 55 : 63}%)`;
        ctx.beginPath(); ctx.moveTo(o.boxL, y); ctx.lineTo(o.boxRight, y); ctx.stroke();
      }
      // Auflösung ganz unten
      const ry = sim.floorY - 230;
      const cx = (o.boxL + o.boxRight) / 2;
      if (!sim.done) {
        ctx.fillStyle = '#2a2140';
        ctx.fillRect(cx - 150, ry - 150, 300, 300);
        H.outlinedText('?', cx, ry + 70, H.FONT_IT, 220, 300, '#FFD60A', 10);
      } else {
        const s = 330 * (0.6 + 0.4 * H.ease((vt - fx.flash) / 0.4));
        ctx.drawImage(H.skinSprite('cat', 1), cx - s / 2, ry - s / 2, s, s);
      }
      for (const p of fx.parts) if (p.world) drawPart(ctx, p);
      drawTrailBall(ctx, sim, fx, '#E5312B', 0);
      ctx.restore();
      for (const p of fx.parts) if (!p.world) drawPart(ctx, p);
      return;
    } else if (o.scene === 'battle') {
      ctx.save();
      ctx.shadowColor = '#fff';
      ctx.shadowBlur = 18;
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 7;
      ctx.beginPath(); ctx.arc(o.cx, o.cy, o.arenaR, 0, TAU); ctx.stroke();
      ctx.restore();
      for (const b of sim.balls) {
        if (b.dead) continue;
        const c = TEAMS[b.team].color;
        for (const L of b.lasers) {
          const age = t - L.t;
          if (age > 0.9) continue;
          ctx.globalAlpha = 1 - age / 0.9;
          ctx.strokeStyle = c;
          ctx.lineWidth = 3.5;
          ctx.beginPath(); ctx.moveTo(L.x, L.y); ctx.lineTo(b.x, b.y); ctx.stroke();
        }
        ctx.globalAlpha = 1;
      }
      for (const b of sim.balls) {
        if (b.dead) continue;
        const c = TEAMS[b.team].color;
        const r = sim.br;
        ctx.save();
        ctx.shadowColor = c; ctx.shadowBlur = 22;
        ctx.fillStyle = '#111'; ctx.beginPath(); ctx.arc(b.x, b.y, r, 0, TAU); ctx.fill();
        ctx.lineWidth = 8; ctx.strokeStyle = c; ctx.stroke();
        ctx.restore();
        const s = r * 1.55;
        ctx.drawImage(H.skinSprite('faces', b.team), b.x - s / 2, b.y - s / 2, s, s);
        // Lebensbalken
        const w = 96;
        ctx.fillStyle = 'rgba(255,255,255,0.18)'; ctx.fillRect(b.x - w / 2, b.y - r - 22, w, 10);
        ctx.fillStyle = c; ctx.fillRect(b.x - w / 2, b.y - r - 22, (w * b.hp) / o.hp, 10);
      }
    } else if (o.scene === 'power') {
      const sy = sim.surface();
      const size = POWER_BLOCKS[Math.min(sim.block, POWER_BLOCKS.length - 1)];
      const slide = fx.newBlock != null ? H.ease((vt - fx.newBlock) / 0.35) : 1;
      const off = (1 - slide) * 700;
      // Rahmen
      ctx.strokeStyle = '#fff'; ctx.lineWidth = 6;
      ctx.beginPath(); ctx.moveTo(o.boxL - 8, o.blockTop - 420); ctx.lineTo(o.boxL - 8, o.blockBottom + 6); ctx.lineTo(o.boxRight + 8, o.blockBottom + 6); ctx.lineTo(o.boxRight + 8, o.blockTop - 420); ctx.stroke();
      if (!sim.done) {
        // Streifen: je größer der Block, desto dichter (Moiré wie im Original)
        const h = o.blockBottom - o.blockTop;
        const period = Math.max(3, h / size);
        ctx.fillStyle = '#2A0F2E';
        ctx.fillRect(o.boxL, sy + off, o.boxRight - o.boxL, o.blockBottom - sy);
        ctx.fillStyle = '#FF2E63';
        for (let y = o.blockBottom - period; y >= sy - 0.5; y -= period) ctx.fillRect(o.boxL, y + off, o.boxRight - o.boxL, Math.max(1.2, period * 0.55));
        ctx.globalAlpha = 0.85;
        H.outlinedText(H.fmt(sim.rem), (o.boxL + o.boxRight) / 2, Math.min(o.blockBottom - 30, sy + 80) + off, H.FONT_IT, 44, 400, '#fff', 8);
        ctx.globalAlpha = 1;
      }
      drawTrailBall(ctx, sim, fx, '#ffffff', 0);
      const b = sim.balls[0];
      H.outlinedText(H.fmt(sim.done ? sim.power / 2 : sim.power), b.x, b.y - 40, H.FONT_IT, 46, 400, '#fff', 8);
    } else if (o.scene === 'tunnel') {
      const b = sim.balls[0];
      const hole = sim.r(Math.min(sim.passed, sim.n - 1));
      const zt = 300 / hole;
      fx.zoom = fx.zoom == null ? zt : fx.zoom + (zt - fx.zoom) * 0.15;
      const z = fx.zoom;
      const cx = 540 - b.x * z * 0.25;
      const cy = o.cy - b.y * z * 0.25;
      const step = Math.max(1, Math.ceil(4.5 / (o.tunnelStep * z))); // sichtbare feine Linien statt Farbfläche
      const maxR = 1700 / z;
      const B = sim.B;
      const HUES = [265, 330, 48, 95, 170, 215];
      ctx.lineWidth = 1.3;
      for (let i = sim.passed; i < sim.n && sim.r(i) < maxR; i += step) {
        const R = sim.r(i) * z;
        const sec = Math.floor((i / sim.n) * HUES.length);
        ctx.strokeStyle = `hsl(${HUES[sec]},70%,${i % (2 * step) ? 62 : 74}%)`;
        ctx.beginPath();
        const base = i * B;
        let k = 0;
        // zusammenhängende, intakte Bogenstücke zeichnen
        while (k < B) {
          if (!sim.alive[base + k]) { k++; continue; }
          let e = k;
          while (e < B && sim.alive[base + e]) e++;
          const a0 = (k / B) * TAU;
          const a1 = (e / B) * TAU;
          ctx.moveTo(cx + Math.cos(a0) * R, cy + Math.sin(a0) * R);
          ctx.arc(cx, cy, R, a0, a1);
          k = e;
        }
        ctx.stroke();
      }
      H.outlinedText(H.fmt(sim.n - sim.passed), cx, cy + 18, H.FONT_IT, 52, 400, 'rgba(255,255,255,0.75)', 0);
      // Ball mit Schweif (Bildschirmkoordinaten)
      fx.trail = fx.trail || [];
      fx.trail.unshift(cx + b.x * z, cy + b.y * z);
      if (fx.trail.length > 40) fx.trail.length = 40;
      ctx.strokeStyle = '#8B7BFF'; ctx.lineWidth = 5; ctx.lineCap = 'round';
      ctx.beginPath();
      for (let k = 0; k < fx.trail.length; k += 2) (k ? ctx.lineTo : ctx.moveTo).call(ctx, fx.trail[k], fx.trail[k + 1]);
      ctx.stroke();
      ctx.fillStyle = '#FFE14D';
      ctx.beginPath(); ctx.arc(cx + b.x * z, cy + b.y * z, Math.max(6, sim.br * z), 0, TAU); ctx.fill();
      for (const p of fx.parts) {
        if (!p.world) continue;
        ctx.globalAlpha = 1 - p.life / p.max; ctx.fillStyle = p.col;
        ctx.fillRect(cx + p.x * z - 1, cy + p.y * z - 1, 3, 3);
      }
      ctx.globalAlpha = 1;
      return;
    } else if (o.scene === 'press') {
      const w = sim.w;
      const H2 = o.pressH / 2;
      ctx.strokeStyle = 'rgba(255,255,255,0.9)';
      ctx.lineWidth = 3;
      ctx.beginPath(); ctx.arc(o.cx, o.cy, o.arenaR, 0, TAU); ctx.stroke();
      // Stangen + Platten
      ctx.strokeStyle = '#8E949C'; ctx.lineWidth = 8;
      for (const s of [-1, 1]) {
        const xo = o.cx + s * (w / 2 + 26);
        ctx.beginPath(); ctx.moveTo(xo, o.cy); ctx.lineTo(o.cx + s * o.arenaR, o.cy); ctx.stroke();
        const x0 = Math.min(o.cx + s * (w / 2), xo);
        ctx.fillStyle = '#A7ADB5'; ctx.fillRect(x0, o.cy - H2, 26, o.pressH);
        ctx.fillStyle = '#E8C26A'; ctx.fillRect(s < 0 ? o.cx - w / 2 - 5 : o.cx + w / 2, o.cy - H2 + 8, 5, o.pressH - 16);
      }
      const flash = fx.crushFlash != null ? Math.max(0, 1 - (vt - fx.crushFlash) / 0.15) : 0;
      if (flash > 0) { ctx.globalAlpha = flash * 0.6; ctx.fillStyle = '#fff'; ctx.fillRect(o.cx - 20, o.cy - H2, 40, o.pressH); ctx.globalAlpha = 1; }
      ctx.globalCompositeOperation = 'lighter';
      const spr = H.glowSprite(240);
      for (const b of sim.balls) {
        if (b.dead) continue;
        const s = sim.br * 3.2;
        ctx.drawImage(spr, b.x - s / 2, b.y - s / 2, s, s);
      }
      ctx.globalCompositeOperation = 'source-over';
      ctx.fillStyle = '#5B4BFF';
      for (const b of sim.balls) { if (b.dead) continue; ctx.beginPath(); ctx.arc(b.x, b.y, sim.br, 0, TAU); ctx.fill(); }
    }
    for (const p of fx.parts) drawPart(ctx, p);
  }

  function drawPart(ctx, p) {
    ctx.globalAlpha = 1 - p.life / p.max;
    ctx.fillStyle = p.col;
    ctx.fillRect(p.x - p.s / 2, p.y - p.s / 2, p.s, p.s);
    ctx.globalAlpha = 1;
  }

  function drawTrailBall(ctx, sim, fx, col, idx, radius) {
    const b = sim.balls[idx];
    const r = radius || sim.br;
    fx.trails = fx.trails || {};
    const tr = (fx.trails[b.id] = fx.trails[b.id] || []);
    tr.unshift(b.x, b.y);
    if (tr.length > 36) tr.length = 36;
    for (let k = tr.length / 2 - 1; k >= 1; k--) {
      const f = k / 18;
      ctx.globalAlpha = 0.5 * (1 - f);
      ctx.fillStyle = col;
      ctx.beginPath(); ctx.arc(tr[2 * k], tr[2 * k + 1], r * (1 - 0.6 * f), 0, TAU); ctx.fill();
    }
    ctx.globalAlpha = 1;
    ctx.fillStyle = col;
    ctx.beginPath(); ctx.arc(b.x, b.y, r, 0, TAU); ctx.fill();
  }

  const PU = { x2: { col: '#FF2D95', label: '×2' }, big: { col: '#34C759', label: 'XL' }, fast: { col: '#FFD60A', label: '»' } };
  function drawPowerups(ctx, sim, vt, H) {
    for (const p of sim.powerups) {
      const age = sim.t - p.t0;
      const pop = H.ease(Math.min(1, age / 0.25));
      const fade = age > 6 ? 1 - (age - 6) : 1; // blinkt aus
      const pulse = 1 + 0.08 * Math.sin(age * 8);
      const r = 30 * pop * pulse;
      ctx.save();
      ctx.globalAlpha = Math.max(0, fade);
      ctx.shadowColor = PU[p.kind].col;
      ctx.shadowBlur = 25;
      ctx.fillStyle = PU[p.kind].col;
      ctx.beginPath(); ctx.arc(p.x, p.y, r, 0, TAU); ctx.fill();
      ctx.shadowBlur = 0;
      ctx.lineWidth = 4; ctx.strokeStyle = '#fff'; ctx.stroke();
      ctx.restore();
      ctx.globalAlpha = Math.max(0, fade);
      H.outlinedText(PU[p.kind].label, p.x, p.y + 12 * pop, H.FONT_IT, 34 * pop, 80, '#fff', 6);
      ctx.globalAlpha = 1;
    }
  }

  const TXT = {
    de: {
      dense: (n) => [`SCHAFFT DER BALL ${n} RINGE`, 'IN 1 MINUTE?'], rings: 'RINGE', done: 'GESCHAFFT!', timeUp: 'ZEIT UM!',
      layers: ['WAS IST GANZ UNTEN?'], layersEnd: 'EINE KATZE!',
      battle: ['WER GEWINNT?'], round: 'RUNDE 1', wins: (n) => `${n} GEWINNT!`,
      press: ['HYDRAULISCHE PRESSE'], balls: 'BÄLLE', wait: 'Warte aufs Ende!', pressEnd: (n) => `${n} BÄLLE!`,
      power: 'JEDER TREFFER = ×2 KRAFT', powerEnd: 'ALLES ZERSTÖRT!',
      tunnel: ['ENTKOMMT ER JEMALS?'], tunnelEnd: 'ENDLICH FREI!',
    },
    en: {
      dense: (n) => [`CAN THE BALL BREAK ${n} RINGS`, 'IN 1 MINUTE?'], rings: 'RINGS', done: 'DONE!', timeUp: "TIME'S UP!",
      layers: ['WHAT IS AT THE BOTTOM?'], layersEnd: 'A CAT!',
      battle: ['WHO WINS?'], round: 'ROUND 1', wins: (n) => `${n} WINS!`,
      press: ['HYDRAULIC PRESS'], balls: 'BALLS', wait: 'Wait for the ending!', pressEnd: (n) => `${n} BALLS!`,
      power: 'EACH HIT ×2 THE POWER', powerEnd: 'EVERYTHING DESTROYED!',
      tunnel: ['WILL IT EVER ESCAPE?'], tunnelEnd: 'FINALLY FREE!',
    },
  };

  function drawText(ctx, sim, vt, o, fx, H) {
    const L = TXT[o.lang] || TXT.de;
    const lang = o.lang === 'en' ? 'en' : 'de';
    const top = 300;
    const dark = o.scene === 'layers';
    if (o.scene === 'dense') {
      L.dense(o.denseN).forEach((ln, i) => H.outlinedText(ln, 540, top + i * 70, H.FONT_IT, 60, 920, '#FFE15A', 10));
      const left = Math.max(0, o.timeLimit - (sim.done ? sim.finalTime || o.timeLimit : sim.t));
      const mm = Math.floor(left / 60);
      const ss = Math.ceil(left % 60) === 60 ? 59 : Math.floor(left % 60);
      H.outlinedText(`${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}`, 540, 1520, H.FONT_IT, 72, 600, left < 10 ? '#FF5A5A' : '#fff', 10);
      H.outlinedText(`${H.fmt(sim.broken)} / ${o.denseN} ${L.rings}`, 540, 1585, H.FONT_IT, 40, 800, '#C9B8FF', 8);
    } else if (o.scene === 'layers') {
      L.layers.forEach((ln, i) => H.outlinedText(ln, 540, top + i * 70, H.FONT_IT, 66, 920, '#fff', 12));
      H.outlinedText(H.fmt(sim.broken), 540, top + 110, H.FONT_IT, 80, 600, '#fff', 12);
    } else if (o.scene === 'battle') {
      H.outlinedText(L.battle[0], 540, top, H.FONT_IT, 92, 920, '#fff', 12);
      H.outlinedText(L.round, 540, top + 70, H.FONT_IT, 52, 600, '#FF3B30', 9);
      // Punktestand
      const n = o.teams;
      const pw = 205;
      for (let k = 0; k < n; k++) {
        const b = sim.balls[k];
        const x = 540 - ((n - 1) * (pw + 14)) / 2 + k * (pw + 14);
        const y = 1500;
        ctx.globalAlpha = b.dead ? 0.35 : 1;
        ctx.fillStyle = TEAMS[k].color;
        ctx.beginPath();
        ctx.roundRect ? ctx.roundRect(x - pw / 2, y - 36, pw, 66, 33) : ctx.rect(x - pw / 2, y - 36, pw, 66);
        ctx.fill();
        ctx.fillStyle = k === 3 ? '#111' : '#fff';
        ctx.font = `34px ${H.FONT_IT}`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'alphabetic';
        ctx.fillText(`${TEAMS[k].name[lang]} ${b.hp}`, x, y + 10);
        ctx.globalAlpha = 1;
      }
    } else if (o.scene === 'power') {
      H.outlinedText(L.power, 540, top, H.FONT_IT, 62, 920, '#FF4F7B', 10);
    } else if (o.scene === 'tunnel') {
      L.tunnel.forEach((ln, i) => H.outlinedText(ln, 540, top + i * 70, H.FONT_IT, 62, 920, '#fff', 10));
    } else if (o.scene === 'press') {
      H.outlinedText(L.press[0], 540, top - 10, H.FONT_IT, 66, 920, '#fff', 10);
      H.outlinedText(`${H.fmt(sim.done ? o.goal : sim.inside)} / ${H.fmt(o.goal)} ${L.balls}`, 540, top + 80, H.FONT_IT, 62, 900, '#fff', 10);
      H.outlinedText(L.wait, 540, 1560, H.FONT_IT, 72, 920, '#fff', 12);
    }
    // schwebende Texte (Schaden, K.O.)
    for (const f of fx.floats) {
      const age = vt - f.t0;
      if (age > 0.9) continue;
      ctx.globalAlpha = 1 - age / 0.9;
      H.outlinedText(f.text, f.x, f.y - 70 * age, H.FONT_IT, f.big ? 70 : 40, 400, f.col, 8);
      ctx.globalAlpha = 1;
    }
    fx.floats = fx.floats.filter((f) => vt - f.t0 < 0.9);
    // Endkarte
    if (sim.done && fx.flash != null) {
      const a = H.clamp((vt - fx.flash - 0.4) / 0.4, 0, 1);
      if (a > 0) {
        ctx.globalAlpha = a;
        let big;
        let col = '#FFD60A';
        let small = '';
        const last = fx.final || {};
        if (o.scene === 'dense') { big = last.success ? L.done : L.timeUp; small = last.success ? `${last.time.toFixed(1).replace('.', lang === 'de' ? ',' : '.')} s` : `${sim.broken} / ${o.denseN}`; }
        else if (o.scene === 'layers') { big = L.layersEnd; }
        else if (o.scene === 'battle') { const w = TEAMS[last.winner || 0]; big = L.wins(w.name[lang]); col = w.color; }
        else if (o.scene === 'power') { big = L.powerEnd; small = `${H.fmt(last.power || 0)}×`; col = '#FF4F7B'; }
        else if (o.scene === 'tunnel') { big = L.tunnelEnd; }
        else { big = L.pressEnd(H.fmt(o.goal)); }
        const y = o.scene === 'layers' ? 760 : o.cy;
        H.outlinedText(big, 540, y, H.FONT_IT, 120, 960, col, 16);
        if (small) H.outlinedText(small, 540, y + 90, H.FONT_IT, 64, 800, '#fff', 10);
        ctx.globalAlpha = 1;
      }
    }
    void dark;
  }

  return {
    PRESETS,
    TEAMS,
    has: (scene) => !!CLASSES[scene],
    create: (o) => new CLASSES[o.scene](o),
    onEvent,
    update,
    background,
    draw,
    drawText,
  };
});
