// Copyright 2010 Joseph Jordan <joe.ftpii@psychlaw.com.au>
// This code is licensed to you under the terms of the GNU GPL, version 2;
// see file COPYING or http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt
// Modified 2026 for ftpii BR: DVD, NTFS, NAND-image and SD Gecko devices removed; globals made extern.
#ifndef _FS_H_
#define _FS_H_

#include <gctypes.h>
#include <ogc/disc_io.h>

typedef struct {
    const char *name;
    const char *alias;
    const char *mount_point;
    const char *prefix;
    bool inserted;
    const DISC_INTERFACE *disc;
} VIRTUAL_PARTITION;

extern VIRTUAL_PARTITION VIRTUAL_PARTITIONS[];
extern const u32 MAX_VIRTUAL_PARTITIONS;
extern VIRTUAL_PARTITION *PA_SD;
extern VIRTUAL_PARTITION *PA_USB;
extern VIRTUAL_PARTITION *PA_ISFS;
extern VIRTUAL_PARTITION *PA_OTP;
extern VIRTUAL_PARTITION *PA_SEEPROM;

void initialise_fs();

bool mounted(VIRTUAL_PARTITION *partition);

bool mount(VIRTUAL_PARTITION *partition);

bool unmount(VIRTUAL_PARTITION *partition);

bool mount_virtual(const char *dir);

bool unmount_virtual(const char *dir);

void check_removable_devices(u64 now);

void remount_storage();

char *dirname(char *path);

char *basename(char *path);

#endif /* _FS_H_ */
