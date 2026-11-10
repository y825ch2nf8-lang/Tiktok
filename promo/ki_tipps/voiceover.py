"""Mix the spoken commentary into the rendered ki_tipps videos.

usage: python3 promo/ki_tipps/voiceover.py            (run from the repo root)
vo/NN.mp3 holds one take per video (five sentences, see SCRIPTS). The take is cut at its sentence pauses and
each sentence is placed at the start of its scene, so voice and picture stay in sync; music is ducked under it.
"""
import re, subprocess, sys, glob, os
D = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(D))
SCENES = [0.10, 2.50, 6.10, 12.10, 18.10]; DUR = 21.6
CTA = "Probier's aus, und folg mir für mehr KI-Tricks."
SCRIPTS = {
 '01': "Dein Fernseher zeigt dir Werbung?|Öffne die Einstellungen und mach ein Foto vom Menü.|Dann fragst du die KI: Wo schalte ich hier Werbung und Tracking aus?|Sie zeigt dir den Weg durchs Menü, und du stellst beides auf Aus.",
 '02': "Brief vom Amt, kein Wort verstanden?|Deck Namen und Adresse ab und mach ein Foto.|Dann fragst du die KI: Erklär mir diesen Brief in einfachen Worten. Was muss ich bis wann tun?|Du erfährst, worum es geht, was du tun musst, und bis wann.",
 '03': "Dieses Abo kostet dich jeden Monat Geld.|Such dir Anbieter und Kundennummer raus.|Dann sagst du der KI: Schreib mir eine Kündigung zum nächstmöglichen Termin, mit Bitte um Bestätigung.|Du bekommst das fertige Schreiben und musst es nur noch abschicken.",
 '04': "Nichts zu essen da?|Mach die Tür auf und fotografier deinen Kühlschrank.|Dann fragst du die KI: Was kann ich daraus in zwanzig Minuten kochen? Gib mir drei Ideen.|Du bekommst drei Gerichte mit Rezept, ganz ohne Einkaufen.",
 '05': "Zahlst du zu viel fürs Handy?|Lad deine Rechnung als PDF aus der App.|Dann fragst du die KI: Welche Posten sind Extras oder Drittanbieter, die ich kündigen kann?|Sie erklärt dir jeden Posten und zeigt, wie du die Extras loswirst.",
 '06': "Deine Waschmaschine blinkt nur noch?|Fotografier das Display mit dem Fehlercode.|Dann fragst du die KI: Was bedeutet dieser Fehler, und was kann ich selbst prüfen?|Du erfährst, was der Code heißt, und wann wirklich der Techniker ran muss.",
 '07': "Dein Handy trackt dich.|Sag der KI, welches Modell du hast.|Dann schreibst du: Führ mich Schritt für Schritt durch die Einstellungen, die Tracking und personalisierte Werbung abschalten.|Danach sind App-Tracking und personalisierte Werbung aus.",
 '08': "Flug verspätet? Hol dir Geld zurück.|Notier dir Flugnummer, Datum und Verspätung.|Dann sagst du der KI: Schreib eine Forderung an die Airline, nach der EU-Fluggastrechte-Verordnung.|Ab drei Stunden Verspätung stehen dir oft zweihundertfünfzig bis sechshundert Euro zu.",
 '09': "Erst prüfen, dann unterschreiben.|Lad den Vertrag hoch und schwärz vorher deine Daten.|Dann fragst du die KI: Welche Klauseln sind ungewöhnlich oder nachteilig für mich?|Sie markiert auffällige Stellen und erklärt sie in einfachen Worten.",
 '10': "Stopp, noch nicht kaufen!|Fotografier das Produkt mit dem Preisschild.|Dann fragst du die KI: Ist dieser Preis gut? Nenn mir typische Preise und günstigere Alternativen.|Du bekommst eine Einschätzung, aber check die Preise kurz gegen.",
}
def run(*a): return subprocess.run(a, capture_output=True, text=True)
def probe(f): return float(run('ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f).stdout)

for n, txt in sorted(SCRIPTS.items()):
    vo = f'{D}/vo/{n}.mp3'; vid = glob.glob(f'{D}/out/ki_trick_{n}_*_reel.mp4')[0]
    parts = txt.split('|') + [CTA]; total = probe(vo)
    log = run('ffmpeg', '-i', vo, '-af', 'silencedetect=noise=-35dB:d=0.15', '-f', 'null', '-').stderr
    st = [float(v) for v in re.findall(r'silence_start: ([\d.]+)', log)]; en = [float(v) for v in re.findall(r'silence_end: ([\d.]+)', log)]
    sil = [(a, b) for a, b in zip(st, en) if a > 0.2 and b < total - 0.2]
    lead = en[0] if st and st[0] < 0.05 else 0.0
    tail = st[-1] if len(st) > len(en) or (en and en[-1] > total - 0.05) else total
    # expected sentence boundaries from character counts, snapped to the nearest real pause
    chars = [len(p) for p in parts]; cum = 0; cuts = []
    for c in chars[:-1]:
        cum += c; guess = lead + (tail - lead) * cum / sum(chars)
        cand = [s for s in sil if s not in cuts]
        cuts.append(min(cand, key=lambda s: abs((s[0] + s[1]) / 2 - guess)))
    cuts.sort()
    segs = []; a = lead
    for s in cuts: segs.append((a, s[0] + 0.06)); a = s[1] - 0.04
    segs.append((a, tail + 0.08))
    # optional re-recorded hook line (vo/NN_hook.mp3) replaces the first sentence; long ones are sped up slightly
    hook = f'{D}/vo/{n}_hook.mp3'; hk = None
    if os.path.exists(hook):
        hl = run('ffmpeg', '-i', hook, '-af', 'silencedetect=noise=-35dB:d=0.1', '-f', 'null', '-').stderr
        hs = [float(v) for v in re.findall(r'silence_start: ([\d.]+)', hl)]; he = [float(v) for v in re.findall(r'silence_end: ([\d.]+)', hl)]
        ht = probe(hook); a0 = he[0] if hs and hs[0] < 0.05 else 0.0
        b0 = hs[-1] + 0.08 if hs and (len(hs) > len(he) or he[-1] > ht - 0.05) and hs[-1] > a0 else ht
        tempo = min(1.18, max(1.0, (b0 - a0) / 2.25)); hk = (a0, b0, tempo); segs[0] = (0, (b0 - a0) / tempo)
    pos = []; t = 0
    for (a, b), sc in zip(segs, SCENES): p = max(sc, t + 0.10); pos.append(p); t = p + (b - a)
    over = t - (DUR - 0.15)
    info = ' '.join(f'{p:.2f}+{b - a:.2f}' for p, (a, b) in zip(pos, segs))
    print(n, f'take {total:.2f}s  placed: {info}  end {t:.2f}' + ('  OVERRUN' if over > 0 else ''))
    fc = ''.join(f'[1:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.02,adelay={int(p * 1000)}:all=1[v{i}];' for i, ((a, b), p) in enumerate(zip(segs, pos)) if not (hk and i == 0))
    if hk: fc += f'[2:a]atrim={hk[0]:.3f}:{hk[1]:.3f},asetpts=PTS-STARTPTS,atempo={hk[2]:.3f},adelay={int(pos[0] * 1000)}:all=1[v0];'
    fc += ''.join(f'[v{i}]' for i in range(5)) + 'amix=inputs=5:normalize=0,highpass=f=70,acompressor=threshold=-18dB:ratio=3:attack=5:release=120:makeup=4,apad=whole_dur=21.6,asplit[vo][sc];'
    fc += '[0:a]volume=0.55[m];[m][sc]sidechaincompress=threshold=0.02:ratio=8:attack=15:release=350[duck];'
    fc += '[duck][vo]amix=inputs=2:normalize=0,alimiter=limit=0.8:level=0[a]'
    out = f'{ROOT}/output/ki_tipps/' + os.path.basename(vid).replace('_reel.mp4', '_stimme.mp4')
    r = run('ffmpeg', '-y', '-loglevel', 'error', '-i', vid, '-i', vo, *(['-i', hook] if hk else []), '-filter_complex', fc, '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-t', str(DUR), '-movflags', '+faststart', out)
    if r.returncode: print(r.stderr); sys.exit(1)
