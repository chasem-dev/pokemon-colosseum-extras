"""Pokémon XD's text (US disc, GXXE01), for an XD language pack's template.

XD's message groups are laid out as Colosseum's (colomsg.py): .msg members of the archives, the names and
descriptions in common.fsys's common_rel, and main.dol's own group (the memory card and options text). Its
keys are global as Colosseum's, all under 0xFFFFF, with a few hundred
said two ways on the disc: the same line in two menus wrapped differently, or a menu Colosseum left on XD's disc. The
template takes, for each key, the English the most archives have, and of those first one that isn't a leftover.

The US disc also holds a few menus in French, German, Italian and Spanish (<archive>_fr.fsys ...) and the names in
those languages in common_rel, from XD's European build: left out here, as are groups in other region tags.
"""
import collections
import re

import colodisc as cd
import colomsg as cm

XD_DISC = "GXXE01"
XD_PAL_DISC = "GXXP01"
LANGUAGE_ARCHIVE = re.compile(r"_(fr|ge|it|sp)$")
# archives of Colosseum's (or of the e-Reader's) that XD's disc still carries: their lines lose a tie
LEFTOVERS = ("carde_menu", "ex_coupon", "ex_shrine", "ex_title", "ex_top", "Script_test")
JAPANESE = re.compile("[぀-ヿ一-鿿！-～]")


def visible(text):
    return re.sub(r"\{[^}]*\}|\\n", "", text).strip()


def english(archives):
    """{key: (font, text, where)} of XD's English lines. archives: make_language_packs.Archives of the US disc."""
    seen = collections.defaultdict(lambda: collections.defaultdict(list))   # key -> text -> [(font, where)]

    def take(font, ents, where):
        for key, raw in ents:
            t = cm.decode(raw)
            if visible(t) and not JAPANESE.search(t):
                seen[key][t].append((font, where))

    for arc in archives.names():
        if LANGUAGE_ARCHIVE.search(arc):
            continue
        for m in archives.get(arc, (0x0A,)):
            hdr, ents = cm.parse_group(m.data)
            if hdr["tag"] == b"US":
                take(hdr["font"], ents, "%s/%s" % (arc, m.name))
    rel = next((m.data for m in archives.get("common", (0x1C,)) if m.name == "common_rel"), None)
    if rel is not None:
        for o, tag, font, count in cm.find_groups(rel, [b"US"]):
            take(font, cm.parse_group(rel, o)[1], "common_rel")
    # main.dol's own group: the memory card, the options and other system text
    dol, _ = archives.disc.dol()
    for o, tag, font, count in cm.scan_groups(dol, [b"US"]):
        take(font, cm.parse_group(dol, o)[1], "main.dol")

    def rank(item):
        text, uses = item
        own = [w for _, w in uses if not w.split("/")[0] in LEFTOVERS]
        return (len({w.split("/")[0] for w in own}), len(own), len(uses))

    out = {}
    for key, texts in seen.items():
        text, uses = max(texts.items(), key=rank)
        font, where = uses[0]
        out[key] = (font, text, where)
    return out
