"""HWP to Markdown 변환 라이브러리.

한글 문서(HWP)를 Markdown으로 변환합니다.

Examples:
    >>> from hwp_to_markdown import convert
    >>> markdown = convert("document.hwp")
    >>> convert("document.hwp", output="document.md")
"""

from .converter import HwpConversionError, convert

__version__ = "0.1.0"
__all__ = ["convert", "HwpConversionError"]
