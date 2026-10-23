"""Small WBFS helpers.

python wbfs_utils.py region SOURCE.wbfs TARGET.wbfs   copy the 32-byte region/age-rating block (disc offset
                                                      0x4E000) from SOURCE into TARGET, in place; the old
                                                      bytes are saved as TARGET.region_before
python wbfs_utils.py extents FILE...                  how many pieces each file is in on disk (Windows)

wit composes rebuilt images (e.g. after translating a game) with a zeroed region block; copying it back from
the original disc keeps the image like the original. `wit mix ORIG select update header region NEW select
data ORIG select channel -D out.wbfs --wbfs` rebuilds a whole disc the same way.
"""
import struct, sys

REGION_OFF, REGION_LEN = 0x4E000, 0x20


def region_pos(path):
    with open(path, 'rb') as f:
        h = f.read(12)
        assert h[:4] == b'WBFS', f'{path}: not a WBFS file'
        hd_sec, s = 1 << h[8], h[9]
        f.seek(hd_sec + 0x100 + 2 * (REGION_OFF >> s))  # disc info: 0x100-byte header copy, then the block table
        phys = struct.unpack('>H', f.read(2))[0]
        assert phys, 'block not allocated'
        return (phys << s) + (REGION_OFF & ((1 << s) - 1))


def copy_region(src, dst):
    with open(src, 'rb') as f:
        f.seek(region_pos(src))
        good = f.read(REGION_LEN)
    pos = region_pos(dst)
    with open(dst, 'r+b') as f:
        f.seek(pos)
        old = f.read(REGION_LEN)
        assert old[:4] == good[:4], 'different region code: refusing'
        open(dst + '.region_before', 'wb').write(old)
        f.seek(pos)
        f.write(good)
    print('before:', old.hex())
    print('after :', good.hex())


def extents(path):
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    k32.CreateFileW.restype = wintypes.HANDLE
    h = k32.CreateFileW(path, 0x80000000, 7, None, 3, 0, None)
    if h == wintypes.HANDLE(-1).value:
        raise OSError(ctypes.get_last_error(), path)
    count, start = 0, 0
    try:
        while True:
            out = ctypes.create_string_buffer(1 << 16)
            ret = wintypes.DWORD()
            ok = k32.DeviceIoControl(h, 0x00090073, struct.pack('<q', start), 8, out, len(out), ctypes.byref(ret), None)
            err = ctypes.get_last_error()
            if not ok and err != 234:  # ERROR_MORE_DATA
                raise OSError(err, path)
            n = struct.unpack_from('<I', out.raw, 0)[0]
            count += n
            if ok:
                return count
            start = struct.unpack_from('<q', out.raw, 16 + (n - 1) * 16)[0]
    finally:
        k32.CloseHandle(h)


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == 'region':
        copy_region(sys.argv[2], sys.argv[3])
    elif len(sys.argv) >= 3 and sys.argv[1] == 'extents':
        for p in sys.argv[2:]:
            print(f'{extents(p):7d}  {p}')
    else:
        sys.exit(__doc__)
