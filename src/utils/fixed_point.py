"""Q16.8 定点数和 FP32 浮点数格式转换工具

Q16.8: 16位整数 + 8位小数，共24位，用32位整数存储（高8位未用或符号扩展）
范围: -65536.0 ~ 65535.99609375
精度: 1/256 ≈ 0.00390625
"""
import struct
from typing import Tuple


def float_to_q16_8(value: float) -> int:
    """浮点数转 Q16.8 定点数"""
    scaled = value * 256.0
    if scaled >= 0:
        return int(round(scaled)) & 0xFFFFFFFF
    else:
        return int(round(scaled)) & 0xFFFFFFFF


def q16_8_to_float(raw: int) -> float:
    """Q16.8 定点数转浮点数（支持32位有符号解释）"""
    if raw & 0x800000:
        # 负数，符号扩展到32位
        raw = raw | 0xFF000000
    # 转为有符号32位整数
    signed = raw if raw < 0x80000000 else raw - 0x100000000
    return signed / 256.0


def float_to_fp32_bytes(value: float) -> bytes:
    """浮点数转 FP32 字节"""
    return struct.pack('<f', value)


def fp32_bytes_to_float(data: bytes) -> float:
    """FP32 字节转浮点数"""
    return struct.unpack('<f', data)[0]


def float_to_fp32_hex(value: float) -> str:
    """浮点数转 FP32 十六进制表示"""
    raw = struct.pack('<f', value)
    return f"0x{struct.unpack('<I', raw)[0]:08X}"


def fp32_hex_to_float(hex_str: str) -> float:
    """FP32 十六进制表示转浮点数"""
    hex_str = hex_str.strip()
    if hex_str.startswith("0x") or hex_str.startswith("0X"):
        hex_str = hex_str[2:]
    raw_int = int(hex_str, 16)
    raw_bytes = struct.pack('<I', raw_int)
    return struct.unpack('<f', raw_bytes)[0]


def float_to_fp32_binary(value: float) -> str:
    """浮点数转 FP32 二进制表示"""
    raw = struct.pack('<f', value)
    bits = struct.unpack('<I', raw)[0]
    return f"{bits:032b}"


def fp32_binary_to_float(bin_str: str) -> float:
    """FP32 二进制表示转浮点数"""
    bin_str = bin_str.strip().replace(" ", "")
    raw_int = int(bin_str, 2)
    raw_bytes = struct.pack('<I', raw_int)
    return struct.unpack('<f', raw_bytes)[0]


def q16_8_to_binary(value: float) -> str:
    """浮点数转 Q16.8 二进制表示（24位）"""
    raw = float_to_q16_8(value)
    return f"{raw & 0xFFFFFF:024b}"


def q16_8_binary_to_float(bin_str: str) -> float:
    """Q16.8 二进制表示转浮点数"""
    bin_str = bin_str.strip().replace(" ", "")
    raw = int(bin_str, 2)
    return q16_8_to_float(raw)


def q16_8_to_hex(value: float) -> str:
    """浮点数转 Q16.8 十六进制表示"""
    raw = float_to_q16_8(value)
    return f"0x{raw & 0xFFFFFF:06X}"


def q16_8_hex_to_float(hex_str: str) -> float:
    """Q16.8 十六进制表示转浮点数"""
    hex_str = hex_str.strip()
    if hex_str.startswith("0x") or hex_str.startswith("0X"):
        hex_str = hex_str[2:]
    raw = int(hex_str, 16)
    return q16_8_to_float(raw)


def format_q16_8(value: float, fmt: str) -> str:
    """格式化 Q16.8 值

    Args:
        value: 浮点数值
        fmt: 'dec' | 'bin' | 'hex'
    """
    if fmt == 'dec':
        return f"{value:.4f}"
    elif fmt == 'bin':
        return q16_8_to_binary(value)
    elif fmt == 'hex':
        return q16_8_to_hex(value)
    return str(value)


def parse_q16_8(text: str, fmt: str) -> float:
    """解析 Q16.8 值

    Args:
        text: 文本输入
        fmt: 'dec' | 'bin' | 'hex'
    """
    if fmt == 'dec':
        return float(text)
    elif fmt == 'bin':
        return q16_8_binary_to_float(text)
    elif fmt == 'hex':
        return q16_8_hex_to_float(text)
    return float(text)


def format_fp32(value: float, fmt: str) -> str:
    """格式化 FP32 值"""
    if fmt == 'dec':
        return f"{value:.6g}"
    elif fmt == 'bin':
        return float_to_fp32_binary(value)
    elif fmt == 'hex':
        return float_to_fp32_hex(value)
    return str(value)


def parse_fp32(text: str, fmt: str) -> float:
    """解析 FP32 值"""
    if fmt == 'dec':
        return float(text)
    elif fmt == 'bin':
        return fp32_binary_to_float(text)
    elif fmt == 'hex':
        return fp32_hex_to_float(text)
    return float(text)
