/*
 * Gemeinfreie Songs (Komponist > 70 Jahre tot, § 64 UrhG, bzw. Volkslied), eigene Transkription.
 *
 * Format:
 *   melody: "NOTE:Dauer ..."   Dauer in Schlägen (1 = ein Beat), R = Pause, | nur zur Lesbarkeit
 *   chords: "Akkord:Dauer ..."  z. B. Am, C, G7, Dm, Ab, Am/E (Slash = Bassnote)
 *   bpm, meter (Schläge pro Takt), drums (Positionen im Takt), form (Transposition je Durchlauf)
 * Melodie und Akkorde müssen gleich lang sein. Aus der Melodie entstehen auch die Aufprall-Noten.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.Melodies = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const NAMES = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11, H: 11 };
  function midi(name) {
    const m = /^([A-H])(#|b)?(-?\d)$/.exec(name);
    if (!m) throw new Error('Unbekannte Note: ' + name);
    const n = NAMES[m[1]] + (m[2] === '#' ? 1 : m[2] === 'b' ? -1 : 0);
    return n + (parseInt(m[3], 10) + 1) * 12;
  }

  const QUALITY = { '': [0, 4, 7], m: [0, 3, 7], 7: [0, 4, 7, 10], m7: [0, 3, 7, 10], maj7: [0, 4, 7, 11], dim: [0, 3, 6] };
  function chord(name) {
    const [main, slash] = name.split('/');
    const m = /^([A-G])(#|b)?(.*)$/.exec(main);
    if (!m || !(m[3] in QUALITY)) throw new Error('Unbekannter Akkord: ' + name);
    const root = NAMES[m[1]] + (m[2] === '#' ? 1 : m[2] === 'b' ? -1 : 0);
    let bass = root;
    if (slash) {
      const s = /^([A-G])(#|b)?$/.exec(slash);
      bass = NAMES[s[1]] + (s[2] === '#' ? 1 : s[2] === 'b' ? -1 : 0);
    }
    return { root, bass, intervals: QUALITY[m[3]], name };
  }

  function parseTimed(str, fn) {
    return str
      .replace(/\|/g, ' ')
      .trim()
      .split(/\s+/)
      .map((tok) => {
        const i = tok.lastIndexOf(':');
        if (i < 0) throw new Error('Dauer fehlt: ' + tok);
        return { v: fn(tok.slice(0, i)), dur: parseFloat(tok.slice(i + 1)) };
      });
  }

  const SONGS = {
    korobeiniki: {
      title: 'Korobeiniki (Volkslied, bekannt aus Tetris)',
      bpm: 144, meter: 4, transpose: 0,
      melody: `E5:1 B4:.5 C5:.5 D5:1 C5:.5 B4:.5 | A4:1 A4:.5 C5:.5 E5:1 D5:.5 C5:.5 | B4:1.5 C5:.5 D5:1 E5:1 | C5:1 A4:1 A4:2 |
               R:.5 D5:1 F5:.5 A5:1 G5:.5 F5:.5 | E5:1.5 C5:.5 E5:1 D5:.5 C5:.5 | B4:1 B4:.5 C5:.5 D5:1 E5:1 | C5:1 A4:1 A4:2`,
      chords: 'Am/E:4 Am:4 E:4 Am:4 Dm:4 C:4 E:4 Am:4',
      form: [0],
    },
    turca: {
      title: 'Türkischer Marsch (Mozart)',
      bpm: 126, meter: 2, transpose: 0,
      melody: `B4:.25 A4:.25 G#4:.25 A4:.25 | C5:.5 R:.5 D5:.25 C5:.25 B4:.25 C5:.25 | E5:.5 R:.5 F5:.25 E5:.25 D#5:.25 E5:.25 |
               B5:.25 A5:.25 G#5:.25 A5:.25 B5:.25 A5:.25 G#5:.25 A5:.25 | C6:1`,
      chords: 'Am:3 Am:2 E:2 Am:1',
      form: [0, 0, -12, 0],
    },
    hummelflug: {
      title: 'Hummelflug (Rimski-Korsakow)',
      bpm: 140, meter: 2, transpose: 0,
      melody: `E5:.25 D#5:.25 D5:.25 C#5:.25 C5:.25 F5:.25 E5:.25 D#5:.25 | E5:.25 D#5:.25 D5:.25 C#5:.25 C5:.25 C#5:.25 D5:.25 D#5:.25 |
               E5:.25 D#5:.25 D5:.25 C#5:.25 C5:.25 F5:.25 E5:.25 D#5:.25 | E5:.25 D#5:.25 D5:.25 C#5:.25 C5:.25 C#5:.25 D5:.25 D#5:.25`,
      chords: 'Am:2 E:2 Am:2 E:2',
      form: [0, 5, 0, -7],
    },
    jinglebells: {
      title: 'Jingle Bells (Pierpont)',
      bpm: 128, meter: 4, transpose: 12,
      melody: `E4:1 E4:1 E4:2 | E4:1 E4:1 E4:2 | E4:1 G4:1 C4:1.5 D4:.5 | E4:4 |
               F4:1 F4:1 F4:1.5 F4:.5 | F4:1 E4:1 E4:1 E4:.5 E4:.5 | E4:1 D4:1 D4:1 E4:1 | D4:2 G4:2 |
               E4:1 E4:1 E4:2 | E4:1 E4:1 E4:2 | E4:1 G4:1 C4:1.5 D4:.5 | E4:4 |
               F4:1 F4:1 F4:1.5 F4:.5 | F4:1 E4:1 E4:1 E4:.5 E4:.5 | G4:1 G4:1 F4:1 D4:1 | C4:4`,
      chords: 'C:4 C:4 C:4 C:4 F:4 C:4 D7:4 G7:4 C:4 C:4 C:4 C:4 F:4 C:4 G7:4 C:4',
      form: [0],
    },
    toccata: {
      title: 'Toccata und Fuge d-Moll (Bach)',
      bpm: 96, meter: 4, transpose: 0,
      melody: `A5:.25 G5:.25 A5:3.5 | G5:.25 F5:.25 E5:.25 D5:.25 C#5:1 D5:2 |
               A4:.25 G4:.25 A4:3.5 | E4:.5 F4:.5 C#4:1 D4:2 |
               A3:.25 G3:.25 A3:3.5 | G3:.25 F3:.25 E3:.25 D3:.25 C#3:1 D3:2`,
      chords: 'Dm:4 A:2 Dm:2 Dm:4 A:2 Dm:2 Dm:4 A:2 Dm:2',
      form: [0],
    },
    bergkoenig: {
      title: 'In der Halle des Bergkönigs (Grieg)',
      bpm: 132, meter: 4, transpose: 12,
      melody: `B3:.5 C#4:.5 D4:.5 E4:.5 F#4:.5 D4:.5 F#4:1 | F4:.5 C#4:.5 F4:1 E4:.5 C4:.5 E4:1 |
               B3:.5 C#4:.5 D4:.5 E4:.5 F#4:.5 D4:.5 F#4:.5 B4:.5 | A4:.5 F#4:.5 D4:.5 F#4:.5 A4:2`,
      chords: 'Bm:4 C#:2 C:2 Bm:4 D:4',
      form: [0, 0, 7, 7],
    },
    fuenfte: {
      title: '5. Sinfonie (Beethoven)',
      bpm: 108, meter: 2, transpose: 12,
      melody: `R:.5 G4:.5 G4:.5 G4:.5 | Eb4:2 | R:.5 F4:.5 F4:.5 F4:.5 | D4:2 |
               R:.5 G4:.5 G4:.5 G4:.5 | Eb4:.5 Ab4:.5 Ab4:.5 Ab4:.5 | G4:.5 Eb5:.5 Eb5:.5 Eb5:.5 | C5:2`,
      chords: 'Cm:2 Cm:2 G:2 G:2 Cm:2 Ab:2 Cm:2 Ab:2',
      form: [0],
    },
    elise: {
      title: 'Für Elise (Beethoven)',
      bpm: 140, meter: 3, transpose: 0,
      drums: { kick: [0], clap: [1.5], hat: 0.5 },
      melody: `E5:.5 D#5:.5 E5:.5 B4:.5 D5:.5 C5:.5 | A4:1 R:.5 C4:.5 E4:.5 A4:.5 | B4:1 R:.5 E4:.5 G#4:.5 B4:.5 |
               C5:1 R:.5 E4:.5 E5:.5 D#5:.5 | E5:.5 D#5:.5 E5:.5 B4:.5 D5:.5 C5:.5 | A4:1 R:.5 C4:.5 E4:.5 A4:.5 |
               B4:1 R:.5 E4:.5 C5:.5 B4:.5 | A4:2 E5:.5 D#5:.5`,
      chords: 'Am:3 Am:3 E:3 Am:3 Am:3 Am:3 E:3 Am:3',
      form: [0],
    },
    ode: {
      title: 'Ode an die Freude (Beethoven)',
      bpm: 116, meter: 4, transpose: 12,
      melody: `E4:1 E4:1 F4:1 G4:1 | G4:1 F4:1 E4:1 D4:1 | C4:1 C4:1 D4:1 E4:1 | E4:1.5 D4:.5 D4:2 |
               E4:1 E4:1 F4:1 G4:1 | G4:1 F4:1 E4:1 D4:1 | C4:1 C4:1 D4:1 E4:1 | D4:1.5 C4:.5 C4:2 |
               D4:1 D4:1 E4:1 C4:1 | D4:1 E4:.5 F4:.5 E4:1 C4:1 | D4:1 E4:.5 F4:.5 E4:1 D4:1 | C4:1 D4:1 G3:2 |
               E4:1 E4:1 F4:1 G4:1 | G4:1 F4:1 E4:1 D4:1 | C4:1 C4:1 D4:1 E4:1 | D4:1.5 C4:.5 C4:2`,
      chords: 'C:4 G:4 C:4 C:2 G:2 C:4 G:4 C:4 G:2 C:2 G:4 G7:2 C:2 G7:4 C:2 G:2 C:4 G:4 C:4 G:2 C:2',
      form: [0],
    },
    nachtmusik: {
      title: 'Eine kleine Nachtmusik (Mozart)',
      bpm: 128, meter: 4, transpose: 12,
      melody: `G4:1 R:.5 D4:.5 G4:1 R:.5 D4:.5 | G4:.5 D4:.5 G4:.5 B4:.5 D5:1 R:1 |
               C5:1 R:.5 A4:.5 C5:1 R:.5 A4:.5 | C5:.5 A4:.5 F#4:.5 A4:.5 D4:1 R:1`,
      chords: 'G:4 G:4 D7:4 D7:4',
      form: [0],
    },
    morgenstimmung: {
      title: 'Morgenstimmung (Grieg)',
      bpm: 168, meter: 6, transpose: 12,
      drums: { kick: [0, 3], clap: [3], hat: 1 },
      melody: `G4:1 E4:1 D4:1 C4:1 D4:1 E4:1 | G4:1 E4:1 D4:1 C4:1 D4:1 E4:1 |
               D4:1 E4:1 G4:1 E4:1 G4:1 A4:1 | E4:1 A4:1 G4:1 E4:1 D4:1 C4:1`,
      chords: 'C:6 C:6 C:3 Am:3 Am:3 C:3',
      form: [0],
    },
    wiegenlied: {
      title: 'Wiegenlied (Brahms)',
      bpm: 100, meter: 3, transpose: 12,
      drums: { kick: [0], clap: [2], hat: 0.5 },
      melody: `G4:2 E4:.5 E4:.5 | G4:2 E4:.5 G4:.5 | C5:1 B4:1.5 A4:.5 | A4:1 G4:1 D4:.5 E4:.5 |
               F4:1 D4:1 D4:.5 E4:.5 | F4:2 D4:.5 F4:.5 | B4:.5 A4:.5 G4:1 B4:1 | C5:2 E4:.5 E4:.5`,
      chords: 'C:3 C:3 F:3 G:3 G7:3 G7:3 G7:3 C:3',
      form: [0],
    },
  };

  const DEFAULT_DRUMS = {
    2: { kick: [0, 1], clap: [1], hat: 0.5 },
    3: { kick: [0], clap: [2], hat: 0.5 },
    4: { kick: [0, 1, 2, 3], clap: [1, 3], hat: 0.5 },
    6: { kick: [0, 3], clap: [3], hat: 1 },
  };

  /** Song in einen Loop aus absoluten Beats übersetzen (inkl. Form/Transposition). */
  function compile(key) {
    const s = SONGS[key];
    if (!s) throw new Error('Unbekannter Song "' + key + '". Verfügbar: ' + Object.keys(SONGS).join(', '));
    if (s._compiled) return s._compiled;
    const mel = parseTimed(s.melody, (v) => (v === 'R' ? null : midi(v)));
    const chs = parseTimed(s.chords, chord);
    const melLen = mel.reduce((a, n) => a + n.dur, 0);
    const chLen = chs.reduce((a, c) => a + c.dur, 0);
    if (Math.abs(melLen - chLen) > 1e-6) throw new Error(`${key}: Melodie (${melLen}) und Akkorde (${chLen}) unterschiedlich lang`);
    const notes = [];
    const chords = [];
    let beat = 0;
    for (const tr of s.form) {
      let b = beat;
      for (const n of mel) {
        if (n.v != null) notes.push({ beat: b, dur: n.dur, midi: n.v + tr + s.transpose });
        b += n.dur;
      }
      b = beat;
      for (const c of chs) {
        chords.push({ beat: b, dur: c.dur, root: (c.v.root + tr + 120) % 12, bass: (c.v.bass + tr + 120) % 12, intervals: c.v.intervals });
        b += c.dur;
      }
      beat += melLen;
    }
    return (s._compiled = {
      key,
      title: s.title,
      bpm: s.bpm,
      meter: s.meter,
      drums: s.drums || DEFAULT_DRUMS[s.meter] || DEFAULT_DRUMS[4],
      loopBeats: beat,
      notes,
      chords,
    });
  }

  // Kompatible Sicht für die Aufprall-Noten (eine Note pro Kollision)
  const MELODIES = {};
  for (const key of Object.keys(SONGS)) {
    Object.defineProperty(MELODIES, key, {
      enumerable: true,
      get() {
        const c = compile(key);
        const first = c.chords[0];
        return {
          title: SONGS[key].title,
          notes: c.notes.map((n) => n.midi),
          transpose: 0,
          tonic: 48 + first.root,
          chord: first.intervals.slice(0, 3),
        };
      },
    });
  }

  function get(name) {
    if (!SONGS[name]) throw new Error('Unbekannte Melodie "' + name + '". Verfügbar: ' + Object.keys(SONGS).join(', '));
    return MELODIES[name];
  }

  return { SONGS, MELODIES, get, compile, midi, chord };
});
