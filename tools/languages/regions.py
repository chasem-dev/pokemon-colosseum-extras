"""Text and fonts from another region's disc, for the packs made from discs other than Colosseum's European one:
Pokémon XD's European disc (GXXP01: English, French, German, Italian and Spanish) and the Japanese discs of both
games (GC6J01, GXXJ01).

Every disc keeps its text in message groups (colomsg.py): the archives' .msg members, the groups in common.fsys's
common_rel and main.dol's own group. A group's region tag says its language: XD's European disc holds five of each
(UK, FR, GE, IT, SP), each archive's menus in all five or in a language's own archive (<archive>_fr.fsys ...);
XD's Japanese disc tags them JP; Colosseum's Japanese disc leaves them untagged. Message keys are the same on every
region's disc, so a line goes where the US game shows the same key.

A floor's own letters are a font file in its archive (.fnt, opened with the floor): the Japanese discs keep their kanji
there, a floor's file holding the ones its text uses.
"""
import collections
import re
import struct

import colodisc as cd
import colomsg as cm

LANGUAGE_ARCHIVE = re.compile(r"_(fr|ge|it|sp)$")
ENDING = re.compile(r"(?:\{clear\}|\{page\})+$")
CODE = re.compile(r"\{[0-9a-f]{2}(?::[0-9a-f]*)?\}")


def visible(text):
    return re.sub(r"\{[^}]*\}|\\n", "", text).strip()


def base_archive(name):
    return LANGUAGE_ARCHIVE.sub("", name)


def message_groups(archives, tags=None):
    """Every message group of a disc: [(where, font, [(key, raw)])], where an archive name, common_rel or main.dol.
    tags: the region tags to keep (None: all)."""
    out = []
    for arc in archives.names():
        for m in archives.get(arc, (0x0A,)):
            hdr, ents = cm.parse_group(m.data)
            if tags is None or hdr["tag"] in tags:
                out.append((arc, hdr["font"], ents))
    rel = next((m.data for m in archives.get("common", (0x1C,)) if m.name == "common_rel"), None)
    dol, _ = archives.disc.dol()
    for where, b in (("common_rel", rel), ("main.dol", dol)):
        if b is None:
            continue
        for o, tag, font, count in cm.scan_groups(b, tags):
            out.append((where, font, cm.parse_group(b, o)[1]))
    return out


def translations(archives, tags):
    """{key: [(archive, text)]} of the groups with these tags."""
    out = collections.defaultdict(list)
    for where, font, ents in message_groups(archives, tags):
        for key, raw in ents:
            out[key].append((base_archive(where), cm.decode(raw)))
    return out


def pick(english, found, keep=None):
    """{key: text}: for each English line (english: {key: (font, text, where)}), the translation found for its key,
    the one from the English line's own archive when the disc says it two ways, else the commonest. keep(text)
    decides whether a line is a translation at all."""
    out = {}
    for key, (font, eng, where) in english.items():
        cands = found.get(key)
        if not cands:
            continue
        arc = where.split("/")[0]
        own = [t for a, t in cands if a == arc]
        t = collections.Counter(own or [t for _, t in cands]).most_common(1)[0][0]
        if t == eng or (keep and not keep(t)):
            continue
        if not visible(t):   # a line of codes alone: kept where it says more than the English (a particle in a code)
            codes, eng_codes = set(CODE.findall(t)), set(CODE.findall(eng))
            if not (codes > eng_codes):
                continue
        # the US script shows the line: it ends as the US line does ({clear} closes the box, {page} goes on)
        out[key] = ENDING.sub("", t) + "".join(ENDING.findall(eng)[-1:])
    return out


# ---------------------------------------------------------------------------------------- fonts
def font_file_glyphs(data, fonts):
    """Add a font file's glyphs (a chain of blocks: id, cell width and height, next block's offset, a bank) to
    fonts: {font id: {code: (w, h, yoff, bitmap)}}, the first file's glyph kept for a code."""
    off = 0
    while off + 24 <= len(data):
        fid, w, h, nxt = struct.unpack_from(">HBBI", data, off)
        if fid == 0xFFFF:
            break
        bank = off + 8
        n, do = cd.be16(data, bank), cd.be32(data, bank + 4)
        for k in range(n):
            e = bank + 16 + 8 * k
            if e + 8 > len(data):
                break
            code, gw, gh = cd.be16(data, e), data[e + 2], data[e + 3]
            o = cd.be32(data, e + 4)
            nb = ((gw + 1) & ~1) // 2 * gh
            src = bank + do + (o & 0xFFFFFF)
            if gw and gh and src + nb <= len(data):
                fonts[fid].setdefault(code, (gw, gh, o >> 24, data[src:src + nb]))
        if not nxt:
            break
        off += nxt


def archive_fonts(archives):
    """{font id: {code: glyph}} of every font file in the disc's archives (floors' and menus' own letters)."""
    fonts = collections.defaultdict(dict)
    for arc in archives.names():
        if arc.startswith(("pkx_", "wzx_")):
            continue
        for m in archives.get(arc, (0x0C,)):
            font_file_glyphs(m.data, fonts)
    return fonts


def merge_fonts(*sets):
    out = collections.defaultdict(dict)
    for s in sets:
        for fid, glyphs in s.items():
            for code, g in glyphs.items():
                out[fid].setdefault(code, g)
    return out


def text_chars(lines):
    """The characters a pack's lines draw (codes and escapes left out)."""
    chars = set()
    for t in lines.values():
        chars.update(re.sub(r"\{[^}]*\}|\\n|\\[{}\\]", "", t))
    return chars
