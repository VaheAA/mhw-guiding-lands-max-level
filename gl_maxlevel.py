#!/usr/bin/env python3
"""Set Monster Hunter World: Iceborne Guiding Lands region levels in a PC save.

Usage:
  gl_maxlevel.py                      # show levels (auto-detects the Steam save)
  gl_maxlevel.py --apply              # set every region of slot 1 to level 7
  gl_maxlevel.py --apply --slot 2 --level 6
  gl_maxlevel.py path/to/SAVEDATA1000 --apply

The game must be closed. A timestamped backup is written next to the save
before anything is changed, and the result is decrypted again and verified.
"""

import argparse
import glob
import os
import shutil
import struct
import subprocess
import sys
import time

import mhw_crypt

REGIONS = ("Ancient Forest", "Wildspire Waste", "Coral Highlands",
           "Rotten Vale", "Elder's Recess", "Hoarfrost Reach")

# Offsets inside a character slot (see MHWISaveEditor types/mhw_save.h).
NAME_OFFSET = 0x4
HR_OFFSET = 0x44
GUIDING_LANDS_OFFSET = 0x20686F
REGION_XP = GUIDING_LANDS_OFFSET + 0x4        # u32[8]
LEVEL_TOTAL = GUIDING_LANDS_OFFSET + 0x24     # u32
REGION_UNLOCKED = GUIDING_LANDS_OFFSET + 0xD8  # u8[8], max level per region

XP_PER_LEVEL = 10000
XP_MAX = 65000                        # level 7 with a full overflow bar
LEVEL_TOTAL_UNCAP = XP_MAX * len(REGIONS)


def find_save():
    pattern = os.path.expanduser("~/.local/share/Steam/userdata/*/582010/remote/SAVEDATA1000")
    found = glob.glob(pattern)
    if len(found) != 1:
        sys.exit(f"Could not auto-detect a single save ({len(found)} found); pass the path explicitly.")
    return found[0]


def game_running():
    try:
        return subprocess.run(["pgrep", "-if", "MonsterHunterWorld"], capture_output=True).returncode == 0
    except FileNotFoundError:
        return False


def level_of(xp):
    return xp // XP_PER_LEVEL + 1


def slot_info(save, slot):
    base = mhw_crypt.SLOT_REGIONS[slot][0]
    name = bytes(save[base + NAME_OFFSET:base + NAME_OFFSET + 64]).split(b"\0")[0].decode("utf-8", "replace")
    hr = struct.unpack_from("<I", save, base + HR_OFFSET)[0]
    xp = struct.unpack_from("<6I", save, base + REGION_XP)
    unlocked = list(save[base + REGION_UNLOCKED:base + REGION_UNLOCKED + 6])
    total = struct.unpack_from("<I", save, base + LEVEL_TOTAL)[0]
    return name, hr, xp, unlocked, total


def print_slot(save, slot):
    name, hr, xp, unlocked, total = slot_info(save, slot)
    print(f"Slot {slot + 1}: {name!r}  HR {hr}  level_total {total}")
    for region, x, cap in zip(REGIONS, xp, unlocked):
        print(f"  {region:<16} Lv {level_of(x)}  ({x:>5} xp, max unlocked Lv {cap})")


def set_levels(save, slot, level):
    base = mhw_crypt.SLOT_REGIONS[slot][0]
    xp = XP_MAX if level == 7 else (level - 1) * XP_PER_LEVEL
    for i in range(len(REGIONS)):
        struct.pack_into("<I", save, base + REGION_XP + 4 * i, xp)
        cap = base + REGION_UNLOCKED + i
        save[cap] = max(save[cap], level)
    total = struct.unpack_from("<I", save, base + LEVEL_TOTAL)[0]
    struct.pack_into("<I", save, base + LEVEL_TOTAL, max(total, LEVEL_TOTAL_UNCAP))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("save", nargs="?", help="path to SAVEDATA1000 (default: auto-detect Steam/Proton save)")
    ap.add_argument("--slot", type=int, default=1, choices=(1, 2, 3), help="character slot (default 1)")
    ap.add_argument("--level", type=int, default=7, choices=range(1, 8), help="target level (default 7)")
    ap.add_argument("--apply", action="store_true", help="write changes (otherwise only show current levels)")
    args = ap.parse_args()

    path = args.save or find_save()
    data = open(path, "rb").read()
    if len(data) != mhw_crypt.ICEBORNE_SAVE_SIZE:
        sys.exit(f"{path}: unexpected size {len(data)}, expected an Iceborne PC save.")

    save, hash_ok, checks = mhw_crypt.decrypt_save(data)
    if not (hash_ok and all(checks)):
        sys.exit(f"{path}: integrity check failed (hash={hash_ok}, checksums={checks}); refusing to touch it.")

    slot = args.slot - 1
    print(f"Save: {path}\n")
    print_slot(save, slot)
    if not args.apply:
        print("\nDry run. Re-run with --apply to set every region to "
              f"Lv {args.level}.")
        return

    if slot_info(save, slot)[1] == 0:
        sys.exit("That slot looks empty (HR 0); nothing to do.")
    if game_running():
        sys.exit("Monster Hunter World appears to be running. Close it first.")

    set_levels(save, slot, args.level)
    out = mhw_crypt.encrypt_save(save)

    # Verify the re-encrypted file before replacing the original.
    check, hash_ok, checks = mhw_crypt.decrypt_save(out)
    same_data = all(check[o:o + n] == save[o:o + n] for o, n, _ in mhw_crypt.all_regions())
    if not (hash_ok and all(checks) and same_data):
        sys.exit("Verification of the re-encrypted save failed; original left untouched.")

    backup = f"{path}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(path, backup)
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(out)
    os.replace(tmp, path)

    print(f"\nBackup: {backup}\nWritten:\n")
    print_slot(check, slot)


if __name__ == "__main__":
    main()
