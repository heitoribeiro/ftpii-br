"""See what Mario Kart Wii does on the network: the Wii uses this PC as its DNS server.

Every DNS query is logged and forwarded to the router. Names of the login (NAS), friend server (gpcm/gpsp)
and connection test are answered with this PC's address; the TCP connections that follow are relayed
unchanged to the real server while their traffic is logged (HTTP text, TLS record types, who closes, when).
Nothing is modified, so the console talks to the real servers exactly as it would directly.
"""
import datetime, os, re, select, socket, struct, sys, threading

if len(sys.argv) < 3:
    sys.exit("usage: python wii_net_spy.py <this PC's LAN IP> <router IP>\n"
             "Then set the Wii's primary DNS to this PC's IP, and set it back to automatic afterwards.")
PC_IP = sys.argv[1]
UPSTREAM = (sys.argv[2], 53)
LOG = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wii_net_spy.log'),
           'a', encoding='utf-8', buffering=1)
INTERCEPT = re.compile(r'(^|\.)(naswii|nas|main\.nas|ca\.nas|conntest)\.|^gpcm\.|^gpsp\.|\.available\.gs\.')
# GameSpy's own "available" servers are gone; Nintendo-domain availability checks go to Wiimmfi's instead
DEAD_AVAILABLE = '95.217.77.151'
real = {}            # name -> real IPv4
last_nas_https = [None]
lock = threading.Lock()


def log(*a):
    line = datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3] + ' ' + ' '.join(str(x) for x in a)
    with lock:
        print(line, flush=True)
        LOG.write(line + '\n')


def qname(pkt):
    i, parts = 12, []
    while pkt[i]:
        parts.append(pkt[i + 1:i + 1 + pkt[i]].decode(errors='replace'))
        i += pkt[i] + 1
    qtype = struct.unpack('>H', pkt[i + 1:i + 3])[0]
    return '.'.join(parts).lower(), qtype, i + 5


def dns_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(('0.0.0.0', 53))
    log('DNS ouvindo em', PC_IP, ':53')
    while True:
        pkt, addr = s.recvfrom(2048)
        try:
            name, qtype, qend = qname(pkt)
        except Exception:
            continue
        if qtype == 1 and INTERCEPT.search(name):
            try:
                ip = socket.gethostbyname(name)
            except OSError:
                ip = None
            if '.available.gs.nintendowifi.net' in name:
                ip = DEAD_AVAILABLE
            if ip:
                real.pop(name, None)  # re-insert so "most recent" lookups see it last
                real[name] = ip
                if 'nas' in name:
                    last_nas_https[0] = name
                resp = (pkt[:2] + b'\x81\x80' + b'\x00\x01\x00\x01\x00\x00\x00\x00' + pkt[12:qend]
                        + b'\xc0\x0c\x00\x01\x00\x01\x00\x00\x00\x1e\x00\x04' + socket.inet_aton(PC_IP))
                s.sendto(resp, addr)
                log(f'DNS {addr[0]} {name} -> PC (real {ip}) [interceptado]')
                continue
        u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        u.settimeout(4)
        try:
            u.sendto(pkt, UPSTREAM)
            resp, _ = u.recvfrom(4096)
            s.sendto(resp, addr)
            ips = re.findall(rb'\xc0.\x00\x01\x00\x01.{6}(.{4})', resp, re.S)
            log(f'DNS {addr[0]} {name} type={qtype} -> {[socket.inet_ntoa(x) for x in ips]}')
        except Exception as e:
            log(f'DNS {addr[0]} {name} type={qtype} SEM RESPOSTA do roteador ({e})')


TLS_TYPES = {20: 'ChangeCipherSpec', 21: 'Alert', 22: 'Handshake', 23: 'AppData'}
HS_TYPES = {1: 'ClientHello', 2: 'ServerHello', 11: 'Certificate', 12: 'ServerKeyExchange', 13: 'CertRequest',
            14: 'ServerHelloDone', 15: 'CertVerify', 16: 'ClientKeyExchange', 20: 'Finished'}


def describe(data, port):
    if port == 443 and data[:1] and data[0] in TLS_TYPES:
        out, i = [], 0
        while i + 5 <= len(data):
            t, ver, ln = data[i], data[i + 1:i + 3].hex(), struct.unpack('>H', data[i + 3:i + 5])[0]
            d = TLS_TYPES.get(t, t)
            if t == 22 and i + 5 < len(data) and ln:
                d += '/' + HS_TYPES.get(data[i + 5], str(data[i + 5]))
            if t == 21 and ln >= 2:
                d += f'(level={data[i + 5]} desc={data[i + 6]})'
            out.append(f'{d} v{ver} {ln}B')
            i += 5 + ln
        return 'TLS ' + ', '.join(out)
    txt = data[:600].decode('latin-1')
    return repr(txt)


def relay(port):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('0.0.0.0', port))
    srv.listen(8)
    log('TCP relay ouvindo na porta', port)
    while True:
        c, addr = srv.accept()
        threading.Thread(target=handle, args=(c, addr, port), daemon=True).start()


def target_for(port, first):
    if port == 80:
        # Prefer the Host header, but fall back to the names this DNS intercepted: the Wii's header
        # did not resolve as-is during the first test (conntest), which broke the connection test.
        m = re.search(rb'\r\nHost: *([^\r\n:]+)', first, re.I)
        host = m.group(1).decode(errors='replace').strip().lower() if m else None
        log('  Host header:', repr(m.group(1)) if m else None)
        if host in real:
            return host, real[host]
        for name in reversed(list(real)):
            if host and (host in name or name in host):
                return name, real[name]
        for name in reversed(list(real)):
            if not name.startswith(('gpcm', 'gpsp')):
                return name, real[name]
        return host, None
    if port == 443:
        host = last_nas_https[0]
        return host, real.get(host)
    # most recently resolved one: Wiimmfi and WiiLink tests run back to back in the same session
    host = next((n for n in reversed(list(real)) if n.startswith('gpcm' if port == 29900 else 'gpsp')), None)
    return host, real.get(host)


def handle(c, addr, port):
    tag = f'[{addr[0]}:{addr[1]}->{port}]'
    try:
        c.settimeout(None)
        first = b''
        if port in (80, 443):
            r, _, _ = select.select([c], [], [], 20)
            first = c.recv(65536) if r else b''
        host, ip = target_for(port, first)
        log(tag, 'conexao do Wii para', host, ip)
        if first:
            log(tag, 'WII ->', describe(first, port))
        if not ip:
            log(tag, 'sem destino, fechando')
            c.close()
            return
        s = socket.create_connection((ip, port), 15)
        if first:
            s.sendall(first)
        socks = {c: ('WII ->', s), s: ('SERV ->', c)}
        while True:
            r, _, _ = select.select(list(socks), [], [], 120)
            if not r:
                log(tag, 'nenhum dado por 120 s (parado)')
                break
            for src in r:
                data = src.recv(65536)
                who, dst = socks[src]
                if not data:
                    log(tag, who, 'FECHOU a conexao')
                    raise StopIteration
                log(tag, who, describe(data, port))
                dst.sendall(data)
    except StopIteration:
        pass
    except Exception as e:
        log(tag, 'erro', type(e).__name__, e)
    finally:
        for x in (c,):
            try:
                x.close()
            except Exception:
                pass


def udp_relay(port):
    """Availability check (UDP 27900): relay each Wii packet to the real server and the replies back."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(('0.0.0.0', port))
    log('UDP relay ouvindo na porta', port)
    upstreams = {}  # wii addr -> (socket to server, server ip)

    def back(wii, up):
        while True:
            try:
                data, src = up.recvfrom(4096)
            except OSError:
                return
            log(f'[UDP {wii[0]}:{wii[1]}->{port}] SERV {src[0]} -> {data[:64].hex()} ({len(data)}B)')
            s.sendto(data, wii)

    while True:
        data, wii = s.recvfrom(4096)
        names = [n for n in real if '.available.gs.' in n]
        game = data[5:].split(b'\0')[0].decode(errors='replace') if data[:1] == b'\x09' else ''
        host = next((n for n in reversed(names) if game and n.startswith(game + '.')), names[-1] if names else None)
        ip = real.get(host)
        log(f'[UDP {wii[0]}:{wii[1]}->{port}] WII -> {data[:64].hex()} ({len(data)}B) jogo={game!r} destino={host} {ip}')
        if not ip:
            continue
        if wii not in upstreams:
            up = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            up.bind(('0.0.0.0', 0))  # Windows refuses recvfrom on an unbound UDP socket
            upstreams[wii] = up
            threading.Thread(target=back, args=(wii, up), daemon=True).start()
        upstreams[wii].sendto(data, (ip, port))


threading.Thread(target=dns_server, daemon=True).start()
threading.Thread(target=udp_relay, args=(27900,), daemon=True).start()
for p in (80, 443, 29900, 29901):
    threading.Thread(target=relay, args=(p,), daemon=True).start()
threading.Event().wait()
