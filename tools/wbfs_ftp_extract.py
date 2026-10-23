"""Extract one file (e.g. opening.bnr) from a WBFS game on the Wii's HD over FTP, without moving the HD.

Reads only the needed bytes with FTP REST: WBFS block table -> disc partition table -> DATA partition
ticket (title key, decrypted with the console's common key from the NAND backup) -> FST -> file clusters
(AES-CBC, 0x8000-byte clusters with 0x400 hash + 0x7C00 data).

python wbfs_ftp_extract.py GAMEID /files/opening.bnr out_path
"""
import ftplib, io, os, struct, sys
from Crypto.Cipher import AES
sys.path.insert(0, os.path.dirname(__file__))
import wii_ftp as w

# Path to the 16-byte common key dumped from YOUR console (for example /otp/common_key.bin read through
# ftpii BR, or the OTP of a BootMii backup). It is never included here; do not share it.
COMMON_KEY_FILE = os.environ.get('WII_COMMON_KEY', '')
PASSWORD = os.environ.get('WII_FTP_PASS', '')


class RemoteFile:
    """A WBFS image on the Wii's HD; images over 4 GiB are split into .wbfs, .wbf1, ... on FAT32."""

    def __init__(self, ftp, parts):
        self.f = ftp
        self.parts = []  # (path, start, size)
        start = 0
        for path, size in parts:
            self.parts.append((path, start, size))
            start += size
        self.cache = {}

    def read(self, off, n):
        """Read n bytes at off (whole 64 KiB pages, cached)."""
        out = bytearray()
        page = 0x40000  # fewer RETRs: each one is a fresh data connection and file open on the Wii
        while n > 0:
            # pages are aligned inside each part file, so none straddles the .wbfs/.wbf1 boundary
            path, start, size = next(p for p in self.parts if p[1] <= off < p[1] + p[2])
            base = start + (off - start) // page * page
            if base not in self.cache:
                self.cache[base] = self._fetch(base, min(page, start + size - base))
            chunk = self.cache[base][off - base:off - base + n]
            if not chunk:
                raise EOFError(off)
            out += chunk
            off += len(chunk)
            n -= len(chunk)
        return bytes(out)

    def _fetch(self, off, n):
        # Many aborted RETRs in a row can make ftpii answer "550 Success" (open failed, errno 0):
        # give it a moment and start a fresh session.
        for attempt in range(5):
            try:
                return self._fetch_once(off, n)
            except (ftplib.Error, OSError):
                if attempt == 4:
                    raise
                try:
                    self.f.close()
                except Exception:
                    pass
                import time
                time.sleep(3 + 2 * attempt)
                self.f = w.connect(PASSWORD)

    def _fetch_once(self, off, n):
        path, start, size = next(p for p in self.parts if p[1] <= off < p[1] + p[2])
        conn = self.f.transfercmd(f'RETR {path}', rest=off - start)
        buf = bytearray()
        while len(buf) < n:
            d = conn.recv(n - len(buf))
            if not d:
                break
            buf += d
        conn.close()
        try:
            self.f.voidresp()  # 226 if the file ended, otherwise the server reports the aborted transfer
        except ftplib.Error:
            pass
        return bytes(buf)


class WbfsDisc:
    def __init__(self, rf):
        self.rf = rf
        h = rf.read(0, 12)
        assert h[:4] == b'WBFS'
        self.hd_sec = 1 << h[8]
        self.s = h[9]
        self.table_off = self.hd_sec + 0x100

    def read(self, off, n):
        out = bytearray()
        while n > 0:
            blk, inner = off >> self.s, off & ((1 << self.s) - 1)
            phys = struct.unpack('>H', self.rf.read(self.table_off + 2 * blk, 2))[0]
            take = min(n, (1 << self.s) - inner)
            out += self.rf.read((phys << self.s) + inner, take) if phys else b'\0' * take
            off += take
            n -= take
        return bytes(out)


class Partition:
    def __init__(self, disc):
        self.disc = disc
        count, table = struct.unpack('>II', disc.read(0x40000, 8))
        entries = [struct.unpack('>II', disc.read((table << 2) + 8 * i, 8)) for i in range(count)]
        self.off = next(o << 2 for o, t in entries if t == 0)  # DATA partition
        tik = disc.read(self.off, 0x2A4)
        enc_key, tid, kidx = tik[0x1BF:0x1CF], tik[0x1DC:0x1E4], tik[0x1F1]
        assert kidx == 0, 'only the normal common key is supported'
        self.key = AES.new(open(COMMON_KEY_FILE, 'rb').read(), AES.MODE_CBC, tid + b'\0' * 8).decrypt(enc_key)
        self.data_off = self.off + (struct.unpack('>I', disc.read(self.off + 0x2B8, 4))[0] << 2)

    def read(self, off, n):
        out = bytearray()
        while n > 0:
            cl, inner = divmod(off, 0x7C00)
            raw = self.disc.read(self.data_off + cl * 0x8000, 0x8000)
            plain = AES.new(self.key, AES.MODE_CBC, raw[0x3D0:0x3E0]).decrypt(raw[0x400:])
            take = min(n, 0x7C00 - inner)
            out += plain[inner:inner + take]
            off += take
            n -= take
        return bytes(out)

    def find(self, path):
        fst_off, fst_size = struct.unpack('>II', self.read(0x424, 8))
        fst = self.read(fst_off << 2, fst_size << 2)
        n = struct.unpack('>I', fst[8:12])[0]
        names = fst[n * 12:]

        def name(i):
            o = struct.unpack('>I', fst[i * 12:i * 12 + 4])[0] & 0xFFFFFF
            return names[o:names.index(b'\0', o)].decode('latin-1')

        parts = [p for p in path.strip('/').split('/') if p][1:]  # drop the leading "files"
        i, end = 1, n
        for depth, part in enumerate(parts):
            last = depth == len(parts) - 1
            while i < end:
                is_dir = fst[i * 12] == 1
                nxt = struct.unpack('>I', fst[i * 12 + 8:i * 12 + 12])[0] if is_dir else i + 1
                if name(i).lower() == part.lower():
                    if last:
                        o, size = struct.unpack('>II', fst[i * 12 + 4:i * 12 + 12])
                        return o << 2, size
                    i, end = i + 1, nxt
                    break
                i = nxt
            else:
                raise FileNotFoundError(path)
        raise FileNotFoundError(path)


def extract(ftp, gid, path, out):
    folder = next(n for n, d, _ in w.listing(ftp, '/usb/wbfs') if d and n.endswith(f'[{gid}]'))
    files = {n.lower(): (n, s) for n, d, s in w.listing(ftp, f'/usb/wbfs/{folder}') if not d}
    base = next(k for k in files if k.endswith('.wbfs'))[:-5]
    parts = [files[base + '.wbfs']]
    while f'{base}.wbf{len(parts)}' in files:
        parts.append(files[f'{base}.wbf{len(parts)}'])
    part = Partition(WbfsDisc(RemoteFile(ftp, [(f'/usb/wbfs/{folder}/{n}', s) for n, s in parts])))
    off, size = part.find(path)
    data = part.read(off, size)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, 'wb').write(data)
    return size


if __name__ == '__main__':
    if len(sys.argv) != 4 or not COMMON_KEY_FILE:
        sys.exit(__doc__ + "\nSet WII_COMMON_KEY to your console's common_key.bin and WII_FTP_PASS to the ftpii password.")
    gid, path, out = sys.argv[1:4]
    ftp = w.connect(PASSWORD)
    print(gid, extract(ftp, gid, path, out), 'bytes ->', out)
    ftp.quit()
