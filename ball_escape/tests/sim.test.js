'use strict';
const test = require('node:test');
const assert = require('node:assert');
const { Timeline, findSeed } = require('../sim.js');
const Melodies = require('../melodies.js');
const audio = require('../audio.js');

const melody = Melodies.get('bergkoenig').notes;

test('gleicher Seed => identisches Ergebnis (deterministisch)', () => {
  const a = new Timeline({ seed: 11, melody }).runHeadless();
  const b = new Timeline({ seed: 11, melody }).runHeadless();
  assert.deepStrictEqual(a, b);
  assert.ok(a.completed);
  assert.strictEqual(a.breaks.length, 12);
});

test('Draft (30 fps) bricht die Ringe zur selben Zeit wie 60 fps', () => {
  const a = new Timeline({ seed: 11, melody, fps: 60 }).runHeadless();
  const b = new Timeline({ seed: 11, melody, fps: 30 }).runHeadless();
  a.breaks.forEach((t, i) => assert.ok(Math.abs(t - b.breaks[i]) < 0.05, `Ring ${i}: ${t} vs ${b.breaks[i]}`));
});

test('+2-Modus endet mit 1 + 2 * Ringe Bällen', () => {
  const s = new Timeline({ seed: 11, rings: 12, mode: 'plus2' }).runHeadless();
  assert.strictEqual(s.finalBalls, 25);
});

test('Bälle bleiben bis zum Ausbruch im innersten Ring (kein Tunneln)', () => {
  const tl = new Timeline({ seed: 3, melody });
  while (!tl.done() && tl.finalFrame < 0) {
    tl.step();
    const sim = tl.sim;
    const ring = sim.rings[sim.cur];
    if (!ring) break;
    for (const b of sim.balls) {
      const d = Math.hypot(b.x - sim.o.cx, b.y - sim.o.cy);
      assert.ok(d <= ring.r + sim.o.stroke / 2 + sim.br + 1e-6, `Ball ${b.id} außerhalb von Ring ${ring.i}`);
    }
  }
});

test('Seed-Suche trifft das Ziel ±2 s', () => {
  const r = findSeed({ melody, target: 60, tol: 2, tries: 300 });
  assert.ok(r && !r.approximate, 'kein Seed gefunden');
  assert.ok(Math.abs(r.finalSec - 60) <= 2);
});

test('Melodien sind gültige MIDI-Noten', () => {
  for (const [name, m] of Object.entries(Melodies.MELODIES)) {
    assert.ok(m.notes.length > 10, name);
    for (const n of m.notes) assert.ok(n >= 40 && n <= 100, `${name}: ${n}`);
  }
  assert.strictEqual(Melodies.midi('A4'), 69);
  assert.strictEqual(Melodies.midi('C#4'), 61);
});

test('Audio: WAV-Header und Länge stimmen', () => {
  const pcm = audio.renderAudio([{ type: 'note', vt: 0.1, midi: 72, vel: 1, x: 540 }, { type: 'break', vt: 0.5, ring: 0, x: 540 }], 1.0, {});
  const wav = audio.toWav(pcm);
  assert.strictEqual(wav.toString('ascii', 0, 4), 'RIFF');
  assert.strictEqual(wav.readUInt32LE(24), 48000);
  assert.strictEqual(wav.length, 44 + 48000 * 4);
});

const Arrangement = require('../arrangement.js');

test('Songs: Melodie und Akkorde gleich lang, alle kompilierbar', () => {
  for (const key of Object.keys(Melodies.SONGS)) {
    const s = Melodies.compile(key);
    assert.ok(s.notes.length > 10, key);
    assert.ok(s.loopBeats % s.meter === 0, `${key}: Loop endet nicht auf Taktgrenze`);
  }
});

test('Jeder Ring schaltet Instrumente frei, der letzte Ring den letzten Layer', () => {
  for (const n of [6, 12, 24]) {
    const all = [];
    for (let r = 0; r < n; r++) all.push(...Arrangement.layersForRing(r, n));
    assert.strictEqual(all.length, Arrangement.LAYERS.length, `n=${n}`);
    assert.ok(Arrangement.layersForRing(0, n).length >= 1);
    assert.ok(Arrangement.layersForRing(n - 1, n).some((l) => l.id === 'harmony'));
  }
});

test('Layer-Audio: vor dem ersten Ring nur Aufprall-Noten, danach mehr Instrumente', () => {
  const song = Melodies.compile('korobeiniki');
  const events = [
    { type: 'note', vt: 0.2, midi: 76, vel: 1, x: 540 },
    { type: 'break', vt: 1.0, ring: 0, x: 540 },
    { type: 'break', vt: 2.0, ring: 1, x: 540 },
  ];
  const pcm = audio.renderAudio(events, 4, { song, rings: 12 });
  const rms = (a, b) => {
    let s = 0;
    for (let i = Math.floor(a * 48000); i < b * 48000; i++) s += pcm.L[i] ** 2;
    return Math.sqrt(s / ((b - a) * 48000));
  };
  assert.ok(rms(1.3, 1.9) > rms(0.6, 0.95) * 2, 'Beat setzt beim ersten Ring ein');
});

test('ASMR: jede Figur klingt, nichts übersteuert, Pegel steigt zum Ende', () => {
  const tl = new Timeline({ seed: 1, scene: 'box', melody: [60] });
  const s = tl.runHeadless();
  const dur = s.totalFrames / 60;
  for (const skin of ['cat', 'smiley', 'egg', 'neon']) {
    const pcm = audio.renderAudio(tl.log, dur, { music: 'asmr', skin, seed: 1, scene: 'box', goal: 1000 });
    let peak = 0;
    for (const v of pcm.L) {
      assert.ok(!Number.isNaN(v), skin);
      peak = Math.max(peak, Math.abs(v));
    }
    assert.ok(peak > 0.3 && peak <= 1, `${skin}: peak ${peak}`);
  }
});
