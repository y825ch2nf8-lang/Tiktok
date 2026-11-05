/*
 * Arrangement: Jeder zerbrochene Ring schaltet ein Instrument frei. Beim letzten Ring läuft der
 * komplette Song. Erzeugt den Notenplan (Sekunden) pro Instrument aus einem Song (melodies.js).
 * Läuft in Node (Audio) und im Browser (Beschriftung + Beat-Puls im Bild).
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.Arrangement = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  // Reihenfolge = Reihenfolge, in der die Ringe die Instrumente freischalten
  const LAYERS = [
    { id: 'kick', label: 'Beat' },
    { id: 'pluck', label: 'Melodie' },
    { id: 'bass', label: 'Bass' },
    { id: 'hats', label: 'Hi-Hats' },
    { id: 'pad', label: 'Synth-Flächen' },
    { id: 'clap', label: 'Clap' },
    { id: 'arp', label: 'Arpeggio' },
    { id: 'lead', label: 'Lead-Synth' },
    { id: 'bell', label: 'Glocken' },
    { id: 'perc', label: 'Percussion' },
    { id: 'stabs', label: 'Sub & Stabs' },
    { id: 'harmony', label: 'Harmonie' },
  ];
  const LAYER_OF = { kick: 0, pluck: 1, bass: 2, hats: 3, pad: 4, clap: 5, arp: 6, lead: 7, bell: 8, openhat: 9, shaker: 9, stab: 10, sub: 10, harmony: 11 };

  /** Ring-Index (0-basiert), der Layer j freischaltet. Letzter Layer = letzter Ring. */
  function ringForLayer(j, nRings) {
    if (nRings <= 1) return 0;
    return Math.round((j * (nRings - 1)) / (LAYERS.length - 1));
  }

  function layersForRing(r, nRings) {
    return LAYERS.filter((_, j) => ringForLayer(j, nRings) === r);
  }

  /** Freischaltzeit (Sekunden) je Layer aus den Ringbruch-Zeiten. */
  function unlockTimes(breakTimes, nRings) {
    return LAYERS.map((_, j) => {
      const r = ringForLayer(j, nRings);
      return r < breakTimes.length ? breakTimes[r] : Infinity;
    });
  }

  function chordTones(c, base) {
    // Akkordtöne um `base` (MIDI) herum, aufsteigend
    return c.intervals.map((iv) => {
      let n = base + ((c.root + iv) % 12);
      if (n < base) n += 12;
      return n;
    }).sort((a, b) => a - b);
  }

  /** Akkord zur Zeit t (Sekunden) – für Aufprall-Töne im Akkord. */
  function chordAt(song, startSec, t) {
    const bs = 60 / song.bpm;
    let beat = (t - startSec) / bs;
    beat = ((beat % song.loopBeats) + song.loopBeats) % song.loopBeats;
    for (const c of song.chords) if (beat >= c.beat && beat < c.beat + c.dur) return c;
    return song.chords[0];
  }

  /**
   * Alle Noten von startSec bis endSec. Ergebnis: [{ inst, layer, t, dur, midi, vel }]
   */
  function schedule(song, startSec, endSec) {
    const bs = 60 / song.bpm;
    const out = [];
    const push = (inst, beat, durBeats, midi, vel) => {
      const t = startSec + beat * bs;
      if (t < endSec) out.push({ inst, layer: LAYER_OF[inst], t, dur: durBeats * bs, midi, vel: vel == null ? 1 : vel });
    };
    const loops = Math.ceil((endSec - startSec) / (song.loopBeats * bs)) + 1;
    const d = song.drums;
    for (let k = 0; k < loops; k++) {
      const off = k * song.loopBeats;
      // Drums
      for (let bar = 0; bar < song.loopBeats; bar += song.meter) {
        for (const p of d.kick) push('kick', off + bar + p, 0.5);
        for (const p of d.clap) push('clap', off + bar + p, 0.5);
        for (let p = 0; p < song.meter - 1e-9; p += d.hat) push('hats', off + bar + p, d.hat, null, p % 1 === 0 ? 1 : 0.7);
        for (let p = 0; p < song.meter - 1e-9; p += 1) push('openhat', off + bar + p + 0.5, 0.5);
        for (let p = 0; p < song.meter - 1e-9; p += 0.25) push('shaker', off + bar + p, 0.25, null, p % 0.5 === 0 ? 0.6 : 1);
      }
      // Harmonie-Instrumente
      for (const c of song.chords) {
        const b0 = off + c.beat;
        const bassMidi = 36 + c.bass;
        for (let p = 0; p < c.dur - 1e-9; p += 0.5) push('bass', b0 + p, 0.45, bassMidi + (p % 1 === 0 ? 0 : 12), p % 1 === 0 ? 1 : 0.8);
        push('sub', b0, c.dur, 24 + c.bass);
        for (const n of chordTones(c, 57)) push('pad', b0, c.dur, n);
        const arp = chordTones(c, 69);
        const seq = [arp[0], arp[1], arp[2], arp[0] + 12, arp[2], arp[1]];
        let i = 0;
        for (let p = 0; p < c.dur - 1e-9; p += 0.25) push('arp', b0 + p, 0.25, seq[i++ % seq.length]);
        for (let p = 0.5; p < c.dur - 1e-9; p += 1) for (const n of chordTones(c, 60)) push('stab', b0 + p, 0.25, n);
      }
      // Melodie-Instrumente
      for (const n of song.notes) {
        const b = off + n.beat;
        push('pluck', b, n.dur, n.midi);
        push('lead', b, n.dur, n.midi);
        push('bell', b, n.dur, n.midi + 12);
        const c = chordAt(song, 0, n.beat * bs);
        const below = chordTones(c, n.midi - 12).filter((x) => x <= n.midi - 3);
        if (below.length) push('harmony', b, n.dur, below[below.length - 1]);
      }
    }
    out.sort((a, b) => a.t - b.t);
    return out;
  }

  return { LAYERS, LAYER_OF, ringForLayer, layersForRing, unlockTimes, schedule, chordAt, chordTones };
});
