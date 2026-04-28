import math
import random
import re
import struct
from typing import Dict, List, Optional, Tuple, Union

from ..models.config import RasterConfig
from ..models.triangle import Triangle
from .pb_rules import (
    INDEX_DATA_BITS,
    STRUCT_FIELD_OFFSETS,
    STRUCT_SCHEMAS,
    STRUCT_WIDTHS,
    enforce_bf_flag_zero,
    fields_with_offsets,
    get_control_word_values,
    get_filtered_state_block_members,
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

    point_mode = _parse_point_primblk_literal(text)
    coords = _parse_position_coord_literals(text)
    index_data = [] if point_mode else _parse_index_data_literals(text)
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
    this_is_point_primblk = random.getrandbits(1)
    words, index_data_start_bit = _build_template_words(len(vertices), len(index_words), this_is_point_primblk)
    emitted_index_words = [] if this_is_point_primblk else index_words
    for index, raw in enumerate(emitted_index_words):
        _write_bits(words, index_data_start_bit + index * INDEX_DATA_BITS, INDEX_DATA_BITS, raw)
    coord_start_bit = _coord_start_bit(index_data_start_bit, emitted_index_words, this_is_point_primblk)
    for index, vertex in enumerate(vertices):
        _write_bits(words, coord_start_bit + index * COORD_BITS, COORD_BITS, _pack_position_coord(vertex))

    # Rule 5: Enforce bf_flag=0 when isp_twosided=0
    if emitted_index_words:
        enforce_bf_flag_zero(words, len(triangles), index_data_start_bit)

    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(format_annotated_pb_dump(words, vertices, emitted_index_words, this_is_point_primblk))
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
) -> str:
    if index_words is None:
        index_words = []
    if this_is_point_primblk is None:
        this_is_point_primblk = 0 if index_words else 1
    primitive_count = len(index_words) if index_words else len(vertices) // 3
    parts = [
        "pb_instruction random block",
        _format_pb_instruction_table(words, len(vertices), primitive_count, this_is_point_primblk),
        "",
        "PB Dump v1 field tables",
        "",
        _format_unified_table(words, vertices, index_words, this_is_point_primblk),
        "Final 256-bit memory dump",
        format_memory_dump(words).rstrip(),
        "",
    ]
    return "\n".join(parts)


def _format_pb_instruction_table(
    words: Dict[int, int],
    vertex_count: int,
    primitive_count: int,
    this_is_point_primblk: int,
) -> str:
    rows = [_table_header()]
    primitive_values, primblk_values, prim_header_values = _build_pb_instruction_values(
        words,
        vertex_count,
        primitive_count,
        this_is_point_primblk,
    )

    rows.append(_table_parent_row("primitive_block_instruction", "primitive_block_instruction_c", "@5569182"))
    for name, width in PRIMITIVE_BLOCK_INSTRUCTION_FIELDS:
        rows.append(_table_row(name, "integral", width, primitive_values[name], "", indent=1))

    rows.append(_table_parent_row("primblk_cfg", "rgx_raster_primitive_block_cfg", "@1174", indent=1))
    for item in PRIMBLK_CFG_ROWS:
        if item == "prim_header":
            rows.append(_table_parent_row("prim_header", "integral", "", indent=2))
            for name, width in PRIM_HEADER_FIELDS:
                rows.append(_table_row(name, "integral", width, prim_header_values[name], "", indent=3))
            continue
        name, width = item
        rows.append(_table_row(name, "integral", width, primblk_values[name], "", indent=2))

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



def _build_pb_instruction_values(
    words: Dict[int, int],
    vertex_count: int,
    primitive_count: int,
    this_is_point_primblk: int,
) -> Tuple[Dict[str, int], Dict[str, int], Dict[str, int]]:
    control_values = get_control_word_values(words)
    filtered_members = get_filtered_state_block_members(words)
    state_names = {member.name for member in filtered_members}
    vertex_varying = _read_member_struct(words, filtered_members, "vertex_varying_comp_size")
    vertex_format_one = _read_member_struct(words, filtered_members, "vertex_position_comp_format_word_one")
    pds_word1 = _read_member_struct(words, filtered_members, "pds_state_word1")
    vf_vertex_total = max(0, min(vertex_count - 1, 63))
    cs_prim_total = max(0, min(primitive_count, 127))
    cs_mask_fmt = 2
    varying_number = 0x77
    primitive_values = {name: 0 for name, _ in PRIMITIVE_BLOCK_INSTRUCTION_FIELDS}
    primitive_values.update({
        "vf_vertex_total": vf_vertex_total,
        "cs_prim_total": cs_prim_total,
        "cs_mask_fmt": cs_mask_fmt,
        "this_is_point_primblk": this_is_point_primblk,
        "index_mask_visible_prim_number": 0 if this_is_point_primblk else cs_prim_total,
        "isp_scenable": control_values.get("isp_scenable", 0),
        "vf_vpt_id_pres": vertex_format_one.get("vf_vpt_id_pres", 0),
        "pds_douti": pds_word1.get("pds_douti", 0),
        "vf_prim_id_pres": vertex_format_one.get("vf_prim_id_pres", 0),
        "varying_number_per_vertex": varying_number,
        "cs_tsp_comp_format_size": vertex_varying.get("cs_tsp_comp_format_size", 0),
        "cs_tsp_comp_table_size": vertex_varying.get("cs_tsp_comp_table_size", 0),
        "cs_tsp_comp_vertex_size": vertex_varying.get("cs_tsp_comp_vertex_size", 0),
    })
    prim_header_values = {
        "cs_type": 0,
        "cs_isp_state_size": min(len(filtered_members), 127),
        "cs_prim_total": cs_prim_total,
        "cs_mask_fmt": cs_mask_fmt,
        "cs_prim_base_pres": 0,
        "cs_prim_base_offset": 0,
    }
    primblk_values = _default_primblk_cfg_values()
    prim_mask_word0 = _build_prim_mask_word(min(primitive_count, 4), 0)
    prim_mask_word1 = _build_prim_mask_word(max(0, min(primitive_count - 4, 4)), 4)
    prim_mask_word2 = _build_prim_mask_word(max(0, min(primitive_count - 8, 4)), 8)
    instruction_bits = sum(width for _, width in PRIMITIVE_BLOCK_INSTRUCTION_FIELDS)
    state_bits = sum(STRUCT_WIDTHS[member.schema_name] for member in filtered_members)
    payload_bits = STRUCT_WIDTHS["point_pitch_s"] if this_is_point_primblk else primitive_count * INDEX_DATA_BITS
    coord_bits = vertex_count * COORD_BITS
    primblk_values.update({
        "prim_mask_word0_exist": 1 if primitive_count > 0 else 0,
        "prim_mask_word1_exist": 1 if primitive_count > 4 else 0,
        "prim_mask_word2_exist": 1 if primitive_count > 8 else 0,
        "primblk_instruction_size": min(math.ceil((instruction_bits + state_bits + payload_bits + coord_bits) / 8), 1023),
        "isp_state_fb_exist": 1 if "isp_state_word_fb" in state_names else 0,
        "isp_state_ba_exist": 1 if "isp_state_word_ba" in state_names else 0,
        "isp_state_bb_exist": 1 if "isp_state_word_bb" in state_names else 0,
        "isp_state_csc_exist": 1 if "isp_state_word_csc" in state_names else 0,
        "isp_state_misc_exist": 1 if "isp_state_word_misc" in state_names else 0,
        "isp_state_dbmin_exist": 1 if "isp_state_word_dbmin" in state_names else 0,
        "isp_state_dbmax_exist": 1 if "isp_state_word_dbmax" in state_names else 0,
        "vertex_total_real": vf_vertex_total,
        "primitive_total_real": cs_prim_total,
        "ceil_half_vertex_total": min(math.ceil(vertex_count / 2), 63),
        "ceil_half_primitive_total": min(math.ceil(primitive_count / 2), 127),
        "varying_comp_format_number_total": varying_number,
        "prim_mask_word0": prim_mask_word0,
        "prim_mask_word1": prim_mask_word1,
        "prim_mask_word2": prim_mask_word2,
        "unmerged_byte_based_prim_mask_word0": prim_mask_word0,
        "unmerged_byte_based_prim_mask_word1": prim_mask_word1,
        "unmerged_byte_based_prim_mask_word2": prim_mask_word2,
    })
    for word_name, raw in (("prim_mask_word0", prim_mask_word0), ("prim_mask_word1", prim_mask_word1), ("prim_mask_word2", prim_mask_word2)):
        primblk_values[f"{word_name}.byte_mask"] = _extract_bits(raw, 0, 4)
        primblk_values[f"{word_name}.bit_mask"] = _extract_bits(raw, 4, 4)
    primblk_values.update({
        "prim_mask_word0.index_mask": _extract_bits(prim_mask_word0, 8, 8),
        "prim_mask_word0.reserved": _extract_bits(prim_mask_word0, 16, 4),
        "prim_mask_word0[0]": _extract_bits(prim_mask_word0, 20, 3),
        "prim_mask_word0[1]": _extract_bits(prim_mask_word0, 23, 3),
        "prim_mask_word0[2]": _extract_bits(prim_mask_word0, 26, 3),
        "prim_mask_word0[3]": _extract_bits(prim_mask_word0, 29, 3),
    })
    return primitive_values, primblk_values, prim_header_values


def _default_primblk_cfg_values() -> Dict[str, int]:
    values = {name: 0 for item in PRIMBLK_CFG_ROWS if item != "prim_header" for name, _ in [item]}
    for name in values:
        if name.endswith("_rate"):
            values[name] = 50
    values.update({
        "mt_cr_isp_msaa_rast_mode": 3,
        "mt_cr_isp_msaa_mode": 1,
        "effective_msaa_mode": 1,
        "mt_cr_frag_ctrl_screen_offset": 0xC400,
        "mt_cr_frag_ctrl_screen_guardband": 0x30D7,
        "mt_cr_frag_screen_xmax_real": 0x080D,
        "mt_cr_frag_screen_ymax_real": 0x000A,
        "mt_cr_context_mapping_pm_frag_vce": 0x1F,
        "mt_cr_context_mapping_frag_frag": 0x1F,
        "mt_cr_isp_pixel_base_addr": 0x2AC4,
        "mt_cr_isp_dbias_base_addr": 0x8048E3B78D0,
        "mt_cr_isp_scissor_base_addr": 0x167C08A22770,
        "cs_prim_total_zero_rate": 1,
        "cs_prim_total_nonzero_rate": 99,
        "enable_vertex_data_compress_rate": 0,
        "disable_vertex_data_compress_rate": 100,
        "enable_varying_data_compress_rate": 0,
        "disable_varying_data_compress_rate": 100,
    })
    return values


def _read_member_struct(words: Dict[int, int], members, member_name: str) -> Dict[str, int]:
    offset = 0
    for member in members:
        width = STRUCT_WIDTHS[member.schema_name]
        if member.name == member_name:
            return _unpack_struct(member.schema_name, _read_bits_with_default(words, offset, width))
        offset += width
    return {}


def _build_prim_mask_word(count: int, base_index: int) -> int:
    raw = 0
    mask = (1 << min(max(count, 0), 4)) - 1 if count > 0 else 0
    raw |= mask
    raw |= mask << 4
    raw |= mask << 8
    for slot in range(4):
        raw |= ((base_index + slot) & 0x7) << (20 + slot * 3)
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
            rows.extend(_format_struct_field_rows("index_data_s", raw, indent=2))
    
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


def _table_title(title: str) -> str:
    return title


def _table_parent_row(name: str, data_type: str, note: str = "", indent: int = 0) -> str:
    field_name = f"{'  ' * indent}{name}"
    note_text = " ".join(part for part in (_display_type_name(data_type), note) if part)
    return f"{field_name:<58} {'-':<24} {note_text}"


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


def _parse_point_primblk_literal(text: str) -> int:
    match = POINT_PRIMBLK_RE.search(text)
    return int(match.group(1)) if match else 0


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


def _coord_start_bit(payload_start_bit: int, index_words: List[int], this_is_point_primblk: int) -> int:
    if this_is_point_primblk:
        return payload_start_bit + STRUCT_WIDTHS["point_pitch_s"]
    return payload_start_bit + len(index_words) * INDEX_DATA_BITS


def _extract_position_coords_from_words(words: Dict[int, int]) -> List[Tuple[float, float, float]]:
    explicit_count = _extract_vertex_total(words)
    index_data_start_bit = _index_data_start_bit(words)
    primitive_count = explicit_count // 3 if explicit_count else _primitive_count_from_words(words, index_data_start_bit)
    index_words = [] if _has_point_pitch(words) else [0] * primitive_count
    coord_start_bit = _coord_start_bit(index_data_start_bit, index_words, _has_point_pitch(words))
    available_count = _available_position_coord_count(words, coord_start_bit)
    if explicit_count and explicit_count <= available_count:
        count = explicit_count
    else:
        count = available_count

    if count <= 0:
        raise ValueError("PB dump does not contain position coord data after index_data")

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


def _available_position_coord_count(words: Dict[int, int], coord_start_bit: int) -> int:
    count = 0
    while count < MAX_VERTEX_COUNT:
        start = coord_start_bit + count * COORD_BITS
        end = start + COORD_BITS - 1
        needed_words = range(start // 256, end // 256 + 1)
        if any(index not in words for index in needed_words):
            break
        count += 1
    return count


def _primitive_count_from_words(words: Dict[int, int], index_data_start_bit: int) -> int:
    max_bit = (max(words) + 1) * 256 if words else index_data_start_bit
    remaining_bits = max(0, max_bit - index_data_start_bit)
    return min(MAX_VERTEX_COUNT // 3, remaining_bits // (INDEX_DATA_BITS + 3 * COORD_BITS))


def _extract_vertex_total(words: Dict[int, int]) -> int:
    try:
        offset = 0
        for member in get_filtered_state_block_members(words):
            if member.name == "vertex_position_comp_format_word_one":
                field_offset = STRUCT_FIELD_OFFSETS["vertex_position_comp_format_word_one_s"]["vf_vertex_total"]
                encoded_total = _read_bits(words, offset + field_offset, 6)
                return encoded_total + 1 if encoded_total else 0
            offset += STRUCT_WIDTHS[member.schema_name]
    except ValueError:
        return 0
    return 0


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
