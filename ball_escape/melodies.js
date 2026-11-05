/*
 * Gemeinfreie Melodien (Komponisten > 70 Jahre tot, § 64 UrhG), eigene Transkription vom Notentext.
 * Jede Kollision spielt die nächste Note. Werte = MIDI-Nummern (60 = C4).
 * Eigene Melodie hinzufügen: einfach ein neues Objekt mit `notes` (Notennamen) eintragen.
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
    let n = NAMES[m[1]] + (m[2] === '#' ? 1 : m[2] === 'b' ? -1 : 0);
    return n + (parseInt(m[3], 10) + 1) * 12;
  }
  const seq = (s) => s.trim().split(/\s+/).map(midi);
  const up = (arr, k) => arr.map((n) => n + k);

  // Grieg (†1907): In der Halle des Bergkönigs – Hauptthema in h-Moll.
  const berg = seq(`
    B3 C#4 D4 E4 F#4 D4 F#4  F4 C#4 F4  E4 C4 E4
    B3 C#4 D4 E4 F#4 D4 F#4 B4  A4 F#4 D4 F#4 A4`);

  // Beethoven (†1827): Ode an die Freude.
  const ode = seq(`
    E4 E4 F4 G4 G4 F4 E4 D4 C4 C4 D4 E4 E4 D4 D4
    E4 E4 F4 G4 G4 F4 E4 D4 C4 C4 D4 E4 D4 C4 C4
    D4 D4 E4 C4 D4 E4 F4 E4 C4 D4 E4 F4 E4 D4 C4 D4 G3
    E4 E4 F4 G4 G4 F4 E4 D4 C4 C4 D4 E4 D4 C4 C4`);

  // Beethoven (†1827): Für Elise – Anfangsthema.
  const elise = seq(`
    E5 D#5 E5 D#5 E5 B4 D5 C5 A4  C4 E4 A4 B4  E4 G#4 B4 C5
    E4 E5 D#5 E5 D#5 E5 B4 D5 C5 A4  C4 E4 A4 B4  E4 C5 B4 A4`);

  const MELODIES = {
    bergkoenig: {
      title: 'In der Halle des Bergkönigs (Grieg)',
      // Wie im Original: Thema wiederholt sich und steigt höher.
      notes: [].concat(berg, berg, up(berg, 7), up(berg, 7), up(berg, 12), up(berg, 12)),
      transpose: 12,
      tonic: midi('B3'),
      chord: [0, 3, 7], // Moll
    },
    ode: {
      title: 'Ode an die Freude (Beethoven)',
      notes: ode,
      transpose: 12,
      tonic: midi('C4'),
      chord: [0, 4, 7],
    },
    elise: {
      title: 'Für Elise (Beethoven)',
      notes: elise,
      transpose: 0,
      tonic: midi('A4'),
      chord: [0, 3, 7],
    },
  };

  function get(name) {
    const m = MELODIES[name];
    if (!m) throw new Error('Unbekannte Melodie "' + name + '". Verfügbar: ' + Object.keys(MELODIES).join(', '));
    return m;
  }

  return { MELODIES, get, midi };
});
