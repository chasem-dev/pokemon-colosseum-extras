"""Reading Pokémon Colosseum discs (GameCube ISO/GCM): the file table, FSYS archives and main.dol.

Nothing here writes to a disc. Plain Python, no dependencies.
"""
import struct

LZSS_MAGIC = b"LZSS"


def be16(b, o): return struct.unpack_from(">H", b, o)[0]
def be32(b, o): return struct.unpack_from(">I", b, o)[0]


class Disc:
    """A disc image: its id (GC6E01, GC6P01, ...), its files by name and main.dol."""

    def __init__(self, path):
        self.path = path
        self.f = open(path, "rb")
        head = self.read(0, 0x440)
        self.id = head[:6].decode("ascii", "replace")
        dol_off, fst_off, fst_size = struct.unpack(">III", head[0x420:0x42C])
        self.dol_off = dol_off
        fst = self.read(fst_off, fst_size)
        n = be32(fst, 8)
        strs = n * 12
        self.files = {}
        # Colosseum keeps its files at the root, apart from movie/: names are unique without paths
        def walk(i, end, prefix):
            while i < end:
                w0, a, b = struct.unpack_from(">III", fst, i * 12)
                o = strs + (w0 & 0xFFFFFF)
                name = fst[o:fst.index(b"\0", o)].decode("shift_jis")
                if w0 >> 24:
                    walk(i + 1, b, prefix + name + "/")
                    i = b
                else:
                    self.files[prefix + name] = (a, b)
                    i += 1
        walk(1, n, "")

    def read(self, off, n):
        self.f.seek(off)
        return self.f.read(n)

    def file(self, name):
        off, n = self.files[name]
        return self.read(off, n)

    def dol(self):
        """main.dol: (bytes, [(file offset, address, size)] of its sections)."""
        head = self.read(self.dol_off, 0x100)
        offs = struct.unpack(">18I", head[:72])
        addrs = struct.unpack(">18I", head[0x48:0x90])
        sizes = struct.unpack(">18I", head[0x90:0xD8])
        end = max(o + s for o, s in zip(offs, sizes) if s)
        return self.read(self.dol_off, end), [(o, a, s) for o, a, s in zip(offs, addrs, sizes) if s]


def dol_addr_to_off(sections, addr):
    for o, a, s in sections:
        if a <= addr < a + s:
            return o + addr - a
    raise KeyError(hex(addr))


def lzss_decode(src, out_size):
    """Okumura LZSS (N 4096, F 18, threshold 2, zeroed window, r from 0xFEE), as the game's loader."""
    window = bytearray(4096)
    r = 0xFEE
    out = bytearray()
    i, n = 0, len(src)
    flags = 0
    while len(out) < out_size and i < n:
        flags >>= 1
        if not flags & 0x100:
            flags = src[i] | 0xFF00
            i += 1
            if i >= n:
                break
        if flags & 1:
            c = src[i]; i += 1
            out.append(c); window[r] = c; r = (r + 1) & 0xFFF
        else:
            if i + 1 >= n:
                break
            a, b = src[i], src[i + 1]; i += 2
            pos = a | ((b & 0xF0) << 4)
            length = (b & 0x0F) + 3
            for k in range(length):
                c = window[(pos + k) & 0xFFF]
                out.append(c); window[r] = c; r = (r + 1) & 0xFFF
    return bytes(out[:out_size])


class Member:
    __slots__ = ("id", "name", "type", "data")

    def __init__(self, id, name, type, data):
        self.id, self.name, self.type, self.data = id, name, type, data


def fsys_members(data, want=None):
    """The members of an FSYS archive, unpacked: [Member]. want(name, type) can skip members unread."""
    if data[:4] != b"FSYS":
        raise ValueError("not an FSYS archive")
    count = be32(data, 0x0C)
    tables = be32(data, 0x18)
    entry_table = be32(data, tables)
    out = []
    for k in range(count):
        e = be32(data, entry_table + 4 * k)
        if not e:
            break
        mid = be32(data, e)
        off = be32(data, e + 4)
        size = be32(data, e + 8)
        flags = be32(data, e + 0x0C)
        packed_n = be32(data, e + 0x14)
        name_off = be32(data, e + 0x24)
        name = data[name_off:data.index(b"\0", name_off)].decode("shift_jis", "replace")
        typ = (mid >> 8) & 0xFF
        if want and not want(name, typ):
            out.append(Member(mid, name, typ, None))
            continue
        raw = data[off:off + packed_n]
        if flags & 0x80000000 and raw[:4] == LZSS_MAGIC:
            body = lzss_decode(raw[16:], size)
        else:
            body = raw[:size]
        out.append(Member(mid, name, typ, body))
    return out


# file types, by the id's third byte
TYPE_EXT = {0x02: "rdat", 0x04: "dat", 0x06: "ccd", 0x08: "samp", 0x0A: "msg", 0x0C: "fnt", 0x0E: "scd",
            0x10: "dats", 0x12: "gtx", 0x14: "gpt1", 0x18: "cam", 0x1C: "rel", 0x1E: "pkx", 0x20: "wzx",
            0x28: "isd", 0x2A: "ish", 0x2C: "thh", 0x2E: "thd", 0x30: "gsw", 0x32: "atx", 0x34: "bin"}


def type_ext(t):
    return TYPE_EXT.get(t, "%02x" % t)
