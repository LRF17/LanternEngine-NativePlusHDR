"""Assemble a complete, isolated Windows package from pinned runtime resources.

The released package's executables are not the engine reconstructed from its public
source snapshot. Only its models, DLLs, icons, notices and defaults are reused. The
engine, helper programs, launcher and preparation scripts all come from our build.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import urllib.request
from zipfile import ZipFile

BASE_URL = ('https://github.com/Awakenchan/LanternEngine/releases/download/'
            'v0.9.40/LanternEngine-v0.9.40-win64.zip')
BASE_SHA = 'd0401188f4d755880c26aad0a577beeaea7dc5d9ba355c2764e64134dc4d1055'


def archive(url, digest, cache):
    path = cache / url.rsplit('/', 1)[-1]
    if not path.exists():
        urllib.request.urlretrieve(url, path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise RuntimeError(f'Unexpected SHA-256: {path}')
    return ZipFile(path)


def assemble(engine, overlay, destination, cache):
    if destination.exists():
        raise RuntimeError('Use an empty destination; never merge a distribution into a player folder')
    cache.mkdir(parents=True, exist_ok=True)
    destination.mkdir(parents=True)
    runtime = destination / 'engine'
    # PowerShell-built ZIPs have backslashes even when inspected on Linux.
    with archive(BASE_URL, BASE_SHA, cache) as base:
        for member in base.infolist():
            path = PurePosixPath(member.filename.replace('\\', '/'))
            if member.is_dir() or '..' in path.parts or not path.parts or path.parts[0] != 'BloodbornePC':
                continue
            relative = PurePosixPath(*path.parts[1:])
            if not relative.parts:
                continue
            if relative.suffix.lower() == '.exe' and relative.name != 'Bloodborne.exe':
                continue  # no stock launcher/start/probe/helper executables
            if relative.parts[:2] == ('engine', 'out') and relative.suffix.lower() not in ('.dll', '.ico'):
                continue  # no stock cache identifiers or prepared files
            target = destination.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(base.read(member))
    # The patches match the compiled runtime, rather than the release binary. No scripts and no
    # Python: the start is bb-start.exe since Lantern 0.9.32, and Lantern's package has neither
    # (its launcher removes engine\scripts and engine\tools on a new engine, Updater.CleanOldFiles).
    target = runtime / 'patches'
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(engine / 'patches', target, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copytree(overlay / 'out', runtime / 'out', dirs_exist_ok=True)
    shutil.copytree(overlay / 'licenses', destination / 'licenses', dirs_exist_ok=True)
    shutil.copy2(overlay / 'README-NativePlusHDR.md', destination / 'README-NativePlusHDR.md')
    # The launcher build is Lantern Engine.exe since Lantern 9.8 (Bloodborne Launcher.exe before).
    launcher = overlay / 'Lantern Engine.exe'
    if not launcher.is_file():
        launcher = overlay / 'Bloodborne Launcher.exe'
    shutil.copy2(launcher, destination / 'Lantern Engine.exe')
    # The native Bloodborne.exe forwarder from this release starts Lantern Engine.exe --play.
    # The release's version: the workflow's (a release's tag), else ports/lantern/VERSION.
    version = os.environ.get('BB_RELEASE_VERSION') or (Path(__file__).with_name('VERSION')
                                                        .read_text(encoding='utf-8').strip())
    (destination / 'package.json').write_text(json.dumps({
        'version': version, 'engine': 'lantern-fps95-nativeplus-v8',
        'source': 'https://github.com/LRF17/LanternEngine-NativePlusHDR/tree/lantern-Native+HDR',
        'runtime_resources': 'v0.9.40',
    }, indent=2), encoding='utf-8')
    # Explicit shipped HDR defaults in the shipped settings (engine\lantern.default.ini, which the
    # launcher copies to lantern.ini when a folder has neither it nor an older bbport.ini), so no
    # player's existing settings are replaced.
    ini = runtime / 'lantern.default.ini'
    defaults = dict(line.split('=', 1) for line in (overlay / 'nativeplus-example.ini').read_text().splitlines())
    defaults.pop('hdr')  # HDR output remains opt-in; Windows HDR must be enabled too.
    # Peak and paper white come from the display's peak unless the player sets them.
    unset = {'hdr_peak', 'hdr_paper_white'}
    lines = [line for line in ini.read_text(encoding='utf-8-sig').splitlines()
             if line.split('=', 1)[0].strip() not in defaults.keys() | unset]
    ini.write_text('\n'.join(lines + [f'{k}={v}' for k, v in defaults.items()]) + '\n', encoding='utf-8')
    required = ['Lantern Engine.exe', 'Bloodborne.exe', 'engine/out/bb-probe.exe', 'engine/out/bb-start.exe',
                'engine/out/bb-engine-assets.exe', 'engine/out/bb-gpu-capabilities.exe',
                'engine/out/bb-shader-lab.exe', 'engine/out/bb-isa-scan.exe', 'engine/out/gpu-cache.id',
                'engine/out/nvngx_dlss.dll', 'engine/patches/redzone.json',
                'licenses/RenoDX-MIT.txt']
    for name in required:
        if not (destination / name).is_file():
            raise RuntimeError(f'Incomplete distribution: {name}')
    # out\ at the top is the layout before engine\ (bb-start.exe in engine\out is ours, built here).
    if (destination / 'out').exists():
        raise RuntimeError('Mixed engine layouts in distribution')
    print(f'Complete Native+ HDR package: {destination}')


if __name__ == '__main__':
    assemble(*map(Path, sys.argv[1:5]))
