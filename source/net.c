// Copyright 2010 Joseph Jordan <joe.ftpii@psychlaw.com.au>
// This code is licensed to you under the terms of the GNU GPL, version 2;
// see file COPYING or http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt
// Modified 2026 for ftpii BR:
//  - static transfer buffers (the 32 KB stack buffers were close to the thread stack size),
//  - up to four buffers moved per main-loop pass instead of one, so the loop overhead
//    (controller polling, device checks, redraws) weighs less on throughput,
//  - larger listen backlog, byte counting for the on-screen speed, bilingual messages.
#include <errno.h>
#include <gccore.h>
#include <network.h>
#include <stdio.h>
#include <string.h>
#include <sys/fcntl.h>

#include "net.h"
#include "reset.h"
#include "ui.h"

#define MAX_NET_BUFFER_SIZE 32768
#define MIN_NET_BUFFER_SIZE 4096
#define FILE_BUFFER_SIZE 65536
#define CHUNKS_PER_CALL 4
#define LISTEN_BACKLOG 8

static u32 NET_BUFFER_SIZE = MAX_NET_BUFFER_SIZE;
static char file_buffer[FILE_BUFFER_SIZE] __attribute__((aligned(32)));

void initialise_network() {
    printf("Iniciando a rede... / Waiting for network...\n");
    ui_set_ip(0);
    ui_draw(true);
    s32 result = -1;
    while (!check_reset_synchronous() && result < 0) {
        while (!check_reset_synchronous() && (result = net_init()) == -EAGAIN);
        if (result < 0) printf("net_init() falhou / failed: [%i] %s\n", result, strerror(-result));
    }
    if (result >= 0) {
        u32 ip = 0;
        do {
            ip = net_gethostip();
            if (!ip) printf("Sem IP ainda / no IP yet, retrying...\n");
        } while (!check_reset_synchronous() && !ip);
        if (ip) {
            struct in_addr addr;
            addr.s_addr = ip;
            printf("Rede pronta / Network ready: %s\n", inet_ntoa(addr));
            ui_set_ip(ip);
        }
    }
}

s32 set_blocking(s32 s, bool blocking) {
    s32 flags;
    flags = net_fcntl(s, F_GETFL, 0);
    if (flags >= 0) flags = net_fcntl(s, F_SETFL, blocking ? (flags&~4) : (flags|4));
    return flags;
}

s32 net_close_blocking(s32 s) {
    set_blocking(s, true);
    return net_close(s);
}

s32 create_server(u16 port) {
    s32 server = net_socket(AF_INET, SOCK_STREAM, IPPROTO_IP);
    if (server < 0) die("Error creating socket", -server);
    set_blocking(server, false);

    struct sockaddr_in bindAddress;
    memset(&bindAddress, 0, sizeof(bindAddress));
    bindAddress.sin_family = AF_INET;
    bindAddress.sin_port = htons(port);
    bindAddress.sin_addr.s_addr = htonl(INADDR_ANY);

    s32 ret;
    if ((ret = net_bind(server, (struct sockaddr *)&bindAddress, sizeof(bindAddress))) < 0) {
        net_close(server);
        printf("Erro no bind / bind error: [%i] %s\n", -ret, strerror(-ret));
        return ret;
    }
    if ((ret = net_listen(server, LISTEN_BACKLOG)) < 0) {
        net_close(server);
        printf("Erro no listen / listen error: [%i] %s\n", -ret, strerror(-ret));
        return ret;
    }

    return server;
}

typedef s32 (*transferrer_type)(s32 s, void *mem, s32 len);
static s32 transfer_exact(s32 s, char *buf, s32 length, transferrer_type transferrer) {
    s32 result = 0;
    s32 remaining = length;
    s32 bytes_transferred;
    set_blocking(s, true);
    while (remaining) {
        try_again_with_smaller_buffer:
        bytes_transferred = transferrer(s, buf, MIN(remaining, NET_BUFFER_SIZE));
        if (bytes_transferred > 0) {
            remaining -= bytes_transferred;
            buf += bytes_transferred;
        } else if (bytes_transferred < 0) {
            if (bytes_transferred == -EINVAL && NET_BUFFER_SIZE == MAX_NET_BUFFER_SIZE) {
                NET_BUFFER_SIZE = MIN_NET_BUFFER_SIZE;
                goto try_again_with_smaller_buffer;
            }
            result = bytes_transferred;
            break;
        } else {
            result = -ENODATA;
            break;
        }
    }
    set_blocking(s, false);
    return result;
}

s32 send_exact(s32 s, char *buf, s32 length) {
    return transfer_exact(s, buf, length, (transferrer_type)net_write);
}

/*
    Returns -EAGAIN while there is more to send, 0 when the file was sent completely,
    or a negative error.
*/
s32 send_from_file(s32 s, FILE *f) {
    u32 chunk;
    for (chunk = 0; chunk < CHUNKS_PER_CALL; chunk++) {
        s32 bytes_read = fread(file_buffer, 1, FILE_BUFFER_SIZE, f);
        if (bytes_read > 0) {
            s32 result = send_exact(s, file_buffer, bytes_read);
            if (result < 0) return result;
            ui_count_bytes(bytes_read);
        }
        if (bytes_read < FILE_BUFFER_SIZE) return -!feof(f);
    }
    return -EAGAIN;
}

/*
    Returns -EAGAIN while the connection is open but has no data right now,
    0 at end of file, or a negative error.
*/
s32 recv_to_file(s32 s, FILE *f) {
    u32 chunk;
    for (chunk = 0; chunk < CHUNKS_PER_CALL * 2; chunk++) {
        try_again_with_smaller_buffer:;
        s32 bytes_read = net_read(s, file_buffer, NET_BUFFER_SIZE);
        if (bytes_read < 0) {
            if (bytes_read == -EINVAL && NET_BUFFER_SIZE == MAX_NET_BUFFER_SIZE) {
                NET_BUFFER_SIZE = MIN_NET_BUFFER_SIZE;
                goto try_again_with_smaller_buffer;
            }
            return bytes_read;
        } else if (bytes_read == 0) {
            return 0;
        }

        s32 bytes_written = fwrite(file_buffer, 1, bytes_read, f);
        if (bytes_written < bytes_read) return -1;
        ui_count_bytes(bytes_read);
    }
    return -EAGAIN;
}
