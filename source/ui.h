// ftpii BR: bilingual (PT/EN) status screen (added 2026).
// This code is licensed to you under the terms of the GNU GPL, version 2.
#ifndef _UI_H_
#define _UI_H_

#include <gctypes.h>

void ui_init();
void ui_set_ip(u32 ip);
void ui_set_password(const char *password);
void ui_set_clients(u32 count, u32 max);
void ui_transfer_begin(bool upload, const char *name);
void ui_transfer_end();
void ui_count_bytes(u32 bytes);
void ui_draw(bool force);

// Log line (printf-style). Long lines are truncated to the screen width.
int ui_printf(const char *fmt, ...) __attribute__((format(printf, 1, 2)));

#ifndef UI_IMPLEMENTATION
#define printf ui_printf
#endif

#endif /* _UI_H_ */
