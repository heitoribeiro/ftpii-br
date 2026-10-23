// ftpii BR: compatibility layer for current devkitPPC/libogc (added 2026).
// This code is licensed to you under the terms of the GNU GPL, version 2.
#include <errno.h>
#include <malloc.h>
#include <reent.h>
#include <string.h>

#include "compat.h"

static const devoptab_t *dir_devoptab(DIR_ITER *dir) {
    if (!dir || dir->device < 0 || dir->device >= STD_MAX) return NULL;
    return devoptab_list[dir->device];
}

/*
    libsysbase stores the device's private data in the reent structure before every devoptab call,
    and current drivers depend on it (the FatFs-based libfat looks its volume up through it).
    Calling the devoptab directly without doing the same crashes inside f_opendir.
*/
static struct _reent *reent_for(const devoptab_t *dt) {
    struct _reent *r = _REENT;
    r->_errno = 0;
    r->deviceData = dt->deviceData;
    return r;
}

DIR_ITER *ftpii_diropen(const char *path) {
    int device = FindDevice(path);
    if (device < 0) {
        errno = ENODEV;
        return NULL;
    }
    const devoptab_t *dt = devoptab_list[device];
    if (!dt || !dt->diropen_r) {
        errno = ENOSYS;
        return NULL;
    }
    DIR_ITER *dir = malloc(sizeof(DIR_ITER));
    if (!dir) {
        errno = ENOMEM;
        return NULL;
    }
    dir->device = device;
    dir->dirStruct = malloc(dt->dirStateSize ? dt->dirStateSize : 4);
    if (!dir->dirStruct) {
        free(dir);
        errno = ENOMEM;
        return NULL;
    }
    struct _reent *r = reent_for(dt);
    if (!dt->diropen_r(r, dir, path)) {
        errno = r->_errno ? r->_errno : ENOENT;
        free(dir->dirStruct);
        free(dir);
        return NULL;
    }
    return dir;
}

int ftpii_dirnext(DIR_ITER *dir, char *filename, struct stat *st) {
    const devoptab_t *dt = dir_devoptab(dir);
    if (!dt || !dt->dirnext_r) {
        errno = EBADF;
        return -1;
    }
    struct _reent *r = reent_for(dt);
    memset(st, 0, sizeof(*st));
    int ret = dt->dirnext_r(r, dir, filename, st);
    if (ret) errno = r->_errno;
    return ret;
}

int ftpii_dirclose(DIR_ITER *dir) {
    const devoptab_t *dt = dir_devoptab(dir);
    int ret = -1;
    if (dt && dt->dirclose_r) ret = dt->dirclose_r(reent_for(dt), dir);
    if (dir) {
        free(dir->dirStruct);
        free(dir);
    }
    return ret;
}
