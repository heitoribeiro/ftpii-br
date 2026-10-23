// Copyright 2010 Joseph Jordan <joe.ftpii@psychlaw.com.au>
// This code is licensed to you under the terms of the GNU GPL, version 2;
// see file COPYING or http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt
// Modified 2026 for ftpii BR: bilingual status screen, automatic SD/USB mounting,
// B remounts both storage devices, HOME also exits, DVD support removed,
// password also read from an "ftpiibr_<password>" app folder.
#include <network.h>
#include <ogc/isfs.h>
#include <ogc/lwp_watchdog.h>
#include <string.h>
#include <unistd.h>
#include <wiiuse/wpad.h>

#include "diag.h"
#include "ftp.h"
#include "fs.h"
#include "iospatch.h"
#include "net.h"
#include "pad.h"
#include "reset.h"
#include "ui.h"
#include "version.h"

diag_t diag;

static const u16 PORT = 21;
static const char *APP_DIR_PREFIXES[] = { "ftpiibr_", "ftpii_", NULL };

static void initialise_video() {
    VIDEO_Init();
    GXRModeObj *rmode = VIDEO_GetPreferredMode(NULL);
    VIDEO_Configure(rmode);
    void *xfb = MEM_K0_TO_K1(SYS_AllocateFramebuffer(rmode));
    VIDEO_SetNextFramebuffer(xfb);
    VIDEO_ClearFrameBuffer(rmode, xfb, COLOR_BLACK);
    VIDEO_Flush();
    VIDEO_WaitVSync();
    if (rmode->viTVMode & VI_NON_INTERLACE) VIDEO_WaitVSync();
    CON_InitEx(rmode, 20, 30, rmode->fbWidth - 40, rmode->xfbHeight - 60);
    VIDEO_SetBlack(FALSE);
    VIDEO_Flush();
    VIDEO_WaitVSync();
    if (rmode->viTVMode & VI_NON_INTERLACE) VIDEO_WaitVSync();
}

static void set_password_from_executable(char *executable) {
    char *dir = basename(dirname(executable));
    u32 i;
    for (i = 0; APP_DIR_PREFIXES[i]; i++) {
        size_t len = strlen(APP_DIR_PREFIXES[i]);
        if (strncasecmp(APP_DIR_PREFIXES[i], dir, len) == 0) {
            set_ftp_password(dir + len);
            return;
        }
    }
}

static void initialise_ftpii(int argc, char **argv) {
    initialise_video();
    ui_init();
    ui_set_password(NULL);
    // Runtime-only patch (gone after power off) that lets this IOS read the NAND, as in ftpii 0.0.22.
    diag.ios_version = IOS_GetVersion();
    diag.ios_revision = IOS_GetRevision();
    diag.ahbprot = *(vu32 *)0xcd800064 == 0xffffffff;
    diag.patches_applied = IOSPATCH_Apply();
    printf("%s (IOS %i)\n", FTPII_BR_NAME, IOS_GetVersion());
    if (argc > 1) set_ftp_password(argv[1]);
    else if (argc == 1) set_password_from_executable(argv[0]);
    PAD_Init();
    WPAD_Init();
    initialise_reset_buttons();
    initialise_fs();
}

static void process_buttons() {
    u32 wii = check_wiimote(WPAD_BUTTON_A | WPAD_BUTTON_HOME | WPAD_BUTTON_B);
    u32 gc = check_gamecube(PAD_BUTTON_A | PAD_BUTTON_START | PAD_BUTTON_B);
    if ((wii & (WPAD_BUTTON_A | WPAD_BUTTON_HOME)) || (gc & (PAD_BUTTON_A | PAD_BUTTON_START))) {
        printf("Saindo... / Exiting...\n");
        set_reset_flag();
    } else if ((wii & WPAD_BUTTON_B) || (gc & PAD_BUTTON_B)) {
        remount_storage();
    }
}

int main(int argc, char **argv) {
    initialise_ftpii(argc, argv);

    bool network_down = true;
    s32 server = -1;
    while (!reset()) {
        if (network_down) {
            net_close(server);
            initialise_network();
            server = create_server(PORT);
            if (server < 0) continue;
            printf("Pronto na porta / Listening on port %u\n", PORT);
            network_down = false;
        }
        network_down = process_ftp_events(server);
        process_buttons();
        check_removable_devices(gettime());
        ui_draw(false);
    }
    ui_draw(true);
    cleanup_ftp();
    net_close(server);

    u32 i;
    for (i = 0; i < MAX_VIRTUAL_PARTITIONS; i++) unmount(VIRTUAL_PARTITIONS + i);

    ISFS_Deinitialize();

    maybe_poweroff();
    return 0;
}
