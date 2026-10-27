from pathlib import Path
import os,sys,time
import traceback
slot_errors=[]
def record_exception(*exc):
    slot_errors.append(''.join(traceback.format_exception(*exc)))
    sys.__excepthook__(*exc)
sys.excepthook=record_exception
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
temp=Path(sys.argv[1]);os.environ['APPDATA']=str(temp/'gui-test-settings'/str(time.time_ns()))
os.environ['QT_QPA_PLATFORM']='offscreen'
os.environ['QQDEBREATH_NATIVE_DIR']=str(temp/'native')
import debreath_tool_app as app
from PyQt5.QtWidgets import QApplication,QMessageBox
from qq_debreath import __version__
gui=QApplication([])
win=app.MainWindow();gui.processEvents()
assert __version__=='1.12' and win.windowTitle().endswith('1.12')
errors=[];QMessageBox.critical=lambda *args:errors.append(str(args[2]))
app.ensure_numpy();np=app.np
win.audio=np.zeros((48000*2,1),dtype=np.float64)
win.sr=48000;win.path=temp/'synthetic.wav'
win.model=app.load_model(root/'breath_frame_model.joblib')
win.wave.regions=[app.Region(.1,.4,'Breath')]
win.analyze()
deadline=time.monotonic()+30
while win.analysis_thread is not None:
    gui.processEvents();time.sleep(.005)
    assert time.monotonic()<deadline,'GUI worker stalled'
assert not errors,errors
assert win.analyze_btn.isEnabled() and win.analysis_progress is None
assert not win.wave.regions,'Pure silence produced a region'
assert win.undo_stack,'Analysis lost Undo'
win.undo();assert len(win.wave.regions)==1
win.redo();assert not win.wave.regions
win.close();gui.processEvents()
assert not slot_errors,slot_errors
print('PASS: 1.12 main window, real AnalyzeThread completion, progress cleanup, Undo/Redo; offscreen only')
