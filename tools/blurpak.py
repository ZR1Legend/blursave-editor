"""Read-only reader for Blur's PAK files (cache/*.pak, magic "2KAP").

The format is described in the Blur Map Builder (MIT licence, (c) 2026 MDPRO), pak/pak.py; this is a small re-implementation
of the reading part. Directory: entries sorted by hash; names XOR-scrambled; data zlib (one stream for 0x40-byte entries,
64 KB chunks of raw deflate for 0x28-byte entries).
"""
import mmap
import struct
import zlib

KEY = b"VXo40j3@$%\\%`x"
NO_DATA = 0xFFFFFFFFFFFFFFFF


class Pak:
    def __init__(self, path):
        with open(path, "rb") as f:
            self.d = d = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)     # mapped: root.pak is 500+ MB
        if d[:4] != b"2KAP":
            raise ValueError("not a PAK file: %s" % path)
        self.align = struct.unpack_from("<I", d, 8)[0]
        self.esize = 0x40 if d[0x11] == 1 else 0x28
        pos = 0x38
        nsize = struct.unpack_from("<I", d, pos)[0]
        if nsize == 0:
            pos = self.align
            nsize = struct.unpack_from("<I", d, pos)[0]
        names = bytes(c ^ KEY[i % len(KEY)] for i, c in enumerate(d[pos + 4:pos + 4 + nsize]))
        dir_off = (pos + 4 + nsize + self.align - 1) // self.align * self.align
        count = struct.unpack_from("<I", d, dir_off)[0]
        self.files = {}
        for i in range(count):
            a = dir_off + 8 + self.esize * i
            _, noff, _, size, _, off, _, zsize = struct.unpack_from("<IIIIQQII", d, a)
            name = names[noff:names.index(b"\0", noff)].decode("latin1").replace("\\", "/").lower()
            self.files[name] = (size, off, zsize)

    def close(self):
        self.d.close()

    def names(self, prefix=""):
        return [n for n in self.files if n.startswith(prefix.lower())]

    def read(self, name):
        """bytes of `name` (e.g. "/ui/data/ipf/car_icons_a.ipf"), None if the entry has no data"""
        size, off, zsize = self.files[name.replace("\\", "/").lower()]
        if off == NO_DATA:
            return None
        raw = self.d[off * self.align:off * self.align + zsize]
        if self.esize == 0x40:
            return zlib.decompress(raw)[:size]
        out, at = bytearray(), 4                       # 0x28 packs: u32 chunk size, then [u32 length + raw deflate]
        while at < len(raw):
            n = struct.unpack_from("<I", raw, at)[0]
            out += zlib.decompressobj(-15).decompress(raw[at + 4:at + 4 + n])
            at += 4 + n
        return bytes(out)[:size]
