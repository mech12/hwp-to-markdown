"""HWP/HWPX to Markdown 변환 핵심 모듈."""

import re
import shutil
import subprocess
import tempfile
import warnings
from enum import Enum
from pathlib import Path
from typing import Literal, Optional

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from markdownify import markdownify as md

from .config import settings

# hwp5html이 생성하는 XHTML을 lxml로 파싱할 때 발생하는 경고 억제
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


class ConversionMethod(str, Enum):
    """변환 방법을 지정하는 열거형."""

    AUTO = "auto"  # 자동 감지 (기본값)
    PYHWP = "pyhwp"  # pyhwp(hwp5html) 사용 - HWP만 지원
    HWPX_NATIVE = "hwpx-native"  # HWPX 네이티브 파서 사용
    LIBREOFFICE = "libreoffice"  # LibreOffice 사용 - HWP/HWPX 모두 지원


class HwpConversionError(Exception):
    """HWP 변환 중 발생하는 오류."""

    pass


def _is_hwpx_file(file_path: Path) -> bool:
    """파일이 HWPX 형식인지 확인."""
    from .hwpx_parser import is_hwpx_file

    return is_hwpx_file(file_path)


def _is_hwp5_file(file_path: Path) -> bool:
    """파일이 HWP5 형식인지 확인 (OLE2 Compound Binary)."""
    try:
        with open(file_path, "rb") as f:
            # OLE2 매직 넘버 확인
            magic = f.read(8)
            return magic[:4] == b"\xd0\xcf\x11\xe0"
    except Exception:
        return False


def hwp_to_html(hwp_path: str | Path) -> tuple[str, Path]:
    """HWP 파일을 HTML로 변환 (pyhwp 사용).

    Args:
        hwp_path: HWP 파일 경로

    Returns:
        tuple: (HTML 내용, 임시 디렉토리 Path)

    Raises:
        HwpConversionError: 변환 실패 시
        FileNotFoundError: HWP 파일이 없을 경우
    """
    hwp_path = Path(hwp_path)
    if not hwp_path.exists():
        raise FileNotFoundError(f"HWP 파일을 찾을 수 없습니다: {hwp_path}")

    # 임시 디렉토리 생성 (호출자가 정리해야 함)
    tmpdir = tempfile.mkdtemp(prefix="hwp2md_")
    tmpdir_path = Path(tmpdir)

    try:
        # hwp5html 실행
        result = subprocess.run(
            ["hwp5html", "--output", str(tmpdir_path), str(hwp_path)],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise HwpConversionError(
                f"hwp5html 변환 실패: {result.stderr or result.stdout}"
            )

        # HTML 파일 찾기
        html_file = tmpdir_path / "index.xhtml"
        if not html_file.exists():
            # 다른 가능한 파일명 시도
            html_files = list(tmpdir_path.glob("*.html")) + list(
                tmpdir_path.glob("*.xhtml")
            )
            if html_files:
                html_file = html_files[0]
            else:
                raise HwpConversionError(
                    f"변환된 HTML 파일을 찾을 수 없습니다: {tmpdir_path}"
                )

        html_content = html_file.read_text(encoding="utf-8")
        return html_content, tmpdir_path

    except FileNotFoundError as e:
        shutil.rmtree(tmpdir, ignore_errors=True)
        if "hwp5html" in str(e):
            raise HwpConversionError(
                "hwp5html을 찾을 수 없습니다. pyhwp가 설치되어 있는지 확인하세요."
            ) from e
        raise


def extract_images(
    html_dir: Path, output_dir: Path, base_name: Optional[str] = None
) -> dict[str, str]:
    """HTML 디렉토리에서 이미지를 추출하여 출력 디렉토리로 복사.

    Args:
        html_dir: hwp5html이 생성한 임시 디렉토리
        output_dir: 이미지를 저장할 디렉토리
        base_name: 이미지 폴더 이름 (None이면 설정값 사용)

    Returns:
        dict: 원본 경로 -> 새 경로 매핑
    """
    if base_name is None:
        base_name = settings.converter.images_dir_name
    images_dir = output_dir / base_name
    path_mapping = {}

    # bindata 폴더에서 이미지 찾기
    bindata_dir = html_dir / "bindata"
    if bindata_dir.exists():
        images_dir.mkdir(parents=True, exist_ok=True)

        for img_file in bindata_dir.iterdir():
            if img_file.is_file():
                new_path = images_dir / img_file.name
                shutil.copy2(img_file, new_path)
                # HTML 내 상대 경로 -> 새 상대 경로
                path_mapping[f"bindata/{img_file.name}"] = f"{base_name}/{img_file.name}"

    return path_mapping


def html_to_markdown(
    html: str, image_mapping: Optional[dict[str, str]] = None
) -> str:
    """HTML을 Markdown으로 변환.

    Args:
        html: HTML 문자열
        image_mapping: 이미지 경로 매핑 (원본 -> 새 경로)

    Returns:
        str: Markdown 문자열
    """
    # BeautifulSoup으로 불필요한 태그 제거
    soup = BeautifulSoup(html, "lxml")

    # script, style, meta, link 태그 완전 제거
    for tag in soup.find_all(["script", "style", "meta", "link"]):
        tag.decompose()

    # 테이블 셀 안의 이미지를 마커로 치환 (markdownify가 테이블 내 이미지를 무시하는 문제 해결)
    # 마커 형식: IMGPLACEHOLDER{index}ENDIMG (언더스코어 없이 - markdownify 이스케이프 방지)
    image_placeholders: list[tuple[str, str, str]] = []  # (marker, img_src, alt)
    for idx, img in enumerate(soup.find_all("img")):
        if img.find_parent("table"):
            src = img.get("src", "")
            alt = img.get("alt", "")
            marker = f"IMGPLACEHOLDER{idx}ENDIMG"
            image_placeholders.append((marker, src, alt))
            img.replace_with(marker)

    html = str(soup)

    # 이미지 경로 치환
    if image_mapping:
        for old_path, new_path in image_mapping.items():
            html = html.replace(old_path, new_path)

    # markdownify로 변환
    markdown = md(
        html,
        heading_style=settings.converter.heading_style,
        bullets=settings.converter.bullet_style,
    )

    # 이미지 마커를 markdown 이미지 문법으로 복원
    for marker, src, alt in image_placeholders:
        # 이미지 경로 매핑 적용
        if image_mapping and src in image_mapping:
            src = image_mapping[src]
        md_image = f"![{alt}]({src})"
        markdown = markdown.replace(marker, md_image)

    # 후처리: 불필요한 빈 줄 정리
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    markdown = markdown.strip()

    return markdown


def _convert_with_pyhwp(
    hwp_path: Path,
    output: Optional[Path],
    images_dir: Optional[Path],
) -> str:
    """pyhwp(hwp5html)를 사용하여 변환."""
    html_content, tmpdir = hwp_to_html(hwp_path)

    try:
        image_mapping = None

        if output:
            output_dir = output.parent
            output_dir.mkdir(parents=True, exist_ok=True)

            if images_dir:
                img_output_dir = images_dir
            else:
                img_output_dir = output_dir

            image_mapping = extract_images(tmpdir, img_output_dir)

        markdown = html_to_markdown(html_content, image_mapping)

        if output:
            output.write_text(markdown, encoding="utf-8")

        return markdown

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _convert_with_hwpx_native(
    hwpx_path: Path,
    output: Optional[Path],
    images_dir: Optional[Path],
) -> str:
    """HWPX 네이티브 파서를 사용하여 변환."""
    from .hwpx_parser import extract_images_from_hwpx, hwpx_to_html

    html_content, tmpdir = hwpx_to_html(hwpx_path)

    try:
        image_mapping = None

        if output:
            output_dir = output.parent
            output_dir.mkdir(parents=True, exist_ok=True)

            if images_dir:
                img_output_dir = images_dir
            else:
                img_output_dir = output_dir

            # HWPX에서 직접 이미지 추출
            image_mapping = extract_images_from_hwpx(hwpx_path, img_output_dir)

        markdown = html_to_markdown(html_content, image_mapping)

        if output:
            output.write_text(markdown, encoding="utf-8")

        return markdown

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _convert_with_libreoffice(
    file_path: Path,
    output: Optional[Path],
    images_dir: Optional[Path],
) -> str:
    """LibreOffice를 사용하여 변환."""
    from .libreoffice_converter import (
        LibreOfficeConversionError,
        extract_images_libreoffice,
        libreoffice_to_html,
    )

    try:
        html_content, tmpdir = libreoffice_to_html(file_path)
    except LibreOfficeConversionError as e:
        raise HwpConversionError(str(e)) from e

    try:
        image_mapping = None

        if output:
            output_dir = output.parent
            output_dir.mkdir(parents=True, exist_ok=True)

            if images_dir:
                img_output_dir = images_dir
            else:
                img_output_dir = output_dir

            image_mapping = extract_images_libreoffice(tmpdir, img_output_dir)

        markdown = html_to_markdown(html_content, image_mapping)

        if output:
            output.write_text(markdown, encoding="utf-8")

        return markdown

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def convert(
    hwp_path: str | Path,
    output: Optional[str | Path] = None,
    images_dir: Optional[str | Path] = None,
    method: ConversionMethod | Literal["auto", "pyhwp", "hwpx-native", "libreoffice"] = ConversionMethod.AUTO,
) -> str:
    """HWP/HWPX 파일을 Markdown으로 변환.

    Args:
        hwp_path: HWP/HWPX 파일 경로
        output: 출력 Markdown 파일 경로 (None이면 문자열만 반환)
        images_dir: 이미지 저장 디렉토리 (None이면 output과 같은 위치에 images/ 생성)
        method: 변환 방법
            - "auto": 파일 형식에 따라 자동 선택 (기본값)
            - "pyhwp": pyhwp(hwp5html) 사용 (HWP만 지원)
            - "hwpx-native": HWPX 네이티브 파서 사용 (HWPX만 지원)
            - "libreoffice": LibreOffice 사용 (HWP/HWPX 모두 지원)

    Returns:
        str: 변환된 Markdown 문자열

    Raises:
        HwpConversionError: 변환 실패 시
        FileNotFoundError: 파일이 없을 경우

    Examples:
        >>> from hwp_to_markdown import convert
        >>> # 자동 감지 (기본)
        >>> markdown = convert("document.hwp")
        >>> markdown = convert("document.hwpx")
        >>>
        >>> # 명시적 변환 방법 지정
        >>> markdown = convert("document.hwpx", method="hwpx-native")
        >>> markdown = convert("document.hwpx", method="libreoffice")
        >>>
        >>> # 파일로 저장
        >>> convert("document.hwp", output="document.md")
    """
    hwp_path = Path(hwp_path)
    output_path = Path(output) if output else None
    images_path = Path(images_dir) if images_dir else None

    if not hwp_path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {hwp_path}")

    # 문자열을 Enum으로 변환
    if isinstance(method, str):
        method = ConversionMethod(method)

    # 자동 감지 모드
    if method == ConversionMethod.AUTO:
        if _is_hwpx_file(hwp_path):
            # HWPX 파일: 네이티브 파서 우선 시도
            try:
                return _convert_with_hwpx_native(hwp_path, output_path, images_path)
            except Exception as e:
                # 네이티브 파서 실패 시 LibreOffice 시도
                from .libreoffice_converter import is_libreoffice_available

                if is_libreoffice_available():
                    try:
                        return _convert_with_libreoffice(hwp_path, output_path, images_path)
                    except Exception:
                        pass
                raise HwpConversionError(f"HWPX 변환 실패: {e}") from e
        elif _is_hwp5_file(hwp_path):
            # HWP5 파일: pyhwp 사용
            return _convert_with_pyhwp(hwp_path, output_path, images_path)
        else:
            # 확장자 기반 판단
            ext = hwp_path.suffix.lower()
            if ext == ".hwpx":
                return _convert_with_hwpx_native(hwp_path, output_path, images_path)
            elif ext == ".hwp":
                return _convert_with_pyhwp(hwp_path, output_path, images_path)
            else:
                raise HwpConversionError(
                    f"지원하지 않는 파일 형식입니다: {hwp_path}"
                )

    # 명시적 변환 방법
    elif method == ConversionMethod.PYHWP:
        if _is_hwpx_file(hwp_path):
            raise HwpConversionError(
                "pyhwp는 HWPX 형식을 지원하지 않습니다. "
                "'hwpx-native' 또는 'libreoffice' 방법을 사용하세요."
            )
        return _convert_with_pyhwp(hwp_path, output_path, images_path)

    elif method == ConversionMethod.HWPX_NATIVE:
        if not _is_hwpx_file(hwp_path):
            raise HwpConversionError(
                "hwpx-native 방법은 HWPX 형식만 지원합니다. "
                "HWP 파일은 'pyhwp' 또는 'libreoffice' 방법을 사용하세요."
            )
        return _convert_with_hwpx_native(hwp_path, output_path, images_path)

    elif method == ConversionMethod.LIBREOFFICE:
        from .libreoffice_converter import is_libreoffice_available

        if not is_libreoffice_available():
            raise HwpConversionError(
                "LibreOffice가 설치되어 있지 않습니다. "
                "LibreOffice를 설치하거나 다른 변환 방법을 사용하세요."
            )
        return _convert_with_libreoffice(hwp_path, output_path, images_path)

    else:
        raise ValueError(f"알 수 없는 변환 방법: {method}")
