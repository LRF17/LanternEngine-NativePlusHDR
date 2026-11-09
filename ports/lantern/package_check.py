"""Checks of the assembled Windows package, without running or writing anything in it."""
import json
from pathlib import Path
import re
import sys

root = Path(sys.argv[1]).resolve()
# Lantern 0.9.40's layout: the native start and launcher, no Python and no Vulkan loader.
for name in ['Lantern Engine.exe', 'Bloodborne.exe', 'engine/out/bb-start.exe', 'engine/out/bb-probe.exe',
             'engine/out/bb-isa-scan.exe', 'engine/out/gpu-cache.id']:
    assert (root / name).is_file(), f'missing {name}'
for name in ['engine/scripts', 'engine/tools', 'engine/out/vulkan-1.dll', 'user', 'logs', 'out']:
    assert not (root / name).exists(), f'{name} must not ship'
assert not list(root.rglob('__pycache__')), 'no __pycache__ may ship'
# The shipped settings (copied to lantern.ini by the launcher in a folder without settings).
ini = (root / 'engine/lantern.default.ini').read_text()
assert 'hdr_mode=nativeplus' in ini and 'hdr_tonemapper=5' in ini
assert not (root / 'bbport.ini').exists() and not (root / 'lantern.ini').exists()
# Left to the display's peak (hdr_peak_auto) and the engine's paper white.
assert not any(line.split('=', 1)[0] in ('hdr_peak', 'hdr_paper_white') for line in ini.splitlines())
# The package's engine id is the launcher's (Updater.EngineId): the updater downloads the whole
# package only when a release's id differs from the installed one, the launcher alone otherwise.
engine = json.loads((root / 'package.json').read_text(encoding='utf-8'))['engine']
updater = (Path(__file__).resolve().parents[2] / 'launcher/windows/BloodborneLauncher/Core/Updater.cs').read_text(encoding='utf-8')
launcher_engine = re.search(r'EngineId = "([^"]+)"', updater).group(1)
assert engine == launcher_engine, f'package.json engine {engine} differs from Updater.EngineId {launcher_engine}'
print('Package layout, shipped settings and engine id checked; an in-game launch is still required.')
