#!/usr/bin/env python3
"""Language packs for the Pokémon Colosseum and XD PC port, made from the games' European and Japanese discs.

    make_language_packs.py US.iso PAL.iso OUT [--langs fr,de,es,it] [--template]

US.iso is GC6E01 (what the port plays), PAL.iso is GC6P01 (English, French, German, Spanish and
Italian). Each language becomes OUT/<code>/ and OUT/colosseum-language-<code>.zip, with:

  pack.json      what the pack is (code, name, version, source)
  text.txt       the game's text, by message key (format: README.txt and colomsg.py)
  font.bin       glyphs the US fonts lack (° ♪ γ) and the ones PAL redrew, as font banks
  sprites.txt    menu pictures cut from the translated sheets: the rectangle each takes
  files/<archive>.fsys/<member>.<type>   members of the US disc's archives replaced: the
                 translated menu sheets, battle HUD sheets and the colosseum and round title cards

Lines without a translation (US-only features, such as the Relic Stone's Celebi and the e-Reader
cards) are left out, so the game shows its English there.

--template also writes OUT/template/text.txt: every English line, for translating into a language
the European disc doesn't have. A pack needs only pack.json and text.txt; the rest is optional.

The same tool makes the other packs, from the other discs (the US disc first, as above):

    make_language_packs.py XD_US.iso XD_PAL.iso OUT      Pokémon XD in French, German, Spanish and Italian (GXXP01)
    make_language_packs.py US.iso JP.iso OUT             Pokémon Colosseum in Japanese (GC6J01)
    make_language_packs.py XD_US.iso XD_JP.iso OUT       Pokémon XD in Japanese (GXXJ01)
    make_language_packs.py XD_US.iso - OUT --template    XD's template (OUT/xd-template/: every English line)

XD's packs go in OUT/xd/<code>/ and OUT/xd/xd-language-<code>-<version>.zip, Colosseum's Japanese one in OUT/ja/
and OUT/colosseum-language-ja-<version>.zip; text and letters as above (regions.py), the European XD menu sheets
and title cards, and the Japanese discs' title cards.
"""
import argparse
import collections
import difflib
import hashlib
import json
import os
import re
import shutil
import struct
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import colodisc as cd  # noqa: E402
import colomsg as cm  # noqa: E402
import regions  # noqa: E402
import xdtext  # noqa: E402

PACK_FORMAT = 1
LANGS = {  # pack code: (PAL message suffix, PAL archive suffix, wzx prefix, name)
    "fr": ("fr", "fr", "fre", "Français"),
    "de": ("ge", "ge", "ger", "Deutsch"),
    "es": ("sp", "sp", "spa", "Español"),
    "it": ("it", "it", "ita", "Italiano"),
}
# PAL archives renamed from the US ones
PAL_NAME = {"colosseumbattle_menu": "cb_menu", "pokemonchange_menu": "pokechg_menu",
            "colosseumbattleconnection_menu": "cb_connect_menu"}
US_NAME = {v: k for k, v in PAL_NAME.items()}

# Lines the European text says differently from what the US game does: the options menu has no
# language there, and a GBA game must be an American one.
OVERRIDES = {
    "fr": {0x3C17: "Régler le son et la fonction\\nvibration de la manette.{clear}",
           0x44F0: "Communication impossible. Cette\\ncartouche POKéMON GBA n'est pas\\ncompatible avec une version américaine.{page}"
                   "Veuillez éteindre la Game Boy Advance\\nconnectée au port manette {2f}.{clear}"},
    "de": {0x3C17: "Stelle die Rumble-Funktion des\\nControllers und den Ton ein.{clear}",
           0x44F0: "Keine Verbindung möglich!\\nDieses POKéMON-Spielmodul für den\\nGBA ist keine amerikanische Version.{page}"
                   "Bitte den Game Boy Advance an\\nController-Anschlussbuchse {2f}\\nausschalten.{clear}"},
    "es": {0x3C17: "Elige el tipo de sonido y si activas\\no no la función de vibración del mando.{clear}",
           0x44F0: "No se puede establecer la conexión.\\nEl cartucho de POKéMON de GBA no es\\ncompatible con la consola americana.{page}"
                   "Apaga la consola Game Boy Advance\\nconectada al Puerto del Mando {2f}.{clear}"},
    "it": {0x3C17: "Imposta il suono e la funzione\\nRumble del controller.{clear}",
           0x44F0: "Collegamento impossibile.\\nQuesta non è una cassetta di gioco\\nPOKéMON Game Boy Advance\\nversione americana.{page}"
                   "Spegni (OFF) il Game Boy Advance\\nconnesso alla presa per controller {2f}.{clear}"},
}

ENDING = re.compile(r"(?:\{clear\}|\{page\})+$")
JAPANESE = re.compile("[぀-ヿ一-鿿！-～]")
SPRITE_TABLE_US = 0x802E7CE8   # lbl_802E7CE8: menuSpriteBiosGetPtr's table, 0x18-byte records
SPRITE_COUNT_US = 986


def log(*a):
    print(*a, flush=True)


class Archives:
    """A disc's FSYS archives, unpacked on demand."""

    def __init__(self, disc):
        self.disc = disc
        self.cache = {}

    def names(self):
        return sorted(n[:-5] for n in self.disc.files if n.endswith(".fsys"))

    def get(self, name, types=None):
        key = (name, types)
        if key not in self.cache:
            fn = name + ".fsys"
            if fn not in self.disc.files:
                self.cache[key] = []
            else:
                want = (lambda n, t: t in types) if types else None
                self.cache[key] = [m for m in cd.fsys_members(self.disc.file(fn), want) if m.data is not None]
        return self.cache[key]


def visible(text):
    return re.sub(r"\{[^}]*\}|\\n", "", text).strip()


# ---------------------------------------------------------------------------------------- text
def colosseum_english(us):
    """{key: (font, english, where)}: Colosseum's English lines, the archives' then common_rel's."""
    english = {}
    for arc in us.names():
        for m in us.get(arc, (0x0A,)):
            hdr, ents = cm.parse_group(m.data)
            for key, raw in ents:
                t = cm.decode(raw)
                if key not in english and visible(t) and not JAPANESE.search(t):
                    english[key] = (hdr["font"], t, "%s/%s" % (arc, m.name))
    ucr = next(m.data for m in us.get("common", (0x1C,)) if m.name == "common_rel")
    for uo, _, font, count in cm.find_groups(ucr, [b"US"]):
        if font != 1:
            continue
        for key, raw in cm.parse_group(ucr, uo)[1]:
            t = cm.decode(raw)
            if key not in english and visible(t) and not JAPANESE.search(t):
                english[key] = (font, t, "common_rel")
    return english


def gather_text(us, pal):
    """{lang: {key: text}}, {key: (font, english, where)} for every US line with a translation."""
    english = colosseum_english(us)
    trans = {code: collections.defaultdict(collections.Counter) for code in LANGS}
    for arc in us.names():
        for m in us.get(arc, (0x0A,)):
            base = PAL_NAME.get(arc, arc)
            for code, (msuf, asuf, _, _) in LANGS.items():
                cands = [(base, "%s_%s" % (m.name, msuf)), ("%s_%s" % (base, asuf), "%s_%s" % (m.name, msuf)),
                         ("%s_%s" % (base, asuf), m.name)]
                for a, n in cands:
                    hit = [x for x in pal.get(a, (0x0A,)) if x.name == n]
                    if hit:
                        for key, raw in cm.parse_group(hit[0].data)[1]:
                            trans[code][key][cm.decode(raw)] += 1
                        break
    # the shared names and descriptions in common_rel: one group per language
    ucr = next(m.data for m in us.get("common", (0x1C,)) if m.name == "common_rel")
    pcr = next(m.data for m in pal.get("common", (0x1C,)) if m.name == "common_rel")
    ugroups = [g for g in cm.find_groups(ucr, [b"US"]) if g[2] == 1]
    pgroups = cm.find_groups(pcr, [b"UK", b"GE", b"FR", b"IT", b"SP"])
    tag_of = {"fr": b"FR", "de": b"GE", "es": b"SP", "it": b"IT"}
    for uo, _, font, count in ugroups:
        hdr, ents = cm.parse_group(ucr, uo)
        ukeys = {k for k, _ in ents}
        for code in LANGS:
            for po, tag, pfont, pcount in pgroups:
                if tag != tag_of[code]:
                    continue
                pents = cm.parse_group(pcr, po)[1]
                if len(ukeys & {k for k, _ in pents}) < 0.9 * len(ukeys):
                    continue
                for key, raw in pents:
                    trans[code][key][cm.decode(raw)] += 1
    out = {}
    for code in LANGS:
        lines = {}
        for key, (font, eng, where) in english.items():
            c = trans[code].get(key)
            if not c:
                continue
            t = c.most_common(1)[0][0]
            if not visible(t) or JAPANESE.search(t) or t == eng:
                continue
            # the US script shows the line: it ends as the US line does ({clear} closes the box, {page} goes on)
            t = ENDING.sub("", t) + "".join(ENDING.findall(eng)[-1:])
            lines[key] = t
        for key, t in OVERRIDES.get(code, {}).items():
            if key in english:
                lines[key] = t
        out[code] = lines
    return out, english


FONT_NOTE = {
    "Pokémon Colosseum": "The game's fonts have the Latin-1 letters, Œ œ ‘ ’ “ ” „ …\n"
                         "# and, with this pack's font.bin, ° ♪ γ.\n",
    "Pokémon XD": "XD's fonts have the letters of French, German, Spanish and\n"
                  "# Italian (À-ü, ß, Œ œ, ¡ ¿, « », ‘ ’ “ ” „) and ♂ ♀, but not ° ♪ …: a letter they lack needs a font.bin.\n",
}


def write_text(path, code, name, lines, english, template=False, game="Pokémon Colosseum"):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("# %s text: %s (%s). Language pack format %d.\n" % (game, name, code, PACK_FORMAT))
        f.write("# Each line: the message key (hex), a tab, the text. A '#' line is a comment: above each\n"
                "# line, where it appears and its English. \\n breaks a line; {clear} ends a box and {page}\n"
                "# starts the next; other {..} are the game's codes (names, numbers, colours): keep them.\n"
                "# A key left out shows the English. " + FONT_NOTE.get(game, FONT_NOTE["Pokémon Colosseum"]))
        for font in (0, 1):
            keys = sorted(k for k in (english if template else lines) if english[k][0] == font)
            if not keys:
                continue
            f.write("\n[font %d]\n" % font)
            for k in keys:
                f.write("# %s: %s\n" % (english[k][2], english[k][1]))
                f.write("%05x\t%s\n" % (k, english[k][1] if template else lines[k]))


# ---------------------------------------------------------------------------------------- font
def font_banks(dol, sections):
    """{font id: {code: (w, h, yoff, bitmap)}} of the fonts in main.dol (a chain of font files)."""
    fonts = collections.defaultdict(dict)
    for o, a, s in sections:
        d = dol[o:o + s]
        i = 0
        while i + 40 <= len(d):
            n, do = cd.be16(d, i + 8), cd.be32(d, i + 12)
            ok = 4 <= n <= 20000 and 16 + 8 * n <= do and i + 8 + do <= len(d)
            if ok:
                codes = [cd.be16(d, i + 24 + 8 * k) for k in range(n)]
                ok = all(codes[k] < codes[k + 1] for k in range(n - 1)) and d[i] == 0 and d[i + 1] < 8
            if not ok:
                i += 4
                continue
            fid = cd.be16(d, i)
            bank = i + 8
            for k in range(n):
                e = bank + 16 + 8 * k
                code, w, h = cd.be16(d, e), d[e + 2], d[e + 3]
                off = cd.be32(d, e + 4)
                nb = ((w + 1) & ~1) // 2 * h
                src = bank + do + (off & 0xFFFFFF)
                fonts[fid].setdefault(code, (w, h, off >> 24, d[src:src + nb]))
            i = bank + 16 + 8 * n
    return fonts


def european_glyph(code, us, glyph):
    """A glyph the European font has that the US one lacks or draws differently (kana and kanji left out: the
    European text uses none)."""
    return code < 0x3000 and (us is None or us != glyph)


def font_file(us_fonts, pal_fonts, us_dims, want=european_glyph):
    """font.bin: for each font, a font file (8-byte header, bank, bitmaps) of the other disc's glyphs that
    want(code, US glyph or None, glyph) takes. Big-endian, chained by the headers' next offsets."""
    files = []
    report = {}
    for fid in sorted(pal_fonts):
        if fid not in us_fonts or fid not in us_dims:
            continue
        glyphs = []
        for code, g in sorted(pal_fonts[fid].items()):
            if want(code, us_fonts[fid].get(code), g):
                glyphs.append((code, g))
        if not glyphs:
            continue
        report[fid] = "".join(chr(c) for c, _ in glyphs)
        n = len(glyphs)
        data_off = 16 + 8 * n
        table, body = bytearray(), bytearray()
        for code, (w, h, yoff, bm) in glyphs:
            table += struct.pack(">HBBI", code, w, h, (yoff << 24) | len(body))
            body += bm
            body += b"\0" * (-len(body) % 4)
        bank = struct.pack(">HHIII", n, 0, data_off, 0, 0) + table + body
        w, h = us_dims[fid]
        files.append(bytearray(struct.pack(">HBBI", fid, w, h, 0)) + bank)
    out = bytearray()
    for i, f in enumerate(files):
        f += b"\0" * (-len(f) % 32)
        if i + 1 < len(files):
            struct.pack_into(">I", f, 4, len(f))
        out += f
    return bytes(out), report


def font_dims(dol, sections):
    dims = {}
    for o, a, s in sections:
        d = dol[o:o + s]
        for i in range(0, len(d) - 24, 4):
            fid = cd.be16(d, i)
            if fid < 8 and d[i + 2] == d[i + 3] and 8 <= d[i + 2] <= 32 and cd.be16(d, i + 8) > 300:
                dims.setdefault(fid, (d[i + 2], d[i + 3]))
    return dims


# ------------------------------------------------------------------------------------- sprites
def us_sprites(dol, sections):
    base = cd.dol_addr_to_off(sections, SPRITE_TABLE_US)
    out = []
    for i in range(SPRITE_COUNT_US):
        r = dol[base + 0x18 * i:base + 0x18 * (i + 1)]
        x, y, w, h = struct.unpack_from(">hhhh", r, 8)
        out.append(dict(flags=cd.be16(r, 0), rect=(x, y, w, h), tex=cd.be32(r, 0x10)))
    return out


def pal_sprites(dol, sections, us):
    """PAL's table: 0x48-byte records, five (rect, texture) slots, found by the US table's start."""
    probe = next(r for r in us if r["tex"] & 0xFFFF == 0x1200)
    pat = struct.pack(">hhhhI", *probe["rect"], probe["tex"])
    at = dol.find(pat)
    k = us.index(probe)
    base = at - 8 - 0x48 * k
    out = []
    i = 0
    while base + 0x48 * (i + 1) <= len(dol):
        r = dol[base + 0x48 * i:base + 0x48 * (i + 1)]
        if not any(r) or r[0x46:0x48] != b"\0\0":   # the table ends in zeros
            break
        slots = [(struct.unpack_from(">hhhh", r, 8 + 12 * s), cd.be32(r, 16 + 12 * s)) for s in range(5)]
        out.append(dict(flags=cd.be16(r, 0), slots=slots))
        i += 1
    return out


# ---------------------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("us_iso")
    ap.add_argument("pal_iso")
    ap.add_argument("out")
    ap.add_argument("--langs", default=",".join(LANGS))
    ap.add_argument("--version", default="1.0.0")
    ap.add_argument("--template", action="store_true")
    ap.add_argument("--no-zip", action="store_true")
    args = ap.parse_args()
    usd = cd.Disc(args.us_iso)
    if usd.id == xdtext.XD_DISC and args.pal_iso == "-":
        return xd_main(args, usd)
    if args.pal_iso == "-":
        sys.exit("need the European disc (GC6P01) for Colosseum's packs")
    pald = cd.Disc(args.pal_iso)
    other = {(xdtext.XD_DISC, xdtext.XD_PAL_DISC): xd_pal_main, ("GC6E01", JA_DISC["GC6E01"]): ja_main,
             (xdtext.XD_DISC, JA_DISC[xdtext.XD_DISC]): ja_main}.get((usd.id, pald.id))
    if other:
        return other(args, usd, pald)
    if usd.id != "GC6E01" or pald.id != "GC6P01":
        sys.exit("need GC6E01 and GC6P01 discs (got %s and %s)" % (usd.id, pald.id))
    us, pal = Archives(usd), Archives(pald)
    langs = [c for c in args.langs.split(",") if c]
    os.makedirs(args.out, exist_ok=True)

    log("text: reading both discs' messages")
    text, english = gather_text(us, pal)
    if args.template:
        os.makedirs(os.path.join(args.out, "template"), exist_ok=True)
        write_text(os.path.join(args.out, "template", "text.txt"), "xx", "template", {}, english, template=True)

    log("font")
    udol, usec = usd.dol()
    pdol, psec = pald.dol()
    ufonts, pfonts = font_banks(udol, usec), font_banks(pdol, psec)
    fontbin, freport = font_file(ufonts, pfonts, font_dims(udol, usec))
    log("  glyphs per font:", {k: v for k, v in freport.items()})

    log("sprites")
    usp = us_sprites(udol, usec)
    psp = pal_sprites(pdol, psec, usp)
    log("  US %d records, PAL %d" % (len(usp), len(psp)))

    # every PAL texture: id -> (archive, member name, data); and US ids by member name
    log("textures: indexing archives")
    pal_tex = {}
    for a in pal.names():
        if a.startswith(("pkx_", "wzx_")):
            continue
        for m in pal.get(a, (0x12,)):
            pal_tex.setdefault(m.id, (a, m.name, m.data))
    us_by_name = collections.defaultdict(set)    # (us archive, name) -> ids
    us_where = collections.defaultdict(set)      # id -> us archives holding it
    us_data = {}
    for a in us.names():
        if a.startswith(("pkx_", "wzx_")):
            continue
        for m in us.get(a, (0x12,)):
            us_by_name[(a, m.name)].add(m.id)
            us_where[m.id].add(a)
            us_data.setdefault(m.id, m.data)

    def lang_of_archive(a):
        for code, (_, asuf, _, _) in LANGS.items():
            if a.endswith("_" + asuf):
                return code, a[:-len(asuf) - 1]
        return None, a

    # the slots' languages: by which language's archive each slot's textures come from
    votes = collections.defaultdict(collections.Counter)
    for r in psp:
        for s, (rect, tex) in enumerate(r["slots"]):
            if tex in pal_tex:
                code, _ = lang_of_archive(pal_tex[tex][0])
                if code:
                    votes[s][code] += 1
    slot_of = {}
    for s, c in votes.items():
        code = c.most_common(1)[0][0]
        slot_of[code] = s
    log("  sprite slots:", {c: s for c, s in sorted(slot_of.items(), key=lambda x: x[1])})

    def us_tex_for(pal_id, en_id):
        """The US texture id a PAL language texture stands in for, and its data."""
        if pal_id == en_id:
            return en_id, None
        if pal_id not in pal_tex:
            return None, None
        a, name, data = pal_tex[pal_id]
        _, base = lang_of_archive(a)
        usa = US_NAME.get(base, base)
        ids = us_by_name.get((usa, name)) or set()
        if not ids:   # sheets the US keeps in common.fsys (the battle HUD)
            ids = us_by_name.get(("common", name)) or set()
        if len(ids) != 1:
            return None, None
        return next(iter(ids)), data

    # the two tables mostly list the same sprites in the same order: line them up
    ukeys = [(r["flags"], r["rect"], r["tex"]) for r in usp]
    pkeys = [(r["flags"], r["slots"][0][0], r["slots"][0][1]) for r in psp]
    aligned = {}
    for blk in difflib.SequenceMatcher(None, ukeys, pkeys, autojunk=False).get_matching_blocks():
        for k in range(blk.size):
            aligned[blk.a + k] = blk.b + k
    log("  %d of %d US sprites lined up with PAL's" % (len(aligned), len(usp)))

    for code in langs:
        msuf, asuf, wpre, lname = LANGS[code]
        d = os.path.join(args.out, code)
        if os.path.exists(d):
            shutil.rmtree(d)
        os.makedirs(os.path.join(d, "files"))
        replaced = {}     # us texture id -> data
        problems = collections.Counter()

        # sprites: US records whose PAL record (same English rectangle and texture) differs here
        by_en = collections.defaultdict(list)
        for r in psp:
            by_en[(r["slots"][0][0], r["slots"][0][1])].append(r)
        sprite_lines = []
        s = slot_of.get(code)
        for i, r in enumerate(usp):
            if not r["tex"] or s is None:
                continue
            if i in aligned:   # the same place in both tables
                cands = [psp[aligned[i]]]
            else:
                cands = by_en.get((r["rect"], r["tex"]), [])
            alts = {p["slots"][s] for p in cands}
            if not alts:
                continue
            if len(alts) > 1:
                problems["sprite with two translations"] += 1
                continue
            rect, ptex = alts.pop()
            if (rect, ptex) == (r["rect"], r["tex"]):
                continue
            utex, data = us_tex_for(ptex, r["tex"])
            if utex is None:
                problems["sprite texture not on the US disc"] += 1
                continue
            if data is not None:
                replaced[utex] = data
            if (utex, tuple(rect)) == (r["tex"], tuple(r["rect"])):
                continue   # the same place on this language's copy of the sheet
            sprite_lines.append("%03d %08x %d %d %d %d\t%08x %d %d %d %d" % ((i, r["tex"]) + r["rect"] + (utex,) + tuple(rect)))

        # sheets that change by language but aren't cut into sprites (or are, unchanged): by name
        for a in pal.names():
            lc, base = lang_of_archive(a)
            if lc != code:
                continue
            en_members = {m.name: m for m in pal.get(base, (0x12,))}
            usa = US_NAME.get(base, base)
            for m in pal.get(a, (0x12,)):
                en = en_members.get(m.name)
                if en is not None and en.data == m.data:
                    continue
                ids = us_by_name.get((usa, m.name)) or us_by_name.get(("common", m.name)) or set()
                if len(ids) == 1:
                    replaced.setdefault(next(iter(ids)), m.data)
                else:
                    problems["sheet without a US counterpart"] += 1

        nfiles = 0
        for utex, data in sorted(replaced.items()):
            if us_data.get(utex) == data:
                continue
            for a in sorted(us_where[utex]):
                name = next(m.name for m in us.get(a, (0x12,)) if m.id == utex)
                p = os.path.join(d, "files", a + ".fsys")
                os.makedirs(p, exist_ok=True)
                with open(os.path.join(p, "%s.%s" % (name, cd.type_ext(0x12))), "wb") as f:
                    f.write(data)
                nfiles += 1

        # the colosseum and round title cards: whole effects
        nwzx = 0
        for a in pal.names():
            if not a.startswith("wzx_%s_" % wpre):
                continue
            usa = "wzx_" + a[len("wzx_%s_" % wpre):]
            if usa == "wzx_hyper_pokemon_battle02":
                continue
            um = us.get(usa)
            pm = pal.get(a)
            if len(um) != 1 or len(pm) != 1:
                problems["title card not matched"] += 1
                continue
            p = os.path.join(d, "files", usa + ".fsys")
            os.makedirs(p, exist_ok=True)
            with open(os.path.join(p, "%s.%s" % (um[0].name, cd.type_ext(um[0].type))), "wb") as f:
                f.write(pm[0].data)
            nwzx += 1

        write_text(os.path.join(d, "text.txt"), code, lname, text[code], english)
        with open(os.path.join(d, "font.bin"), "wb") as f:
            f.write(fontbin)
        with open(os.path.join(d, "sprites.txt"), "w", encoding="utf-8", newline="\n") as f:
            f.write("# Menu pictures cut from this language's sheets. Each line: the sprite's index, then its\n"
                    "# texture id and rectangle (x y w h) on the US disc, a tab, and the texture and rectangle to\n"
                    "# use instead. A line whose first half doesn't match the game is skipped.\n")
            f.write("\n".join(sprite_lines) + "\n")
        info = dict(format=PACK_FORMAT, code=code, name=lname, version=args.version,
                    game="GC6E01", source="Pokémon Colosseum, European disc (GC6P01)",
                    lines=len(text[code]), sprites=len(sprite_lines), files=nfiles + nwzx)
        with open(os.path.join(d, "pack.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
            f.write("\n")
        shutil.copy(os.path.join(HERE, "README.txt"), os.path.join(d, "README.txt"))
        log("%s: %d lines, %d sprites, %d sheets, %d title cards; %s" % (
            code, len(text[code]), len(sprite_lines), nfiles, nwzx, dict(problems) or "no problems"))
        if not args.no_zip:
            zip_pack(args.out, code, os.path.join(args.out, "colosseum-language-%s-%s.zip" % (code, args.version)))


def zip_pack(root, code, z):
    """root/code/ as a zip whose top folder is the pack's code (as the launcher installs it), the same bytes each time."""
    d = os.path.join(root, code)
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for top, _, files in sorted(os.walk(d)):
            for fn in sorted(files):
                full = os.path.join(top, fn)
                zi = zipfile.ZipInfo(os.path.relpath(full, root).replace(os.sep, "/"), (2026, 1, 1, 0, 0, 0))
                zi.compress_type = zipfile.ZIP_DEFLATED
                zi.external_attr = 0o644 << 16
                with open(full, "rb") as src:
                    zf.writestr(zi, src.read(), compresslevel=9)
    h = hashlib.sha256(open(z, "rb").read()).hexdigest()
    log("  %s %d bytes sha256 %s" % (os.path.basename(z), os.path.getsize(z), h))


GAME_NAME = {"GC6E01": "Pokémon Colosseum", xdtext.XD_DISC: "Pokémon XD"}
GAME_SOURCE = {"GC6P01": "Pokémon Colosseum, European disc (GC6P01)",
               "GC6J01": "Pokémon Colosseum, Japanese disc (GC6J01)",
               xdtext.XD_PAL_DISC: "Pokémon XD: Gale of Darkness, European disc (GXXP01)",
               "GXXJ01": "Pokémon XD: Yami no Kaze Dark Lugia, Japanese disc (GXXJ01)"}
JA_DISC = {"GC6E01": "GC6J01", xdtext.XD_DISC: "GXXJ01"}
ZIP_NAME = {"GC6E01": "colosseum-language-%s-%s.zip", xdtext.XD_DISC: "xd-language-%s-%s.zip"}


def us_english(usd, us):
    return xdtext.english(us) if usd.id == xdtext.XD_DISC else colosseum_english(us)


def pack_root(args, usd):
    """Where a game's packs go: OUT for Colosseum's, OUT/xd for XD's (each pack in a folder named by its code)."""
    root = args.out if usd.id == "GC6E01" else os.path.join(args.out, "xd")
    os.makedirs(root, exist_ok=True)
    return root


def write_pack(args, usd, srcd, root, code, lname, lines, english, fontbin=b"", files=(), extra=None):
    """root/code/: pack.json, text.txt, font.bin (if any), files/ (archive members: {(archive, member file): data}),
    README.txt; and its zip."""
    d = os.path.join(root, code)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    write_text(os.path.join(d, "text.txt"), code, lname, lines, english, game=GAME_NAME[usd.id])
    if fontbin:
        with open(os.path.join(d, "font.bin"), "wb") as f:
            f.write(fontbin)
    for (arc, fn), data in sorted(files.items() if isinstance(files, dict) else files):
        p = os.path.join(d, "files", arc + ".fsys")
        os.makedirs(p, exist_ok=True)
        with open(os.path.join(p, fn), "wb") as f:
            f.write(data)
    info = dict(format=PACK_FORMAT, code=code, name=lname, version=args.version, game=usd.id,
                source=GAME_SOURCE[srcd.id], lines=len(lines), files=len(files))
    info.update(extra or {})
    with open(os.path.join(d, "pack.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
        f.write("\n")
    shutil.copy(os.path.join(HERE, "README.txt"), os.path.join(d, "README.txt"))
    if not args.no_zip:
        zip_pack(root, code, os.path.join(root, ZIP_NAME[usd.id] % (code, args.version)))


def missing_glyphs(lines, fonts):
    """The characters the lines draw that no font has (font 0's chain, which the dialogue draws from)."""
    have = set()
    for f in fonts:
        have |= set(f.get(0, {}))
    return sorted(c for c in regions.text_chars(lines) if ord(c) not in have and c not in " \u3000")


XD_LANGS = {"fr": (b"FR", "fr", "Français"), "de": (b"GE", "ge", "Deutsch"), "es": (b"SP", "sp", "Español"),
            "it": (b"IT", "it", "Italiano")}


def xd_pal_main(args, usd, pald):
    """Pokémon XD in French, German, Spanish and Italian, from XD's European disc."""
    us, pal = Archives(usd), Archives(pald)
    langs = [c for c in args.langs.split(",") if c]
    root = pack_root(args, usd)
    log("text: reading both discs' messages")
    english = us_english(usd, us)
    udol, usec = usd.dol()
    pdol, psec = pald.dol()
    ufonts = font_banks(udol, usec)   # the fonts the game always has (a floor's own come and go with it)
    pfonts = regions.merge_fonts(font_banks(pdol, psec), regions.archive_fonts(pal))
    dims = font_dims(udol, usec)
    for code in langs:
        tag, asuf, lname = XD_LANGS[code]
        lines = regions.pick(english, regions.translations(pal, [tag]))
        chars = {ord(c) for c in regions.text_chars(lines)}
        fontbin, freport = font_file(ufonts, pfonts, dims,
                                     lambda c, u, g: c in chars and c < 0x3000 and (u is None or u != g))
        files = xd_pal_files(us, pal, asuf)
        log("%s: %d of %d lines, font.bin %d bytes %s, %d archive members" % (
            code, len(lines), len(english), len(fontbin), freport, len(files)))
        miss = missing_glyphs(lines, [ufonts, pfonts])
        if miss:
            log("  letters no font has:", "".join(miss))
        write_pack(args, usd, pald, root, code, lname, lines, english, fontbin, files)


# sheets whose European layout differs from the US one (the menus cut them by the US layout): left in English
XD_LAYOUT_CHANGED = {"uv_pkm_status_00"}


# sheets with a title in rows y0..y1 that the menus cut by the US title's width: the language's title is fitted
# into the US one's place, on the US sheet
XD_FIT_TITLE = {"uv_ttl_battle_00": (408, 462)}


def ci8_pixels(data):
    """An 8-bit indexed texture's (width, height, indices by row, palette as RGB5A3 words)."""
    w, h = cd.be16(data, 0), cd.be16(data, 2)
    tw = (w + 7) // 8
    po = cd.be32(data, 0x48)
    pal = [cd.be16(data, po + 2 * i) for i in range(256)]
    px = [[data[0x80 + ((y // 4) * tw + x // 8) * 32 + (y % 4) * 8 + x % 8] for x in range(w)] for y in range(h)]
    return w, h, px, pal


def rgb5a3(v):
    if v & 0x8000:
        return ((v >> 10) & 31) * 255 // 31, ((v >> 5) & 31) * 255 // 31, (v & 31) * 255 // 31, 255
    return ((v >> 8) & 15) * 17, ((v >> 4) & 15) * 17, (v & 15) * 17, ((v >> 12) & 7) * 255 // 7


def fit_title(us_data, lang_data, y0, y1):
    """The US sheet with its title (rows y0..y1) replaced by the language's, squeezed to the US title's width where
    it is wider, in the US sheet's palette. None if either isn't an 8-bit indexed texture."""
    if gtx_shape(us_data)[2:] != (8, 1) or gtx_shape(lang_data)[2:] != (8, 1):
        return None
    uw, uh, upx, upal = ci8_pixels(us_data)
    lw, lh, lpx, lpal = ci8_pixels(lang_data)
    if uh < y1 or lh < y1:
        return None
    ucol, lcol = [rgb5a3(v) for v in upal], [rgb5a3(v) for v in lpal]

    def ink(px, cols, w):
        xs = [x for y in range(y0, y1) for x in range(w) if cols[px[y][x]][3] > 128 and cols[px[y][x]][0] > 160]
        return (min(xs), max(xs) + 1) if xs else None
    ub, lb = ink(upx, ucol, uw), ink(lpx, lcol, lw)
    if not ub or not lb:
        return None
    nearest = {}
    for i in range(256):
        c = lcol[i]
        nearest[i] = min(range(256), key=lambda j: sum((a - b) ** 2 for a, b in zip(c, ucol[j])))
    clear = min(range(256), key=lambda j: ucol[j][3])
    out = bytearray(us_data)
    tw = (uw + 7) // 8
    width, left = min(ub[1] - ub[0], lb[1] - lb[0]), ub[0]
    for y in range(y0, y1):
        for x in range(uw):
            if left <= x < left + width:
                sx = lb[0] + (x - left) * (lb[1] - lb[0]) // width
                i = nearest[lpx[y][sx]]
            else:
                i = clear
            out[0x80 + ((y // 4) * tw + x // 8) * 32 + (y % 4) * 8 + x % 8] = i
    return bytes(out)


def gtx_shape(data):
    """A texture's (width, height, bits per pixel, format)."""
    return (cd.be16(data, 0), cd.be16(data, 2), data[4], data[0x0B]) if len(data) >= 0x80 else None


def xd_pal_files(us, pal, asuf):
    """Archive members to replace: {(US archive, member file): data}. A language's archive (<archive>_fr.fsys)
    holds the menus' sheets in that language: as the English one's name with the language in it
    (uv_icn_type_big_fr_00), or unnamed, the English sheet it stands for then the one of the same size. A sheet
    goes where the US archive has the English one, laid out as it is; the battle and colosseum title cards
    (wzx_*_fr.fsys) whole, where the US effect is the European English one."""
    files = {}
    for a in pal.names():
        if not a.endswith("_" + asuf):
            continue
        base = a[:-len(asuf) - 1]
        lang = pal.get(a)
        en = pal.get(base)
        usm = us.get(base)
        if not en or not usm:
            continue
        if base.startswith("wzx_"):
            if len(lang) == 1 and len(en) == 1 and len(usm) == 1 and en[0].data == usm[0].data:
                files[(base, "%s.%s" % (usm[0].name, cd.type_ext(usm[0].type)))] = lang[0].data
            continue
        us_by_name = {m.name: m for m in usm if m.type == 0x12}
        en_by_name = {m.name: m for m in en if m.type == 0x12}
        named = {m.name for m in lang if m.name != "(null)"}
        pool = [m for m in en if m.type == 0x12 and m.name not in named]
        for m in lang:
            if m.type != 0x12:
                continue
            if m.name != "(null)":
                e = en_by_name.get(m.name)
                if e is not None and e.data == m.data:
                    continue
                name = m.name.replace("_%s_" % asuf, "_").replace(".gtx", "")
            else:
                cands = [e for e in pool if gtx_shape(e.data) == gtx_shape(m.data)]
                fit = [n for n in XD_FIT_TITLE if n in us_by_name and n in en_by_name and n not in named
                       and cd.be16(en_by_name[n].data, 2) == cd.be16(m.data, 2)]
                if not cands and len(fit) == 1:   # a title sheet made wider for the language's title
                    name = fit[0]
                    data = fit_title(us_by_name[name].data, m.data, *XD_FIT_TITLE[name])
                    if data and data != us_by_name[name].data:
                        files[(base, "%s.%s" % (name, cd.type_ext(0x12)))] = data
                    continue
                if len(cands) != 1:
                    continue
                name = cands[0].name
                if name in XD_FIT_TITLE:
                    data = fit_title(us_by_name[name].data, m.data, *XD_FIT_TITLE[name]) if name in us_by_name else None
                    if data and data != us_by_name[name].data:
                        files[(base, "%s.%s" % (name, cd.type_ext(0x12)))] = data
                    continue
            u = us_by_name.get(name)
            if u is None or name in XD_LAYOUT_CHANGED or gtx_shape(u.data) != gtx_shape(m.data) or u.data == m.data:
                continue
            files[(base, "%s.%s" % (name, cd.type_ext(0x12)))] = m.data
    return files


def ja_main(args, usd, jpd):
    """Japanese, from the game's Japanese disc: its text with the kanji's readings, and the letters it draws."""
    us, jp = Archives(usd), Archives(jpd)
    root = pack_root(args, usd)
    log("text: reading both discs' messages")
    english = us_english(usd, us)
    tags = [b"JP"] if usd.id == xdtext.XD_DISC else None   # Colosseum's Japanese disc leaves its groups untagged
    lines = regions.pick(english, regions.translations(jp, tags))
    log("font")
    udol, usec = usd.dol()
    jdol, jsec = jpd.dol()
    ufonts = font_banks(udol, usec)   # the fonts the game always has (a floor's own come and go with it)
    jfonts = regions.merge_fonts(font_banks(jdol, jsec), regions.archive_fonts(jp))
    chars = {ord(c) for c in regions.text_chars(lines)}

    def want(c, u, g):
        # the letters the text draws that the US font lacks, and its kana and kanji as the Japanese font draws them
        return c in chars and (u is None or (c >= 0x3000 and u != g))
    fontbin, freport = font_file(ufonts, jfonts, font_dims(udol, usec), want)
    log("ja: %d of %d lines, font.bin %d bytes, glyphs per font %s" % (
        len(lines), len(english), len(fontbin), {k: len(v) for k, v in freport.items()}))
    miss = missing_glyphs(lines, [ufonts, jfonts])
    if miss:
        log("  letters no font has:", "".join(miss))
    files = {}
    for a in us.names():   # the battle and colosseum title cards, whole effects
        if not a.startswith(("wzx_battle_name", "wzx_colo_intro")):
            continue
        um, jm = us.get(a), jp.get(a)
        if len(um) == 1 and len(jm) == 1 and um[0].name == jm[0].name and um[0].data != jm[0].data:
            files[(a, "%s.%s" % (um[0].name, cd.type_ext(um[0].type)))] = jm[0].data
    log("  %d title cards" % len(files))
    write_pack(args, usd, jpd, root, "ja", "日本語", lines, english, fontbin, files)


def xd_main(args, usd):
    """Pokémon XD: the template (every English line) for fan translations."""
    if not args.template or args.pal_iso != "-":
        sys.exit("Pokémon XD: only the template so far (make_language_packs.py XD_US.iso - OUT --template); "
                 "packs from XD's European disc (%s) are still to come" % xdtext.XD_PAL_DISC)
    log("text: reading XD's messages")
    english = xdtext.english(Archives(usd))
    d = os.path.join(args.out, "xd-template")
    os.makedirs(d, exist_ok=True)
    write_text(os.path.join(d, "text.txt"), "xx", "template", {}, english, template=True, game="Pokémon XD")
    info = dict(format=PACK_FORMAT, code="xx", name="Template (English)", version=args.version, game=xdtext.XD_DISC,
                source="Pokémon XD: Gale of Darkness, US disc (GXXE01)", lines=len(english))
    with open(os.path.join(d, "pack.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
        f.write("\n")
    shutil.copy(os.path.join(HERE, "README.txt"), os.path.join(d, "README.txt"))
    fonts = collections.Counter(font for font, _, _ in english.values())
    log("xd-template: %d lines (font 0: %d, font 1: %d)" % (len(english), fonts[0], fonts[1]))


if __name__ == "__main__":
    main()
