# ftpii BR

A modified version of **ftpii 0.0.22** by Joseph Jordan (joedj), the FTP server for the Nintendo Wii.
The original source and its isfs/otp/seeprom/iospatch libraries come from the ftpii Google Code
archive and are licensed under the GNU GPL v2 (see `COPYING`). The first commit of this repository
is the unmodified original; every change since then is in the git history.

## Changes from ftpii 0.0.22

- **No more lockups from abandoned connections.** Control connections idle for 180 s are closed, and
  when all 3 slots are in use (the Wii IOS itself stops accepting at 4) the longest-idle client is evicted. In 0.0.22, clients that disconnected
  without `QUIT` (Windows Explorer, scripts that time out) kept the 5 slots forever.
- **No socket leak.** The passive listening socket is closed after every transfer.
- **USB storage mounts by itself**, at start-up (waiting up to 12 s for a hard drive to spin up) and when
  plugged in later. 0.0.22 only woke up the SD card, so a USB drive needed a manual remount with B.
- **Colons allowed in file names**, so NAND saves such as `HP:OOTP` can be downloaded.
- **Bilingual (Portuguese/English) status screen**: address, password, mounted devices, connections,
  current transfer and speed, and a short log instead of a scrolling console.
- `FEAT`, `OPTS UTF8` and the `X*` command aliases; static 64 KB transfer buffers and several buffers
  per loop pass.
- **NAND stays read-only**: the isfs driver has no write functions, and only the in-memory ISFS
  read-permission patch from 0.0.22 is applied (nothing is written to the NAND).
- Removed: DVD, NTFS, NAND-image and SD Gecko support (their libraries no longer build).
- Builds with current devkitPPC/libogc (compatibility layer for the removed `diropen` API).

## Usage

Copy `apps/ftpiibr` to the SD card and start it from the Homebrew Channel. To set a password, rename
the folder to `apps/ftpiibr_YourPassword`. A or HOME exits, B remounts the SD card and USB drive.
Paths: `/sd`, `/usb`, `/isfs` (NAND, read-only), `/otp`, `/seeprom`.
