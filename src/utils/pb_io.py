import math
import random
import re
import struct
from typing import Dict, List, Optional, Tuple

from ..models.config import RasterConfig
from ..models.triangle import Triangle
from .pb_rules import (
    FULL_STATE_BLOCK_MEMBERS,
    INDEX_DATA_BITS,
    INDEX_DATA_START_BIT,
    STATE_BLOCK_MEMBER_OFFSETS,
    STRUCT_SCHEMAS,
    STRUCT_WIDTHS,
    VERTEX_TOTAL_BIT,
    StateBlockMember,
    enforce_bf_flag_zero,
    fields_with_offsets,
    get_filtered_state_block_members,
    randomize_state_dwords,
    state_members_with_offsets,
)

MEMORY_ASSIGNMENT_RE = re.compile(
    r"primitive_block_addr(?:\s*\+\s*(\d+))?\s*\]\s*=\s*256\s*'\s*h\s*([0-9a-fA-F_xXzZ?]+)",
    re.IGNORECASE,
)
POSITION_COORD_RE = re.compile(
    r"original_position_coord\s*\[\s*(\d+)\s*\].*?(?:80\s*)?'\s*h\s*([0-9a-fA-F_]+)",
    re.IGNORECASE,
)
INDEX_DATA_RE = re.compile(
    r"index_data\s*\[\s*(\d+)\s*\](?!\s*\.).*?(?:width\s*=\s*24\b.*?)?\'\s*h\s*([0-9a-fA-F_]+)",
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
    index_data = _parse_index_data_literals(text)
    if not coords:
        words = parse_memory_dump(text)
        coords = _extract_position_coords_from_words(words)
        if not index_data:
            primitive_count = len(coords) // 3
            index_data = _extract_index_data_from_words(words, primitive_count)

    if len(coords) < 3:
        raise ValueError("PB dump must contain at least 3 vertex position coords")

    triangles = _build_triangles(coords, index_data)
    if not triangles:
        raise ValueError("PB dump does not contain any complete triangle primitives")

    return RasterConfig(), triangles


def save_pb_dump(path: str, config: RasterConfig, triangles: List[Triangle]) -> None:
    del config
    vertices = [vertex for triangle in triangles for vertex in triangle.vertices]
    if not vertices:
        raise ValueError("No triangles to export")
    if len(vertices) > MAX_VERTEX_COUNT:
        raise ValueError(f"PB dump v1 supports at most {MAX_VERTEX_COUNT} vertices")

    index_words = [_pack_index_data(i * 3, i * 3 + 1, i * 3 + 2) for i in range(len(triangles))]
    words = _build_template_words(len(vertices), len(index_words))
    for index, raw in enumerate(index_words):
        _write_bits(words, INDEX_DATA_START_BIT + index * INDEX_DATA_BITS, INDEX_DATA_BITS, raw)
    for index, vertex in enumerate(vertices):
        _write_bits(words, COORD_START_BIT + index * COORD_BITS, COORD_BITS, _pack_position_coord(vertex))

    # Rule 5: Enforce bf_flag=0 when isp_twosided=0
    enforce_bf_flag_zero(words, len(triangles))

    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(format_annotated_pb_dump(words, vertices, index_words))
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


def format_annotated_pb_dump(
    words: Dict[int, int],
    vertices: List[Tuple[float, float, float]],
    index_words: Optional[List[int]] = None,
) -> str:
    if index_words is None:
        index_words = []
    parts = [
        "PB Dump v1 field tables",
        "",
        _format_unified_table(words, vertices, index_words),
        "Final 256-bit memory dump",
        format_memory_dump(words).rstrip(),
        "",
    ]
    return "\n".join(parts)


def _format_unified_table(
    words: Dict[int, int],
    vertices: List[Tuple[float, float, float]],
    index_words: List[int],
) -> str:
    rows = [_table_header()]
    
    # State block section with filtered members based on PB rules
    filtered_members = get_filtered_state_block_members(words)
    for member, offset in state_members_with_offsets(filtered_members):
        schema_width = STRUCT_WIDTHS[member.schema_name]
        raw = _read_bits_with_default(words, offset, schema_width)
        rows.append(_table_row(member.name, member.schema_name, schema_width, raw, ""))
        rows.extend(_format_struct_field_rows(member.schema_name, raw))
    
    # Index data section with index_data title (no value display)
    rows.append("index_data")
    for primitive_index, raw in enumerate(index_words):
        rows.append(_table_row(f"p[{primitive_index}]", "integral", INDEX_DATA_BITS, raw, "", indent=1))
        rows.extend(_format_struct_field_rows("index_data_s", raw, indent=2))
    
    # Position coord section with original_position_coord title (no value display)
    rows.append("original_position_coord")
    for index, vertex in enumerate(vertices):
        absolute_bit = COORD_START_BIT + index * COORD_BITS
        raw = _pack_position_coord(vertex)
        x_raw = _extract_bits(raw, 0, 24)
        y_raw = _extract_bits(raw, 24, 24)
        z_raw = _extract_bits(raw, 48, 32)
        rows.append(_table_row(f"v[{index}]", "integral", 80, raw, "", indent=1))
        rows.append(_table_row(f"x[{index}]", "integral", 24, x_raw, f"dec={vertex[0]:.6g}", indent=2))
        rows.append(_table_row(f"y[{index}]", "integral", 24, y_raw, f"dec={vertex[1]:.6g}", indent=2))
        rows.append(_table_row(f"z[{index}]", "integral", 32, z_raw, f"dec={vertex[2]:.6g}", indent=2))
    
    rows.append("")
    return "\n".join(rows)


def _format_struct_field_rows(schema_name: str, raw: int, indent: int = 1) -> List[str]:
    rows = []
    for field, offset in fields_with_offsets(STRUCT_SCHEMAS[schema_name]):
        field_raw = _extract_bits(raw, offset, field.width)
        rows.append(
            _table_row(
                field.name,
                "integral",
                field.width,
                field_raw,
                "",
                indent=indent,
            )
        )
    return rows


def _table_title(title: str) -> str:
    return title


def _table_header() -> str:
    return f"{'field':<58} {'values':<24} note"


def _table_row(name: str, data_type: str, width: int, value: int, bits: str, note: str = "", indent: int = 0) -> str:
    if data_type == "integral":
        field_name = name
        note_parts = [bits]
    else:
        field_name = name
        note_parts = [_display_type_name(data_type), bits]
    if note:
        note_parts.append(note)
    hex_width = (width + 3) // 4
    value_text = f"{width}'h{value:0{hex_width}x}"
    indented_name = f"{'  ' * indent}{field_name}"
    note_text = " ".join(note_parts)
    return f"{indented_name:<58} {value_text:<24} {note_text}"


def _display_type_name(data_type: str) -> str:
    name = data_type
    if name.endswith("_s"):
        name = name[:-2]
    if name.endswith("_word"):
        name = name[:-5]
    return name


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


def _parse_index_data_literals(text: str) -> List[int]:
    values = []
    for match in INDEX_DATA_RE.finditer(text):
        index = int(match.group(1))
        raw = int(match.group(2).replace("_", ""), 16)
        values.append((index, raw))
    return [raw for _, raw in sorted(values)]


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


def _extract_index_data_from_words(words: Dict[int, int], primitive_count: int) -> List[int]:
    index_words = []
    for primitive_index in range(primitive_count):
        raw = _read_bits(words, INDEX_DATA_START_BIT + primitive_index * INDEX_DATA_BITS, INDEX_DATA_BITS)
        index_words.append(raw)
    return index_words


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
    try:
        encoded_total = _read_bits(words, VERTEX_TOTAL_BIT, 6)
    except ValueError:
        return 0
    return encoded_total + 1 if encoded_total else 0


def _build_triangles(coords: List[Tuple[float, float, float]], index_data: List[int]) -> List[Triangle]:
    if index_data:
        triangles = []
        for primitive_index, raw in enumerate(index_data):
            fields = _unpack_index_data(raw)
            indices = [fields["ix_index_0"], fields["ix_index_1"], fields["ix_index_2"]]
            if any(index >= len(coords) for index in indices):
                raise ValueError(f"index_data[{primitive_index}] references a vertex outside original_position_coord")
            vertices = [coords[index] for index in indices]
            triangles.append(Triangle(vertices=vertices, color=DEFAULT_COLORS[primitive_index % len(DEFAULT_COLORS)]))
        return triangles

    usable_count = len(coords) - (len(coords) % 3)
    triangles = []
    for triangle_index in range(usable_count // 3):
        vertices = coords[triangle_index * 3:(triangle_index + 1) * 3]
        triangles.append(Triangle(vertices=vertices, color=DEFAULT_COLORS[triangle_index % len(DEFAULT_COLORS)]))
    return triangles


def _build_template_words(vertex_count: int, primitive_count: int) -> Dict[int, int]:
    end_bit = max(
        COORD_START_BIT + vertex_count * COORD_BITS,
        INDEX_DATA_START_BIT + primitive_count * INDEX_DATA_BITS,
    )
    word_count = max(2, math.ceil(end_bit / 256))
    # Initialize all words to 0, then randomize state block fields
    words = {index: 0 for index in range(word_count)}
    # Rule 7: Randomize all state block dwords (pds, isp, vertex format, point pitch)
    randomize_state_dwords(words)
    words[VERTEX_TOTAL_BIT // 256] = _set_bits(words.get(VERTEX_TOTAL_BIT // 256, 0), VERTEX_TOTAL_BIT % 256, 6, vertex_count - 1)
    for index in range(primitive_count):
        _write_bits(words, INDEX_DATA_START_BIT + index * INDEX_DATA_BITS, INDEX_DATA_BITS, 0)
    return words


def _pack_index_data(
    index0: int,
    index1: int,
    index2: int,
    edge_ab: int = 0,
    edge_bc: int = 0,
    edge_ca: int = 0,
    bf_flag: int = 0,
) -> int:
    for value in (index0, index1, index2):
        if value < 0 or value >= (1 << 6):
            raise ValueError(f"Index value {value} does not fit in 6 bits")
    return (
        index0
        | ((edge_ab & 0x1) << 6)
        | (index1 << 8)
        | ((edge_bc & 0x1) << 14)
        | (index2 << 16)
        | ((edge_ca & 0x1) << 22)
        | ((bf_flag & 0x1) << 23)
    )


def _unpack_index_data(raw: int) -> Dict[str, int]:
    return _unpack_struct("index_data_s", raw)


def _unpack_struct(schema_name: str, raw: int) -> Dict[str, int]:
    return {
        field.name: _extract_bits(raw, offset, field.width)
        for field, offset in fields_with_offsets(STRUCT_SCHEMAS[schema_name])
    }


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


def _read_bits_with_default(words: Dict[int, int], absolute_bit: int, width: int) -> int:
    result = 0
    written = 0
    while written < width:
        word_index = absolute_bit // 256
        offset = absolute_bit % 256
        chunk_width = min(width - written, 256 - offset)
        result |= _extract_bits(words.get(word_index, 0), offset, chunk_width) << written
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
