import math
import re
import struct
from typing import Dict, List, Tuple

from ..models.config import RasterConfig
from ..models.triangle import Triangle

MEMORY_ASSIGNMENT_RE = re.compile(
    r"primitive_block_addr(?:\s*\+\s*(\d+))?\s*\]\s*=\s*256\s*'\s*h\s*([0-9a-fA-F_xXzZ?]+)",
    re.IGNORECASE,
)
POSITION_COORD_RE = re.compile(
    r"original_position_coord\s*\[\s*(\d+)\s*\].*?(?:80\s*)?'\s*h\s*([0-9a-fA-F_]+)",
    re.IGNORECASE,
)

COORD_BITS = 80
COORD_START_BIT = 6 * 256 + 16 * 8
MAX_VERTEX_COUNT = 63
DEFAULT_TEMPLATE_WORDS = {
    0: int("1a17933f8ed7ee08e155437004c47d4221dfffffc26040906625765eb8dcda1d", 16),
    1: int("eecc4149d6779dd058786c350afa46613d45534204e8bd8888888888af000ee0", 16),
}
DEFAULT_COLORS = [
    (255, 100, 100),
    (100, 255, 100),
    (100, 100, 255),
    (255, 255, 100),
    (255, 100, 255),
    (100, 255, 255),
]


def load_pb_dump(path: str) -> Tuple[RasterConfig, List[Triangle]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as exc:
        raise ValueError(f"Failed to read PB dump: {exc}") from exc

    coords = _parse_position_coord_literals(text)
    if not coords:
        words = parse_memory_dump(text)
        coords = _extract_position_coords_from_words(words)

    if len(coords) < 3:
        raise ValueError("PB dump must contain at least 3 vertex position coords")

    usable_count = len(coords) - (len(coords) % 3)
    triangles = []
    for triangle_index in range(usable_count // 3):
        vertices = coords[triangle_index * 3:(triangle_index + 1) * 3]
        triangles.append(Triangle(vertices=vertices, color=DEFAULT_COLORS[triangle_index % len(DEFAULT_COLORS)]))

    return RasterConfig(), triangles


def save_pb_dump(path: str, config: RasterConfig, triangles: List[Triangle]) -> None:
    del config
    vertices = [vertex for triangle in triangles for vertex in triangle.vertices]
    if not vertices:
        raise ValueError("No triangles to export")
    if len(vertices) > MAX_VERTEX_COUNT:
        raise ValueError(f"PB dump v1 supports at most {MAX_VERTEX_COUNT} vertices")

    words = _build_template_words(len(vertices))
    for index, vertex in enumerate(vertices):
        _write_bits(words, COORD_START_BIT + index * COORD_BITS, COORD_BITS, _pack_position_coord(vertex))

    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(format_annotated_pb_dump(words, vertices))
    except OSError as exc:
        raise ValueError(f"Failed to write PB dump: {exc}") from exc


def parse_memory_dump(text: str) -> Dict[int, int]:
    words: Dict[int, int] = {}
    for line in text.splitlines():
        match = MEMORY_ASSIGNMENT_RE.search(line)
        if not match:
            continue
        index = int(match.group(1) or "0")
        literal = match.group(2).replace("_", "")
        literal = re.sub(r"[xXzZ?]", "0", literal)
        words[index] = _parse_sv_256_literal(literal)

    if not words:
        raise ValueError("No 256'h primitive_block_addr memory assignments found")
    return words


def format_memory_dump(words: Dict[int, int]) -> str:
    lines = []
    for index in sorted(words):
        suffix = "" if index == 0 else f"+{index}"
        lines.append(
            f"randomized_3d_memory[frag_vce][primitive_block_addr{suffix}] = "
            f"256'h{_format_sv_256_literal(words[index])} ;"
        )
    return "\n".join(lines) + "\n"


def format_annotated_pb_dump(words: Dict[int, int], vertices: List[Tuple[float, float, float]]) -> str:
    parts = [
        "// ============================================================",
        "// PB Dump v1 field tables",
        "// 256'h literals are printed high-bit on the left; bit0 is the rightmost nibble.",
        "// The final memory dump at the end is generated from the field rows below.",
        "// ============================================================",
        "",
        _format_header_table(words),
        _format_position_coord_table(vertices),
        "// ============================================================",
        "// Final 256-bit memory dump",
        "// ============================================================",
        format_memory_dump(words).rstrip(),
        "",
    ]
    return "\n".join(parts)


def _format_header_table(words: Dict[int, int]) -> str:
    rows = [
        "// Header/template fields",
        _field_row("pds_state_word0", "integral", 32, _extract_bits(words.get(0, 0), 0, 32), "addr+0[31:0]"),
        _field_row("pds_state_word1", "integral", 32, _extract_bits(words.get(0, 0), 32, 32), "addr+0[63:32]"),
        _field_row("isp_state_control_word", "integral", 64, _extract_bits(words.get(0, 0), 64, 64), "addr+0[127:64]"),
        _field_row("isp_state_word_fa", "integral", 32, _extract_bits(words.get(0, 0), 128, 32), "addr+0[159:128]"),
        _field_row("isp_state_word_misc", "integral", 32, _extract_bits(words.get(0, 0), 160, 32), "addr+0[191:160]"),
        _field_row("isp_state_word_dbmin", "integral", 32, _extract_bits(words.get(0, 0), 192, 32), "addr+0[223:192]"),
        _field_row("isp_state_word_dbmax", "integral", 32, _extract_bits(words.get(0, 0), 224, 32), "addr+0[255:224]"),
        _field_row("vertex_varying_comp_size_word", "integral", 32, _extract_bits(words.get(1, 0), 0, 32), "addr+1[31:0]"),
        _field_row("vertex_position_comp_format_word_zero", "integral", 32, _extract_bits(words.get(1, 0), 32, 32), "addr+1[63:32]"),
        _field_row("vertex_position_comp_format_word_one", "integral", 32, _extract_bits(words.get(1, 0), 64, 32), "addr+1[95:64]"),
        "",
    ]
    return "\n".join(rows)


def _format_position_coord_table(vertices: List[Tuple[float, float, float]]) -> str:
    rows = ["// original_position_coord table"]
    for index, vertex in enumerate(vertices):
        absolute_bit = COORD_START_BIT + index * COORD_BITS
        raw = _pack_position_coord(vertex)
        x_raw = _extract_bits(raw, 0, 24)
        y_raw = _extract_bits(raw, 24, 24)
        z_raw = _extract_bits(raw, 48, 32)
        rows.append(_field_row(f"original_position_coord[{index}]", "da(integral)", 80, raw, _bit_range_label(absolute_bit, COORD_BITS)))
        rows.append(_field_row(f"  x[{index}]", "q16.8", 24, x_raw, f"{_bit_range_label(absolute_bit, 24)} dec={vertex[0]:.6g}"))
        rows.append(_field_row(f"  y[{index}]", "q16.8", 24, y_raw, f"{_bit_range_label(absolute_bit + 24, 24)} dec={vertex[1]:.6g}"))
        rows.append(_field_row(f"  z[{index}]", "fp32", 32, z_raw, f"{_bit_range_label(absolute_bit + 48, 32)} dec={vertex[2]:.6g}"))
    rows.append("")
    return "\n".join(rows)


def _field_row(name: str, data_type: str, width: int, value: int, note: str) -> str:
    hex_width = (width + 3) // 4
    return f"// {name:<42} {data_type:<12} width={width:<3} value='h{value:0{hex_width}x}  {note}"


def _bit_range_label(absolute_bit: int, width: int) -> str:
    start_word = absolute_bit // 256
    start_offset = absolute_bit % 256
    end_bit = absolute_bit + width - 1
    end_word = end_bit // 256
    end_offset = end_bit % 256
    if start_word == end_word:
        return f"addr+{start_word}[{end_offset}:{start_offset}]"
    return f"addr+{start_word}[255:{start_offset}]..addr+{end_word}[{end_offset}:0]"


def _parse_position_coord_literals(text: str) -> List[Tuple[float, float, float]]:
    values = []
    for match in POSITION_COORD_RE.finditer(text):
        index = int(match.group(1))
        raw = int(match.group(2).replace("_", ""), 16)
        values.append((index, _unpack_position_coord(raw)))
    return [coord for _, coord in sorted(values)]


def _extract_position_coords_from_words(words: Dict[int, int]) -> List[Tuple[float, float, float]]:
    explicit_count = _extract_vertex_total(words)
    available_count = _available_position_coord_count(words)
    if explicit_count and explicit_count <= available_count:
        count = explicit_count
    else:
        count = available_count

    if count <= 0:
        raise ValueError("PB dump does not contain position coord data at the Doc1 v1 offset")

    coords = []
    for index in range(count):
        raw = _read_bits(words, COORD_START_BIT + index * COORD_BITS, COORD_BITS)
        coords.append(_unpack_position_coord(raw))
    return coords


def _available_position_coord_count(words: Dict[int, int]) -> int:
    count = 0
    while count < MAX_VERTEX_COUNT:
        start = COORD_START_BIT + count * COORD_BITS
        end = start + COORD_BITS - 1
        needed_words = range(start // 256, end // 256 + 1)
        if any(index not in words for index in needed_words):
            break
        count += 1
    return count


def _extract_vertex_total(words: Dict[int, int]) -> int:
    word = words.get(1)
    if word is None:
        return 0
    encoded_total = _extract_bits(word, 64 + 8, 6)
    return encoded_total + 1 if encoded_total else 0


def _build_template_words(vertex_count: int) -> Dict[int, int]:
    end_bit = COORD_START_BIT + vertex_count * COORD_BITS
    word_count = max(2, math.ceil(end_bit / 256))
    words = {index: DEFAULT_TEMPLATE_WORDS.get(index, 0) for index in range(word_count)}
    words[1] = _set_bits(words[1], 64 + 8, 6, vertex_count - 1)
    return words


def _pack_position_coord(vertex: Tuple[float, float, float]) -> int:
    x, y, z = vertex
    return (
        _pack_q16_8_24(x)
        | (_pack_q16_8_24(y) << 24)
        | (_pack_fp32(z) << 48)
    )


def _unpack_position_coord(raw: int) -> Tuple[float, float, float]:
    x = _unpack_q16_8_24(_extract_bits(raw, 0, 24))
    y = _unpack_q16_8_24(_extract_bits(raw, 24, 24))
    z = _unpack_fp32(_extract_bits(raw, 48, 32))
    return x, y, z


def _pack_q16_8_24(value: float) -> int:
    scaled = int(round(value * 256.0))
    minimum = -(1 << 23)
    maximum = (1 << 23) - 1
    if scaled < minimum or scaled > maximum:
        raise ValueError(f"Q16.8 24-bit coordinate out of range: {value}")
    return scaled & 0xFFFFFF


def _unpack_q16_8_24(raw: int) -> float:
    raw &= 0xFFFFFF
    if raw & 0x800000:
        raw -= 1 << 24
    return raw / 256.0


def _pack_fp32(value: float) -> int:
    return struct.unpack(">I", struct.pack(">f", float(value)))[0]


def _unpack_fp32(raw: int) -> float:
    return struct.unpack(">f", raw.to_bytes(4, "big"))[0]


def _read_bits(words: Dict[int, int], absolute_bit: int, width: int) -> int:
    result = 0
    written = 0
    while written < width:
        word_index = absolute_bit // 256
        offset = absolute_bit % 256
        chunk_width = min(width - written, 256 - offset)
        if word_index not in words:
            raise ValueError(f"Missing primitive_block_addr+{word_index} for position coord data")
        result |= _extract_bits(words[word_index], offset, chunk_width) << written
        absolute_bit += chunk_width
        written += chunk_width
    return result


def _write_bits(words: Dict[int, int], absolute_bit: int, width: int, field: int) -> None:
    written = 0
    while written < width:
        word_index = absolute_bit // 256
        offset = absolute_bit % 256
        chunk_width = min(width - written, 256 - offset)
        chunk = _extract_bits(field, written, chunk_width)
        words[word_index] = _set_bits(words.get(word_index, 0), offset, chunk_width, chunk)
        absolute_bit += chunk_width
        written += chunk_width


def _extract_bits(value: int, offset: int, width: int) -> int:
    if width <= 0:
        return 0
    return (value >> offset) & ((1 << width) - 1)


def _set_bits(target: int, offset: int, width: int, field: int) -> int:
    if field < 0 or field >= (1 << width):
        raise ValueError(f"Field value 0x{field:x} does not fit in {width} bits")
    mask = ((1 << width) - 1) << offset
    return (target & ~mask) | (field << offset)


def _parse_sv_256_literal(hex_text: str) -> int:
    value = int(hex_text, 16)
    if value >= (1 << 256):
        raise ValueError("256'h literal exceeds 256 bits")
    return value


def _format_sv_256_literal(value: int) -> str:
    if value < 0 or value >= (1 << 256):
        raise ValueError("Memory word does not fit in 256 bits")
    return f"{value:064x}"
