from __future__ import annotations

import pytest

from dl_toolkit.binio import BinaryFormatError, Reader, Writer


def test_writer_reader_roundtrip_primitives():
    writer = Writer()
    writer.u8(255).u16(65535).i16(-1).u32(4294967295).i32(-2).f32(0.5)
    reader = Reader(writer.data())
    assert reader.u8() == 255
    assert reader.u16() == 65535
    assert reader.i16() == -1
    assert reader.u32() == 4294967295
    assert reader.i32() == -2
    assert reader.f32() == pytest.approx(0.5)
    assert reader.remaining == 0


def test_arrays_roundtrip():
    writer = Writer().u16_array([1, 2, 3]).i16_array([-1, 0, 1]).u32_array([7, 8])
    reader = Reader(writer.data())
    assert reader.u16_array(3) == [1, 2, 3]
    assert reader.i16_array(3) == [-1, 0, 1]
    assert reader.u32_array(2) == [7, 8]


def test_fixed_str_pads_and_trims():
    data = Writer().fixed_str("abc", 8).data()
    assert data == b"abc\x00\x00\x00\x00\x00"
    assert Reader(data).fixed_str(8) == "abc"


def test_fixed_str_rejects_overflow():
    with pytest.raises(BinaryFormatError, match="не помещается"):
        Writer().fixed_str("abcdefgh", 8)


def test_fixed_str_without_terminator_reads_whole_field():
    assert Reader(b"abcd").fixed_str(4) == "abcd"


def test_cstr_roundtrip_and_absolute_read():
    data = Writer().cstr("привет").cstr("мир").data()
    reader = Reader(data)
    assert reader.cstr() == "привет"
    assert reader.cstr() == "мир"
    assert Reader(data).cstr_at(0) == "привет"


def test_cstr_without_terminator_raises():
    with pytest.raises(BinaryFormatError, match="NUL"):
        Reader(b"abc").cstr()


def test_cstr_at_rejects_bad_offset():
    with pytest.raises(BinaryFormatError, match="вне буфера"):
        Reader(b"abc\x00").cstr_at(99)


def test_cstr_at_unterminated_tail_returns_rest():
    assert Reader(b"\x00abc").cstr_at(1) == "abc"


def test_read_past_end_raises():
    with pytest.raises(BinaryFormatError, match="выходит за буфер"):
        Reader(b"\x01").u32()
    with pytest.raises(BinaryFormatError, match="выходит за буфер"):
        Reader(b"\x01").raw(4)
    with pytest.raises(BinaryFormatError, match="выходит за буфер"):
        Reader(b"\x01").f32()


def test_seek_bounds():
    reader = Reader(b"abcd")
    assert reader.seek(4).pos == 4
    with pytest.raises(BinaryFormatError, match="seek"):
        reader.seek(5)
    with pytest.raises(BinaryFormatError, match="seek"):
        reader.seek(-1)


def test_pad_to_extends_and_rejects_shrink():
    assert len(Writer().u8(1).pad_to(4).data()) == 4
    with pytest.raises(BinaryFormatError, match="длиннее"):
        Writer().u32(0).pad_to(2)


def test_len_helpers():
    assert len(Reader(b"abc")) == 3
    assert len(Writer().u16(1)) == 2
