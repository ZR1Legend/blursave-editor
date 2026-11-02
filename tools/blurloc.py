"""Reader for the game's text files (gamedata/xt/loc/*.loc, magic "OLTX").

Layout (little-endian): "OLTX", u32 version (1), u32 0x10; at 0x10: u32 ?, u32 language count (5), u32 ?; then at 0x1c
one 24-byte entry per language (16-byte code "en", ..., u32 offset, u32 size) and, right behind them, the key table.
A table is [u32 count][u32 8] followed by `count` pairs [u32 hash][u32 offset]; offsets are relative to the table.
The key table's offsets point to the key names (ASCII, NUL-terminated), a language table's offsets to the texts
(UTF-16LE, NUL-terminated). The same hash joins a key to its text. The hash function itself is unknown (not CRC32,
FNV, djb2 ...), so keys are joined through the tables, not computed.
"""
import struct


def read_loc(path, lang="en"):
    """{key name: text} of one .loc file (path, or the file's bytes)"""
    d = path if isinstance(path, bytes) else open(path, "rb").read()
    if d[:4] != b"OLTX":
        raise ValueError("not an OLTX file: %s" % (path if isinstance(path, str) else "<bytes>"))
    u = lambda o: struct.unpack_from("<I", d, o)[0]
    nlang = u(0x14)
    ktab = 0x1c + 24 * nlang                       # the key table follows the language entries
    langs = {}
    for i in range(nlang):
        e = 0x1c + 24 * i
        code = d[e:e + 16].split(b"\0")[0].decode("ascii")
        langs[code] = u(e + 16)
    if lang not in langs:
        raise ValueError("language %r not in %s (has %s)" % (lang, path, sorted(langs)))
    key_of = {}
    for i in range(u(ktab)):
        h, o = u(ktab + 8 + 8 * i), u(ktab + 12 + 8 * i)
        key_of[h] = d[ktab + o:d.index(b"\0", ktab + o)].decode("ascii", "replace")
    base, out = langs[lang], {}
    for i in range(u(base)):
        h, o = u(base + 8 + 8 * i), u(base + 12 + 8 * i)
        a = base + o
        e = a
        while d[e:e + 2] != b"\0\0" or (e - a) % 2:
            e += 1
        out[key_of.get(h, "#%08x" % h)] = d[a:e].decode("utf-16le", "replace")
    return out
