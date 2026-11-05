// usage: node render.js <dir> preview|render [feed] [t1,t2,...]
const {chromium}=require('playwright');const {spawn}=require('child_process');const fs=require('fs');
const [D,mode='preview',fmt='reel',times='1.6,3.0,4.3,5.1,7.2,7.95,10.4,14.5,17.6,21.2']=process.argv.slice(2);
const feed=fmt==='feed',VH=feed?1350:1920,OUT=`${D}/video_${fmt}_noaudio.mp4`;
(async()=>{
  const b=await chromium.launch({args:['--allow-file-access-from-files']});
  const p=await b.newPage({viewport:{width:1080,height:VH}});
  await p.goto('file://'+D+'/anim.html'+(feed?'?feed':''));await p.evaluate(()=>window.ready);
  const shot=async t=>{await p.evaluate(t=>render(t),t);return p.screenshot({type:'jpeg',quality:95})};
  if(mode==='preview'){for(const t of times.split(','))fs.writeFileSync(`${D}/prev_${fmt}_${t}.jpg`,await shot(+t))}
  else{
    const fps=30,dur=await p.evaluate(()=>DUR);
    const ff=spawn('ffmpeg',['-y','-loglevel','error','-f','image2pipe','-framerate',''+fps,'-c:v','mjpeg','-i','-','-c:v','libx264','-pix_fmt','yuv420p','-crf','17','-preset','medium',OUT],{stdio:['pipe','inherit','inherit']});
    for(let i=0;i<Math.round(dur*fps);i++){const buf=await shot(i/fps);if(!ff.stdin.write(buf))await new Promise(r=>ff.stdin.once('drain',r))}
    ff.stdin.end();await new Promise(r=>ff.on('close',r));
  }
  await b.close();
})();
