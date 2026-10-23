"""Find the online games in a WBFS folder and, optionally, patch them for Wiimmfi with wit.

python wiimmfi_batch.py scan  WBFS_DIR                       # which games still use nintendowifi.net
python wiimmfi_batch.py patch WBFS_DIR ORIGINALS_DIR GAME_ID...  # patched copy replaces the game folder,
                                                             # the untouched original moves to ORIGINALS_DIR
Needs Wiimms ISO Tools (wit) in PATH or --wit. Each patched copy is checked (wit verify, no nintendowifi.net
left, wiimmfi.de present) before any folder is moved; nothing is deleted.

Notes from real use:
- Mario Kart Wii needs Wiimmfi's newer MKW-specific patch; wit 3.05a's --wiimmfi only applies the generic one
  (the server answers 23904). Let the loader patch Mario Kart Wii instead (WiiFlow: private_server=2).
- USB loaders that support Wiimmfi patch the other games at boot anyway; a pre-patched image mostly helps
  loaders without that option.
"""
import argparse, os, re, shutil, subprocess, tempfile

ENV = dict(os.environ, MSYS_NO_PATHCONV='1')


def run(wit, *args):
    r = subprocess.run([wit, *args], env=ENV, capture_output=True, text=True, errors='replace')
    if r.returncode:
        raise RuntimeError(r.stdout[-1500:] + r.stderr[-1500:])
    return r.stdout


def game_dirs(root):
    for d in sorted(os.listdir(root)):
        m = re.search(r'\[(\w{6})\]$', d)
        imgs = [x for x in os.listdir(os.path.join(root, d)) if x.lower().endswith(('.wbfs', '.iso'))] if m else []
        if imgs:
            yield m[1], d, os.path.join(root, d, imgs[0])


def domain_counts(wit, image):
    """Count nintendowifi.net / wiimmfi.de in main.dol and the .rel/.dol files of the DATA partition."""
    with tempfile.TemporaryDirectory() as tmp:
        run(wit, 'extract', image, tmp, '--psel', 'data', '--files', '+/sys/main.dol', '--files', '+*.rel',
            '--files', '+*.dol', '-q', '-o')
        n = w = 0
        for r, _, fs in os.walk(tmp):
            for fn in fs:
                if fn.endswith(('.dol', '.rel')):
                    data = open(os.path.join(r, fn), 'rb').read()
                    n += data.count(b'nintendowifi.net')
                    w += data.count(b'wiimmfi.de')
        return n, w


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['scan', 'patch'])
    ap.add_argument('wbfs')
    ap.add_argument('originals', nargs='?')
    ap.add_argument('ids', nargs='*')
    ap.add_argument('--wit', default='wit')
    a = ap.parse_args()

    if a.cmd == 'scan':
        for gid, d, img in game_dirs(a.wbfs):
            n, w = domain_counts(a.wit, img)
            tag = 'online (Nintendo WFC)' if n else ('already Wiimmfi' if w else '-')
            print(f'{gid}  nintendowifi={n:3}  wiimmfi={w:3}  {tag:22} {d}')
        return

    assert a.originals and a.ids, 'patch needs ORIGINALS_DIR and at least one game ID'
    os.makedirs(a.originals, exist_ok=True)
    games = {gid: (d, img) for gid, d, img in game_dirs(a.wbfs)}
    for gid in a.ids:
        d, img = games[gid]
        tmp_dir = os.path.join(a.wbfs, f'.wiimmfi_{gid}')
        os.makedirs(tmp_dir, exist_ok=True)
        out = os.path.join(tmp_dir, os.path.basename(img).rsplit('.', 1)[0] + '.wbfs')
        run(a.wit, 'copy', '--wiimmfi', '--psel', 'data', '--wbfs', '--split', img, out)
        assert '+OK' in run(a.wit, 'verify', out), gid
        n, w = domain_counts(a.wit, out)
        assert n == 0 and w > 0, (gid, n, w)
        shutil.move(os.path.join(a.wbfs, d), os.path.join(a.originals, d))
        shutil.move(tmp_dir, os.path.join(a.wbfs, d))
        print(f'{gid}: {w} Wiimmfi addresses, original kept in {a.originals}')


if __name__ == '__main__':
    main()
