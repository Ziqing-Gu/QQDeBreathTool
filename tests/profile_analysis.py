"""Profile the detector on an explicitly supplied read-only WAV."""
import argparse
import cProfile
import json
import os
from pathlib import Path
import pstats
import sys
import time

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
parser = argparse.ArgumentParser()
parser.add_argument('input', type=Path)
parser.add_argument('output', type=Path)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
os.environ['APPDATA'] = str(args.output / 'settings')
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
import debreath_tool_app as app
app.ensure_numpy()
app.ensure_scipy_signal()
app.ensure_scipy_ndimage()
model = app.load_model(root / 'breath_frame_model.joblib')
audio, sr = app.ensure_soundfile().read(str(args.input), always_2d=True, dtype='float64')
audio = app.clean_audio_array(audio)
profile = cProfile.Profile()
start = time.perf_counter()
regions = profile.runcall(app.analyze_regions, audio, sr, model, source_path=args.input)
seconds = time.perf_counter() - start
profile.dump_stats(str(args.output / 'analysis.prof'))
with (args.output / 'profile.txt').open('w', encoding='utf-8') as f:
    pstats.Stats(profile, stream=f).sort_stats('cumulative').print_stats(40)
result = dict(seconds=seconds, regions=[vars(r) for r in regions], input=str(args.input))
(args.output / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print('seconds=', seconds, 'regions=', len(regions), flush=True)
