"""HWP/HWPX to Markdown 변환 라이브러리.

한글 문서(HWP, HWPX)를 Markdown으로 변환합니다.

Examples:
    >>> from hwp_to_markdown import convert
    >>> # HWP 파일 변환
    >>> markdown = convert("document.hwp")
    >>>
    >>> # HWPX 파일 변환 (자동 감지)
    >>> markdown = convert("document.hwpx")
    >>>
    >>> # 변환 방법 명시적 지정
    >>> markdown = convert("document.hwpx", method="libreoffice")
    >>>
    >>> # 파일로 저장
    >>> convert("document.hwp", output="document.md")
"""

from .converter import ConversionMethod, HwpConversionError, convert

__version__ = "0.2.0"
__all__ = ["convert", "HwpConversionError", "ConversionMethod"]
