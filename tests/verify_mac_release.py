"""Validate a freshly built standalone app without private audio or settings."""
from pathlib import Path
import hashlib, json, os, plistlib, re, subprocess, tempfile
import numpy as np
import soundfile as sf

root=Path(__file__).resolve().parents[1]
app=root/'dist/QQDeBreathTool.app'
binary=app/'Contents/MacOS/QQDeBreathTool'
info=plistlib.loads((app/'Contents/Info.plist').read_bytes())
assert info['CFBundleShortVersionString']=='1.12' and info['CFBundleVersion']=='1.12',info
arch=os.environ['EXPECTED_ARCH']
assert subprocess.check_output(['lipo','-archs',str(binary)],text=True).strip()==arch
subprocess.run(['codesign','--verify','--deep','--strict','--verbose=2',str(app)],check=True)
models=[p for p in app.rglob('breath_frame_model.joblib') if p.is_file()]
expected='d655af2bfb260866de74319d179fda0b007e6539711c572967bc0fc709e42afe'
assert models and all(hashlib.sha256(p.read_bytes()).hexdigest()==expected for p in models)
assert not list(app.rglob('qq_fp_control.dll'))
machos=[]; minimum=(0,0)
for p in app.rglob('*'):
    if not p.is_file() or p.is_symlink():continue
    with p.open('rb') as handle:magic=handle.read(4)
    if magic not in (b'\xcf\xfa\xed\xfe',b'\xfe\xed\xfa\xcf',b'\xca\xfe\xba\xbe',b'\xbe\xba\xfe\xca'):continue
    found=subprocess.check_output(['lipo','-archs',str(p)],text=True).strip().split()
    assert arch in found,(p,found)
    loads=subprocess.check_output(['otool','-l',str(p)],text=True)
    versions=re.findall(r'\bminos\s+([0-9.]+)',loads)+re.findall(r'cmd LC_VERSION_MIN_MACOSX.*?\bversion\s+([0-9.]+)',loads,re.S)
    for version in versions:minimum=max(minimum,tuple(int(v) for v in version.split('.')))
    machos.append(dict(path=p.relative_to(app).as_posix(),architectures=found,minimumVersions=versions))
with tempfile.TemporaryDirectory(prefix='qqdebreath-release-') as folder:
    t=Path(folder);wav=t/'silence.wav';sf.write(wav,np.zeros((48000*2,1)),48000,subtype='PCM_16')
    env=dict(os.environ,HOME=str(t),APPDATA=str(t/'settings'),XDG_CONFIG_HOME=str(t/'settings'))
    version=subprocess.run([str(binary),'--version'],env=env,capture_output=True,text=True,timeout=60)
    assert version.returncode==0 and '1.12' in version.stdout,(version.returncode,version.stdout,version.stderr)
    command=[str(binary),'analyze-for-plugin','--input',str(wav),'--output-json',str(t/'result.json'),'--out-dir',str(t/'stems'),'--threshold','0.84']
    result=subprocess.run(command,env=env,capture_output=True,text=True,timeout=120)
    assert result.returncode==0,(result.returncode,result.stdout,result.stderr)
    data=json.loads((t/'result.json').read_text())
    assert data['status']=='ok' and data['regions']==[],data
record=dict(status='PASS',version='1.12',arch=arch,commit=os.environ.get('GITHUB_SHA'),minimumMacOS='.'.join(map(str,minimum)),machoCount=len(machos),machos=machos,modelSha256=expected,codesign='PASS ad-hoc',frozenVersion=version.stdout.strip(),frozenSilenceAnalysis='PASS',interactiveAcceptance=False)
(root/'release/Mac-Verification.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:v for k,v in record.items() if k!='machos'},indent=2))
