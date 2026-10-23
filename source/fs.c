// Copyright 2010 Joseph Jordan <joe.ftpii@psychlaw.com.au>
// This code is licensed to you under the terms of the GNU GPL, version 2;
// see file COPYING or http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt
// Modified 2026 for ftpii BR:
//  - DVD, NTFS, NAND-image and SD Gecko support removed (not needed, and their libraries are gone).
//  - USB storage is now started and mounted automatically, at boot and when plugged in
//    (the original only woke up the SD card, so the HDD needed a manual remount with B).
//  - Bilingual (PT/EN) log messages.
#include <fat.h>
#include <malloc.h>
#include <ogc/ipc.h>
#include <ogc/isfs.h>
#include <ogc/lwp_watchdog.h>
#include <ogc/usbstorage.h>
#include <sdcard/wiisd_io.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#include "compat.h"
#include "fs.h"
#include "isfs.h"
#include "otp.h"
#include "seeprom.h"
#include "ui.h"

#define CACHE_PAGES 16
#define CACHE_SECTORS_PER_PAGE 64
#define USB_BOOT_WAIT_SECONDS 12
#define USB_POLL_SECONDS 4

VIRTUAL_PARTITION VIRTUAL_PARTITIONS[] = {
    { "SD", "/sd", "sd", "sd:/", false, &__io_wiisd },
    { "USB", "/usb", "usb", "usb:/", false, &__io_usbstorage },
    { "NAND", "/isfs", "isfs", "isfs:/", false, NULL },
    { "OTP", "/otp", "otp", "otp:/", false, NULL },
    { "SEEPROM", "/seeprom", "seeprom", "seeprom:/", false, NULL }
};
const u32 MAX_VIRTUAL_PARTITIONS = (sizeof(VIRTUAL_PARTITIONS) / sizeof(VIRTUAL_PARTITION));

VIRTUAL_PARTITION *PA_SD      = VIRTUAL_PARTITIONS + 0;
VIRTUAL_PARTITION *PA_USB     = VIRTUAL_PARTITIONS + 1;
VIRTUAL_PARTITION *PA_ISFS    = VIRTUAL_PARTITIONS + 2;
VIRTUAL_PARTITION *PA_OTP     = VIRTUAL_PARTITIONS + 3;
VIRTUAL_PARTITION *PA_SEEPROM = VIRTUAL_PARTITIONS + 4;

static VIRTUAL_PARTITION *to_virtual_partition(const char *virtual_prefix) {
    u32 i;
    for (i = 0; i < MAX_VIRTUAL_PARTITIONS; i++)
        if (!strcasecmp(VIRTUAL_PARTITIONS[i].alias, virtual_prefix))
            return &VIRTUAL_PARTITIONS[i];
    return NULL;
}

static bool is_fat(VIRTUAL_PARTITION *partition) {
    return partition == PA_SD || partition == PA_USB;
}

bool mounted(VIRTUAL_PARTITION *partition) {
    DIR_ITER *dir = diropen(partition->prefix);
    if (dir) {
        dirclose(dir);
        return true;
    }
    return false;
}

bool mount(VIRTUAL_PARTITION *partition) {
    if (!partition || mounted(partition)) return false;

    bool success = false;
    if (is_fat(partition)) {
        if (partition == PA_SD) partition->disc->shutdown();
        if (partition->disc->startup() && partition->disc->isInserted())
            success = fatMount(partition->mount_point, partition->disc, 0, CACHE_PAGES, CACHE_SECTORS_PER_PAGE);
    } else if (partition == PA_ISFS) {
        success = ISFS_Mount();
    } else if (partition == PA_OTP) {
        success = OTP_Mount();
    } else if (partition == PA_SEEPROM) {
        success = SEEPROM_Mount();
    }
    partition->inserted = success;
    printf("%s: %s\n", partition->name, success ? "montado / mounted" : "falhou / failed");
    return success;
}

bool mount_virtual(const char *dir) {
    return mount(to_virtual_partition(dir));
}

bool unmount(VIRTUAL_PARTITION *partition) {
    if (!partition || !mounted(partition)) return false;

    bool success = false;
    if (is_fat(partition)) {
        fatUnmount(partition->prefix);
        success = true;
    } else if (partition == PA_ISFS) {
        success = ISFS_Unmount();
    } else if (partition == PA_OTP) {
        success = OTP_Unmount();
    } else if (partition == PA_SEEPROM) {
        success = SEEPROM_Unmount();
    }
    printf("%s: %s\n", partition->name, success ? "desmontado / unmounted" : "falhou ao desmontar / unmount failed");
    return success;
}

bool unmount_virtual(const char *dir) {
    return unmount(to_virtual_partition(dir));
}

static u64 sd_check_timer = 0;
static u64 usb_check_timer = 0;

static void check_fat_device(VIRTUAL_PARTITION *partition, u64 now, u64 *timer, u32 interval) {
    if (now <= *timer) return;
    *timer = now + secs_to_ticks(interval);
    if (mounted(partition)) {
        if (!partition->disc->isInserted()) {
            printf("%s removido / removed\n", partition->name);
            unmount(partition);
        }
    } else {
        // Wake the device up before asking whether it is there; USB needs this too.
        if (partition->disc->startup() && partition->disc->isInserted()) {
            printf("%s detectado / detected\n", partition->name);
            mount(partition);
        }
    }
}

void check_removable_devices(u64 now) {
    check_fat_device(PA_SD, now, &sd_check_timer, 2);
    check_fat_device(PA_USB, now, &usb_check_timer, USB_POLL_SECONDS);
}

void remount_storage() {
    printf("Remontando SD e USB / Remounting SD and USB...\n");
    unmount(PA_SD);
    unmount(PA_USB);
    mount(PA_SD);
    mount(PA_USB);
}

void initialise_fs() {
    OTP_Mount();
    SEEPROM_Mount();
    ISFS_SU();
    if (ISFS_Initialize() == IPC_OK) mount(PA_ISFS);

    mount(PA_SD);
    // Hard drives can take several seconds to spin up after the console boots.
    u64 deadline = gettime() + secs_to_ticks(USB_BOOT_WAIT_SECONDS);
    printf("Procurando USB / Looking for USB...\n");
    ui_draw(true);
    while (!mount(PA_USB) && gettime() < deadline) {
        ui_draw(true);
        sleep(1);
    }
    usb_check_timer = gettime() + secs_to_ticks(USB_POLL_SECONDS);
    sd_check_timer = gettime() + secs_to_ticks(2);
}

/*
    Returns a copy of path up to the last '/' character,
    If path does not contain '/', returns "".
    Returns a pointer to internal static storage space that will be overwritten by subsequent calls.
    This function is not thread-safe.
*/
char *dirname(char *path) {
    static char result[MAXPATHLEN];
    strncpy(result, path, MAXPATHLEN - 1);
    result[MAXPATHLEN - 1] = '\0';
    s32 i;
    for (i = strlen(result) - 1; i >= 0; i--) {
        if (result[i] == '/') {
            result[i] = '\0';
            return result;
        }
    }
    return "";
}

/*
    Returns a pointer into path, starting after the right-most '/' character.
    If path does not contain '/', returns path.
*/
char *basename(char *path) {
    s32 i;
    for (i = strlen(path) - 1; i >= 0; i--) {
        if (path[i] == '/') {
            return path + i + 1;
        }
    }
    return path;
}
