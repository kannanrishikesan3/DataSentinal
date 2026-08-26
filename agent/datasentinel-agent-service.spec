# PyInstaller spec for the Windows Service binary. Separate from
# datasentinel-agent.spec (the CLI/on-demand-scan binary) — see
# service_main.py's docstring for why these can't be one executable.
#
# Windows-only build. Running this on Linux/macOS will fail at analysis time
# (pywin32 isn't installed there) — that's intentional, not a bug: there is
# no Linux equivalent of this binary (use scripts/datasentinel-agent.service
# instead).
#
# Build (from an elevated Windows prompt, inside the agent's venv):
#   pyinstaller datasentinel-agent-service.spec --clean

from pathlib import Path

block_cipher = None
project_root = Path(SPECPATH)

a = Analysis(
    ['service_main.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        ('config/default.yaml', 'config'),
    ],
    hiddenimports=[
        'sqlalchemy.dialects.sqlite',
        'sqlalchemy.dialects.sqlite.pysqlite',
        'alembic',
        'alembic.runtime.migration',
        'win32timezone',  # pywin32 service framework needs this at runtime, not just import time
        'servicemanager',
        'win32service',
        'win32serviceutil',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'presidio_analyzer', 'presidio_anonymizer', 'spacy', 'en_core_web_sm', 'en_core_web_lg',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='datasentinel-agent-service',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
