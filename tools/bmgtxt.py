"""Read / write the message lines of wbmgt text files (BMG decoded by Wiimms SZS Tools).

Every non-message line (header, comments, "ID /" placeholders) is kept verbatim; only the
text after "=" (plus its "+" continuation lines) is replaced.
"""
import re, json, sys

LINE = re.compile(r'^(\s+[0-9A-Za-z]+(?:@[0-9A-Fa-f]+)?\s*(?:\[[^\]]*\]\s*)?)=( ?)(.*)$')
CONT = re.compile(r'^\s*\+ ?(.*)$')
ID = re.compile(r'^\s+([0-9A-Za-z]+(?:@[0-9A-Fa-f]+)?)')


def parse(path):
    """Return (messages, layout). layout is a list of ('raw', line) / ('msg', head, space, id)."""
    msgs, layout, cur = {}, [], None
    for raw in open(path, encoding='utf-8').read().splitlines():
        m = LINE.match(raw)
        if m:
            cur = ID.match(m.group(1)).group(1)
            msgs[cur] = m.group(3)
            layout.append(('msg', m.group(1), m.group(2), cur))
            continue
        c = CONT.match(raw)
        if cur and c:
            msgs[cur] += c.group(1)
            continue
        cur = None
        layout.append(('raw', raw))
    return msgs, layout


def generate(dst_path, msgs, layout):
    out = []
    for item in layout:
        if item[0] == 'raw':
            out.append(item[1])
            continue
        _, head, space, mid = item
        parts = msgs[mid].split('\\n')
        segs = [p + '\\n' for p in parts[:-1]] + ([parts[-1]] if parts[-1] else [])
        first = segs[0] if segs else ''
        out.append(f'{head}={space if (space or first) else ""}{first}')
        out += [f'\t+ {s}' for s in segs[1:]]
    open(dst_path, 'w', encoding='utf-8', newline='\n').write('\n'.join(out) + '\n')


USAGE = """Translate game text through wbmgt (Wiimms SZS Tools):
  wbmgt decode Common.bmg -o Common.txt            # BMG -> text
  python bmgtxt.py export Common.txt msgs.json     # messages as {id: text} for translating
  python bmgtxt.py import Common.txt msgs.json Common_new.txt
  wbmgt encode Common_new.txt -o Common.bmg        # text -> BMG
Keep control codes such as \\z{...} and \\n untouched, and check that every character exists in the
game's font before packing the files back into the game."""

if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == 'export':
        msgs, _ = parse(sys.argv[2])
        json.dump(msgs, open(sys.argv[3], 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
        print(len(msgs), 'messages')
    elif len(sys.argv) == 5 and sys.argv[1] == 'import':
        msgs, layout = parse(sys.argv[2])
        new = json.load(open(sys.argv[3], encoding='utf-8'))
        missing = [k for k in msgs if k not in new]
        msgs.update({k: v for k, v in new.items() if k in msgs})
        generate(sys.argv[4], msgs, layout)
        print(len(msgs) - len(missing), 'translated,', len(missing), 'kept as they were')
    else:
        sys.exit(USAGE)
