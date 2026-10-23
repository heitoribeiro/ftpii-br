"""wii_ftp.py - acesso ao Wii pelo ftpii BR / ftpii, numa unica conexao.

Uso:
  python wii_ftp.py info                      mostra o diagnostico (SITE INFO)
  python wii_ftp.py ls /usb/wbfs              lista uma pasta
  python wii_ftp.py get /sd/arquivo destino   baixa um arquivo
  python wii_ftp.py put origem /sd/pasta/     envia um arquivo (ou pasta inteira)
  python wii_ftp.py mirror /isfs/... destino  baixa uma pasta inteira (recursivo)

O Wii e encontrado sozinho: primeiro no ultimo IP usado, depois procurando na rede
um servidor FTP que se apresente como "ftpii". Senha: variavel WII_FTP_PASS ou --senha
(o que vem depois de ftpiibr_ no nome da pasta: apps/ftpiibr_minhasenha -> minhasenha).
Caminhos no Wii: /sd, /usb (HD), /isfs (memoria interna, so leitura), /otp, /seeprom.
"""
import ftplib, ipaddress, json, os, socket, sys, time
from concurrent.futures import ThreadPoolExecutor

STATE = os.path.join(os.path.expanduser('~'), '.wii_ftp.json')
BAD_CHARS = '<>:"\\|?*'  # nao permitidos em nomes de arquivo do Windows


def load_state():
    try:
        return json.load(open(STATE, encoding='utf-8'))
    except Exception:
        return {}


def save_state(state):
    json.dump(state, open(STATE, 'w', encoding='utf-8'))


def banner(ip, timeout=1.5):
    try:
        with socket.create_connection((ip, 21), timeout=timeout) as s:
            return s.recv(128).decode(errors='ignore')
    except Exception:
        return ''


def local_networks():
    nets = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith('127.'):
                nets.add(ipaddress.ip_network(ip + '/24', strict=False))
    except Exception:
        pass
    return nets or {ipaddress.ip_network('192.168.0.0/24')}


def scan_for_wii():
    state = load_state()
    print('Procurando o Wii na rede...', file=sys.stderr)
    hosts = [str(h) for net in local_networks() for h in net.hosts()]
    with ThreadPoolExecutor(64) as pool:
        for ip, b in zip(hosts, pool.map(banner, hosts)):
            if 'ftpii' in b:
                state['ip'] = ip
                save_state(state)
                return ip
    sys.exit('Wii nao encontrado. Abra o ftpii BR no Homebrew Channel e tente de novo.')


def try_login(ip, password):
    """The Wii accepts very few connections, so the real session doubles as the probe."""
    for _ in range(3):
        try:
            f = ftplib.FTP()
            f.connect(ip, 21, timeout=20)
            if 'ftpii' not in f.getwelcome():
                f.close()
                return None
            f.login('anonymous', password)
            return f
        except ftplib.error_temp:  # 421: o Wii esta com o maximo de conexoes; espere um pouco
            time.sleep(5)
        except OSError:
            return None
    return None


def connect(password):
    last = load_state().get('ip')
    f = try_login(last, password) if last else None
    if not f:
        ip = scan_for_wii()
        f = try_login(ip, password)
    if not f:
        sys.exit('Nao foi possivel conectar ao Wii. Abra o ftpii BR no Homebrew Channel.')
    return f


def listing(f, path):
    lines = []
    f.retrlines(f'LIST {path}', lines.append)
    out = []
    for ln in lines:
        p = ln.split(None, 8)
        if len(p) == 9 and p[8] not in ('.', '..'):
            out.append((p[8], ln.startswith('d'), int(p[4])))
    return out


def safe_name(name):
    return ''.join('_' if c in BAD_CHARS else c for c in name)


def mirror(f, remote, local):
    os.makedirs(local, exist_ok=True)
    n = 0
    for name, is_dir, size in listing(f, remote):
        r, l = f'{remote}/{name}', os.path.join(local, safe_name(name))
        if is_dir:
            n += mirror(f, r, l)
        elif not (os.path.exists(l) and os.path.getsize(l) == size):
            with open(l, 'wb') as fh:
                f.retrbinary(f'RETR {r}', fh.write)
            n += 1
    return n


def retrying(action):
    """A sleeping USB hard drive can answer 550 'No such device' for a moment."""
    for attempt in range(5):
        try:
            return action()
        except ftplib.error_perm as e:
            if 'No such device' not in str(e) or attempt == 4:
                raise
            time.sleep(3)


def put(f, src, dest):
    if os.path.isdir(src):
        target = dest.rstrip('/') + '/' + os.path.basename(os.path.abspath(src))
        existing = retrying(lambda: [n for n, d, _ in listing(f, dest.rstrip('/') or '/') if d])
        if os.path.basename(target) not in existing:
            retrying(lambda: f.mkd(target))
        for entry in sorted(os.listdir(src)):
            put(f, os.path.join(src, entry), target + '/')
        return
    target = dest + os.path.basename(src) if dest.endswith('/') else dest

    def send():
        with open(src, 'rb') as fh:
            f.storbinary(f'STOR {target}', fh)
    retrying(send)
    print('enviado', target)


def undo_msys_conversion(arg):
    """Git Bash turns '/usb/x' into 'C:/Program Files/Git/usb/x' for Windows programs."""
    for prefix in ('/sd', '/usb', '/isfs', '/otp', '/seeprom'):
        marker = '/Git' + prefix
        if marker in arg and arg[1:3] == ':/':
            return arg[arg.index(marker) + 4:]
    return arg


def main():
    args = [undo_msys_conversion(a) for a in sys.argv[1:]]
    password = os.environ.get('WII_FTP_PASS', '')
    if '--senha' in args:
        i = args.index('--senha')
        password = args[i + 1]
        del args[i:i + 2]
    if not args:
        sys.exit(__doc__)
    cmd, rest = args[0], args[1:]
    f = connect(password)
    try:
        if cmd == 'info':
            print(f.sendcmd('SITE INFO'))
        elif cmd == 'ls':
            for name, is_dir, size in listing(f, rest[0] if rest else '/'):
                print(f'{"<DIR>" if is_dir else size:>12}  {name}')
        elif cmd == 'get':
            with open(rest[1], 'wb') as fh:
                f.retrbinary(f'RETR {rest[0]}', fh.write)
        elif cmd == 'put':
            put(f, rest[0], rest[1])
        elif cmd == 'mirror':
            print(mirror(f, rest[0].rstrip('/'), rest[1]), 'arquivos baixados')
        else:
            sys.exit(__doc__)
    finally:
        try:
            f.quit()
        except Exception:
            f.close()


if __name__ == '__main__':
    main()
