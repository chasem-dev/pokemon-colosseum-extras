Pokémon Colosseum language pack
===============================

A language pack translates the Pokémon Colosseum PC port (US disc, GC6E01). The launcher installs
packs into mods/languages/<code>/ and chooses one under Settings; without the launcher, start the
game with COLO_LANGUAGE=<code> (or COLO_LANGUAGE=/path/to/a/pack/folder).

Files (all but pack.json and text.txt are optional)

  pack.json    {"format": 1, "code": "fr", "name": "Français", "version": "1.0.0", ...}
  text.txt     the game's text, by message key
  font.bin     glyphs added to the game's fonts
  sprites.txt  where menu pictures are cut from translated sheets
  files/<archive>.fsys/<member>.<type>
               members of the US disc's archives to use instead, in the game's own formats
               (e.g. files/topmenu.fsys/menu_031.gtx)

text.txt

  UTF-8. "[font 0]" and "[font 1]" start the lines drawn in each of the game's two text styles
  (font 1: names, item and move descriptions, the bag). Each line is a message key in hex, a tab,
  and the text; lines starting with # are comments. A key the file leaves out keeps the English.

  In the text:  \n    a line break
                {clear}  the end of a text box     {page}  the next box
                {xx} {xx:hh..}  the game's codes (a name, a number, a colour): copy them as they are
                \{ \} \\   a literal brace or backslash
  Lines need to fit the boxes: count on about 38 letters a line in conversations.

  The fonts have the Latin-1 letters (é ñ ß ...), Œ œ ‘ ’ “ ” „ … ♂ ♀; font.bin from the official
  packs adds ° ♪ γ.

  To start a new language, take template/text.txt (every English line) from the pack tools, or a
  pack's text.txt, change pack.json's code and name, and translate.

sprites.txt

  One line per menu picture: its index, texture id and rectangle (x y w h) on the US disc, a tab,
  then the texture id and rectangle to draw instead. The game checks the first half and skips a
  line that doesn't match.

font.bin

  Font files as the game stores them (big-endian): an 8-byte header (font id, cell width and
  height, offset of the next file or 0), a glyph bank (count, data offset, two list words, then
  8 bytes a glyph: code, width, height, vertical offset and bitmap offset), and 4-bit bitmaps.
  Its glyphs are drawn in place of the font's own for the same character.

Made by make_language_packs.py (pokemon-colosseum-extras, tools/languages) from the European
disc (GC6P01). The packs hold the game's own text and pictures: use them with your own copy of
the game.
