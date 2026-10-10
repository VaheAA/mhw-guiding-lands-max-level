# MHW Guiding Lands Max Level: Save Editor for Monster Hunter World: Iceborne

Set every **Guiding Lands region to level 7** in your **Monster Hunter World: Iceborne** PC save in a few seconds, with no grinding, no Cheat Engine and no game mods.

A small, safe command-line tool for Windows, Linux and the Steam Deck (Proton). It decrypts your `SAVEDATA1000`, changes only the Guiding Lands region levels, re-encrypts the file and checks the result before replacing anything.

```
Slot 1: 'Mugiwara'  HR 212  level_total 390000
  Ancient Forest   Lv 7  (65000 xp, max unlocked Lv 7)
  Wildspire Waste  Lv 7  (65000 xp, max unlocked Lv 7)
  Coral Highlands  Lv 7  (65000 xp, max unlocked Lv 7)
  Rotten Vale      Lv 7  (65000 xp, max unlocked Lv 7)
  Elder's Recess   Lv 7  (65000 xp, max unlocked Lv 7)
  Hoarfrost Reach  Lv 7  (65000 xp, max unlocked Lv 7)
```

## Features

- Sets all 6 Guiding Lands regions (Forest, Wildspire, Coral, Rotten, Volcanic/Elder's Recess, Tundra/Hoarfrost) to any level from 1 to 7
- Unlocks the region level caps, so Rotten Vale and Elder's Recess can reach Lv 7
- Raises the total-level cap so leveling one region never drains the others
- Dry run by default: shows your current levels without changing anything
- Automatic timestamped backup before every write
- Checks the save's integrity (SHA-1 hash and all region checksums) before and after editing, and refuses to write if anything doesn't match
- Changes only the Guiding Lands bytes; your equipment, items and progress are untouched
- Auto-detects the Steam save on Linux and Steam Deck
- Pure Python; the only dependency is `pycryptodome`

## Requirements

- Monster Hunter World **with Iceborne**, PC (Steam) save
- Python 3.9 or newer

PS4 and Xbox saves are not supported.

## Installation

```sh
git clone https://github.com/VaheAA/mhw-guiding-lands-max-level.git
cd mhw-guiding-lands-max-level
python3 -m venv .venv
```

Linux, macOS and Steam Deck:

```sh
.venv/bin/pip install -r requirements.txt
```

Windows (PowerShell):

```powershell
.venv\Scripts\pip install -r requirements.txt
```

## Usage

> **Close the game first.** It's also a good idea to keep your own copy of the save folder.

### 1. Find your save

| Platform | Location |
|---|---|
| Windows | `C:\Program Files (x86)\Steam\userdata\<your-steam-id>\582010\remote\SAVEDATA1000` |
| Linux / Steam Deck | `~/.local/share/Steam/userdata/<your-steam-id>/582010/remote/SAVEDATA1000` |

On Linux and Steam Deck the tool finds the save automatically when you have only one Steam account. On Windows, pass the path explicitly.

### 2. Check your current levels (dry run)

```sh
.venv/bin/python gl_maxlevel.py
# Windows:
.venv\Scripts\python gl_maxlevel.py "C:\Program Files (x86)\Steam\userdata\<id>\582010\remote\SAVEDATA1000"
```

### 3. Apply

```sh
.venv/bin/python gl_maxlevel.py --apply
```

### Options

| Option | Default | Description |
|---|---|---|
| `save` (positional) | auto-detect | Path to `SAVEDATA1000` |
| `--slot 1\|2\|3` | `1` | Which character slot to edit |
| `--level 1-7` | `7` | Target level for every region |
| `--apply` | off | Write the changes; without it the tool only shows your current levels |

Examples:

```sh
.venv/bin/python gl_maxlevel.py --apply --slot 2              # second character
.venv/bin/python gl_maxlevel.py --apply --level 6             # everything to Lv 6
.venv/bin/python gl_maxlevel.py /path/to/SAVEDATA1000 --apply
```

### 4. Launch the game

If Steam Cloud reports a **sync conflict**, choose the **local** files. Otherwise Steam may restore the old save from the cloud.

In the Guiding Lands, you can turn on **Fix Region Levels** in the in-game settings so your regions stay at level 7.

## Restoring a backup

Each `--apply` writes `SAVEDATA1000.bak-YYYYMMDD-HHMMSS` next to your save. To undo, close the game and copy the backup back over `SAVEDATA1000`.

## How it works

1. The whole save is Blowfish-decrypted, and its SHA-1 hash is checked.
2. Each region (system data plus three character slots) is decrypted with the Iceborne salted AES scheme, and each region's checksum is checked.
3. In the chosen slot, the tool writes:
   - region XP: `65000` for Lv 7 (a full overflow bar), otherwise `(level - 1) * 10000`
   - the per-region max-level unlock: raised to the target level
   - `level_total`: raised to `390000` (6 × 65000)
4. The checksums and hash are rebuilt and the file is re-encrypted.
5. The output is decrypted again and compared with what was intended. The backup is made and the original replaced only if that check passes.

| Field | Offset in character slot |
|---|---|
| Guiding Lands block | `0x20686F` |
| Region XP `u32[8]` | `+0x04` |
| `level_total` `u32` | `+0x24` |
| Max unlocked level `u8[8]` | `+0xD8` |

Slot 1 starts at file offset `0x3010D8` in the decrypted save. Slots are `0x209AC0` bytes apart.

## Project structure

```
gl_maxlevel.py    # command-line tool
mhw_crypt.py      # Iceborne save encryption/decryption (Blowfish + salted AES + checksums)
mhw_constants.py  # key-derivation tables
```

`mhw_crypt` can also be used on its own:

```python
import mhw_crypt
plain, hash_ok, checksums_ok = mhw_crypt.decrypt_save(open("SAVEDATA1000", "rb").read())
encrypted = mhw_crypt.encrypt_save(plain)
```

## FAQ

**Can I get banned?**
There are no known bans for single-player save edits in MHW, and this tool only changes Guiding Lands progress. Still, use it at your own risk, preferably for solo play.

**Does it work without Iceborne?**
No. Base-game saves have a different size, and the tool refuses to edit them.

**Does it give me tempered monsters, materials or Guiding Lands materials?**
No. It only sets region levels. Monsters and materials for a region's level spawn naturally once the region is at that level.

**I got "integrity check failed."**
The file isn't a valid, unmodified Iceborne PC save, or it was edited by another tool. Nothing was written.

**I got "Monster Hunter World appears to be running."**
Close the game completely, then run the tool again.

## Disclaimer

This is an unofficial fan tool, not affiliated with or endorsed by CAPCOM. Monster Hunter is a trademark of CAPCOM CO., LTD. Back up your saves; the authors aren't responsible for lost progress.

## Credits

- [LEGENDFF/mhw-Savecrypt](https://github.com/LEGENDFF/mhw-Savecrypt): reverse-engineered Iceborne save encryption (ported here to Python)
- [EnderHDMC/MHWISaveEditor](https://github.com/EnderHDMC/MHWISaveEditor): save layout and Guiding Lands structure
# mhw-guiding-lands-max-level
