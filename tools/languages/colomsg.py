"""Pokémon Colosseum message groups (.msg members and the groups inside common_rel), and the
text form a language pack's text.txt uses for them.

A group: 0x10-byte header (u16 group id, u8, u8 font id, u16 count, 2-byte region tag, two list
pointers), then count x (u32 key, u32 offset from the group), then the strings: UTF-16BE ending
at 0x0000, with control codes 0xFFFF xx and, for some, argument bytes.

Text form (text.txt), one string on one line:
  \\n             line break (control 0x00)
  {clear}        control 0x02 (end of a box)
  {page}         control 0x03 (next box)
  {xx}           control xx (two hex digits), no arguments
  {xx:hhhh}      control xx and its argument bytes in hex
  \\{ \\} \\\\       a literal brace or backslash
  \\uXXXX \\xHH    a UTF-16 unit or a lone byte the forms above can't write (no disc line needs one)
Every other character is itself (UTF-8 in the file, one UTF-16 unit in the game).
"""
import re
import struct

# argument bytes after a control code (the others take none); checked by round trips over both discs
ARGS = {0x07: 1, 0x09: 1, 0x38: 1, 0x53: 1, 0x5B: 1, 0x5C: 1}
NAMES = {0x02: "clear", 0x03: "page"}
CODES = {v: k for k, v in NAMES.items()}


def parse_group(b, o=0):
    """(header dict, [(key, raw string bytes up to and without the terminator)]) of the group at b[o:]."""
    gid, _, font, count = struct.unpack_from(">HBBH", b, o)
    tag = b[o + 6:o + 8]
    out = []
    for i in range(count):
        key, off = struct.unpack_from(">II", b, o + 0x10 + 8 * i)
        out.append((key, raw_string(b, o + off)))
    return dict(id=gid, font=font, tag=tag, count=count), out


def raw_string(b, at):
    """The string's bytes from at to its 0x0000 terminator, stepping over control codes' arguments."""
    i = at
    while i + 1 < len(b):
        c = (b[i] << 8) | b[i + 1]
        if c == 0:
            return b[at:i]
        if c == 0xFFFF:
            i += 3 + ARGS.get(b[i + 2], 0)
        else:
            i += 2
    return b[at:i]


def decode(raw):
    out = []
    i = 0
    while i < len(raw):
        if i + 1 >= len(raw):   # a stray last byte (a code's argument that ran over): kept as it is
            out.append("\\x%02x" % raw[i])
            i += 1
            continue
        c = (raw[i] << 8) | raw[i + 1]
        if c == 0xFFFF:
            code = raw[i + 2] if i + 2 < len(raw) else 0
            n = ARGS.get(code, 0)
            args = raw[i + 3:i + 3 + n]
            i += 3 + n
            if code == 0x00:
                out.append("\\n")
            elif code in NAMES and not args:
                out.append("{%s}" % NAMES[code])
            else:
                out.append("{%02x%s}" % (code, (":" + args.hex()) if args else ""))
            continue
        i += 2
        ch = chr(c)
        if ch == "\\":
            out.append("\\\\")
        elif ch in "{}":
            out.append("\\" + ch)
        elif c < 0x20 or 0xD800 <= c < 0xE000:
            out.append("\\u%04x" % c)
        else:
            out.append(ch)
    return "".join(out)


TOKEN = re.compile(r"\\n|\\\\|\\\{|\\\}|\\u([0-9a-fA-F]{4})|\\x([0-9a-fA-F]{2})|\{([^{}]*)\}|(.)", re.S)


def encode(text):
    out = bytearray()
    for m in TOKEN.finditer(text):
        s = m.group(0)
        if s == "\\n":
            out += b"\xff\xff\x00"
        elif s == "\\\\":
            out += b"\x00\\"
        elif s in ("\\{", "\\}"):
            out += b"\x00" + s[1].encode()
        elif m.group(1):
            out += struct.pack(">H", int(m.group(1), 16))
        elif m.group(2):
            out.append(int(m.group(2), 16))
        elif m.group(3) is not None:
            body = m.group(3)
            if body in CODES:
                out += bytes([0xFF, 0xFF, CODES[body]])
            else:
                code, _, args = body.partition(":")
                out += bytes([0xFF, 0xFF, int(code, 16)]) + bytes.fromhex(args)
        else:
            c = ord(m.group(4))
            if c > 0xFFFF:
                raise ValueError("character outside the game's range: %r" % m.group(4))
            out += struct.pack(">H", c)
    return bytes(out)


def build_group(entries, font, tag=b"US"):
    """A group from [(key, raw bytes)], keys sorted (the game binary-searches them)."""
    entries = sorted(entries)
    head = struct.pack(">HBBH2sII", 0, 0, font, len(entries), tag, 0, 0)
    table = bytearray()
    body = bytearray()
    base = 0x10 + 8 * len(entries)
    for key, raw in entries:
        table += struct.pack(">II", key, base + len(body))
        body += raw + b"\0\0"
    return head + bytes(table) + bytes(body)


def find_groups(b, tags):
    """Offsets of message groups embedded in a module (common_rel), by their region tags."""
    found = []
    for m in re.finditer(b"|".join(re.escape(t) for t in tags), b):
        o = m.start() - 6
        if o < 0 or o % 4:
            continue
        gid, _, font, count = struct.unpack_from(">HBBH", b, o)
        if not 0 < count < 5000 or gid != 0:
            continue
        key0, off0 = struct.unpack_from(">II", b, o + 0x10)
        if not 0x10 + 8 * count <= off0 < len(b) - o:
            continue
        found.append((o, b[o + 6:o + 8], font, count))
    return found
