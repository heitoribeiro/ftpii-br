// Copyright 2010 Joseph Jordan <joe.ftpii@psychlaw.com.au>
// This code is licensed to you under the terms of the GNU GPL, version 2;
// see file COPYING or http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt
// Modified 2026 for ftpii BR: the ISFS permission check is now located by searching IOS memory for
// its byte pattern, as runtimeiospatch does (USB Loader GX; Joseph Jordan, damysteryman,
// Christopher Bratusek, DarkMatterCore, megazig, FIX94 - GPLv2), instead of the fixed address used
// in 2010, which no longer matched. Only this one in-memory patch is applied (it is lost at power
// off); the DVD read-limit patch was dropped with DVD support. Nothing is written to the NAND.
#include <gccore.h>
#include <ogc/machine/processor.h>
#include <string.h>

#include "iospatch.h"

#define MEM_PROT 0xd8b420a

static bool have_ahbprot() {
    return read32(0xcd800064) == 0xffffffff;
}

static void disable_memory_protection() {
    write32(MEM_PROT, read32(MEM_PROT) & 0x0000FFFF);
}

// Thumb code of the ISFS permission check: "beq" (0xD0) becomes an unconditional branch (0xE0).
static const u8 isfs_permissions_old[] = { 0x42, 0x8B, 0xD0, 0x01, 0x25, 0x66 };
static const u8 isfs_permissions_new[] = { 0x42, 0x8B, 0xE0, 0x01, 0x25, 0x66 };

static u32 apply_patch(const u8 *old, u32 old_size, const u8 *patch, u32 patch_size) {
    u8 *ptr = (u8 *)*((u32 *)0x80003134);   // start of the IOS area in MEM2
    u8 *end = (u8 *)0x94000000;
    u32 found = 0;
    while (ptr < end - old_size) {
        if (!memcmp(ptr, old, old_size)) {
            memcpy(ptr, patch, patch_size);
            DCFlushRange((u8 *)(((u32)ptr) >> 5 << 5), (patch_size >> 5 << 5) + 64);
            ICInvalidateRange((u8 *)(((u32)ptr) >> 5 << 5), (patch_size >> 5 << 5) + 64);
            found++;
        }
        ptr++;
    }
    return found;
}

u32 IOSPATCH_Apply() {
    if (!have_ahbprot()) return 0;
    disable_memory_protection();
    return apply_patch(isfs_permissions_old, sizeof(isfs_permissions_old), isfs_permissions_new, sizeof(isfs_permissions_new));
}
