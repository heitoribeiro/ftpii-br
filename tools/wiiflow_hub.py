"""Turn WiiFlow Lite 5.6.x into one "emulator hub": a console menu on start, one button per system.

Writes, under OUT (copy its contents to the SD card root):
  wiiflow/plugins/*.ini            plugins for the GX emulators, launching straight into the chosen ROM
  wiiflow/source_menu/             source_menu.ini + the button images it uses
  apps/wiiflow/wiiflow_lite.ini    your current settings with: language, source menu on start, plugin view

python wiiflow_hub.py --ini wiiflow_lite.ini --source-menu-zip source_menu.optional.zip --out hub
  wiiflow_lite.ini           from sd:/apps/wiiflow/ (start WiiFlow once so it exists)
  source_menu.optional.zip   from the WiiFlow Lite release page (button images)

Argument formats, from the emulators' sources: Snes9x GX, FCE Ultra GX and VBA GX read argv[1] = folder,
argv[2] = file name; Genesis Plus GX joins argv[1] and argv[2] directly, so its folder needs a trailing
slash. Not64 and WiiSX do not load a ROM from arguments, so their buttons just open the emulator
(source=homebrew, autoboot=<folder in sd:/apps>). Covers go to wiiflow/covers/<coverFolder>/<rom file>.png
(see libretro_covers.py). Edit PLUGINS / APPS below for other emulators or folders.
"""
import argparse, os, re, zipfile

GX_ARGS = '{device}:/{path}|{name}'
GEN_ARGS = '{device}:/{path}/|{name}'

# file, display name, magic, dol, ROM folder (on the SD), file types, cover folder, args, case color, button image
PLUGINS = [
    ('GBA', 'Game Boy Advance', '56424188', 'sd:/apps/vbagx/boot.dol', 'vbagx/roms/', '.gba|.zip', 'GBA', GX_ARGS, '6A5ACD', 'Game_Boy_Advance'),
    ('GBC', 'Game Boy Color', '56424178', 'sd:/apps/vbagx/boot.dol', 'vbagx/roms/', '.gbc', 'GBC', GX_ARGS, 'FFD700', 'Game_Boy_Color'),
    ('GB', 'Game Boy', '56424168', 'sd:/apps/vbagx/boot.dol', 'vbagx/roms/', '.gb', 'GB', GX_ARGS, '808080', 'Game_Boy'),
    ('SNES', 'Super Nintendo', '534E4553', 'sd:/apps/snes9xgx/boot.dol', 'snes9xgx/roms/', '.smc|.sfc|.fig|.swc|.zip', 'SNES', GX_ARGS, '9370DB', 'snes'),
    ('NES', 'NES', '46434555', 'sd:/apps/fceugx/boot.dol', 'fceugx/roms/', '.nes|.fds|.unf|.zip', 'NES', GX_ARGS, 'B22222', 'nes'),
    ('MD', 'Mega Drive', '53454761', 'sd:/apps/genplus/boot.dol', 'genplus/roms/', '.md|.gen|.smd|.bin|.zip', 'MD', GEN_ARGS, '1E1E1E', 'Sega_Genesis'),
    ('SMS', 'Master System', '53454771', 'sd:/apps/genplus/boot.dol', 'genplus/roms/', '.sms', 'SMS', GEN_ARGS, '1E1E1E', 'Sega_MasterSystem'),
    ('GG', 'Game Gear', '53454791', 'sd:/apps/genplus/boot.dol', 'genplus/roms/', '.gg', 'GG', GEN_ARGS, '1E1E1E', 'Game_Gear'),
]
# buttons that open an app (folder name in sd:/apps, case-sensitive)
APPS = [('Nintendo 64', 'not64', 'Nintendo_64'), ('PlayStation', 'wiiSX', 'Playstation'),
        ('GameCube', 'nintendont', 'Gamecube')]
WII_GAMES_BUTTON = ('Wii', 'Wii')  # source=wii: the Wii games on the USB drive (needs "Mount SD only" = No)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--ini', required=True)
    ap.add_argument('--source-menu-zip', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--language', default='brazilian', help='a file name in sd:/wiiflow/languages without .ini')
    ap.add_argument('--no-wii-button', action='store_true')
    a = ap.parse_args()

    plug_dir = os.path.join(a.out, 'wiiflow', 'plugins')
    src_dir = os.path.join(a.out, 'wiiflow', 'source_menu')
    os.makedirs(plug_dir, exist_ok=True)
    os.makedirs(src_dir, exist_ok=True)
    for fn, name, magic, dol, romdir, types, cover, args, color, _ in PLUGINS:
        with open(os.path.join(plug_dir, fn + '.ini'), 'w', encoding='utf-8', newline='\n') as f:
            f.write(f'[PLUGIN]\ndisplayname={name}\ndolFile={dol}\nmagic={magic}\nromDir={romdir}\n'
                    f'fileTypes={types}\ncoverFolder={cover}\ncoverColor={color}\narguments={args}\n'
                    'rompartition=0\nboxmode=0\n')

    buttons = [('plugin', name, magic, '', img) for _, name, magic, *_, img in PLUGINS]
    buttons += [('homebrew', title, '', app, img) for title, app, img in APPS]
    if not a.no_wii_button:
        buttons.append(('wii', WII_GAMES_BUTTON[0], '', '', WII_GAMES_BUTTON[1]))
    assert len(buttons) <= 12, 'the source menu shows 12 buttons per page'
    images = set()
    with open(os.path.join(src_dir, 'source_menu.ini'), 'w', encoding='utf-8', newline='\n') as f:
        for i, (source, title, magic, autoboot, img) in enumerate(buttons):
            f.write(f'[BUTTON_{i}]\nautoboot={autoboot}\ncat_page=1\ncategory=0\nhidden=no\n'
                    f'image={img}.png\nimage_s={img}b.png\n' + (f'magic={magic}\n' if magic else '')
                    + f'source={source}\ntitle={title}\n\n')
            images |= {f'{img}.png', f'{img}b.png'}
    with zipfile.ZipFile(a.source_menu_zip) as z:
        for n in z.namelist():
            if n.count('/') == 1 and n.split('/')[-1] in images:
                open(os.path.join(src_dir, n.split('/')[-1]), 'wb').write(z.read(n))
    missing = images - set(os.listdir(src_dir))
    assert not missing, f'images not in the zip: {missing}'

    text = open(a.ini, encoding='utf-8').read()
    for key, val in [('language', a.language), ('source_on_start', 'yes'), ('sources', '8'),
                     ('database_titles', 'no')]:
        text, n = re.subn(rf'^{key}=.*$', f'{key}={val}', text, flags=re.M)
        assert n == 1, f'{key} not found in {a.ini}'
    os.makedirs(os.path.join(a.out, 'apps', 'wiiflow'), exist_ok=True)
    open(os.path.join(a.out, 'apps', 'wiiflow', 'wiiflow_lite.ini'), 'w', encoding='utf-8', newline='\n').write(text)
    print(f'{len(PLUGINS)} plugins, {len(buttons)} buttons -> {a.out} (copy to the SD card root)')


if __name__ == '__main__':
    main()
