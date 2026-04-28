from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple
import random


@dataclass(frozen=True)
class FieldSpec:
    name: str
    width: int


@dataclass(frozen=True)
class StateBlockMember:
    name: str
    schema_name: str
    emit_when: str = "always"


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
    StateBlockMember("pds_state_word0", "pds_state_word0_s"),
    StateBlockMember("pds_state_word1", "pds_state_word1_s"),
    StateBlockMember("isp_state_control", "isp_state_control_word_s"),
    StateBlockMember("isp_state_word_fa", "isp_state_word_a_s"),
    StateBlockMember("isp_state_word_fb", "isp_state_word_b_s"),
    StateBlockMember("isp_state_word_ba", "isp_state_word_a_s"),
    StateBlockMember("isp_state_word_bb", "isp_state_word_b_s"),
    StateBlockMember("isp_state_word_csc", "isp_state_word_csc_s"),
    StateBlockMember("isp_state_word_misc", "isp_state_word_misc_s"),
    StateBlockMember("isp_state_word_dbmin", "isp_state_word_dbmin_s"),
    StateBlockMember("isp_state_word_dbmax", "isp_state_word_dbmax_s"),
    StateBlockMember("vertex_varying_comp_size", "vertex_varying_comp_size_word_s"),
    StateBlockMember("vertex_position_comp_format_word_zero", "vertex_position_comp_format_word_zero_s"),
    StateBlockMember("vertex_position_comp_format_word_one", "vertex_position_comp_format_word_one_s"),
    StateBlockMember("point_pitch", "point_pitch_s"),
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
    STATE_BLOCK_MEMBER_OFFSETS["vertex_position_comp_format_word_one"]
    + STRUCT_FIELD_OFFSETS["vertex_position_comp_format_word_one_s"]["vf_vertex_total"]
)


def fields_with_offsets(fields: Iterable[FieldSpec]) -> Iterable[tuple[FieldSpec, int]]:
    offset = 0
    for field in fields:
        yield field, offset
        offset += field.width


def state_members_with_offsets(members: Iterable[StateBlockMember] = FULL_STATE_BLOCK_MEMBERS) -> Iterable[tuple[StateBlockMember, int]]:
    offset = 0
    for member in members:
        yield member, offset
        offset += STRUCT_WIDTHS[member.schema_name]


# =============================================================================
# PB Rules: Conditional state block member visibility and randomization
# =============================================================================

def get_field_value(words: Dict[int, int], absolute_bit: int, width: int) -> int:
    """Extract a field value from the words dictionary."""
    from .pb_io import _read_bits_with_default
    return _read_bits_with_default(words, absolute_bit, width)


def get_control_word_values(words: Dict[int, int]) -> Dict[str, int]:
    """Extract all control word field values from isp_state_control."""
    from .pb_io import _read_bits_with_default
    control_offset = STATE_BLOCK_MEMBER_OFFSETS["isp_state_control"]
    raw = _read_bits_with_default(words, control_offset, STRUCT_WIDTHS["isp_state_control_word_s"])
    return {
        field.name: (raw >> STRUCT_FIELD_OFFSETS["isp_state_control_word_s"][field.name]) & ((1 << field.width) - 1)
        for field in STRUCT_SCHEMAS["isp_state_control_word_s"]
    }


def get_filtered_state_block_members(words: Dict[int, int]) -> List[StateBlockMember]:
    """Get state block members filtered by PB rules.
    
    Rules:
    1. If isp_miscenable=1 then isp_state_word_misc exists, otherwise not.
    2. If isp_miscenable=1 and dbt_op!=0, then isp_state_word_dbmin and isp_state_word_dbmax exist.
    3. If isp_samplemaskenable or isp_dbenable or isp_scenable is 1, then isp_state_word_csc exists.
    4. If isp_twosided=1, then isp_state_word_ba exists. If isp_bpres=1, then isp_state_word_bb also exists.
    5. If isp_twosided=0, then all prim's ix_bf_flag in index_data = 0.
    6. If isp_bpres=1, then isp_state_word_fb exists.
    7. pds_state and isp_state dwords all default to random.
    """
    control_values = get_control_word_values(words)
    
    isp_miscenable = control_values.get("isp_miscenable", 0)
    isp_samplemaskenable = control_values.get("isp_samplemaskenable", 0)
    isp_dbenable = control_values.get("isp_dbenable", 0)
    isp_scenable = control_values.get("isp_scenable", 0)
    isp_twosided = control_values.get("isp_twosided", 0)
    isp_bpres = control_values.get("isp_bpres", 0)
    
    # Get dbt_op from misc word if misc is enabled
    dbt_op = 0
    if isp_miscenable:
        misc_offset = STATE_BLOCK_MEMBER_OFFSETS["isp_state_word_misc"]
        from .pb_io import _read_bits_with_default
        misc_raw = _read_bits_with_default(words, misc_offset, STRUCT_WIDTHS["isp_state_word_misc_s"])
        dbt_op = (misc_raw >> STRUCT_FIELD_OFFSETS["isp_state_word_misc_s"]["dbt_op"]) & ((1 << 2) - 1)
    
    # Base members that always exist (pds_state words)
    result = [
        StateBlockMember("pds_state_word0", "pds_state_word0_s"),
        StateBlockMember("pds_state_word1", "pds_state_word1_s"),
    ]
    
    # isp_state_control always exists
    result.append(StateBlockMember("isp_state_control", "isp_state_control_word_s"))
    
    # Rule 7: pds_state dwords default to random
    _randomize_pds_state(words)
    
    # Rule 6: If isp_bpres=1, then isp_state_word_fb exists
    if isp_bpres:
        result.append(StateBlockMember("isp_state_word_fb", "isp_state_word_b_s"))
    
    # isp_state_word_fa always exists (front face a)
    result.append(StateBlockMember("isp_state_word_fa", "isp_state_word_a_s"))
    
    # Rule 4: If isp_twosided=1, then isp_state_word_ba exists
    if isp_twosided:
        result.append(StateBlockMember("isp_state_word_ba", "isp_state_word_a_s"))
        # Rule 4: If isp_bpres=1, then isp_state_word_bb also exists
        if isp_bpres:
            result.append(StateBlockMember("isp_state_word_bb", "isp_state_word_b_s"))
    
    # Rule 3: If isp_samplemaskenable or isp_dbenable or isp_scenable is 1, then isp_state_word_csc exists
    if isp_samplemaskenable or isp_dbenable or isp_scenable:
        result.append(StateBlockMember("isp_state_word_csc", "isp_state_word_csc_s"))
    
    # Rule 1: If isp_miscenable=1 then isp_state_word_misc exists
    if isp_miscenable:
        result.append(StateBlockMember("isp_state_word_misc", "isp_state_word_misc_s"))
        
        # Rule 2: If isp_miscenable=1 and dbt_op!=0, then dbmin/dbmax exist
        if dbt_op != 0:
            result.append(StateBlockMember("isp_state_word_dbmin", "isp_state_word_dbmin_s"))
            result.append(StateBlockMember("isp_state_word_dbmax", "isp_state_word_dbmax_s"))
    
    # Always add these members
    result.extend([
        StateBlockMember("vertex_varying_comp_size", "vertex_varying_comp_size_word_s"),
        StateBlockMember("vertex_position_comp_format_word_zero", "vertex_position_comp_format_word_zero_s"),
        StateBlockMember("vertex_position_comp_format_word_one", "vertex_position_comp_format_word_one_s"),
        StateBlockMember("point_pitch", "point_pitch_s"),
    ])
    
    return result


def _randomize_pds_state(words: Dict[int, int]) -> None:
    """Rule 7: Randomize pds_state dwords - randomize each sub-field individually."""
    from .pb_io import _write_bits
    pds_w0_offset = STATE_BLOCK_MEMBER_OFFSETS["pds_state_word0"]
    pds_w1_offset = STATE_BLOCK_MEMBER_OFFSETS["pds_state_word1"]
    
    # Randomize pds_state_word0 sub-fields
    for field in STRUCT_SCHEMAS["pds_state_word0_s"]:
        field_offset = STRUCT_FIELD_OFFSETS["pds_state_word0_s"][field.name]
        random_value = random.getrandbits(field.width)
        _write_bits(words, pds_w0_offset + field_offset, field.width, random_value)
    
    # Randomize pds_state_word1 sub-fields
    for field in STRUCT_SCHEMAS["pds_state_word1_s"]:
        field_offset = STRUCT_FIELD_OFFSETS["pds_state_word1_s"][field.name]
        random_value = random.getrandbits(field.width)
        _write_bits(words, pds_w1_offset + field_offset, field.width, random_value)


def _randomize_isp_state(words: Dict[int, int]) -> None:
    """Rule 7: Randomize isp_state dwords - randomize each sub-field individually."""
    from .pb_io import _write_bits
    
    # Randomize isp_state_control word sub-fields
    control_offset = STATE_BLOCK_MEMBER_OFFSETS["isp_state_control"]
    for field in STRUCT_SCHEMAS["isp_state_control_word_s"]:
        field_offset = STRUCT_FIELD_OFFSETS["isp_state_control_word_s"][field.name]
        random_value = random.getrandbits(field.width)
        _write_bits(words, control_offset + field_offset, field.width, random_value)
    
    # Always randomize isp_state_word_fa
    fa_offset = STATE_BLOCK_MEMBER_OFFSETS["isp_state_word_fa"]
    for field in STRUCT_SCHEMAS["isp_state_word_a_s"]:
        field_offset = STRUCT_FIELD_OFFSETS["isp_state_word_a_s"][field.name]
        random_value = random.getrandbits(field.width)
        _write_bits(words, fa_offset + field_offset, field.width, random_value)
    
    # Randomize isp_state_word_fb (exists when isp_bpres=1)
    fb_offset = STATE_BLOCK_MEMBER_OFFSETS["isp_state_word_fb"]
    for field in STRUCT_SCHEMAS["isp_state_word_b_s"]:
        field_offset = STRUCT_FIELD_OFFSETS["isp_state_word_b_s"][field.name]
        random_value = random.getrandbits(field.width)
        _write_bits(words, fb_offset + field_offset, field.width, random_value)
    
    # Randomize isp_state_word_ba (exists when isp_twosided=1)
    ba_offset = STATE_BLOCK_MEMBER_OFFSETS["isp_state_word_ba"]
    for field in STRUCT_SCHEMAS["isp_state_word_a_s"]:
        field_offset = STRUCT_FIELD_OFFSETS["isp_state_word_a_s"][field.name]
        random_value = random.getrandbits(field.width)
        _write_bits(words, ba_offset + field_offset, field.width, random_value)
    
    # Randomize isp_state_word_bb (exists when isp_twosided=1 and isp_bpres=1)
    bb_offset = STATE_BLOCK_MEMBER_OFFSETS["isp_state_word_bb"]
    for field in STRUCT_SCHEMAS["isp_state_word_b_s"]:
        field_offset = STRUCT_FIELD_OFFSETS["isp_state_word_b_s"][field.name]
        random_value = random.getrandbits(field.width)
        _write_bits(words, bb_offset + field_offset, field.width, random_value)
    
    # Randomize isp_state_word_csc (exists when isp_samplemaskenable or isp_dbenable or isp_scenable)
    csc_offset = STATE_BLOCK_MEMBER_OFFSETS["isp_state_word_csc"]
    for field in STRUCT_SCHEMAS["isp_state_word_csc_s"]:
        field_offset = STRUCT_FIELD_OFFSETS["isp_state_word_csc_s"][field.name]
        random_value = random.getrandbits(field.width)
        _write_bits(words, csc_offset + field_offset, field.width, random_value)
    
    # Randomize isp_state_word_misc (exists when isp_miscenable=1)
    misc_offset = STATE_BLOCK_MEMBER_OFFSETS["isp_state_word_misc"]
    for field in STRUCT_SCHEMAS["isp_state_word_misc_s"]:
        field_offset = STRUCT_FIELD_OFFSETS["isp_state_word_misc_s"][field.name]
        random_value = random.getrandbits(field.width)
        _write_bits(words, misc_offset + field_offset, field.width, random_value)
    
    # Randomize isp_state_word_dbmin (exists when isp_miscenable=1 and dbt_op!=0)
    dbmin_offset = STATE_BLOCK_MEMBER_OFFSETS["isp_state_word_dbmin"]
    for field in STRUCT_SCHEMAS["isp_state_word_dbmin_s"]:
        field_offset = STRUCT_FIELD_OFFSETS["isp_state_word_dbmin_s"][field.name]
        random_value = random.getrandbits(field.width)
        _write_bits(words, dbmin_offset + field_offset, field.width, random_value)
    
    # Randomize isp_state_word_dbmax (exists when isp_miscenable=1 and dbt_op!=0)
    dbmax_offset = STATE_BLOCK_MEMBER_OFFSETS["isp_state_word_dbmax"]
    for field in STRUCT_SCHEMAS["isp_state_word_dbmax_s"]:
        field_offset = STRUCT_FIELD_OFFSETS["isp_state_word_dbmax_s"][field.name]
        random_value = random.getrandbits(field.width)
        _write_bits(words, dbmax_offset + field_offset, field.width, random_value)


def enforce_bf_flag_zero(words: Dict[int, int], primitive_count: int) -> None:
    """Rule 5: If isp_twosided=0, then all prim's ix_bf_flag in index_data = 0."""
    control_values = get_control_word_values(words)
    isp_twosided = control_values.get("isp_twosided", 0)
    
    if isp_twosided == 0:
        from .pb_io import _read_bits_with_default, _write_bits
        for prim_index in range(primitive_count):
            prim_offset = INDEX_DATA_START_BIT + prim_index * INDEX_DATA_BITS
            current = _read_bits_with_default(words, prim_offset, INDEX_DATA_BITS)
            # Clear ix_bf_flag (bit 23)
            current &= ~(1 << 23)
            _write_bits(words, prim_offset, INDEX_DATA_BITS, current)


def randomize_state_dwords(words: Dict[int, int]) -> None:
    """Rule 7: Randomize all pds_state and isp_state dwords."""
    _randomize_pds_state(words)
    _randomize_isp_state(words)
