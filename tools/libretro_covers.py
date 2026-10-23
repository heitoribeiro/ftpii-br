"""Box art for WiiFlow's emulator plugins from the libretro-thumbnails project.

python libretro_covers.py ROM_FOLDER_OR_LIST OUT [--manual "My Rom=Official No-Intro Name" ...]

ROM_FOLDER_OR_LIST is a folder of ROMs or a text file with one file name per line (e.g. the output of
`wii_ftp.py ls /sd/vbagx/roms`). Covers are written as OUT/<cover folder>/<rom file name>.png, the path
WiiFlow uses for plugin covers (wiiflow/covers/<coverFolder>/<rom file>.png). Names are matched exactly
(No-Intro naming), then by title without the region/revision tags, then fuzzily; --manual handles the
rest. libretro-thumbnails stores duplicates as symlinks, which are followed. Images are scaled to 512 px.
Needs the GitHub CLI (`gh`) for the repository file lists, and Pillow.
"""
import argparse, io, json, os, re, subprocess, urllib.parse, urllib.request
from difflib import SequenceMatcher
from PIL import Image

# extension -> (libretro-thumbnails repository, cover folder used by wiiflow_hub.py)
SYSTEMS = {
    '.gb': ('Nintendo_-_Game_Boy', 'GB'), '.gbc': ('Nintendo_-_Game_Boy_Color', 'GBC'),
    '.gba': ('Nintendo_-_Game_Boy_Advance', 'GBA'), '.nes': ('Nintendo_-_Nintendo_Entertainment_System', 'NES'),
    '.sfc': ('Nintendo_-_Super_Nintendo_Entertainment_System', 'SNES'),
    '.smc': ('Nintendo_-_Super_Nintendo_Entertainment_System', 'SNES'),
    '.md': ('Sega_-_Mega_Drive_-_Genesis', 'MD'), '.gen': ('Sega_-_Mega_Drive_-_Genesis', 'MD'),
    '.sms': ('Sega_-_Master_System_-_Mark_III', 'SMS'), '.gg': ('Sega_-_Game_Gear', 'GG'),
}
_trees = {}


def boxarts(repo):
    if repo not in _trees:
        out = subprocess.run(['gh', 'api', f'repos/libretro-thumbnails/{repo}/git/trees/master?recursive=1',
                              '--jq', '[.tree[].path | select(startswith("Named_Boxarts/"))]'],
                             capture_output=True, text=True, check=True).stdout
        _trees[repo] = [p[len('Named_Boxarts/'):-4] for p in json.loads(out)]
    return _trees[repo]


def key(name):
    base = re.split(r' \(| \[', name)[0].lower()
    return re.sub(r'[^a-z0-9]', '', base.replace('&', 'and'))


def thumb_name(stem):
    return re.sub(r'[&*/:`<>?\\|]', '_', stem)  # libretro-thumbnails' file-name rule


def pick(stem, names, manual):
    if stem in manual:
        return manual[stem], 'manual'
    if thumb_name(stem) in names:
        return thumb_name(stem), 'exact'
    same = [n for n in names if key(n) == key(stem)]
    if same:
        return sorted(same, key=lambda n: ('(USA' not in n, '(Europe' not in n, len(n)))[0], 'same title'
    best = max(names, key=lambda n: SequenceMatcher(None, key(n), key(stem)).ratio())
    r = SequenceMatcher(None, key(best), key(stem)).ratio()
    return (best, f'fuzzy {r:.2f}') if r >= 0.85 else (None, f'not found (closest: {best} {r:.2f})')


def fetch(repo, name):
    url = (f'https://raw.githubusercontent.com/libretro-thumbnails/{repo}/master/Named_Boxarts/'
           + urllib.parse.quote(name + '.png'))
    data = urllib.request.urlopen(url, timeout=60).read()
    if not data.startswith(b'\x89PNG'):  # a symlink: the file holds the target name
        data = urllib.request.urlopen(urllib.parse.urljoin(url, urllib.parse.quote(data.decode().strip())), timeout=60).read()
    img = Image.open(io.BytesIO(data)).convert('RGB')
    img.thumbnail((512, 512), Image.LANCZOS)
    return img


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('roms')
    ap.add_argument('out')
    ap.add_argument('--manual', action='append', default=[], help='"rom file name without extension=No-Intro name"')
    a = ap.parse_args()
    manual = dict(m.split('=', 1) for m in a.manual)
    if os.path.isdir(a.roms):
        roms = sorted(os.listdir(a.roms))
    else:
        roms = [ln.strip().split()[-1] if ln.strip()[:1].isdigit() else ln.strip()
                for ln in open(a.roms, encoding='utf-8') if ln.strip()]
    found = 0
    for rom in roms:
        stem, ext = os.path.splitext(rom)
        if ext.lower() not in SYSTEMS:
            continue
        repo, folder = SYSTEMS[ext.lower()]
        name, how = pick(stem, boxarts(repo), manual)
        if name:
            os.makedirs(os.path.join(a.out, folder), exist_ok=True)
            fetch(repo, name).save(os.path.join(a.out, folder, rom + '.png'), optimize=True)
            found += 1
        print(f'{how:30} {rom}  <=  {name}')
    print(found, 'covers')


if __name__ == '__main__':
    main()
