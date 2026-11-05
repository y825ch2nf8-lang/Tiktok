"""AI super-resolution for promo plates: Real-ESRGAN x4plus, run on CPU with ncnn.

usage:
  python3 promo/engine/upscale.py in.png out.jpg            # 4x
  python3 promo/engine/upscale.py in.png out.jpg --tile 192 --threads 4

The model files come from the `realesrgan-ncnn-py` wheel on PyPI (PyPI is reachable in cloud
sessions even when GitHub releases / Hugging Face are blocked). They are cached in
promo/engine/models/ (git-ignored). Speed on 4 CPU cores: ~1 megapixel input per 1-2 min.
"""
import argparse, glob, os, subprocess, sys, tempfile, time, zipfile
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.join(HERE, 'models')
NAME = 'realesrgan-x4plus'


def ensure_ncnn():
    try:
        import ncnn  # noqa: F401
    except ImportError:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', 'ncnn'])


def ensure_model():
    p, b = (os.path.join(MODELS, f'{NAME}.{e}') for e in ('param', 'bin'))
    if os.path.exists(p) and os.path.exists(b):
        return p, b
    os.makedirs(MODELS, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        subprocess.check_call([sys.executable, '-m', 'pip', 'download', 'realesrgan-ncnn-py', '--no-deps', '--only-binary=:all:',
                               '--python-version', '3.12', '--platform', 'manylinux2014_x86_64', '-d', td, '-q'])
        whl = glob.glob(os.path.join(td, '*.whl'))[0]
        z = zipfile.ZipFile(whl)
        for e in ('param', 'bin'):
            open(os.path.join(MODELS, f'{NAME}.{e}'), 'wb').write(z.read(f'realesrgan_ncnn_py/models/{NAME}.{e}'))
    return p, b


def upscale(img: Image.Image, tile=192, pad=12, threads=4, log=True) -> Image.Image:
    ensure_ncnn()
    import ncnn
    p, b = ensure_model()
    net = ncnn.Net(); net.opt.use_vulkan_compute = False; net.opt.num_threads = threads
    net.load_param(p); net.load_model(b)
    src = np.asarray(img.convert('RGB'))
    h, w = src.shape[:2]; S = 4
    out = np.zeros((h * S, w * S, 3), np.float32)
    tiles = [(y, x) for y in range(0, h, tile) for x in range(0, w, tile)]
    t0 = time.time()
    for k, (y, x) in enumerate(tiles):
        y0, x0 = max(0, y - pad), max(0, x - pad)
        y1, x1 = min(h, y + tile + pad), min(w, x + tile + pad)
        patch = np.ascontiguousarray(src[y0:y1, x0:x1])
        m = ncnn.Mat.from_pixels(patch.tobytes(), ncnn.Mat.PixelType.PIXEL_RGB, x1 - x0, y1 - y0)
        m.substract_mean_normalize([0, 0, 0], [1 / 255.0] * 3)
        ex = net.create_extractor(); ex.input('data', m)
        _, o = ex.extract('output')
        o = np.array(o).transpose(1, 2, 0)                       # (H, W, 3) in 0..1
        ty, tx = (y - y0) * S, (x - x0) * S
        th, tw = min(tile, h - y) * S, min(tile, w - x) * S
        out[y * S:y * S + th, x * S:x * S + tw] = o[ty:ty + th, tx:tx + tw]
        if log and (k % 10 == 0 or k == len(tiles) - 1):
            el = time.time() - t0
            print(f'  tile {k + 1}/{len(tiles)}  {el:.0f}s elapsed, ~{el / (k + 1) * (len(tiles) - k - 1):.0f}s left', flush=True)
    return Image.fromarray((out.clip(0, 1) * 255 + .5).astype(np.uint8))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('src'); ap.add_argument('dst')
    ap.add_argument('--tile', type=int, default=192); ap.add_argument('--threads', type=int, default=os.cpu_count() or 4)
    ap.add_argument('--quality', type=int, default=93)
    ap.add_argument('--mix', type=float, default=.8, help='AI share; rest is Lanczos (tames invented detail)')
    a = ap.parse_args()
    im = Image.open(a.src).convert('RGB')
    print(f'{a.src}: {im.size} -> x4 Real-ESRGAN (mix {a.mix})')
    res = upscale(im, a.tile, threads=a.threads)
    if a.mix < 1:
        res = Image.blend(im.resize(res.size, Image.LANCZOS), res, a.mix)
    res.save(a.dst, quality=a.quality) if a.dst.lower().endswith(('.jpg', '.jpeg')) else res.save(a.dst)
    print(f'wrote {a.dst}: {res.size}')
