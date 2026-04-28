import math
import re
import struct
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

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


@dataclass(frozen=True)
class FieldSpec:
    name: str
    width: int


@dataclass(frozen=True)
class StateBlockMember:
    name: str
    schema_name: str


STRUCT_SCHEMAS: Dict[str, Tuple[FieldSpec, ...]] = {
    "pds_state_word0_s": (
        FieldSpec("pds_fragment_addr", 28),
        FieldSpec("reserved", 4),
    ),
    "pds_state_word1_s": (
        FieldSpec("pds_douti", 1),
        FieldSpec("reserved", 11),
        FieldSpec("pds_index", 20),
    ),
    "isp_state_control_word_s": (
        FieldSpec("reserved", 13),
        FieldSpec("pt_upfront_depth_disable", 1),
        FieldSpec("vptgroup_id", 1),
        FieldSpec("depthclamp_en", 1),
        FieldSpec("isp_upass", 16),
        FieldSpec("inputcoverage_en", 1),
        FieldSpec("isp_miscenable", 1),
        FieldSpec("isp_samplemaskenable", 1),
        FieldSpec("isp_perfenable", 1),
        FieldSpec("isp_upass_reserved", 8),
        FieldSpec("isp_twosided", 1),
        FieldSpec("isp_bpres", 1),
        FieldSpec("isp_dbenable", 1),
        FieldSpec("isp_scenable", 1),
        FieldSpec("isp_oqenable", 1),
        FieldSpec("isp_oqboolean", 1),
        FieldSpec("isp_oqindex", 14),
    ),
    "isp_state_word_a_s": (
        FieldSpec("ispa_objtype", 4),
        FieldSpec("ispa_passtype", 3),
        FieldSpec("ispa_tagwritedisable", 1),
        FieldSpec("reserved", 2),
        FieldSpec("ispa_dwritedisable", 1),
        FieldSpec("ispa_dfbztestenable", 1),
        FieldSpec("ispa_dcmpmode", 3),
        FieldSpec("ispa_linefilllastpixel", 1),
        FieldSpec("ispa_pointlinewidth", 8),
        FieldSpec("ispa_sreference", 8),
    ),
    "isp_state_word_b_s": (
        FieldSpec("reserved", 4),
        FieldSpec("ispb_scmpmode", 3),
        FieldSpec("ispb_sop1", 3),
        FieldSpec("ispb_sop2", 3),
        FieldSpec("ispb_sop3", 3),
        FieldSpec("ispb_scmpmask", 8),
        FieldSpec("ispb_swmask", 8),
    ),
    "isp_state_word_csc_s": (
        FieldSpec("isp_cindex", 16),
        FieldSpec("isp_scindex", 16),
    ),
    "isp_state_word_misc_s": (
        FieldSpec("reserved", 7),
        FieldSpec("ps_query_slot", 14),
        FieldSpec("ps_query_enable", 1),
        FieldSpec("dbt_op", 2),
        FieldSpec("sr_comb_op", 3),
        FieldSpec("per_draw_sr", 4),
        FieldSpec("per_prim_sr_en", 1),
    ),
    "isp_state_word_dbmin_s": (FieldSpec("depth_bound_min", 32),),
    "isp_state_word_dbmax_s": (FieldSpec("depth_bound_max", 32),),
    "vertex_varying_comp_size_word_s": (
        FieldSpec("reserved", 4),
        FieldSpec("cs_tsp_comp_format_size", 6),
        FieldSpec("cs_tsp_comp_table_size", 10),
        FieldSpec("cs_tsp_comp_vertex_size", 12),
    ),
    "vertex_position_comp_format_word_zero_s": (
        FieldSpec("cs_isp_comp_format_z1", 4),
        FieldSpec("cs_isp_comp_format_z0", 4),
        FieldSpec("cs_isp_comp_format_y1", 4),
        FieldSpec("cs_isp_comp_format_y0", 4),
        FieldSpec("cs_isp_comp_format_x2", 4),
        FieldSpec("cs_isp_comp_format_x1", 4),
        FieldSpec("cs_isp_comp_format_x0", 4),
    ),
    "vertex_position_comp_format_word_one_s": (
        FieldSpec("reserved", 14),
        FieldSpec("vf_vpt_id_pres", 1),
        FieldSpec("vf_prim_msaa_disable", 1),
        FieldSpec("vf_prim_id_pres", 1),
        FieldSpec("vf_vertex_clipped", 1),
        FieldSpec("vf_vertex_total", 6),
        FieldSpec("cf_isp_comp_format_z3", 4),
        FieldSpec("cf_isp_comp_format_z2", 4),
    ),
    "point_pitch_s": (
        FieldSpec("pp_padjust1", 3),
        FieldSpec("pp_pitch1", 13),
        FieldSpec("pp_padjust0", 3),
        FieldSpec("pp_pitch0", 13),
    ),
    "index_data_s": (
        FieldSpec("ix_index_0", 6),
        FieldSpec("ix_edge_flag_ab", 1),
        FieldSpec("reserved0", 1),
        FieldSpec("ix_index_1", 6),
        FieldSpec("ix_edge_flag_bc", 1),
        FieldSpec("reserved1", 1),
        FieldSpec("ix_index_2", 6),
        FieldSpec("ix_edge_flag_ca", 1),
        FieldSpec("ix_bf_flag", 1),
    ),
}

FULL_STATE_BLOCK_MEMBERS = (
    StateBlockMember("pds_w0", "pds_state_word0_s"),
    StateBlockMember("pds_w1", "pds_state_word1_s"),
    StateBlockMember("isp_ctrl", "isp_state_control_word_s"),
    StateBlockMember("isp_a", "isp_state_word_a_s"),
    StateBlockMember("isp_b", "isp_state_word_b_s"),
    StateBlockMember("isp_csc", "isp_state_word_csc_s"),
    StateBlockMember("isp_misc", "isp_state_word_misc_s"),
    StateBlockMember("db_min", "isp_state_word_dbmin_s"),
    StateBlockMember("db_max", "isp_state_word_dbmax_s"),
    StateBlockMember("vert_cmp_size", "vertex_varying_comp_size_word_s"),
    StateBlockMember("vert_fmt0", "vertex_position_comp_format_word_zero_s"),
    StateBlockMember("vert_fmt1", "vertex_position_comp_format_word_one_s"),
    StateBlockMember("pt_pitch", "point_pitch_s"),
)

STRUCT_WIDTHS = {name: sum(field.width for field in fields) for name, fields in STRUCT_SCHEMAS.items()}
STRUCT_FIELD_OFFSETS: Dict[str, Dict[str, int]] = {}
for _schema_name, _fields in STRUCT_SCHEMAS.items():
    _offset = 0
    STRUCT_FIELD_OFFSETS[_schema_name] = {}
    for _field in _fields:
        STRUCT_FIELD_OFFSETS[_schema_name][_field.name] = _offset
        _offset += _field.width

STATE_BLOCK_MEMBER_OFFSETS: Dict[str, int] = {}
_offset = 0
for _member in FULL_STATE_BLOCK_MEMBERS:
    STATE_BLOCK_MEMBER_OFFSETS[_member.name] = _offset
    _offset += STRUCT_WIDTHS[_member.schema_name]
FULL_STATE_BLOCK_BITS = _offset
INDEX_DATA_BITS = STRUCT_WIDTHS["index_data_s"]
INDEX_DATA_START_BIT = FULL_STATE_BLOCK_BITS
VERTEX_TOTAL_BIT = (
    STATE_BLOCK_MEMBER_OFFSETS["vert_fmt1"]
    + STRUCT_FIELD_OFFSETS["vertex_position_comp_format_word_one_s"]["vf_vertex_total"]
)


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
        "// ============================================================",
        "// PB Dump v1 field tables",
        "// 256'h literals are printed high-bit on the left; bit0 is the rightmost nibble.",
        "// Field rows follow gpu_isp_pds_bif_pkg packed struct order from low bit to high bit.",
        "// The final memory dump at the end is generated from the field rows below.",
        "// ============================================================",
        "",
        _format_state_block_table(words),
        _format_index_data_table(index_words),
        _format_position_coord_table(vertices),
        "// ============================================================",
        "// Final 256-bit memory dump",
        "// ============================================================",
        format_memory_dump(words).rstrip(),
        "",
    ]
    return "\n".join(parts)


def _fields_with_offsets(fields: Iterable[FieldSpec]) -> Iterable[Tuple[FieldSpec, int]]:
    offset = 0
    for field in fields:
        yield field, offset
        offset += field.width


def _state_members_with_offsets(members: Iterable[StateBlockMember]) -> Iterable[Tuple[StateBlockMember, int]]:
    offset = 0
    for member in members:
        yield member, offset
        offset += STRUCT_WIDTHS[member.schema_name]


def _format_state_block_table(words: Dict[int, int]) -> str:
    rows = ["// gpu_isp_full_state_block_s"]
    for member, offset in _state_members_with_offsets(FULL_STATE_BLOCK_MEMBERS):
        schema_width = STRUCT_WIDTHS[member.schema_name]
        raw = _read_bits_with_default(words, offset, schema_width)
        rows.append(_field_row(member.name, member.schema_name, schema_width, raw, _bit_range_label(offset, schema_width)))
        rows.extend(_format_struct_field_rows(member.name, member.schema_name, raw, offset))
    rows.append("")
    return "\n".join(rows)


def _format_index_data_table(index_words: List[int]) -> str:
    rows = ["// index_data_s table"]
    for primitive_index, raw in enumerate(index_words):
        absolute_bit = INDEX_DATA_START_BIT + primitive_index * INDEX_DATA_BITS
        rows.append(_field_row(f"index_data[{primitive_index}]", "index_data_s", INDEX_DATA_BITS, raw, _bit_range_label(absolute_bit, INDEX_DATA_BITS)))
        rows.extend(_format_struct_field_rows(f"  index_data[{primitive_index}]", "index_data_s", raw, absolute_bit))
    rows.append("")
    return "\n".join(rows)


def _format_struct_field_rows(prefix: str, schema_name: str, raw: int, absolute_bit: int) -> List[str]:
    rows = []
    for field, offset in _fields_with_offsets(STRUCT_SCHEMAS[schema_name]):
        field_raw = _extract_bits(raw, offset, field.width)
        rows.append(
            _field_row(
                f"{prefix}.{field.name}",
                "integral",
                field.width,
                field_raw,
                _bit_range_label(absolute_bit + offset, field.width),
            )
        )
    return rows


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
    return f"// {name:<54} {data_type:<42} width={width:<3} value='h{value:0{hex_width}x}  {note}"


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
    words = {index: DEFAULT_TEMPLATE_WORDS.get(index, 0) for index in range(word_count)}
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
        for field, offset in _fields_with_offsets(STRUCT_SCHEMAS[schema_name])
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
