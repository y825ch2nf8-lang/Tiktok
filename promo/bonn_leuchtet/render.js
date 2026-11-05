const {chromium}=require('playwright');const {spawn}=require('child_process');
const S=process.argv[2], mode=process.argv[3]||'preview';
(async()=>{
  const b=await chromium.launch({args:['--allow-file-access-from-files']});
  const p=await b.newPage({viewport:{width:1080,height:1920}});
  await p.goto('file://'+S+'/anim.html');await p.evaluate(()=>window.ready);
  const shot=async t=>{await p.evaluate(t=>render(t),t);return p.screenshot({type:'jpeg',quality:95})};
  if(mode==='preview'){
    for(const t of [2.6,6.5,12.5,17.5,21.5]){require('fs').writeFileSync(`${S}/prev_${t}.jpg`,await shot(t))}
  } else {
    const fps=30,dur=await p.evaluate(()=>DUR);
    const ff=spawn('ffmpeg',['-y','-loglevel','error','-f','image2pipe','-framerate',''+fps,'-c:v','mjpeg','-i','-','-c:v','libx264','-pix_fmt','yuv420p','-crf','18','-preset','medium',S+'/video_noaudio.mp4'],{stdio:['pipe','inherit','inherit']});
    for(let i=0;i<dur*fps;i++){const buf=await shot(i/fps);if(!ff.stdin.write(buf))await new Promise(r=>ff.stdin.once('drain',r))}
    ff.stdin.end();await new Promise(r=>ff.on('close',r));
  }
  await b.close();
})();
