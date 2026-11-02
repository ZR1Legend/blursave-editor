"""Reader for the game's picture bundle ui_frontend.bpr (root.pak, /ui/data/): the pictures of the menus.

The layout is described in the Blur Map Builder (MIT licence, (c) 2026 MDPRO), ui/bpr.py: header {"2RZB", u8 3, u8 2, u16 size of
records + names, u32 records size, u32 data size, u32 0} (0x14 bytes); records of 28 bytes chained by their u16 size, the last
record has size 0: {u16 size, u16 name offset, u32 data offset, u16 1, u16 0, u32 data size, u32 0, u16 format (1 = DXT1,
5 = DXT5), u16 mips, u16 width, u16 height}; the names (zero-ended); the data (offsets relative to its start).
The first mip level of each picture is stored first. Needs PIL (development tool only, not part of the editor).
"""
import struct

from PIL import Image

REC = struct.Struct("<HHIHHIIHHHH")


def pictures(d):
    """{name: (format, width, height, bytes of the first mip level)}"""
    magic, _, _, rn_size, rec_size, data_size, _ = struct.unpack_from("<4sBBHIII", d, 0)
    if magic != b"2RZB":
        raise ValueError("not a picture bundle")
    names_at, data_at = 0x14 + rec_size, 0x14 + rn_size
    names = d[names_at:data_at]
    out, p = {}, 0x14
    while True:
        size, noff, doff, _, _, dsize, _, fmt, _, w, h = REC.unpack_from(d, p)
        if size == 0:
            break
        name = names[noff:names.index(b"\0", noff)].decode("latin1")
        nbytes = {1: w * h // 2, 5: w * h, 6: w * h * 4, 7: w * h}.get(fmt, w * h // 2)       # 6: 32 bit, 7: 8 bit
        out[name] = (fmt, w, h, d[data_at + doff:data_at + doff + nbytes])
        p += size
    return out


def _c565(c):
    return ((c >> 11 & 31) * 255 // 31, (c >> 5 & 63) * 255 // 63, (c & 31) * 255 // 31)


def decode(fmt, w, h, data, order="BGRA"):
    """RGBA picture of DXT1 (fmt 1), DXT5 (fmt 5) or uncompressed 32 bit data (fmt 6, byte order `order`; the logo is ARGB,
    the gamer picture BGRA); fmt 7 (8 bit) becomes white with that alpha"""
    if fmt == 6:
        return Image.frombuffer("RGBA", (w, h), data, "raw", order, 0, 1)
    if fmt == 7:
        img = Image.new("RGBA", (w, h), (255, 255, 255, 255))
        img.putalpha(Image.frombuffer("L", (w, h), data, "raw", "L", 0, 1))
        return img
    img = Image.new("RGBA", (w, h))
    px = img.load()
    i = 0
    for by in range(0, h, 4):
        for bx in range(0, w, 4):
            alpha = None
            if fmt == 5:
                a0, a1 = data[i], data[i + 1]
                abits = int.from_bytes(data[i + 2:i + 8], "little")
                if a0 > a1:
                    al = [a0, a1] + [((7 - k) * a0 + k * a1) // 7 for k in range(1, 7)]
                else:
                    al = [a0, a1] + [((5 - k) * a0 + k * a1) // 5 for k in range(1, 5)] + [0, 255]
                alpha = (abits, al)
                i += 8
            c0, c1, bits = struct.unpack_from("<HHI", data, i)
            i += 8
            a, b = _c565(c0), _c565(c1)
            if c0 > c1 or fmt == 5:
                pal = [a, b, tuple((2 * x + y) // 3 for x, y in zip(a, b)), tuple((x + 2 * y) // 3 for x, y in zip(a, b))]
            else:
                pal = [a, b, tuple((x + y) // 2 for x, y in zip(a, b)), (0, 0, 0)]
            for k in range(16):
                x, y = bx + k % 4, by + k // 4
                px[x, y] = pal[bits >> (2 * k) & 3] + ((alpha[1][alpha[0] >> (3 * k) & 7],) if alpha else (255,))
    return img
