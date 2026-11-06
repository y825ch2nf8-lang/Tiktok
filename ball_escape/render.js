#!/usr/bin/env node
/*
 * Ball-Escape-Video rendern: Seed suchen -> Audio synthetisieren -> Frames im Headless-Chromium
 * zeichnen -> per FFmpeg zu MP4 (H.264, 1080x1920, 60 fps, AAC). Dazu Caption + Hashtags.
 *
 *   node ball_escape/render.js                       # Standard: 12 Ringe, +2, Bergkönig, ~60 s Finale
 *   node ball_escape/render.js --draft               # schnelle Vorschau (540x960, 30 fps, gleiches Ergebnis)
 *   node ball_escape/render.js --mode double --target 25 --melody ode
 *   node ball_escape/render.js --seed 11 --seconds 10
 *   node ball_escape/render.js --melody korobeiniki,turca,hummelflug   # Serie: ein Video pro Song
 *   node ball_escape/render.js --music bounce          # ohne Song-Aufbau, nur Aufprall-Noten
 *   node ball_escape/render.js --scene box --sound asmr # Geräusche statt Musik (passend zur Figur)
 *   node ball_escape/render.js --scene box --sound asmr --threads --skin cat  # Fäden + gezupfter Faden
 *   node ball_escape/render.js --scene layers --sound asmr --reveal meinmeme.mp4  # Meme-Ende
 *   node ball_escape/render.js --serve               # Live-Vorschau im Browser (http://localhost:8080)
 */
'use strict';

const fs = require('fs');
const path = require('path');
const http = require('http');
const { spawn } = require('child_process');
const { once } = require('events');
const audio = require('./audio');
const Melodies = require('./melodies');

const HERE = __dirname;
const ROOT = path.resolve(HERE, '..');

function parseArgs(argv) {
  const a = {
    rings: 12,
    mode: 'plus2',
    melody: 'bergkoenig',
    seed: 'auto',
    target: null,
    tol: 2,
    fps: 60,
    draft: false,
    seconds: null,
    out: null,
    serve: false,
    port: 8080,
    crf: 23, // ≈ 20–30 MB: sieht auf TikTok gleich aus, lässt sich aber am Handy laden
    hook: null,
    seedStart: 1,
    music: 'layers',
    scene: 'rings',
    skin: null,
    lang: 'de',
    watermark: null,
    goal: 1000,
    sound: 'music',
    length: null,
    threads: false,
    loop: null,
    reveal: null,
    revealSec: null,
    asmr: null,
  };
  for (let i = 2; i < argv.length; i++) {
    const k = argv[i].replace(/^--/, '');
    const next = () => argv[++i];
    switch (k) {
      case 'draft': a.draft = true; break;
      case 'threads': a.threads = true; break;
      case 'serve': a.serve = true; break;
      case 'help': case 'h': a.help = true; break;
      case 'rings': case 'target': case 'tol': case 'fps': case 'seconds': case 'port': case 'crf': case 'seedStart':
        a[k] = Number(next()); break;
      case 'seed-start': a.seedStart = Number(next()); break;
      case 'seed': { const v = next(); a.seed = v === 'auto' ? 'auto' : Number(v); break; }
      case 'mode': case 'melody': case 'out': case 'hook': case 'music': case 'scene': case 'skin': case 'lang': case 'watermark': case 'sound': case 'asmr': case 'length': case 'loop': case 'reveal': a[k] = next(); break;
      case 'reveal-sec': a.revealSec = Number(next()); break;
      case 'goal': a.goal = Number(next()); break;
      default: throw new Error('Unbekannte Option: ' + argv[i] + ' (siehe --help)');
    }
  }
  if (a.sound === 'asmr') a.music = 'asmr';
  if (a.threads && a.music === 'asmr' && !a.asmr) a.asmr = 'drop'; // Nutzer-Wahl: Wassertropfen
  // Kurz (≈35 s) = mehr Leute schauen bis zum Ende -> mehr Likes & Push. Lang (≈67 s) erst ab 10K Followern
  // sinnvoll (Creator Rewards). Standard: Box kurz, Ringe lang.
  const FORMAT_TARGET = { dense: 58, layers: 30, battle: 20, press: 30, power: 19, tunnel: 35 };
  if (FORMAT_TARGET[a.scene]) {
    if (a.target == null) a.target = FORMAT_TARGET[a.scene];
    if (a.sound === 'music') a.music = 'asmr';
    a.length = 'format';
  }
  if (!a.length) a.length = a.scene === 'box' ? 'short' : 'long';
  if (a.length === 'short' && a.scene !== 'box') throw new Error('--length short gibt es bisher nur mit --scene box.');
  if (a.target == null) a.target = a.length === 'short' ? 30 : a.mode === 'double' ? 25 : 60;
  if (a.draft) a.fps = 30;
  return a;
}

const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.ttf': 'font/ttf', '.css': 'text/css' };
function serve(port) {
  const server = http.createServer((req, res) => {
    const u = decodeURIComponent(req.url.split('?')[0]);
    const file = path.join(HERE, u === '/' ? 'index.html' : u);
    if (!file.startsWith(HERE) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
      res.writeHead(404);
      return res.end('not found');
    }
    res.writeHead(200, { 'Content-Type': MIME[path.extname(file)] || 'application/octet-stream' });
    fs.createReadStream(file).pipe(res);
  });
  return new Promise((resolve) => server.listen(port, '127.0.0.1', () => resolve(server)));
}

const FORMAT_CAPTIONS = {
  dense: { de: ['Schafft der Ball 500 Ringe in 1 Minute? 😳 Bis zum Ende schauen 👀', 'Hättest du gedacht, dass er es schafft? 👇'], en: ['Can the ball break 500 rings in 1 minute? 😳 Watch till the end 👀', 'Did you think it would make it? 👇'] },
  layers: { de: ['Was ist ganz unten? 👀 Bis zum Ende schauen!', 'Hättest du das erwartet? 🐱👇'], en: ['What is at the bottom? 👀 Watch till the end!', 'Did you expect that? 🐱👇'] },
  battle: { de: ['Wer gewinnt? 🔴🔵🟢🟡 Tipp vorher in die Kommentare!', 'Wer hat richtig getippt? Runde 2 kommt 👇'], en: ['Who wins? 🔴🔵🟢🟡 Guess in the comments first!', 'Who guessed right? Round 2 is coming 👇'] },
  power: { de: ['Jeder Treffer verdoppelt die Kraft 💥 Bis zum Ende schauen 👀', 'Bei welchem Block hast du gedacht, jetzt ist Schluss? 👇'], en: ['Each hit doubles the power 💥 Watch till the end 👀', 'Which block did you think would stop it? 👇'] },
  tunnel: { de: ['Es ist so nervig, wenn der Ball nicht entkommt 😤', 'Bei welcher Zahl hättest du aufgegeben? 👇'], en: ["It's so annoying when the ball won't escape 😤", 'At which number would you have given up? 👇'] },
  press: { de: ['Hydraulische Presse: schafft sie 500 Bälle? 😳 Warte aufs Ende!', 'Was soll ich als Nächstes in die Presse tun? 👇'], en: ['Hydraulic press: can it reach 500 balls? 😳 Wait for the ending!', 'What should I put in the press next? 👇'] },
};

function captionFor(a, sum, mel) {
  const en = a.lang === 'en';
  if (FORMAT_CAPTIONS[a.scene]) {
    const [cap, pin] = FORMAT_CAPTIONS[a.scene][en ? 'en' : 'de'];
    return { hook: cap, caption: cap, hashtags: ['#satisfyingvideos', '#bouncingball', '#asmr', '#physics'], pinnedComment: pin, answer: '' };
  }
  const balls = sum.finalBalls.toLocaleString(en ? 'en-US' : 'de-DE');
  const box = a.scene === 'box';
  const hook = a.hook
    ? a.hook.replace('|', ' ')
    : box
      ? (en ? 'How fast did you guess the song?' : 'Wie schnell hast du den Song erkannt?')
      : (en ? `Can the ball break ${a.rings} rings?` : `Kann der Ball ${a.rings} Ringe zerstören?`);
  if (a.music === 'asmr') {
    const goal = a.goal.toLocaleString(en ? 'en-US' : 'de-DE');
    const melodyDrops = a.asmr === 'dropmelody';
    const q = a.hook ? a.hook.replace('|', ' ') : box
      ? melodyDrops
        ? (en ? 'How fast can you guess the song?' : 'Wie schnell erkennst du den Song?')
        : (en ? `Can it reach ${goal} balls?` : `Schafft er ${goal} Bälle?`)
      : hook;
    return {
      hook: q,
      caption: en ? `${q} 😳 Watch till the end 👀 Sound on 🔊` : `${q} 😳 Bis zum Ende schauen 👀 Ton an 🔊`,
      hashtags: ['#satisfyingvideos', '#bouncingball', '#asmr', '#physics'],
      pinnedComment: melodyDrops
        ? (en ? `It was "${mel.title}" 💧 Which song next? 👇` : `Es war „${mel.title}“ 💧 Welcher Song als Nächstes? 👇`)
        : (en ? `${balls} balls 🔥 Which song or sound next? 👇` : `${balls} Bälle 🔥 Welches Geräusch als Nächstes? 💧👇`),
      answer: balls,
    };
  }
  const layered = a.music !== 'bounce';
  const extra = layered
    ? (en ? ' Every step adds an instrument until the full song plays 🎶' : ' Mit jeder Stufe kommt ein Instrument dazu, bis der ganze Song läuft 🎶')
    : '';
  // Kurz halten: Frage + 4 Hashtags (so machen es die erfolgreichsten Accounts der Nische)
  const hashtags = ['#satisfyingvideos', '#bouncingball', '#relaxing', '#physics'];
  return {
    hook,
    caption: `${hook} 🎵${extra} 👇`,
    hashtags,
    pinnedComment: en
      ? `It was "${mel.title}" 🎵 ${balls} balls 🔥 Which song next?`
      : `Es war „${mel.title}“ 🎵 ${balls} Bälle 🔥 Welcher Song als Nächstes?`,
    answer: balls,
  };
}

function probe(file) {
  const { execFileSync } = require('child_process');
  const out = execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration:stream=codec_type', '-of', 'json', file]).toString();
  const j = JSON.parse(out);
  return { duration: parseFloat(j.format.duration) || 0, hasAudio: (j.streams || []).some((st) => st.codec_type === 'audio') };
}

/** Schneidet das Video beim Finale ab und hängt das Meme (Bild oder Clip) im Vollbild an. */
async function makeReveal(mainPath, revealPath, outPath, cutAt, revealSec, fps) {
  if (!fs.existsSync(revealPath)) throw new Error('Meme-Datei nicht gefunden: ' + revealPath);
  const isImage = /\.(png|jpe?g|webp|bmp)$/i.test(revealPath);
  const info = isImage ? { duration: 0, hasAudio: false } : probe(revealPath);
  const dur = revealSec || (isImage ? 3 : Math.min(info.duration, 8));
  const inputs = ['-i', mainPath];
  if (isImage) inputs.push('-loop', '1', '-t', String(dur), '-i', revealPath);
  else inputs.push('-t', String(dur), '-i', revealPath);
  if (!info.hasAudio) inputs.push('-f', 'lavfi', '-t', String(dur), '-i', 'anullsrc=r=48000:cl=stereo');
  const ra = info.hasAudio ? '[1:a]' : '[2:a]';
  // Vordergrund eingepasst, Hintergrund = unscharfe Vergrößerung (kein Schwarz), Bild zoomt leicht rein
  const filter = [
    `[0:v]trim=0:${cutAt},setpts=PTS-STARTPTS,fps=${fps},format=yuv420p,setsar=1[a]`,
    `[0:a]atrim=0:${cutAt},asetpts=PTS-STARTPTS,aresample=48000[aa]`,
    `[1:v]fps=${fps},split[r1][r2]`,
    `[r1]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=28:2,eq=brightness=-0.12[bg]`,
    `[r2]scale=1040:1700:force_original_aspect_ratio=decrease,scale='trunc(iw*(1+0.06*t/${dur})/2)*2':'trunc(ih*(1+0.06*t/${dur})/2)*2':eval=frame[fg]`,
    `[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p,setsar=1,trim=0:${dur},setpts=PTS-STARTPTS[b]`,
    `${ra}atrim=0:${dur},asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo[ba]`,
    `[a][aa][b][ba]concat=n=2:v=1:a=1[v][o]`,
  ].join(';');
  const args = ['-y', '-loglevel', 'error', ...inputs, '-filter_complex', filter, '-map', '[v]', '-map', '[o]',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '23', '-maxrate', '8M', '-bufsize', '16M', '-pix_fmt', 'yuv420p',
    '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', outPath];
  const ff = spawn('ffmpeg', args, { stdio: ['ignore', 'inherit', 'inherit'] });
  const [code] = await once(ff, 'close');
  if (code !== 0) throw new Error('Meme-Schnitt fehlgeschlagen (FFmpeg ' + code + ')');
}

async function main() {
  const a = parseArgs(process.argv);
  if (a.help) {
    console.log(fs.readFileSync(__filename, 'utf8').split('\n').slice(2, 17).join('\n'));
    return;
  }
  const server = await serve(a.port);
  const base = `http://127.0.0.1:${a.port}/`;
  if (a.serve) {
    console.log(`Vorschau läuft: ${base}  (Strg+C zum Beenden)`);
    return;
  }

  let chromium;
  try {
    ({ chromium } = require('playwright'));
  } catch (e) {
    console.error('Playwright fehlt. Einmalig ausführen:\n  cd ball_escape && npm install && npx playwright install chromium');
    process.exit(1);
  }

  const melodies = a.melody.split(',').map((m) => m.trim()).filter(Boolean);
  melodies.forEach((m) => Melodies.get(m)); // früh prüfen
  if (melodies.length > 1 && a.seed !== 'auto') throw new Error('Bei mehreren Melodien bitte --seed auto verwenden.');

  const browser = await chromium.launch();
  try {
    for (let idx = 0; idx < melodies.length; idx++) {
      if (melodies.length > 1) console.log(`\n=== Video ${idx + 1}/${melodies.length}: ${Melodies.get(melodies[idx]).title} ===`);
      await renderOne(browser, base, a, melodies[idx], a.seedStart + idx * 1000);
    }
  } finally {
    await browser.close();
    server.close();
  }
}

async function renderOne(browser, base, a, melodyName, seedStart) {
  const mel = Melodies.get(melodyName);
  const simOpts = {
    rings: a.rings,
    mode: a.mode,
    fps: a.fps,
    melody: mel.notes.map((n) => n + mel.transpose),
    song: melodyName,
    music: a.music,
    scene: a.scene,
    lang: a.lang,
    goal: a.goal,
  };
  if (a.length === 'short') Object.assign(simOpts, { boxGapDeg: 70, startSpeed: 900, outroDur: 4.5 });
  const pacing = a.length === 'short' ? { minFirst: 0.8, maxFirst: 3, maxGap: 6 } : a.length === 'format' ? { minFirst: 0.2, maxFirst: 12, maxGap: 30 } : {};
  if (a.skin) simOpts.skin = a.skin;
  if (a.threads) simOpts.threads = true;
  if (a.goal <= 200) Object.assign(simOpts, { ballR: 80, ballRMin: 22 }); // wenige, große Figuren (Top-Video Racery: ~10 große Gesichter)
  if (a.goal <= 200 && a.length === 'short') simOpts.boxGapDeg = 48;
  if (a.asmr) simOpts.asmr = a.asmr;
  if (a.loop === 'seamless') Object.assign(simOpts, { loop: 'seamless', outroDur: 2.4, slowmoDur: 0.5 });
  if (a.watermark) simOpts.watermark = a.watermark;
  if (a.hook) simOpts.hook = a.hook;

  const scale = a.draft ? 0.5 : 1;
  const page = await browser.newPage({ viewport: { width: 1080 * scale, height: 1920 * scale } });
  page.on('pageerror', (e) => console.error('Browser-Fehler:', e.message));
  try {
    await page.goto(base + 'index.html?mode=render');
    await page.waitForFunction(() => window.BE && window.BE.ready, null, { timeout: 30000 });

    // 1) Seed
    let seed = a.seed;
    if (seed === 'auto') {
      process.stdout.write(`Suche Seed (letzter Ring bei ~${a.target} s) … `);
      const t0 = Date.now();
      const r = await page.evaluate((o) => BE.findSeed(o), Object.assign({}, simOpts, pacing, { target: a.target, tol: a.tol, start: seedStart }));
      if (!r) throw new Error('Kein passender Seed gefunden – andere --target/--tol probieren.');
      seed = r.seed;
      console.log(`Seed ${seed} (Finale ${r.finalSec.toFixed(1)} s${r.approximate ? ', nur ungefähr' : ''}, ${r.tried} getestet, ${((Date.now() - t0) / 1000).toFixed(1)} s)`);
    }
    simOpts.seed = seed;

    // 2) Komplett simulieren -> Events -> Audio
    const sum = await page.evaluate((o) => BE.simulate(o), simOpts);
    if (!sum.completed) console.warn('Achtung: Der letzte Ring bricht bei diesem Seed nicht innerhalb des Zeitlimits.');
    let frames = sum.totalFrames;
    if (a.seconds) frames = Math.min(frames, Math.round(a.seconds * a.fps));
    const dur = frames / a.fps;
    console.log(`${a.scene === 'box' ? 'Instrument-Meilensteine' : 'Ringe brechen'} bei: ${sum.stages.map((b) => b.toFixed(1)).join(', ')} s`);
    console.log(`Videolänge: ${dur.toFixed(2)} s, ${frames} Frames, End-Bälle: ${sum.finalBalls}`);

    const workDir = path.join(ROOT, 'output', 'work', 'ball_escape');
    fs.mkdirSync(workDir, { recursive: true });
    const wavPath = path.join(workDir, `audio_seed${seed}_${process.pid}_${melodyName}.wav`); // eindeutig, auch bei parallelen Läufen
    const loopChimeAt = sum.completed && !a.seconds ? dur - 1.4 : null;
    const pcm = audio.renderAudio(sum.events.filter((e) => e.vt < dur), dur, { seed, tonic: mel.tonic, chord: mel.chord, loopChimeAt, song: Melodies.compile(melodyName), rings: a.scene === 'box' ? 12 : a.rings, stageTimes: sum.stages.filter((t) => t < dur), music: a.music, skin: simOpts.skin || 'smiley', asmr: a.asmr, scene: a.scene, goal: a.goal });
    fs.writeFileSync(wavPath, audio.toWav(pcm));

    // 3) Frames -> FFmpeg
    const date = new Date().toISOString().slice(0, 10);
    const soundTag = (a.loop === 'seamless' ? 'loop_' : '') + (a.threads ? 'faden_' : '') + (a.music === 'asmr' ? 'asmr-' + (a.asmr || audio.ASMR_FOR_SKIN[simOpts.skin || 'smiley']) : melodyName);
    const name = `${date}_ball-escape_${a.scene === 'box' ? 'box' + a.goal : a.scene === 'rings' ? a.rings + 'ringe' : a.scene}_${simOpts.skin || 'smiley'}_${soundTag}_${a.lang}_seed${seed}${a.draft ? '_draft' : ''}`;
    const outPath = path.resolve((a.out && a.melody.indexOf(',') < 0 && a.out) || path.join(ROOT, 'output', 'finished', name + '.mp4'));
    fs.mkdirSync(path.dirname(outPath), { recursive: true });
    const ff = spawn('ffmpeg', [
      '-y', '-loglevel', 'error',
      '-f', 'image2pipe', '-framerate', String(a.fps), '-c:v', 'mjpeg', '-i', '-',
      '-i', wavPath,
      '-c:v', 'libx264', '-preset', a.draft ? 'veryfast' : 'medium', '-crf', String(a.draft ? 26 : a.crf), '-maxrate', '8M', '-bufsize', '16M',
      '-pix_fmt', 'yuv420p', '-r', String(a.fps), '-g', String(a.fps * 2),
      '-c:a', 'aac', '-b:a', '192k', '-ar', '48000',
      '-shortest', '-movflags', '+faststart', outPath,
    ], { stdio: ['pipe', 'inherit', 'inherit'] });
    const ffDone = once(ff, 'close');

    await page.evaluate((o) => BE.setup(o), Object.assign({}, simOpts, { capture: true, renderScale: scale, jpegQuality: a.draft ? 0.85 : 0.95 }));
    const t0 = Date.now();
    for (let k = 0; k < frames; k++) {
      const url = await page.evaluate((i) => BE.renderFrame(i), k);
      const buf = Buffer.from(url.slice(url.indexOf(',') + 1), 'base64');
      if (!ff.stdin.write(buf)) await once(ff.stdin, 'drain');
      if (k % (a.fps * 5) === 0 || k === frames - 1) {
        const el = (Date.now() - t0) / 1000;
        const eta = k ? (el / k) * (frames - k) : 0;
        process.stdout.write(`\rRendern ${String(Math.round(((k + 1) / frames) * 100)).padStart(3)} %  (${k + 1}/${frames}, noch ~${Math.round(eta)} s)   `);
      }
    }
    ff.stdin.end();
    const [code] = await ffDone;
    process.stdout.write('\n');
    if (code !== 0) throw new Error('FFmpeg ist mit Code ' + code + ' abgebrochen.');

    // 4) Determinismus-Check: gerenderte Ringbrüche == simulierte
    const info = await page.evaluate(() => BE.info());
    const rendered = info.breaks.map((f) => +(f / a.fps).toFixed(3));
    const expected = sum.breaks.filter((b) => b < dur);
    const same = rendered.length === expected.length && rendered.every((v, i) => Math.abs(v - expected[i]) < 1e-6);
    if (!same) console.warn('WARNUNG: Render weicht von der Simulation ab (Audio evtl. nicht synchron).');

    // 4b) Meme-Ende: harter Schnitt auf ein eigenes Bild/Video, sobald das Finale erreicht ist
    if (a.reveal && sum.finalSec) {
      const revealOut = outPath.replace(/\.mp4$/, '_meme.mp4');
      await makeReveal(outPath, path.resolve(a.reveal), revealOut, sum.finalSec + 0.15, a.revealSec, a.fps);
      console.log(`Meme-Version: ${revealOut}`);
    }

    // 5) Caption / Metadaten
    const cap = captionFor(a, sum, mel);
    const meta = Object.assign({ video: path.basename(outPath), seed, rings: a.rings, mode: a.mode, melody: mel.title, durationSec: +dur.toFixed(2), breaks: sum.breaks, finalBalls: sum.finalBalls }, cap);
    const metaPath = outPath.replace(/\.mp4$/, '.json');
    fs.writeFileSync(metaPath, JSON.stringify(meta, null, 2));
    fs.writeFileSync(outPath.replace(/\.mp4$/, '.txt'), `${cap.caption}\n\n${cap.hashtags.join(' ')}\n\nAngepinnter Kommentar:\n${cap.pinnedComment}\n`);
    console.log(`Fertig: ${outPath}`);
    console.log(`Caption: ${outPath.replace(/\.mp4$/, '.txt')}`);
  } finally {
    await page.close();
  }
}

main().catch((e) => {
  console.error('Fehler:', e.message);
  process.exit(1);
});
