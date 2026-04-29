import math
import random
from dataclasses import dataclass
import re
import struct
from typing import Dict, List, Optional, Tuple, Union

from ..models.config import RasterConfig
from ..models.triangle import Triangle
from .pb_rules import (
    INDEX_DATA_BITS,
    INDEX_DATA_FIELD_OFFSETS,
    STRUCT_FIELD_OFFSETS,
    STRUCT_SCHEMAS,
    STRUCT_WIDTHS,
    enforce_bf_flag_zero,
    fields_with_offsets,
    get_filtered_state_block_members,
    index_data_fields_with_offsets,
    state_members_with_offsets,
)

MEMORY_ASSIGNMENT_RE = re.compile(
    r"primitive_block_addr(?:\s*\+\s*(\d+))?\s*\]\s*=\s*256\s*'\s*h\s*([0-9a-fA-F_xXzZ?]+)",
    re.IGNORECASE,
)
POINT_PRIMBLK_RE = re.compile(
    r"this_is_point_primblk.*?(?:=\s*)?(?:1\s*'\s*h)?([01])",
    re.IGNORECASE,
)
POSITION_COORD_RE = re.compile(
    r"(?:original_position_coord|v)\s*\[\s*(\d+)\s*\].*?(?:80\s*)?'\s*h\s*([0-9a-fA-F_]+)",
    re.IGNORECASE,
)
INDEX_DATA_RE = re.compile(
    r"(?:index_data|p)\s*\[\s*(\d+)\s*\](?!\s*\.).*?(?:width\s*=\s*24\b.*?)?\'\s*h\s*([0-9a-fA-F_]+)",
    re.IGNORECASE,
)

COORD_BITS = 80
MAX_VERTEX_COUNT = 63
INDEX_DATA_COORD_ALIGNMENT_BITS = 32

DEFAULT_COLORS = [
    (255, 100, 100),
    (100, 255, 100),
    (100, 100, 255),
    (255, 255, 100),
    (255, 100, 255),
    (100, 255, 255),
]


@dataclass
class PbInstructionRandom:
    primitive_values: Dict[str, int]
    primblk_values: Dict[str, int]
    prim_header_values: Dict[str, int]

    @property
    def prim_header(self) -> int:
        return _pack_concat_fields(PRIM_HEADER_FIELDS, self.prim_header_values)

def load_pb_dump(
    path: str,
    output_path: Optional[str] = None,
    primitive_count: Optional[int] = None,
    vertex_count: Optional[int] = None,
) -> Tuple[RasterConfig, List[Triangle]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as exc:
        raise ValueError(f"Failed to read PB dump: {exc}") from exc

    if primitive_count is None:
        raise ValueError("primitive_count is required for PB dump import")
    if vertex_count is None:
        raise ValueError("vertex_count is required for PB dump import")
    if primitive_count < 0:
        raise ValueError("primitive_count must not be negative")
    if vertex_count < 1:
        raise ValueError("vertex_count must be at least 1")

    point_mode = _infer_point_mode_from_ispa_objtype_text(text)
    coords = _parse_position_coord_literals(text)
    index_data = [] if point_mode == 1 else _parse_index_data_literals(text)
    words: Optional[Dict[int, int]] = None

    if not coords or (point_mode == 0 and not index_data):
        words = parse_memory_dump(text)
        if point_mode is None:
            point_mode = _infer_point_mode_from_ispa_objtype_words(words)
        if point_mode is None:
            point_mode = _infer_point_mode_from_layout(words)
        if not coords:
            coords = _extract_position_coords_from_words(words, point_mode, primitive_count, vertex_count)
        if point_mode == 0 and not index_data:
            index_data = _extract_index_data_from_words(words, primitive_count)

    if len(coords) < 3:
        raise ValueError("PB dump must contain at least 3 vertex position coords")

    triangles = _build_triangles(coords, index_data)

    if output_path is not None:
        if words is None:
            words = parse_memory_dump(text)
        _write_parsed_pb_dump(output_path, words, coords, index_data, point_mode)

    return RasterConfig(), triangles


def save_pb_dump(path: str, config: RasterConfig, triangles: List[Triangle]) -> None:
    del config
    vertices = [vertex for triangle in triangles for vertex in triangle.vertices]
    if not vertices:
        raise ValueError("No triangles to export")
    if len(vertices) > MAX_VERTEX_COUNT:
        raise ValueError(f"PB dump v1 supports at most {MAX_VERTEX_COUNT} vertices")

    index_words = [_pack_index_data(i * 3, i * 3 + 1, i * 3 + 2) for i in range(len(triangles))]
    instruction = _randomize_pb_instruction()
    _apply_pb_instruction_constraints(instruction)
    this_is_point_primblk = instruction.primitive_values["this_is_point_primblk"]
    words, index_data_start_bit = _randomize_pb_memory(len(vertices), len(index_words), instruction)
    _enforce_ispa_objtype_consistency(words, this_is_point_primblk)
    emitted_index_words = [] if this_is_point_primblk else index_words
    for index, raw in enumerate(emitted_index_words):
        _write_bits(words, index_data_start_bit + index * INDEX_DATA_BITS, INDEX_DATA_BITS, raw)
    coord_start_bit = _coord_start_bit(index_data_start_bit, emitted_index_words, this_is_point_primblk)
    for index, vertex in enumerate(vertices):
        _write_bits(words, coord_start_bit + index * COORD_BITS, COORD_BITS, _pack_position_coord(vertex))

    _apply_pb_memory_constraints(words, emitted_index_words, len(triangles), index_data_start_bit)

    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(format_annotated_pb_dump(words, vertices, emitted_index_words, this_is_point_primblk, instruction))
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
    this_is_point_primblk: Optional[int] = None,
    instruction: Optional[PbInstructionRandom] = None,
) -> str:
    if index_words is None:
        index_words = []
    if this_is_point_primblk is None:
        this_is_point_primblk = 0 if index_words else 1
    if instruction is None:
        instruction = _randomize_pb_instruction()
        instruction.primitive_values["this_is_point_primblk"] = this_is_point_primblk
        _apply_pb_instruction_constraints(instruction)
    parts = [
        "pb_instruction random block",
        _format_pb_instruction_table(instruction),
        "",
        "PB Dump v1 field tables",
        "",
        _format_unified_table(words, vertices, index_words, this_is_point_primblk),
        "Final 256-bit memory dump",
        format_memory_dump(words).rstrip(),
        "",
    ]
    return "\n".join(parts)


def _write_parsed_pb_dump(
    output_path: str,
    words: Dict[int, int],
    coords: List[Tuple[float, float, float]],
    index_data: List[int],
    point_mode: int,
) -> None:
    content = format_parsed_pb_dump(words, coords, index_data, point_mode)
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
    except OSError as exc:
        raise ValueError(f"Failed to write parsed PB dump: {exc}") from exc


def format_parsed_pb_dump(
    words: Dict[int, int],
    coords: List[Tuple[float, float, float]],
    index_data: List[int],
    point_mode: int,
) -> str:
    parts = [
        "Parsed PB Dump from memory words",
        "",
        _format_unified_table(words, coords, index_data, point_mode),
        "Original 256-bit memory dump",
        format_memory_dump(words).rstrip(),
        "",
    ]
    return "\n".join(parts)


def _format_pb_instruction_table(instruction: PbInstructionRandom) -> str:
    rows = [_table_header()]
    primitive_values = instruction.primitive_values
    primblk_values = instruction.primblk_values
    prim_header_values = instruction.prim_header_values

    rows.append(_table_parent_row("primitive_block_instruction"))
    for name, width in PRIMITIVE_BLOCK_INSTRUCTION_FIELDS:
        rows.append(_table_row(name, "integral", width, primitive_values[name], "", indent=1))

    rows.append(_table_parent_row("primblk_cfg", indent=1))
    in_instruction_tail = False
    for item in PRIMBLK_CFG_ROWS:
        if item == "prim_header":
            rows.append(_table_row("prim_header", "integral", 32, instruction.prim_header, "", indent=1))
            for name, width in PRIM_HEADER_FIELDS:
                rows.append(_table_row(name, "integral", width, prim_header_values[name], "", indent=2))
            continue
        name, width = item
        if name == "primblk_start_byte_base_low_addr":
            in_instruction_tail = True
        indent = 1 if in_instruction_tail else 2
        parent_fields = PACKED_PRIMBLK_CFG_FIELDS.get(name)
        value = _pack_concat_fields(parent_fields, primblk_values) if parent_fields is not None else primblk_values[name]
        rows.append(_table_row(name, "integral", width, value, "", indent=indent))

    return "\n".join(rows)


PRIMITIVE_BLOCK_INSTRUCTION_FIELDS = (
    ("vf_vertex_total", 6),
    ("cs_prim_total", 7),
    ("cs_mask_fmt", 2),
    ("this_is_point_primblk", 1),
    ("index_mask_visible_prim_number", 7),
    ("isp_scenable", 1),
    ("vf_vpt_id_pres", 1),
    ("pds_douti", 1),
    ("vf_prim_id_pres", 1),
    ("varying_number_per_vertex", 8),
    ("cs_tsp_comp_format_size", 6),
    ("cs_tsp_comp_table_size", 10),
    ("cs_tsp_comp_vertex_size", 12),
    ("enable_vertex_data_compress", 1),
    ("enable_varying_data_compress", 1),
)


PRIM_HEADER_FIELDS = (
    ("cs_type", 2),
    ("cs_isp_state_size", 7),
    ("cs_prim_total", 7),
    ("cs_mask_fmt", 2),
    ("cs_prim_base_pres", 1),
    ("cs_prim_base_offset", 13),
)


PRIM_MASK_WORD0_FIELDS = (
    ("prim_mask_word0.byte_mask", 4),
    ("prim_mask_word0.bit_mask", 4),
    ("prim_mask_word0.index_mask", 8),
    ("prim_mask_word0.reserved", 4),
    ("prim_mask_word0[3]", 3),
    ("prim_mask_word0[2]", 3),
    ("prim_mask_word0[1]", 3),
    ("prim_mask_word0[0]", 3),
)


PRIM_MASK_WORD1_FIELDS = (
    ("prim_mask_word1.byte_mask", 4),
    ("prim_mask_word1.bit_mask", 4),
)


PRIM_MASK_WORD2_FIELDS = (
    ("prim_mask_word2.byte_mask", 4),
    ("prim_mask_word2.bit_mask", 4),
)


PACKED_PRIMBLK_CFG_FIELDS = {
    "prim_mask_word0": PRIM_MASK_WORD0_FIELDS,
    "prim_mask_word1": PRIM_MASK_WORD1_FIELDS,
    "prim_mask_word2": PRIM_MASK_WORD2_FIELDS,
}


PRIMBLK_CFG_ROWS: Tuple[Union[str, Tuple[str, int]], ...] = (
    ("mt_cr_isp_msaa_tir_en", 1),
    ("mt_cr_isp_msaa_rast_mode", 3),
    ("mt_cr_isp_msaa_mode", 2),
    ("effective_msaa_mode", 3),
    ("mt_cr_frag_ctrl_screen_offset", 16),
    ("mt_cr_frag_ctrl_screen_guardband", 16),
    ("mt_cr_frag_screen_xmax_real", 16),
    ("mt_cr_frag_screen_ymax_real", 16),
    ("mt_cr_context_mapping_pm_frag_vce", 5),
    ("mt_cr_context_mapping_frag_frag", 5),
    ("mt_cr_isp_pixel_base_addr", 14),
    ("mt_cr_isp_dbias_base_addr", 46),
    ("mt_cr_isp_scissor_base_addr", 46),
    ("mt_cr_isp_ctl_inner_mask_used_by_ps", 10),
    ("primblk_pds_douti_enable_rate", 32),
    ("primblk_pds_douti_disable_rate", 32),
    ("ispa_tagwrite_disable_on_rate", 32),
    ("ispa_tagwrite_disable_off_rate", 32),
    ("ispa_objtype_triangle_rate", 32),
    ("ispa_objtype_line_rate", 32),
    ("ispa_objtype_point_rate", 32),
    ("ispa_passtype_opaque_rate", 32),
    ("ispa_passtype_translucent_rate", 32),
    ("ispa_passtype_punchthrough_rate", 32),
    ("ispa_passtype_fast_punchthrough_rate", 32),
    ("ispa_dcmpmode_never_rate", 32),
    ("ispa_dcmpmode_less_rate", 32),
    ("ispa_dcmpmode_equal_rate", 32),
    ("ispa_dcmpmode_lessequal_rate", 32),
    ("ispa_dcmpmode_greater_rate", 32),
    ("ispa_dcmpmode_notequal_rate", 32),
    ("ispa_dcmpmode_greaterequal_rate", 32),
    ("ispa_dcmpmode_always_rate", 32),
    ("ispb_scmpmode_never_rate", 32),
    ("ispb_scmpmode_less_rate", 32),
    ("ispb_scmpmode_equal_rate", 32),
    ("ispb_scmpmode_lessequal_rate", 32),
    ("ispb_scmpmode_greater_rate", 32),
    ("ispb_scmpmode_notequal_rate", 32),
    ("ispb_scmpmode_greaterequal_rate", 32),
    ("ispb_scmpmode_always_rate", 32),
    ("isp_scenable_enable_rate", 32),
    ("isp_scenable_disable_rate", 32),
    ("isp_dbenable_enable_rate", 32),
    ("isp_dbenable_disable_rate", 32),
    ("isp_oqenable_enable_rate", 32),
    ("isp_oqenable_disable_rate", 32),
    ("isp_upass_enable_rate", 32),
    ("isp_upass_disable_rate", 32),
    ("isp_samplemask_enable_rate", 32),
    ("isp_samplemask_disable_rate", 32),
    ("cs_prim_total_zero_rate", 32),
    ("cs_prim_total_nonzero_rate", 32),
    ("enable_vertex_data_compress_rate", 32),
    ("disable_vertex_data_compress_rate", 32),
    ("enable_varying_data_compress_rate", 32),
    ("disable_varying_data_compress_rate", 32),
    ("primblk_start_byte_base_low_addr", 8),
    ("prim_mask_word0_exist", 1),
    ("prim_mask_word1_exist", 1),
    ("prim_mask_word2_exist", 1),
    ("primblk_instruction_size", 10),
    ("isp_state_fb_exist", 1),
    ("isp_state_ba_exist", 1),
    ("isp_state_bb_exist", 1),
    ("isp_state_csc_exist", 1),
    ("isp_state_misc_exist", 1),
    ("isp_state_dbmin_exist", 1),
    ("isp_state_dbmax_exist", 1),
    ("vertex_total_real", 6),
    ("primitive_total_real", 7),
    ("ceil_half_vertex_total", 6),
    ("ceil_half_primitive_total", 7),
    ("varying_comp_format_number_total", 8),
    "prim_header",
    ("primblk_base_addr", 40),
    ("prim_mask_word0", 32),
    ("prim_mask_word0.byte_mask", 4),
    ("prim_mask_word0.bit_mask", 4),
    ("prim_mask_word0.index_mask", 8),
    ("prim_mask_word0.reserved", 4),
    ("prim_mask_word0[3]", 3),
    ("prim_mask_word0[2]", 3),
    ("prim_mask_word0[1]", 3),
    ("prim_mask_word0[0]", 3),
    ("prim_mask_word1", 32),
    ("prim_mask_word1.byte_mask", 4),
    ("prim_mask_word1.bit_mask", 4),
    ("prim_mask_word2", 32),
    ("prim_mask_word2.byte_mask", 4),
    ("prim_mask_word2.bit_mask", 4),
    ("unmerged_byte_based_prim_mask_word0", 32),
    ("unmerged_byte_based_prim_mask_word1", 32),
    ("unmerged_byte_based_prim_mask_word2", 32),
)



def _randomize_pb_instruction() -> PbInstructionRandom:
    primitive_values = {
        name: random.getrandbits(width)
        for name, width in PRIMITIVE_BLOCK_INSTRUCTION_FIELDS
    }

    prim_header_values = {
        name: random.getrandbits(width)
        for name, width in PRIM_HEADER_FIELDS
    }

    primblk_values = _random_primblk_cfg_values()
    for name, fields in PACKED_PRIMBLK_CFG_FIELDS.items():
        primblk_values[name] = _pack_concat_fields(fields, primblk_values)
    return PbInstructionRandom(primitive_values, primblk_values, prim_header_values)


def _apply_pb_instruction_constraints(instruction: PbInstructionRandom) -> None:
    instruction.primitive_values["this_is_point_primblk"] &= 0x1


def _randomize_pb_memory(vertex_count: int, primitive_count: int, instruction: PbInstructionRandom) -> Tuple[Dict[int, int], int]:
    return _build_template_words(vertex_count, primitive_count, instruction.primitive_values["this_is_point_primblk"])


def _apply_pb_memory_constraints(
    words: Dict[int, int],
    emitted_index_words: List[int],
    triangle_count: int,
    index_data_start_bit: int,
) -> None:
    if emitted_index_words:
        enforce_bf_flag_zero(words, triangle_count, index_data_start_bit)


def _random_primblk_cfg_values() -> Dict[str, int]:
    values = {}
    for item in PRIMBLK_CFG_ROWS:
        if item == "prim_header":
            continue
        name, width = item
        if name in PACKED_PRIMBLK_CFG_FIELDS:
            continue
        values[name] = random.getrandbits(width)
    return values


def _pack_concat_fields(fields, values: Dict[str, int]) -> int:
    """Pack field values into a single integer, MSB-first (first field = highest bits).

    *fields* can be either ``Tuple[Tuple[str, int], ...]`` or
    ``Tuple[FieldSpec, ...]`` – both are accepted.
    """
    raw = 0
    total_width = sum(f.width if hasattr(f, 'width') else f[1] for f in fields)
    bit_pos = total_width
    for f in fields:
        if hasattr(f, 'width'):
            name, width = f.name, f.width
        else:
            name, width = f
        bit_pos -= width
        raw |= (values[name] & ((1 << width) - 1)) << bit_pos
    return raw


def _format_unified_table(
    words: Dict[int, int],
    vertices: List[Tuple[float, float, float]],
    index_words: List[int],
    this_is_point_primblk: int,
) -> str:
    rows = [_table_header()]
    
    # State block section with filtered members based on PB rules
    filtered_members = get_filtered_state_block_members(words)
    for member, offset in state_members_with_offsets(filtered_members):
        schema_width = STRUCT_WIDTHS[member.schema_name]
        raw = _read_bits_with_default(words, offset, schema_width)
        rows.append(_table_row(member.name, member.schema_name, schema_width, raw, ""))
        rows.extend(_format_struct_field_rows(member.schema_name, raw))
    
    if this_is_point_primblk:
        point_pitch_offset = sum(STRUCT_WIDTHS[member.schema_name] for member in filtered_members)
        raw = _read_bits_with_default(words, point_pitch_offset, STRUCT_WIDTHS["point_pitch_s"])
        rows.append(_table_row("point_pitch", "point_pitch_s", STRUCT_WIDTHS["point_pitch_s"], raw, ""))
        rows.extend(_format_struct_field_rows("point_pitch_s", raw))
    else:
        rows.append("index_data")
        for primitive_index, raw in enumerate(index_words):
            rows.append(_table_row(f"p[{primitive_index}]", "integral", INDEX_DATA_BITS, raw, "", indent=1))
            rows.extend(_format_index_data_field_rows(raw, indent=2))
        payload_start_bit = sum(STRUCT_WIDTHS[member.schema_name] for member in filtered_members)
        gap_start_bit = payload_start_bit + len(index_words) * INDEX_DATA_BITS
        gap_bits = _align_up(gap_start_bit, INDEX_DATA_COORD_ALIGNMENT_BITS) - gap_start_bit
        if gap_bits:
            gap_raw = _read_bits_with_default(words, gap_start_bit, gap_bits)
            rows.append(_table_row("index_data_to_coord_alignment", "integral", gap_bits, gap_raw, "align original_position_coord to 32-bit boundary", indent=1))

    # Position coord section with original_position_coord title (no value display)
    rows.append("original_position_coord")
    for index, vertex in enumerate(vertices):
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


def _format_index_data_field_rows(raw: int, indent: int = 1) -> List[str]:
    rows = []
    for field, offset in index_data_fields_with_offsets():
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


def _table_parent_row(name: str, indent: int = 0) -> str:
    field_name = f"{'  ' * indent}{name}"
    return f"{field_name:<58} {'-':<24}"


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


def _parse_point_primblk_literal(text: str) -> Optional[int]:
    match = POINT_PRIMBLK_RE.search(text)
    return int(match.group(1)) if match else None


POINT_OBJTYPE_VALUES = {2, 3, 4, 6}

_ISPA_OBJTYPE_RE = re.compile(
    r"ispa_objtype\s+.*?(?:\d+)\s*'\s*h\s*([0-9a-fA-F]+)",
    re.IGNORECASE,
)


def _infer_point_mode_from_ispa_objtype_text(text: str) -> Optional[int]:
    match = _ISPA_OBJTYPE_RE.search(text)
    if match:
        objtype = int(match.group(1), 16)
        return 1 if objtype in POINT_OBJTYPE_VALUES else 0
    return None


def _infer_point_mode_from_ispa_objtype_words(words: Dict[int, int]) -> Optional[int]:
    try:
        filtered_members = get_filtered_state_block_members(words)
        offset = 0
        for member in filtered_members:
            if member.name == "isp_state_word_fa":
                fa_raw = _read_bits_with_default(words, offset, STRUCT_WIDTHS["isp_state_word_a_s"])
                objtype = _extract_bits(fa_raw, STRUCT_FIELD_OFFSETS["isp_state_word_a_s"]["ispa_objtype"], 4)
                return 1 if objtype in POINT_OBJTYPE_VALUES else 0
            offset += STRUCT_WIDTHS[member.schema_name]
    except (ValueError, KeyError):
        pass
    return None


def _enforce_ispa_objtype_consistency(words: Dict[int, int], this_is_point_primblk: int) -> None:
    try:
        filtered_members = get_filtered_state_block_members(words)
        offset = 0
        for member in filtered_members:
            if member.name == "isp_state_word_fa":
                fa_raw = _read_bits_with_default(words, offset, STRUCT_WIDTHS["isp_state_word_a_s"])
                objtype = _extract_bits(fa_raw, STRUCT_FIELD_OFFSETS["isp_state_word_a_s"]["ispa_objtype"], 4)
                is_point_objtype = objtype in POINT_OBJTYPE_VALUES
                if this_is_point_primblk and not is_point_objtype:
                    new_objtype = 2
                    new_fa = (fa_raw & ~(0xF << STRUCT_FIELD_OFFSETS["isp_state_word_a_s"]["ispa_objtype"])) | (new_objtype << STRUCT_FIELD_OFFSETS["isp_state_word_a_s"]["ispa_objtype"])
                    _write_bits(words, offset, STRUCT_WIDTHS["isp_state_word_a_s"], new_fa)
                elif not this_is_point_primblk and is_point_objtype:
                    new_objtype = 1
                    new_fa = (fa_raw & ~(0xF << STRUCT_FIELD_OFFSETS["isp_state_word_a_s"]["ispa_objtype"])) | (new_objtype << STRUCT_FIELD_OFFSETS["isp_state_word_a_s"]["ispa_objtype"])
                    _write_bits(words, offset, STRUCT_WIDTHS["isp_state_word_a_s"], new_fa)
                return
            offset += STRUCT_WIDTHS[member.schema_name]
    except (ValueError, KeyError):
        pass


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


def _point_pitch_start_bit(words: Dict[int, int]) -> int:
    return sum(STRUCT_WIDTHS[member.schema_name] for member in get_filtered_state_block_members(words))


def _index_data_start_bit(words: Dict[int, int]) -> int:
    return _point_pitch_start_bit(words)


def _has_point_pitch(words: Dict[int, int]) -> int:
    return 1 if _extract_bits(_read_bits_with_default(words, _point_pitch_start_bit(words), STRUCT_WIDTHS["point_pitch_s"]), 0, STRUCT_WIDTHS["point_pitch_s"]) else 0


def _resolve_point_mode(words: Dict[int, int], point_mode: Optional[int]) -> int:
    if point_mode is not None:
        return point_mode
    from_ispa = _infer_point_mode_from_ispa_objtype_words(words)
    if from_ispa is not None:
        return from_ispa
    return _infer_point_mode_from_layout(words)


def _infer_point_mode_from_layout(words: Dict[int, int]) -> int:
    return _has_point_pitch(words)


def _align_up(value: int, alignment: int) -> int:
    return ((value + alignment - 1) // alignment) * alignment


def _coord_start_bit(payload_start_bit: int, index_words: List[int], this_is_point_primblk: int) -> int:
    if this_is_point_primblk:
        return payload_start_bit + STRUCT_WIDTHS["point_pitch_s"]
    index_data_end_bit = payload_start_bit + len(index_words) * INDEX_DATA_BITS
    return _align_up(index_data_end_bit, INDEX_DATA_COORD_ALIGNMENT_BITS)


def _extract_position_coords_from_words(
    words: Dict[int, int],
    this_is_point_primblk: Optional[int] = None,
    primitive_count: Optional[int] = None,
    vertex_count: Optional[int] = None,
) -> List[Tuple[float, float, float]]:
    if this_is_point_primblk is None:
        return _extract_position_coords_from_words(words, _infer_point_mode_from_layout(words), primitive_count, vertex_count)

    index_data_start_bit = _index_data_start_bit(words)
    point_mode = this_is_point_primblk
    if point_mode:
        emitted_primitive_count = 0
    else:
        emitted_primitive_count = primitive_count
    index_words = [] if point_mode else [0] * emitted_primitive_count
    coord_start_bit = _coord_start_bit(index_data_start_bit, index_words, point_mode)
    available_count = _available_position_coord_count(words, coord_start_bit, vertex_count)
    if vertex_count > available_count:
        raise ValueError("PB dump does not contain enough original_position_coord data for the provided vertex count")
    count = vertex_count

    if count <= 0:
        raise ValueError("PB dump does not contain complete original_position_coord data for the resolved PB layout")

    coords = []
    for index in range(count):
        raw = _read_bits(words, coord_start_bit + index * COORD_BITS, COORD_BITS)
        coords.append(_unpack_position_coord(raw))
    return coords


def _extract_index_data_from_words(words: Dict[int, int], primitive_count: int) -> List[int]:
    index_data_start_bit = _index_data_start_bit(words)
    index_words = []
    for primitive_index in range(primitive_count):
        raw = _read_bits(words, index_data_start_bit + primitive_index * INDEX_DATA_BITS, INDEX_DATA_BITS)
        index_words.append(raw)
    return index_words


def _available_position_coord_count(words: Dict[int, int], coord_start_bit: int, max_count: int) -> int:
    count = 0
    while count < max_count:
        start = coord_start_bit + count * COORD_BITS
        end = start + COORD_BITS - 1
        needed_words = range(start // 256, end // 256 + 1)
        if any(index not in words for index in needed_words):
            break
        count += 1
    return count


def _build_triangles(coords: List[Tuple[float, float, float]], index_data: List[int]) -> List[Triangle]:
    if index_data:
        triangles = []
        for primitive_index, raw in enumerate(index_data):
            fields = _unpack_index_data(raw)
            indices = [fields["ix_index_0"], fields["ix_index_1"], fields["ix_index_2"]]
            if any(index >= len(coords) for index in indices):
                continue
            vertices = [coords[index] for index in indices]
            triangles.append(Triangle(vertices=vertices, color=DEFAULT_COLORS[primitive_index % len(DEFAULT_COLORS)]))
        return triangles

    usable_count = len(coords) - (len(coords) % 3)
    triangles = []
    for triangle_index in range(usable_count // 3):
        vertices = coords[triangle_index * 3:(triangle_index + 1) * 3]
        triangles.append(Triangle(vertices=vertices, color=DEFAULT_COLORS[triangle_index % len(DEFAULT_COLORS)]))
    return triangles


def _build_template_words(vertex_count: int, primitive_count: int, this_is_point_primblk: int) -> Tuple[Dict[int, int], int]:
    words: Dict[int, int] = {}
    offset = 0

    def append_random(schema_name: str) -> int:
        nonlocal offset
        raw = _random_struct(schema_name)
        _write_bits(words, offset, STRUCT_WIDTHS[schema_name], raw)
        offset += STRUCT_WIDTHS[schema_name]
        return raw

    append_random("pds_state_word0_s")
    append_random("pds_state_word1_s")
    control_raw = append_random("isp_state_control_word_s")
    control_values = _unpack_struct("isp_state_control_word_s", control_raw)

    append_random("isp_state_word_a_s")
    if control_values["isp_bpres"]:
        append_random("isp_state_word_b_s")
    if control_values["isp_twosided"]:
        append_random("isp_state_word_a_s")
        if control_values["isp_bpres"]:
            append_random("isp_state_word_b_s")
    if control_values["isp_samplemaskenable"] or control_values["isp_dbenable"] or control_values["isp_scenable"]:
        append_random("isp_state_word_csc_s")
    if control_values["isp_miscenable"]:
        misc_raw = append_random("isp_state_word_misc_s")
        misc_values = _unpack_struct("isp_state_word_misc_s", misc_raw)
        if misc_values["dbt_op"] != 0:
            append_random("isp_state_word_dbmin_s")
            append_random("isp_state_word_dbmax_s")

    append_random("vertex_varying_comp_size_word_s")
    append_random("vertex_position_comp_format_word_zero_s")
    vert_fmt1_offset = offset
    append_random("vertex_position_comp_format_word_one_s")

    _write_bits(
        words,
        vert_fmt1_offset + STRUCT_FIELD_OFFSETS["vertex_position_comp_format_word_one_s"]["vf_vertex_total"],
        6,
        vertex_count - 1,
    )

    if this_is_point_primblk:
        append_random("point_pitch_s")
        emitted_primitive_count = 0
    else:
        emitted_primitive_count = primitive_count

    index_data_start_bit = offset - (STRUCT_WIDTHS["point_pitch_s"] if this_is_point_primblk else 0)
    coord_start_bit = _coord_start_bit(index_data_start_bit, [0] * emitted_primitive_count, this_is_point_primblk)
    end_bit = max(coord_start_bit + vertex_count * COORD_BITS, index_data_start_bit + emitted_primitive_count * INDEX_DATA_BITS)
    word_count = max(2, math.ceil(end_bit / 256))
    for index in range(word_count):
        words.setdefault(index, 0)
    for index in range(emitted_primitive_count):
        _write_bits(words, index_data_start_bit + index * INDEX_DATA_BITS, INDEX_DATA_BITS, 0)
    return words, index_data_start_bit


def _random_struct(schema_name: str) -> int:
    raw = 0
    for field, offset in fields_with_offsets(STRUCT_SCHEMAS[schema_name]):
        raw = _set_bits(raw, offset, field.width, random.getrandbits(field.width))
    return raw


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
    offsets = INDEX_DATA_FIELD_OFFSETS
    return (
        (index0 << offsets["ix_index_0"])
        | ((edge_ab & 0x1) << offsets["ix_edge_flag_ab"])
        | (index1 << offsets["ix_index_1"])
        | ((edge_bc & 0x1) << offsets["ix_edge_flag_bc"])
        | (index2 << offsets["ix_index_2"])
        | ((edge_ca & 0x1) << offsets["ix_edge_flag_ca"])
        | ((bf_flag & 0x1) << offsets["ix_bf_flag"])
    )


def _unpack_index_data(raw: int) -> Dict[str, int]:
    return {
        field.name: _extract_bits(raw, offset, field.width)
        for field, offset in index_data_fields_with_offsets()
    }


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
    minimum = 0
    maximum = (1 << 24) - 1
    if scaled < minimum or scaled > maximum:
        raise ValueError(f"Unsigned Q16.8 24-bit coordinate out of range: {value}")
    return scaled


def _unpack_q16_8_24(raw: int) -> float:
    return (raw & 0xFFFFFF) / 256.0


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
    return value & ((1 << 256) - 1)


def _format_sv_256_literal(value: int) -> str:
    if value < 0 or value >= (1 << 256):
        raise ValueError("Memory word does not fit in 256 bits")
    return f"{value:064x}"
