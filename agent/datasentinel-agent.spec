# PyInstaller spec for the DataSentinel endpoint agent.
#
# Build:
#   pyinstaller datasentinel-agent.spec --clean
#
# Presidio/spaCy are deliberately NOT bundled here (see agent/README.md's
# packaging section for why) — the frozen binary runs in the same
# "Presidio unavailable, regex-only detection" mode the agent already
# supports and is tested against (datasentinel_agent.pii.presidio_engine
# degrades gracefully), which covers every required PII/secret category on
# its own. Install a full venv instead of the frozen binary if you need
# Presidio's NLP-based person-name recognizer.

import sys
from pathlib import Path

block_cipher = None
project_root = Path(SPECPATH)

a = Analysis(
    ['main.py'],
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
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Explicitly excluded — see the module docstring above.
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
    name='datasentinel',
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
