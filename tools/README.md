# PC tools for ftpii BR

Python 3 scripts that run on the PC and talk to a Wii running ftpii BR (or plain ftpii).

| Script | What it does |
|---|---|
| `wii_ftp.py` | Finds the Wii on the local network (last IP used, otherwise a /24 scan for an FTP server that greets with "ftpii") and runs one command over a single connection: `info` (`SITE INFO` diagnostics), `ls`, `get`, `put` (files or whole folders) and `mirror` (recursive download, e.g. a NAND backup from `/isfs`). |
| `wbfs_ftp_extract.py` | Extracts one file from a game on the Wii's USB drive without moving the drive, e.g. `opening.bnr` to build a channel banner. It reads only the bytes it needs with FTP `REST`, follows the WBFS block table (including split `.wbf1` parts of games over 4 GiB), decrypts the DATA partition with the title key and walks the FST. Needs `pycryptodome` and the common key dumped from **your own** console. |
| `wii_net_spy.py` | Shows what a game does on the network: the PC becomes the Wii's DNS server, logs every lookup, and relays the login (NAS), friend server (GPCM/GPSP, TCP 29900/29901) and availability check (UDP 27900) to the real servers unchanged while logging the traffic. |

## Setup

```
pip install pycryptodome        # only for wbfs_ftp_extract.py
set WII_FTP_PASS=yourpassword   # the part after "ftpiibr_" in the app folder name (Windows)
export WII_FTP_PASS=yourpassword  # Linux/macOS
```

## Examples

```
python wii_ftp.py info
python wii_ftp.py mirror /isfs/title/00010000 backup_saves
python wii_ftp.py put mychannel.wad /sd/WAD/

set WII_COMMON_KEY=C:\path\to\your\common_key.bin
python wbfs_ftp_extract.py RMCE01 /files/opening.bnr opening.bnr

python wii_net_spy.py 192.168.0.10 192.168.0.1   # this PC's IP, router IP
```

Notes:
- From Git Bash on Windows, arguments such as `/usb/...` are rewritten to `C:/Program Files/Git/usb/...`;
  `wii_ftp.py` undoes that, otherwise run with `MSYS_NO_PATHCONV=1`.
- ftpii answers `550 Success` when a `REST` offset is past the end of the file (that is how the split
  `.wbf1` support was found).
- `wii_net_spy.py`: set the Wii's DNS back to automatic when you are done, or the Wii loses Internet
  access when the PC is off. Windows may ask to allow Python through the firewall.
- Never publish your console's keys (`/otp`, `/seeprom`, `common_key.bin`, NAND backups).
