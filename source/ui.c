// ftpii BR: bilingual (PT/EN) status screen (added 2026).
// Replaces the scrolling console of ftpii with a fixed dashboard plus a short log.
// This code is licensed to you under the terms of the GNU GPL, version 2.
#define UI_IMPLEMENTATION
#include <gccore.h>
#include <network.h>
#include <ogc/lwp_watchdog.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#include "fs.h"
#include "ui.h"
#include "version.h"

#define LOG_LINES 32
#define LINE_MAX 96

static char log_lines[LOG_LINES][LINE_MAX];
static u32 log_head = 0, log_count = 0;
static char partial[LINE_MAX];

static u32 ip_addr = 0;
static char password_text[48] = "";
static u32 clients = 0, clients_max = 0;

static bool transferring = false, transfer_upload = false;
static char transfer_name[48] = "";
static u32 window_bytes = 0;
static u64 window_start = 0;
static u32 speed_kbs = 0;
static u64 total_bytes = 0;

static bool dirty = true;
static u64 last_draw = 0;
static int cols = 74, rows = 25;

void ui_init() {
    CON_GetMetrics(&cols, &rows);
    if (cols > LINE_MAX - 1) cols = LINE_MAX - 1;
    if (cols < 40) cols = 40;
    printf("\x1b[2J");
    window_start = gettime();
}

static void push_line(const char *text) {
    strncpy(log_lines[log_head], text, LINE_MAX - 1);
    log_lines[log_head][LINE_MAX - 1] = '\0';
    log_head = (log_head + 1) % LOG_LINES;
    if (log_count < LOG_LINES) log_count++;
    dirty = true;
}

int ui_printf(const char *fmt, ...) {
    char buf[256];
    va_list ap;
    va_start(ap, fmt);
    int n = vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);
    char *p = buf;
    while (*p) {
        char *nl = strchr(p, '\n');
        size_t len = nl ? (size_t)(nl - p) : strlen(p);
        size_t used = strlen(partial);
        if (used + len >= LINE_MAX) len = LINE_MAX - 1 - used;
        strncat(partial, p, len);
        if (!nl) break;
        if (partial[0]) push_line(partial);
        partial[0] = '\0';
        p = nl + 1;
    }
    return n;
}

void ui_set_ip(u32 ip) { ip_addr = ip; dirty = true; }

void ui_set_password(const char *password) {
    snprintf(password_text, sizeof(password_text), "%s", password && *password ? password : "(sem senha / no password)");
    dirty = true;
}

void ui_set_clients(u32 count, u32 max) { clients = count; clients_max = max; dirty = true; }

void ui_transfer_begin(bool upload, const char *name) {
    transferring = true;
    transfer_upload = upload;
    const char *base = strrchr(name, '/');
    snprintf(transfer_name, sizeof(transfer_name), "%s", base ? base + 1 : name);
    dirty = true;
}

void ui_transfer_end() { transferring = false; dirty = true; }

void ui_count_bytes(u32 bytes) {
    window_bytes += bytes;
    total_bytes += bytes;
}

static void line(int *row, const char *fmt, ...) {
    char buf[LINE_MAX * 2];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);
    buf[cols - 1] = '\0';
    printf("%-*s\n", cols - 1, buf);
    (*row)++;
}

static const char *device_state(VIRTUAL_PARTITION *p) {
    return mounted(p) ? "OK" : "--";
}

void ui_draw(bool force) {
    u64 now = gettime();
    u64 elapsed = diff_msec(window_start, now);
    if (elapsed >= 1000) {
        speed_kbs = (u32)((u64)window_bytes * 1000 / elapsed / 1024);
        window_bytes = 0;
        window_start = now;
        dirty = true;
    }
    if (!force && (!dirty || diff_msec(last_draw, now) < 500)) return;
    last_draw = now;
    dirty = false;

    int row = 0;
    char sep[LINE_MAX];
    memset(sep, '-', cols - 1);
    sep[cols - 1] = '\0';
    struct in_addr addr;
    addr.s_addr = ip_addr;

    printf("\x1b[0;0H");
    line(&row, "%s - Servidor FTP / FTP server", FTPII_BR_NAME);
    line(&row, "%s", sep);
    if (ip_addr) line(&row, "Endereco / Address : ftp://%s   (porta / port 21)", inet_ntoa(addr));
    else line(&row, "Endereco / Address : aguardando rede... / waiting for network...");
    line(&row, "Senha / Password   : %s", password_text);
    line(&row, "Dispositivos / Devices: SD %s   USB %s   NAND %s (so leitura / read-only)",
         device_state(PA_SD), device_state(PA_USB), device_state(PA_ISFS));
    line(&row, "Conexoes / Connections: %u de / of %u", clients, clients_max);
    if (transferring)
        line(&row, "%s: %s  %u KB/s", transfer_upload ? "Recebendo / Receiving" : "Enviando / Sending", transfer_name, speed_kbs);
    else
        line(&row, "Parado / Idle  -  total: %llu MB", total_bytes / (1024 * 1024));
    line(&row, "%s", sep);

    int footer = 2;
    int space = rows - row - footer - 1;
    if (space < 1) space = 1;
    int shown = (int)log_count < space ? (int)log_count : space;
    int i;
    for (i = 0; i < space; i++) {
        if (i < shown) {
            int idx = (log_head + LOG_LINES - shown + i) % LOG_LINES;
            line(&row, " %s", log_lines[idx]);
        } else {
            line(&row, "");
        }
    }
    line(&row, "%s", sep);
    line(&row, "A ou HOME: sair / exit    B: remontar SD e USB / remount SD and USB");
}
