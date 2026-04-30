from dataclasses import dataclass
import re
from typing import List, Optional, Sequence, Tuple


CS_MASK_FMT_INDEX = 0
CS_MASK_FMT_BYTE = 1
CS_MASK_FMT_BIT = 2
CS_MASK_FMT_FULL = 3
DEFAULT_MAX_PRIM_BLK_PRIMITIVES = 80

PB_INSTRUCTION_WORD_RE = re.compile(
    r"pb_instruction(?:\s*\[\s*(\d+)\s*\])?\s*=\s*(?:32\s*)?'\s*h\s*([0-9a-fA-F_]+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PbInstruction:
    cs_type: int
    cs_isp_state_size: int
    cs_prim_total: int
    cs_mask_fmt: int
    cs_prim_base_pres: int
    cs_prim_base_offset: int
    cs_prim_base: Optional[int]
    visible_primitives: Tuple[int, ...]
    raw_header: int
    raw_base: Optional[int]
    raw_mask_words: Tuple[int, ...]

    @property
    def primitive_count(self) -> int:
        return self.cs_prim_total + 1

    @property
    def words(self) -> Tuple[int, ...]:
        packed = [self.raw_header]
        if self.raw_base is not None:
            packed.append(self.raw_base)
        packed.extend(self.raw_mask_words)
        return tuple(packed)


def make_pb_instruction(
    *,
    cs_isp_state_size: int,
    cs_prim_total: int,
    cs_mask_fmt: int,
    cs_prim_base_pres: int = 0,
    cs_prim_base_offset: int = 0,
    cs_prim_base: Optional[int] = None,
    visible_primitives: Sequence[int] = (),
    max_primitives: int = DEFAULT_MAX_PRIM_BLK_PRIMITIVES,
) -> PbInstruction:
    instruction = PbInstruction(
        cs_type=0,
        cs_isp_state_size=cs_isp_state_size,
        cs_prim_total=cs_prim_total,
        cs_mask_fmt=cs_mask_fmt,
        cs_prim_base_pres=cs_prim_base_pres,
        cs_prim_base_offset=cs_prim_base_offset,
        cs_prim_base=cs_prim_base,
        visible_primitives=tuple(sorted(set(visible_primitives))),
        raw_header=0,
        raw_base=None,
        raw_mask_words=(),
    )
    words = pack_pb_instruction_words(instruction, max_primitives)
    return parse_pb_instruction_words(words, max_primitives)


def parse_pb_instruction_words(
    words: Sequence[int],
    max_primitives: int = DEFAULT_MAX_PRIM_BLK_PRIMITIVES,
) -> PbInstruction:
    if not words:
        raise ValueError("PB instruction requires at least one 32-bit word")
    _validate_max_primitives(max_primitives)

    header = _u32(words[0])
    cs_type = (header >> 30) & 0x3
    cs_isp_state_size = (header >> 26) & 0xf
    cs_prim_total = (header >> 19) & 0x7f
    cs_mask_fmt = (header >> 17) & 0x3
    cs_prim_base_pres = (header >> 16) & 0x1
    cs_prim_base_offset = header & 0xffff
    primitive_count = cs_prim_total + 1

    index = 1
    raw_base: Optional[int] = None
    if cs_prim_base_pres:
        if len(words) <= index:
            raise ValueError("PB instruction header requires CS_PRIM_BASE word")
        raw_base = _u32(words[index])
        index += 1

    mask_word_count = _mask_word_count(cs_mask_fmt, primitive_count, cs_prim_base_offset, max_primitives)
    if len(words) < index + mask_word_count:
        raise ValueError("PB instruction does not contain enough primitive mask words")
    raw_mask_words = tuple(_u32(word) for word in words[index:index + mask_word_count])

    if cs_mask_fmt == CS_MASK_FMT_INDEX:
        visible_primitives = _parse_index_mask(raw_mask_words, max_primitives)
    elif cs_mask_fmt == CS_MASK_FMT_BYTE:
        visible_primitives = _parse_byte_mask(cs_prim_base_offset, raw_mask_words, primitive_count)
    elif cs_mask_fmt == CS_MASK_FMT_BIT:
        visible_primitives = _parse_bit_mask(raw_mask_words, primitive_count)
    elif cs_mask_fmt == CS_MASK_FMT_FULL:
        visible_primitives = tuple(range(primitive_count))
    else:
        raise ValueError(f"Unsupported CS_MASK_FMT: {cs_mask_fmt}")

    instruction = PbInstruction(
        cs_type=cs_type,
        cs_isp_state_size=cs_isp_state_size,
        cs_prim_total=cs_prim_total,
        cs_mask_fmt=cs_mask_fmt,
        cs_prim_base_pres=cs_prim_base_pres,
        cs_prim_base_offset=cs_prim_base_offset,
        cs_prim_base=raw_base,
        visible_primitives=tuple(i for i in visible_primitives if i < primitive_count),
        raw_header=header,
        raw_base=raw_base,
        raw_mask_words=raw_mask_words,
    )
    _validate_instruction(instruction, max_primitives)
    return instruction


def pack_pb_instruction_words(
    instruction: PbInstruction,
    max_primitives: int = DEFAULT_MAX_PRIM_BLK_PRIMITIVES,
) -> Tuple[int, ...]:
    _validate_instruction(instruction, max_primitives)

    primitive_count = instruction.primitive_count
    cs_prim_base_offset = instruction.cs_prim_base_offset & 0xffff
    mask_words: Tuple[int, ...]

    if instruction.cs_mask_fmt == CS_MASK_FMT_INDEX:
        mask_words = _pack_index_mask(instruction.visible_primitives, max_primitives)
    elif instruction.cs_mask_fmt == CS_MASK_FMT_BYTE:
        cs_prim_base_offset, mask_words = _pack_byte_mask(instruction.visible_primitives, primitive_count)
    elif instruction.cs_mask_fmt == CS_MASK_FMT_BIT:
        mask_words = _pack_bit_mask(instruction.visible_primitives, primitive_count)
    elif instruction.cs_mask_fmt == CS_MASK_FMT_FULL:
        mask_words = ()
    else:
        raise ValueError(f"Unsupported CS_MASK_FMT: {instruction.cs_mask_fmt}")

    header = (
        ((instruction.cs_type & 0x3) << 30)
        | ((instruction.cs_isp_state_size & 0xf) << 26)
        | ((instruction.cs_prim_total & 0x7f) << 19)
        | ((instruction.cs_mask_fmt & 0x3) << 17)
        | ((instruction.cs_prim_base_pres & 0x1) << 16)
        | cs_prim_base_offset
    )

    packed = [header]
    if instruction.cs_prim_base_pres:
        packed.append(_u32(instruction.cs_prim_base or 0))
    packed.extend(mask_words)
    return tuple(packed)


def parse_pb_instruction_text(text: str, max_primitives: int = DEFAULT_MAX_PRIM_BLK_PRIMITIVES) -> Optional[PbInstruction]:
    matches = PB_INSTRUCTION_WORD_RE.findall(text)
    if not matches:
        return None

    indexed_words = []
    sequential_words = []
    for index_text, value_text in matches:
        value = int(value_text.replace("_", ""), 16)
        if index_text == "":
            sequential_words.append(value)
        else:
            indexed_words.append((int(index_text), value))

    if indexed_words:
        words = [value for _, value in sorted(indexed_words)]
    else:
        words = sequential_words
    return parse_pb_instruction_words(words, max_primitives)


def format_pb_instruction_words(instruction: PbInstruction) -> str:
    return "\n".join(
        f"pb_instruction[{index}] = 32'h{word:08X};"
        for index, word in enumerate(pack_pb_instruction_words(instruction))
    )


def format_pb_instruction_table(instruction: PbInstruction) -> str:
    rows = [_table_header()]
    rows.append(_table_parent_row("pb_instruction_3_1"))
    for index, word in enumerate(pack_pb_instruction_words(instruction)):
        rows.append(_table_row(f"word[{index}]", "integral", 32, word, "", indent=1))
    rows.append(_table_row("cs_type", "integral", 2, instruction.cs_type, "00b Primitive block", indent=1))
    rows.append(_table_row("cs_isp_state_size", "integral", 4, instruction.cs_isp_state_size, "", indent=1))
    rows.append(_table_row("cs_prim_total", "integral", 7, instruction.cs_prim_total, f"primitive_count={instruction.primitive_count}", indent=1))
    rows.append(_table_row("cs_mask_fmt", "integral", 2, instruction.cs_mask_fmt, _mask_fmt_name(instruction.cs_mask_fmt), indent=1))
    rows.append(_table_row("cs_prim_base_pres", "integral", 1, instruction.cs_prim_base_pres, "", indent=1))
    rows.append(_table_row("cs_prim_base_offset", "integral", 16, instruction.cs_prim_base_offset, "byte mask presence bits when cs_mask_fmt=1", indent=1))
    if instruction.cs_prim_base is not None:
        rows.append(_table_row("cs_prim_base", "integral", 32, instruction.cs_prim_base, "primitive block byte address bits 33:2", indent=1))
    rows.append(_table_row("visible_primitive_count", "integral", 16, len(instruction.visible_primitives), "", indent=1))
    rows.append(_table_row("visible_primitives", "list", len(instruction.visible_primitives), 0, ", ".join(str(i) for i in instruction.visible_primitives), indent=1))
    return "\n".join(rows)


def _mask_word_count(cs_mask_fmt: int, primitive_count: int, byte_mask_bits: int, max_primitives: int) -> int:
    if cs_mask_fmt == CS_MASK_FMT_INDEX:
        return 1
    if cs_mask_fmt == CS_MASK_FMT_BYTE:
        group_count = (min(primitive_count, max_primitives) + 7) // 8
        present_groups = sum(1 for group in range(group_count) if byte_mask_bits & (1 << group))
        return (present_groups + 3) // 4
    if cs_mask_fmt == CS_MASK_FMT_BIT:
        return (min(primitive_count, max_primitives) + 31) // 32
    if cs_mask_fmt == CS_MASK_FMT_FULL:
        return 0
    raise ValueError(f"Unsupported CS_MASK_FMT: {cs_mask_fmt}")


def _parse_index_mask(mask_words: Sequence[int], max_primitives: int) -> Tuple[int, ...]:
    word = mask_words[0]
    if max_primitives == 40:
        width, slots, absent = 6, 5, 0x3f
    else:
        width, slots, absent = 7, 4, 0x7f
    mask = (1 << width) - 1
    indices = []
    for slot in range(slots):
        value = (word >> (slot * width)) & mask
        if value != absent:
            indices.append(value)
    return tuple(indices)


def _pack_index_mask(indices: Sequence[int], max_primitives: int) -> Tuple[int, ...]:
    if max_primitives == 40:
        width, slots, absent = 6, 5, 0x3f
    else:
        width, slots, absent = 7, 4, 0x7f
    if len(indices) > slots:
        raise ValueError(f"Index mask can encode at most {slots} primitives")
    values = list(indices) + [absent] * (slots - len(indices))
    word = 0
    for slot, value in enumerate(values):
        word |= (value & ((1 << width) - 1)) << (slot * width)
    return (word,)


def _parse_byte_mask(byte_mask_bits: int, mask_words: Sequence[int], primitive_count: int) -> Tuple[int, ...]:
    groups = []
    for group in range((primitive_count + 7) // 8):
        if byte_mask_bits & (1 << group):
            groups.append(group)
    indices = []
    for packed_index, group in enumerate(groups):
        word = mask_words[packed_index // 4]
        byte_mask = (word >> ((packed_index % 4) * 8)) & 0xff
        for bit in range(8):
            primitive = group * 8 + bit
            if primitive < primitive_count and byte_mask & (1 << bit):
                indices.append(primitive)
    return tuple(indices)


def _pack_byte_mask(indices: Sequence[int], primitive_count: int) -> Tuple[int, Tuple[int, ...]]:
    group_masks = {}
    for primitive in indices:
        if primitive >= primitive_count:
            continue
        group = primitive // 8
        group_masks[group] = group_masks.get(group, 0) | (1 << (primitive % 8))
    byte_mask_bits = 0
    packed_bytes = []
    for group in sorted(group_masks):
        byte_mask_bits |= 1 << group
        packed_bytes.append(group_masks[group])
    words = []
    for start in range(0, len(packed_bytes), 4):
        word = 0
        for offset, byte in enumerate(packed_bytes[start:start + 4]):
            word |= (byte & 0xff) << (offset * 8)
        words.append(word)
    return byte_mask_bits, tuple(words)


def _parse_bit_mask(mask_words: Sequence[int], primitive_count: int) -> Tuple[int, ...]:
    indices = []
    for primitive in range(primitive_count):
        word_index = primitive // 32
        bit = primitive % 32
        if word_index < len(mask_words) and mask_words[word_index] & (1 << bit):
            indices.append(primitive)
    return tuple(indices)


def _pack_bit_mask(indices: Sequence[int], primitive_count: int) -> Tuple[int, ...]:
    words = [0] * ((primitive_count + 31) // 32)
    for primitive in indices:
        if primitive < primitive_count:
            words[primitive // 32] |= 1 << (primitive % 32)
    return tuple(words)


def _validate_instruction(instruction: PbInstruction, max_primitives: int) -> None:
    _validate_max_primitives(max_primitives)
    _validate_width("cs_type", instruction.cs_type, 2)
    if instruction.cs_type != 0:
        raise ValueError("PB instruction CS_TYPE must be 0 for primitive block instructions")
    _validate_width("cs_isp_state_size", instruction.cs_isp_state_size, 4)
    if not 3 <= instruction.cs_isp_state_size <= 10:
        raise ValueError("CS_ISP_STATE_SIZE must be between 3 and 10")
    _validate_width("cs_prim_total", instruction.cs_prim_total, 7)
    if instruction.cs_prim_total > 79:
        raise ValueError("CS_PRIM_TOTAL must be between 0 and 79")
    if instruction.primitive_count > max_primitives:
        raise ValueError("CS_PRIM_TOTAL exceeds MAX_PRIM_BLK_PRIMITIVES")
    _validate_width("cs_mask_fmt", instruction.cs_mask_fmt, 2)
    _validate_width("cs_prim_base_pres", instruction.cs_prim_base_pres, 1)
    _validate_width("cs_prim_base_offset", instruction.cs_prim_base_offset, 16)
    if instruction.cs_mask_fmt == CS_MASK_FMT_BYTE and instruction.cs_prim_base_pres != 1:
        raise ValueError("CS_PRIM_BASE_PRES must be 1 when CS_MASK_FMT is byte-based")
    if instruction.cs_prim_base_pres and instruction.cs_prim_base is not None:
        _validate_width("cs_prim_base", instruction.cs_prim_base, 32)
    for primitive in instruction.visible_primitives:
        if primitive < 0 or primitive >= instruction.primitive_count or primitive >= max_primitives:
            raise ValueError("visible primitive index is out of range")


def _validate_width(name: str, value: int, width: int) -> None:
    if value < 0 or value >= (1 << width):
        raise ValueError(f"{name} does not fit in {width} bits")


def _validate_max_primitives(max_primitives: int) -> None:
    if max_primitives not in {40, 80}:
        raise ValueError("max_primitives must be 40 or 80")


def _u32(value: int) -> int:
    if value < 0 or value > 0xffffffff:
        raise ValueError("PB instruction words must be 32-bit unsigned values")
    return value


def _mask_fmt_name(mask_fmt: int) -> str:
    return {
        CS_MASK_FMT_INDEX: "index-based primitive mask",
        CS_MASK_FMT_BYTE: "byte-based primitive mask",
        CS_MASK_FMT_BIT: "bit-based primitive mask",
        CS_MASK_FMT_FULL: "full primitive mask",
    }.get(mask_fmt, "unknown")


def _table_header() -> str:
    return "| name | type | bits | hex | dec | notes |\n|---|---:|---:|---:|---:|---|"


def _table_parent_row(name: str, indent: int = 0) -> str:
    return f"| {'&nbsp;' * (indent * 4)}{name} |  |  |  |  |  |"


def _table_row(name: str, type_name: str, bits: int, value: int, notes: str, indent: int = 0) -> str:
    prefix = "&nbsp;" * (indent * 4)
    if type_name == "list":
        return f"| {prefix}{name} | {type_name} | {bits} |  |  | {notes} |"
    hex_width = max(1, (bits + 3) // 4)
    return f"| {prefix}{name} | {type_name} | {bits} | 0x{value:0{hex_width}X} | {value} | {notes} |"
