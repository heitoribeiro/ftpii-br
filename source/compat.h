// ftpii BR: compatibility layer for current devkitPPC/libogc (added 2026).
// The DIR_ITER based diropen()/dirnext()/dirclose() API was removed from libsysbase;
// these wrappers call the devoptab directly, which still exposes it.
// This code is licensed to you under the terms of the GNU GPL, version 2.
#ifndef _COMPAT_H_
#define _COMPAT_H_

#include <sys/iosupport.h>
#include <sys/param.h>
#include <sys/stat.h>

#ifndef MAXPATHLEN
#define MAXPATHLEN 1024
#endif

DIR_ITER *ftpii_diropen(const char *path);
int ftpii_dirnext(DIR_ITER *dir, char *filename, struct stat *st);
int ftpii_dirclose(DIR_ITER *dir);

#define diropen ftpii_diropen
#define dirnext ftpii_dirnext
#define dirclose ftpii_dirclose

#endif /* _COMPAT_H_ */
