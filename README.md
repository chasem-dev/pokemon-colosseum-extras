# Pokémon Colosseum extras

Downloads for the [Pokémon Colosseum PC port](https://git.softwareauralabs.com/chase/pokemon-colosseum) and [Colosseum Launcher](https://github.com/chasem-dev/colosseum-launcher), published as [releases](https://github.com/chasem-dev/pokemon-colosseum-extras/releases).

## HD texture pack

All 7,498 textures from the disc, upscaled 4×, in Dolphin's custom texture format. Colosseum Launcher downloads the pinned release by itself and checks it against a SHA-256 before using it.

To install it by hand, unzip it into the port's folder, so that you end up with `mods/textures/colo-upscale-4x/tex1_*.png`.

## Language packs

French, German, Spanish and Italian for the US game: the European release's text, the letters its fonts add, its translated menu and battle pictures and its colosseum title cards, one zip per language. Colosseum Launcher downloads the one chosen under Settings → Gameplay → Language.

They are made from the European disc (GC6P01) and your US disc (GC6E01) with [`tools/languages/make_language_packs.py`](tools/languages/make_language_packs.py) (Python 3, no packages needed):

```sh
python3 tools/languages/make_language_packs.py "Pokemon Colosseum (USA).iso" "Pokemon Colosseum (Europe).iso" out --template
```

A pack is a folder: `pack.json` and `text.txt` are all a translation needs; `font.bin`, `sprites.txt` and `files/` are optional. [`tools/languages/README.txt`](tools/languages/README.txt), also in every pack, describes the files. For a language the European disc doesn't have, start from `out/template/text.txt` (every English line, with where it appears), give `pack.json` your language's code and name, and put the folder in the launcher's languages folder (Settings → Gameplay → Open languages folder), or run the port with `COLO_LANGUAGE=/path/to/the/folder`.

### Pokémon XD and Japanese

The port's XD reads language packs as well, its own (`"game": "GXXE01"` in `pack.json`). XD's packs come in French, German, Spanish and Italian, made from XD's European disc (GXXP01) with its translated menu pictures and title cards, and in Japanese from XD's Japanese disc (GXXJ01). Colosseum has a Japanese pack too, from its Japanese disc (GC6J01). The Japanese packs carry the kanji and kana their text draws, and the kanji's readings shown above them; their menu pictures stay the US ones. Colosseum's Japanese pack also brings back Rui's original outfit, which the US release covered at the waist and legs. The US disc goes first:

```sh
python3 tools/languages/make_language_packs.py "Pokemon XD - Gale of Darkness (USA).iso" "Pokemon XD - Gale of Darkness (Europe) (En,Fr,De,Es,It).iso" out
python3 tools/languages/make_language_packs.py "Pokemon XD - Gale of Darkness (USA).iso" "Pokemon XD - Yami no Kaze Dark Lugia (Japan).iso" out
python3 tools/languages/make_language_packs.py "Pokemon Colosseum (USA).iso" "Pokemon Colosseum (Japan).iso" out
```

XD's packs go in `out/xd/`. For a fan translation of XD, write the template, every English line of XD, from your US disc:

```sh
python3 tools/languages/make_language_packs.py "Pokemon XD - Gale of Darkness (USA).iso" - out --template
```

and translate `out/xd-template/text.txt`, giving `pack.json` your language's code and name. With XD chosen in the launcher, Settings → Gameplay → Open languages folder opens XD's own languages folder.

This repository holds no game code and no disc image. You need your own disc to play. This is an unofficial fan project, not affiliated with Nintendo, Creatures, GAME FREAK or The Pokémon Company.
