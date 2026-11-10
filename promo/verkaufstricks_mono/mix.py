"""Mix the voice (vo/01.mp3, starting LEAD seconds in) over the ducked music into the rendered video.
usage (repo root): python3 promo/verkaufstricks/mix.py"""
import subprocess, os, sys
D = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(D)); LEAD, DUR = 0.15, 33.6
vid = f'{D}/out/verkaufstricks_mono_reel.mp4'; out = f'{ROOT}/output/verkaufstricks/verkaufstrick_01_black_friday_mono.mp4'; os.makedirs(os.path.dirname(out), exist_ok=True)
fc = (f'[1:a]adelay={int(LEAD*1000)}:all=1,highpass=f=70,acompressor=threshold=-18dB:ratio=3:attack=5:release=120:makeup=4,apad=whole_dur={DUR},asplit[vo][sc];'
      '[0:a]volume=0.5[m];[m][sc]sidechaincompress=threshold=0.02:ratio=8:attack=15:release=350[duck];[duck][vo]amix=inputs=2:normalize=0,alimiter=limit=0.8:level=0[a]')
r = subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', vid, '-i', f'{D}/vo/02.mp3', '-filter_complex', fc, '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-t', str(DUR), '-movflags', '+faststart', out])
sys.exit(r.returncode or print('wrote', out))
