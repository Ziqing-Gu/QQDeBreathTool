"""Build the tiny Windows helper into a supplied temporary build directory."""
from pathlib import Path
import os
import shutil
import subprocess
import sys


def build(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).with_name('fp_control.cpp').resolve()
    dll = output / 'qq_fp_control.dll'
    args = ['cl', '/nologo', '/O2', '/MT', '/LD', '/EHsc', str(source),
            '/Fo:' + str(output / 'fp_control.obj'), '/Fe:' + str(dll),
            '/link', '/INCREMENTAL:NO', '/IMPLIB:' + str(output / 'qq_fp_control.lib')]
    if shutil.which('cl'):
        subprocess.run(args, cwd=output, check=True)
    else:
        vswhere = Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')) / 'Microsoft Visual Studio/Installer/vswhere.exe'
        install = subprocess.check_output([str(vswhere), '-latest', '-products', '*', '-requires',
            'Microsoft.VisualStudio.Component.VC.Tools.x86.x64', '-property', 'installationPath'], text=True).strip()
        if not install:
            raise RuntimeError('MSVC x64 build tools are required for the Windows analysis helper.')
        vcvars = Path(install) / 'VC/Auxiliary/Build/vcvars64.bat'
        script = output / 'build-native.cmd'
        # All paths are local build inputs, passed using Windows argument quoting.
        script.write_text('@echo off\ncall "' + str(vcvars) + '"\nif errorlevel 1 exit /b %errorlevel%\n' +
                          subprocess.list2cmdline(args) + '\nexit /b %errorlevel%\n', encoding='utf-8')
        subprocess.run(['cmd', '/d', '/c', str(script)], cwd=output, check=True)
    return dll


if __name__ == '__main__':
    print(build(sys.argv[1]))
