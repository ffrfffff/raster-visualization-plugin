from dataclasses import dataclass
from typing import Dict, Iterable, Tuple


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
