"""MHW: Iceborne (PC) save encryption / decryption.

Python port of LEGENDFF/mhw-Savecrypt (Savecrypt.java).

Layers:
  1. Whole file: Blowfish-ECB with each 32-bit word byte-swapped, SHA-1 of
     everything after the 0x40-byte header stored at 0x0C.
  2. Per region (section0 + 3 character slots): salted AES-ECB with 32
     sub-keys, followed by a 0x200-byte checksum block that seeds the keys.
"""

import hashlib
import struct

from Crypto.Cipher import AES, Blowfish

from mhw_constants import FLOAT_CONSTANTS, INTEGER_CONSTANTS

BLOWFISH_KEY = b"xieZjoe#P2134-3zmaghgpqoe0z8$3azeq"
HEADER_SIZE = 0x40
HASH_OFFSET = 0x0C
CHECKSUM_SIZE = 0x200
MAGIC = b"\x01\x00\x00\x00"
ICEBORNE_SAVE_SIZE = 11284704

# (offset, length, slot id used by the checksum)
SECTION0_REGION = (0x70, 0xDA50, 3)
SLOT_REGIONS = (
    (0x3010D8, 0x2098C0, 0),
    (0x50AB98, 0x2098C0, 1),
    (0x714658, 0x2098C0, 2),
)

M32 = 0xFFFFFFFF
MAGIC_XOR = 0x0BD75F29  # crc32(0x1079000F, b"ONSTER HUNTER WORLD: ICEBORNE")


def _f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


_F32 = tuple(_f32(float(v)) for v in FLOAT_CONSTANTS)


def _swap32(data):
    a = bytearray(data)
    a[0::4], a[1::4], a[2::4], a[3::4] = data[3::4], data[2::4], data[1::4], data[0::4]
    return a


def _crc32_bytes(crc, data):
    for b in data:
        temp = (crc ^ b) & 0xFF
        for _ in range(8):
            temp = (temp >> 1) ^ 0xEDB88320 if temp & 1 else temp >> 1
        crc = (crc >> 8) ^ temp
    return crc & M32


def _crc32_ints(crc, ints):
    return _crc32_bytes(crc, b"".join(struct.pack("<I", v & M32) for v in ints))


def _crc32_fast(crc, data):
    # The game's CRC is the standard reflected CRC-32 without the final XOR,
    # so zlib can do it if we undo zlib's pre/post inversion.
    import zlib
    return zlib.crc32(data, crc ^ M32) ^ M32


def is_decrypted(save):
    return save[:4] == MAGIC


def generate_hash(save):
    return _swap32(hashlib.sha1(bytes(save[HEADER_SIZE:])).digest())


def blowfish(save, decrypt):
    cipher = Blowfish.new(BLOWFISH_KEY, Blowfish.MODE_ECB)
    op = cipher.decrypt if decrypt else cipher.encrypt
    return _swap32(op(bytes(_swap32(save))))


def _generate_salt(key_salt):
    c = key_salt ^ 0x4BF0CF23
    offset = 0x5D7
    change = (key_salt >> 24) + (key_salt >> 16 & 0xFF) + (key_salt >> 8 & 0xFF) + (key_salt & 0xFF) + 1
    out = bytearray()
    for _ in range(0, 0x200, 4):
        v = INTEGER_CONSTANTS[offset & 0xFFF] ^ c
        if v & 7 == 1:
            v ^= MAGIC_XOR
        out += struct.pack("<I", v & M32)
        offset += change
    return bytes(out)


def _generate_keys(key_salt, salt):
    consts = (0x5A8B79A9, 0x34616F90, 0xC4C638DF, 0x94FB64E8)
    keys = []
    for i in range(0x20):
        enc = struct.unpack_from("<I", salt, i * 4)[0]
        keys.append(b"".join(struct.pack("<I", enc ^ c ^ key_salt) for c in consts))
    return keys


def _generate_key_lengths(key_salt, length):
    avg = length >> 5
    avg_f = _f32(avg)
    expected = avg
    lengths = []
    for i in range(31):
        idx = INTEGER_CONSTANTS[((key_salt + i) & 0xFFF) ^ 0x5D7] & 0xFFF ^ 0x885
        v = int(_f32(_f32(_F32[idx] - 0.5) * avg_f))
        lengths.append((v + expected + 0xF) & 0xFFFFFFF0)
        expected += avg
    lengths.append(length)
    return lengths


def generate_checksum(save, offset, length, slot):
    constants = (0x55012174, 0x09FA3690, 0x4F5AE762, 0xA37A55D7)
    gen = (0x2EA10CEB, 0x204DE35E, 0x4BF0CF23, 0x72B401FD, 0x5CDD1F19, 0x681BA6CF, 0x0626B4CA, 0x7C8B3AF0)
    length_int = length >> 3
    slot_consts = [gen[i] ^ constants[(-slot - i - 1) & 3] for i in range(8)]

    crc_lengths = []
    for i in range(7):
        sc = slot_consts[i]
        variation = _F32[(sc + INTEGER_CONSTANTS[sc & 0xFFF]) & 0xFFF]
        crc_lengths.append(int(_f32(_f32(variation - 0.5) * _f32(length_int))) + (i + 1) * length_int)
    crc_lengths.append(length)

    partial = []
    crc_init = slot_consts[0]
    cur_len = crc_lengths[0]
    for i in range(8):
        partial.append(_crc32_fast(crc_init, bytes(save[offset:offset + cur_len])))
        if i < 7:
            offset += cur_len
            cur_len = crc_lengths[i + 1] - crc_lengths[i]
            crc_init = partial[i] ^ slot_consts[i + 1]

    lookup = [slot_consts[i] ^ partial[i] ^ partial[7] for i in range(7)]
    lookup.append(slot_consts[7] ^ partial[7])

    nxt = _crc32_ints(_crc32_ints(0xA37A55D7 ^ constants[3 - slot], slot_consts), partial)
    jump = (nxt >> 24) + (nxt >> 16 & 0xFF) + (nxt >> 8 & 0xFF) + (nxt & 0xFF)
    out = bytearray()
    for _ in range(0, 0x200, 4):
        cur = nxt & 0xFFF
        nxt = (nxt + jump + 1) & 0xFFF
        ic = INTEGER_CONSTANTS[cur]
        v = ic ^ lookup[(ic + slot) & 7]
        if ic & 7 == 1:
            v ^= MAGIC_XOR
        out += struct.pack("<I", v & M32)
    return bytes(out)


def _masks(salt, blocks):
    """Per-block XOR masks (applied before / after the AES step on decrypt)."""
    pre, post = bytearray(), bytearray()
    zero4 = b"\x00" * 4
    s = 0
    for _ in range(blocks):
        a = bytes(salt[(s + k) & 0x1FF] for k in range(16))
        if salt[s & 0x1FF] & 1 == 0:  # branch = 4
            pre += a[8:12] + zero4 + a[12:16] + zero4
            post += zero4 + a[0:4] + zero4 + a[4:8]
        else:  # branch = 0
            pre += zero4 + a[8:12] + zero4 + a[12:16]
            post += a[0:4] + zero4 + a[4:8] + zero4
        s += 4
    return bytes(pre), bytes(post)


def _xor(a, b):
    return (int.from_bytes(a, "little") ^ int.from_bytes(b, "little")).to_bytes(len(a), "little")


def _crypt_region(save, offset, length, key_salt, decrypt):
    salt = _generate_salt(key_salt)
    keys = _generate_keys(key_salt, salt)
    key_lengths = _generate_key_lengths(key_salt, length)
    pos = offset
    for i in range(32):
        end = key_lengths[i] + offset
        if pos >= end:
            continue
        blocks = (end - pos + 15) // 16
        seg_end = pos + blocks * 16
        pre, post = _masks(salt, blocks)
        aes = AES.new(keys[i], AES.MODE_ECB)
        seg = bytes(save[pos:seg_end])
        if decrypt:
            seg = _xor(aes.decrypt(_xor(seg, pre)), post)
        else:
            seg = _xor(aes.encrypt(_xor(seg, post)), pre)
        save[pos:seg_end] = seg
        pos = seg_end


def decrypt_region(save, offset, length, slot):
    key_salt = _crc32_fast(0xA37A55D7, bytes(save[offset + length:offset + length + CHECKSUM_SIZE]))
    _crypt_region(save, offset, length, key_salt, decrypt=True)
    return save[offset + length:offset + length + CHECKSUM_SIZE] == generate_checksum(save, offset, length, slot)


def encrypt_region(save, offset, length, slot):
    checksum = generate_checksum(save, offset, length, slot)
    save[offset + length:offset + length + CHECKSUM_SIZE] = checksum
    key_salt = _crc32_fast(0xA37A55D7, checksum)
    _crypt_region(save, offset, length, key_salt, decrypt=False)


def all_regions():
    return (SECTION0_REGION,) + SLOT_REGIONS


def decrypt_save(data):
    """Returns (plaintext bytearray, hash_ok, [checksum_ok per region])."""
    save = blowfish(data, decrypt=True)
    hash_ok = bytes(save[HASH_OFFSET:HASH_OFFSET + 20]) == bytes(generate_hash(save))
    checks = [decrypt_region(save, *r) for r in all_regions()]
    return save, hash_ok, checks


def encrypt_save(plain):
    save = bytearray(plain)
    for r in all_regions():
        encrypt_region(save, *r)
    save[HASH_OFFSET:HASH_OFFSET + 20] = generate_hash(save)
    return bytes(blowfish(save, decrypt=False))
