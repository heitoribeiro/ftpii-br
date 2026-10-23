// ftpii BR: start-up results reported by SITE INFO (added 2026).
// This code is licensed to you under the terms of the GNU GPL, version 2.
#ifndef _DIAG_H_
#define _DIAG_H_

#include <gctypes.h>

typedef struct {
    s32 ios_version;
    s32 ios_revision;
    bool ahbprot;
    u32 patches_applied;
    s32 es_identify;
    s32 isfs_initialize;
    bool isfs_mounted;
    u32 isfs_entries;
    u32 isfs_unreadable_dirs;
} diag_t;

extern diag_t diag;

#endif /* _DIAG_H_ */
