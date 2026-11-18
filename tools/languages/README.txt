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

Pokémon XD

  XD reads packs too, its own: its message keys are XD's, so a Colosseum pack doesn't fit it.
  An XD pack's pack.json has "game": "GXXE01", and the launcher keeps XD's packs in a folder of
  their own (Settings, with XD chosen: Open languages folder). An XD pack has text.txt, and
  optionally font.bin and files/ (members of XD's archives); sprites.txt is Colosseum's. The
  official XD packs (French, German, Spanish and Italian from XD's European disc, GXXP01, and
  Japanese from its Japanese one, GXXJ01) have text, letters, menu sheets and title cards. Start
  a fan translation from the template, every English line of XD:

    make_language_packs.py "Pokemon XD (USA).iso" - out --template

  writes out/xd-template/ (text.txt and pack.json): change pack.json's code and name and
  translate. XD's fonts have the letters of French, German, Spanish and Italian; ° ♪ … need a
  font.bin.

Japanese

  The Japanese packs (both games, from their Japanese discs: GC6J01, GXXJ01) have the Japanese
  text with its kanji's readings ({04}kanji{05}reading{06}, drawn small above the kanji), the
  kanji and kana their text draws in font.bin, and the title cards. Their menus' pictures stay
  the US ones: the Japanese sheets are laid out for the Japanese menus.

Made by make_language_packs.py (pokemon-colosseum-extras, tools/languages) from the game's
European or Japanese disc (pack.json's "source" says which). The packs hold the game's own text and
pictures: use them with your own copy of the game.
