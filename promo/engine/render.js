// Render a promo project to video or preview stills.
//   node promo/engine/render.js <projectDir> render  reel|feed
//   node promo/engine/render.js <projectDir> preview reel|feed 1.2,3.4,...   -> <projectDir>/preview/contact_<fmt>.jpg
// <projectDir>/index.html must define the canvas page. If <projectDir>/music.wav exists it is muxed in.
const { chromium } = require('playwright');
const { spawn, execFileSync } = require('child_process');
const fs = require('fs'), path = require('path');

const [dirArg, mode = 'preview', fmt = 'reel', times = ''] = process.argv.slice(2);
const D = path.resolve(dirArg), feed = fmt === 'feed', VH = feed ? 1350 : 1920;
const OUT = path.join(D, 'out'); fs.mkdirSync(OUT, { recursive: true });
const name = path.basename(D);

(async () => {
  const b = await chromium.launch({ args: ['--allow-file-access-from-files', '--autoplay-policy=no-user-gesture-required'] });
  const p = await b.newPage({ viewport: { width: 1080, height: VH } });
  p.on('pageerror', e => { console.error('PAGE ERROR', e.message); process.exitCode = 1; });
  await p.goto('file://' + D + '/index.html' + (feed ? '?feed' : ''));
  await p.evaluate(() => window.ready);
  const shot = async t => { await p.evaluate(async t => { await prepare(t); render(t); }, t); return p.screenshot({ type: 'jpeg', quality: 95 }); };

  if (mode === 'preview') {
    const ts = times ? times.split(',').map(Number) : [];
    const dir = path.join(D, 'preview'); fs.mkdirSync(dir, { recursive: true });
    const files = [];
    for (const t of ts) { const f = path.join(dir, `${fmt}_${t}.jpg`); fs.writeFileSync(f, await shot(t)); files.push(f); }
    // contact sheet (5 per row, small) via ffmpeg tile
    if (files.length) {
      const cols = Math.min(5, files.length), rows = Math.ceil(files.length / cols);
      const list = path.join(dir, 'list.txt'); fs.writeFileSync(list, files.map(f => `file '${f}'`).join('\n'));
      execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', list, '-vf', `scale=324:-1,tile=${cols}x${rows}:padding=4:color=white`, '-frames:v', '1', path.join(dir, `contact_${fmt}.jpg`)]);
    }
  } else {
    const fps = 30, dur = await p.evaluate(() => DUR), raw = path.join(OUT, `${name}_${fmt}_noaudio.mp4`);
    const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', '' + fps, '-c:v', 'mjpeg', '-i', '-', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-preset', 'medium', raw], { stdio: ['pipe', 'inherit', 'inherit'] });
    const n = Math.round(dur * fps);
    for (let i = 0; i < n; i++) { const buf = await shot(i / fps); if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r)); }
    ff.stdin.end(); await new Promise(r => ff.on('close', r));
    const wav = path.join(D, 'music.wav');
    if (fs.existsSync(wav)) {
      const fin = path.join(OUT, `${name}_${fmt}.mp4`);
      execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-i', raw, '-i', wav, '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', fin]);
      fs.unlinkSync(raw); console.log('wrote', fin);
    } else console.log('wrote', raw, '(no music.wav found)');
  }
  await b.close();
})();
