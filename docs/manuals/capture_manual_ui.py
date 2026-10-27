"""Capture actual 1.12 widgets with generated demonstration audio, offscreen only."""
from pathlib import Path
import argparse, os, sys, time, json
p=argparse.ArgumentParser();p.add_argument('--temp',type=Path,required=True);a=p.parse_args()
os.environ['QT_QPA_PLATFORM']='offscreen'
os.environ['APPDATA']=str(a.temp/'isolated-settings'/str(time.time_ns()))
os.environ['PYTHONDONTWRITEBYTECODE']='1'
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root))
import debreath_tool_app as app
from PyQt5.QtCore import QRect
from PyQt5.QtGui import QFont, QFontDatabase
from PyQt5.QtWidgets import QApplication
import numpy as np
assets=Path(__file__).parent/'images';assets.mkdir(parents=True,exist_ok=True)
q=QApplication([])
for font in ['msyh.ttc','msyhbd.ttc','arial.ttf']:
    assert QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR'])/'Fonts'/font))>=0
q.setFont(QFont('Microsoft YaHei',9));app.apply_ui_font(q)
w=app.MainWindow();w.resize(1640,760);w.show();q.processEvents()
sr=48000;t=np.arange(sr*12)/sr;rng=np.random.default_rng(112)
x=np.zeros_like(t)
for start,end,amp in [(1.7,3.3,.50),(4.1,5.5,.44),(6.5,7.5,.46),(8.5,10.9,.48)]:
    env=np.maximum(0,np.sin(np.pi*np.clip((t-start)/(end-start),0,1)))**.7
    x+=amp*env*(.6*np.sin(2*np.pi*(157*t+2*np.sin(t*3)))+.25*np.sin(2*np.pi*317*t)+.15*np.sin(2*np.pi*710*t))
for start,end,amp in [(1.1,1.55,.07),(3.65,3.95,.06),(5.8,6.15,.14),(7.8,8.1,.065)]:
    gate=(t>=start)&(t<end);x[gate]+=rng.normal(0,amp,gate.sum())
w.audio=x[:,None];w.sr=sr;w.path=None;w.wave.set_audio(w.audio,sr)
w.wave.set_regions([app.Region(1.1,1.55,'Breath'),app.Region(3.65,3.95,'Breath'),app.Region(5.8,6.15,'Noize'),app.Region(7.8,8.1,'Breath')])
w.wave.selected=0;w.selection_changed(0);w.wave.set_playhead(1.1)
w.status.setText('演示素材 Demo Vocal | 48000 Hz | 1 ch | 12.000 s')
w.push_undo();w.breath_gain_db.setValue(-6,emit=True);q.processEvents()
assert w.grab().save(str(assets/'overview.png'))
assert w.grab(QRect(0,0,680,66)).save(str(assets/'editing-toolbar.png'))
assert w.grab(QRect(w.width()-700,0,700,66)).save(str(assets/'processing-toolbar.png'))
wavegeo=w.wave.geometry()
assert w.grab(QRect(0,wavegeo.bottom()+12,730,74)).save(str(assets/'transport.png'))
assert w.grab(QRect(w.width()-255,wavegeo.bottom()+12,255,74)).save(str(assets/'monitor-gain.png'))
w.wave.set_view(.75,2.0);w.wave.set_playhead(1.1);q.processEvents()
assert w.wave.grab().save(str(assets/'breath-closeup.png'))
w.monitor_voice.setChecked(False);w.monitor_noize.setChecked(False);w.wave.set_view(0,12);q.processEvents()
assert w.grab().save(str(assets/'breath-solo.png'))
w.close();q.processEvents()
(assets/'capture.json').write_text(json.dumps(dict(version='1.12',actualWidgets=True,syntheticAudio=True,manuallyPlacedRegions=True,realUserSettingsAccessed=False,interactiveAcceptance=False),indent=2)+'\n')
print('Captured six actual UI views using generated audio; user settings isolated.')
