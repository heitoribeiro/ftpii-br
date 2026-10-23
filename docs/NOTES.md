# Field notes: a homebrewed Wii in 2026

What we found while setting up one NTSC-U Wii (System Menu 4.3U, HBC, Priiloader, d2x cIOS 249/250/251,
USB Loader GX r1283, WiiFlow Lite 5.6.2, games on a FAT32 USB drive). Each item was checked on the
console; where the cause is still unknown, it says so.

*Resumo em português no final.*

## Mario Kart Wii online hangs at "Connecting to Nintendo WFC..." in USB Loader GX

**Symptom.** With USB Loader GX's Wiimmfi option the game sat at "Connecting to Nintendo WFC..." forever,
no error code. Same with WiiLink WFC's gecko code, and with cIOS 249, 250 and 251.

**What the network capture showed** (`tools/wii_net_spy.py`): connection test, availability check,
NAS login and the Wiimmfi update payload all succeeded. Then on the GPCM friend server (TCP 29900) the
server sent its `\lc\1\challenge\...` and the Wii **never sent `\login\`**.

**Fix: start the game from WiiFlow Lite.** WiiFlow's Wiimmfi patch for Mario Kart Wii is the same code as
USB Loader GX's (we diffed `do_new_wiimmfi()`: identical apart from the patcher name), yet from WiiFlow the
login went through within 0.2 s and online play works. The difference is how each loader hands the
console over to the game (WiiFlow uses a separate small game booter). We did not find the exact cause.

How we set it up:
- WiiFlow per-game setting in `wiiflow/settings/gameconfig2.ini`: `[RMCE01]` `private_server=2` (Wiimmfi).
- WiiFlow launches a game directly when its boot argument is the game ID (`source/main.cpp`), so a
  forwarder channel pointing to `/apps/wiiflow/boot.dol` with argument `RMCE01` gives a Wii Menu channel
  that goes straight into the game.
- WiiFlow must see the USB drive: "Mount SD only" (Settings > Startup) must be **No**. This option is
  stored in WiiFlow's own NAND save, so editing `sd_only=` in `wiiflow_lite.ini` is not enough.

Things that did **not** help: MTU 1400, custom DNS, a different cIOS, Wiimmfi's DNS method through USB
Loader GX (error 20100), patching the image with wit 3.05a `--wiimmfi` (error 23904: that wit only applies
the generic patch, Mario Kart Wii needs the newer one, and it does not set the "already patched" marker at
0x80271d14 (NTSC-U), so loaders patch over it anyway).

## Wiimmfi error 23917

23917 means access denied (ban). <https://wiimmfi.de/show-bans> lists the reason. Ours:
"Versus Race region 870 is forbidden (rk=vs_870). Automatic system ban. Ban for 15 minutes." It came
from an old custom-track mod ("Mario Kart Fusion") that races in a region Wiimmfi does not allow. The ban
covers the whole console, so the original game also got 23917 until it expired. For custom tracks online
use a distribution with an allowed region (Retro Rewind on Retro WFC, CTGP-R on Wiimmfi).

## WiiFlow Lite

- **Console restarts while "caching covers" (stopped at 33/36):** one box cover PNG was truncated.
  Check covers with any image library before copying them in.
- **Emulator hub with plugins:** WiiFlow plugin `.ini` files can launch the GX emulators straight into a
  ROM. Snes9x GX, FCE Ultra GX and VBA GX take `argv[1]` = folder, `argv[2]` = file name
  (`arguments={device}:/{path}|{name}`); Genesis Plus GX joins them directly, so its folder needs a
  trailing slash (`{device}:/{path}/|{name}`). Not64 and WiiSX do not load a ROM from arguments; a source
  menu button with `source=homebrew` and `autoboot=<app folder>` opens them instead.
- One rebuilt (wit-composed) game image crashed WiiFlow's game booter (DSI, DAR 0x4) when started
  through the channel; the same image later started normally once WiiFlow had rebuilt its game list.
  We did not pin down the cause.

## Wii Menu freezes when scrolling to a page of forwarder channels

Forwarder channels built from the game discs' own banners carry the disc's heavy animated icon. Several on
one page ran the Wii Menu out of memory (freeze when scrolling). Rebuilding only the icon as a light
single-texture CMPR image (~10 KB), keeping the disc's animated banner, fixed it. Also: the Wii Menu looks
up `icon.brlyt`/`banner.brlyt` case-sensitively, while the Disc Channel does not, so some discs' banners
need their layout file names lower-cased.

## ftpii

- The Wii IOS accepts only 4 simultaneous connections on a listening socket and stops accepting on the
  5th; ftpii BR serves at most 3 and answers `421` beyond that.
- Wi-Fi throughput is about 500 KB/s down and 350 KB/s up, so moving whole games over Wi-Fi takes hours;
  `wbfs_ftp_extract.py` reads just the bytes it needs instead.
- br7 froze on exit with nothing on screen; br8 shows and logs each exit step (`sd:/ftpiibr_saida.txt`)
  and returns to the Homebrew Channel, or to the Wii Menu when started from a channel.

---

## Resumo em português

- **Mario Kart Wii online travando em "Connecting to Nintendo WFC" no USB Loader GX:** o Wii nunca
  responde o login do servidor de amigos (GPCM). Pelo **WiiFlow Lite**, com o mesmo patch do Wiimmfi,
  funciona. Solução: abrir o jogo pelo WiiFlow (`private_server=2` no `gameconfig2.ini`) e criar um canal
  que chama o WiiFlow com o ID do jogo como argumento. No WiiFlow, "Montar SD somente" precisa estar em
  **Não**.
- **Erro 23917 do Wiimmfi:** bloqueio. Veja o motivo em <https://wiimmfi.de/show-bans>. O nosso foi
  automático, de 15 minutos, por usar um mod com região proibida (Mario Kart Fusion, região 870).
- **WiiFlow reiniciando o console ao carregar capas:** havia uma capa PNG corrompida.
- **Menu do Wii travando ao rolar com canais de jogos:** ícones animados pesados; trocar por ícones leves.
- **Ferramentas para PC** em `tools/`: acesso ao Wii pelo FTP, extração de arquivos dos jogos no HD pelo
  Wi-Fi e diagnóstico de rede dos jogos online.
