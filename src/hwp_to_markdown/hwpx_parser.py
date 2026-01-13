"""HWPX 파일 파서 모듈.

HWPX는 ZIP 기반 XML 포맷으로, 직접 파싱하여 HTML로 변환합니다.
"""

import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET

from .config import settings


class HwpxParseError(Exception):
    """HWPX 파싱 중 발생하는 오류."""

    pass


# HWPX XML 네임스페이스
NAMESPACES = {
    "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
    "hs": "http://www.hancom.co.kr/hwpml/2011/section",
    "hc": "http://www.hancom.co.kr/hwpml/2011/core",
    "hh": "http://www.hancom.co.kr/hwpml/2011/head",
}


def is_hwpx_file(file_path: Path) -> bool:
    """파일이 HWPX 형식인지 확인.

    Args:
        file_path: 확인할 파일 경로

    Returns:
        bool: HWPX 파일이면 True
    """
    try:
        with zipfile.ZipFile(file_path, "r") as zf:
            # HWPX 파일은 mimetype 파일을 포함
            if "mimetype" in zf.namelist():
                mimetype = zf.read("mimetype").decode("utf-8").strip()
                return "hwp" in mimetype.lower()
            # Contents/section0.xml이 있으면 HWPX로 간주
            return "Contents/section0.xml" in zf.namelist()
    except (zipfile.BadZipFile, Exception):
        return False


def _extract_text_from_element(elem: ET.Element) -> str:
    """XML 요소에서 텍스트 추출."""
    texts = []

    # <hp:t> 태그에서 텍스트 추출
    for t_elem in elem.iter("{http://www.hancom.co.kr/hwpml/2011/paragraph}t"):
        if t_elem.text:
            texts.append(t_elem.text)

    # <hp:lineBreak/> 처리
    for _ in elem.iter("{http://www.hancom.co.kr/hwpml/2011/paragraph}lineBreak"):
        texts.append("\n")

    return "".join(texts)


def _parse_table(tbl_elem: ET.Element) -> str:
    """테이블 요소를 HTML로 변환."""
    html_parts = ["<table border='1'>"]

    # 행(tr) 처리
    for tr_elem in tbl_elem.iter("{http://www.hancom.co.kr/hwpml/2011/paragraph}tr"):
        html_parts.append("<tr>")

        # 셀(tc) 처리
        for tc_elem in tr_elem.iter(
            "{http://www.hancom.co.kr/hwpml/2011/paragraph}tc"
        ):
            # 셀 span 정보 추출
            cell_span = tc_elem.find(
                "{http://www.hancom.co.kr/hwpml/2011/paragraph}cellSpan"
            )
            colspan = "1"
            rowspan = "1"
            if cell_span is not None:
                colspan = cell_span.get("colSpan", "1")
                rowspan = cell_span.get("rowSpan", "1")

            # 셀 내용 추출
            cell_text = _extract_text_from_element(tc_elem)
            html_parts.append(
                f"<td colspan='{colspan}' rowspan='{rowspan}'>{cell_text}</td>"
            )

        html_parts.append("</tr>")

    html_parts.append("</table>")
    return "".join(html_parts)


def _parse_paragraph(p_elem: ET.Element) -> str:
    """문단 요소를 HTML로 변환."""
    # 테이블 체크
    tbl_elem = p_elem.find(".//{http://www.hancom.co.kr/hwpml/2011/paragraph}tbl")
    if tbl_elem is not None:
        return _parse_table(tbl_elem)

    # 일반 텍스트 추출
    text = _extract_text_from_element(p_elem)
    if not text.strip():
        return ""

    return f"<p>{text}</p>"


def _parse_section(section_xml: str) -> str:
    """섹션 XML을 HTML로 변환."""
    try:
        root = ET.fromstring(section_xml)
    except ET.ParseError as e:
        raise HwpxParseError(f"섹션 XML 파싱 실패: {e}") from e

    html_parts = []

    # 모든 문단(p) 처리
    for p_elem in root.iter("{http://www.hancom.co.kr/hwpml/2011/paragraph}p"):
        para_html = _parse_paragraph(p_elem)
        if para_html:
            html_parts.append(para_html)

    return "\n".join(html_parts)


def hwpx_to_html(hwpx_path: str | Path) -> tuple[str, Path]:
    """HWPX 파일을 HTML로 변환.

    Args:
        hwpx_path: HWPX 파일 경로

    Returns:
        tuple: (HTML 내용, 임시 디렉토리 Path)

    Raises:
        HwpxParseError: 파싱 실패 시
        FileNotFoundError: 파일이 없을 경우
    """
    hwpx_path = Path(hwpx_path)
    if not hwpx_path.exists():
        raise FileNotFoundError(f"HWPX 파일을 찾을 수 없습니다: {hwpx_path}")

    if not is_hwpx_file(hwpx_path):
        raise HwpxParseError(f"유효한 HWPX 파일이 아닙니다: {hwpx_path}")

    # 임시 디렉토리 생성
    tmpdir = tempfile.mkdtemp(prefix="hwpx2md_")
    tmpdir_path = Path(tmpdir)

    try:
        with zipfile.ZipFile(hwpx_path, "r") as zf:
            html_parts = [
                "<!DOCTYPE html>",
                "<html>",
                "<head><meta charset='utf-8'><title>HWPX Document</title></head>",
                "<body>",
            ]

            # 섹션 파일들 처리 (section0.xml, section1.xml, ...)
            section_files = sorted(
                [n for n in zf.namelist() if re.match(r"Contents/section\d+\.xml", n)]
            )

            if not section_files:
                raise HwpxParseError("HWPX 파일에서 섹션을 찾을 수 없습니다")

            for section_file in section_files:
                section_xml = zf.read(section_file).decode("utf-8")
                section_html = _parse_section(section_xml)
                html_parts.append(section_html)

            # 이미지 추출 (BinData 폴더)
            bindata_dir = tmpdir_path / "bindata"
            for name in zf.namelist():
                if name.startswith("BinData/") and not name.endswith("/"):
                    # 이미지 파일 추출
                    bindata_dir.mkdir(parents=True, exist_ok=True)
                    img_name = Path(name).name
                    img_path = bindata_dir / img_name
                    img_path.write_bytes(zf.read(name))

            html_parts.extend(["</body>", "</html>"])

            html_content = "\n".join(html_parts)

            # HTML 파일 저장
            html_file = tmpdir_path / "index.html"
            html_file.write_text(html_content, encoding="utf-8")

            return html_content, tmpdir_path

    except Exception as e:
        shutil.rmtree(tmpdir, ignore_errors=True)
        if isinstance(e, (HwpxParseError, FileNotFoundError)):
            raise
        raise HwpxParseError(f"HWPX 파싱 실패: {e}") from e


def extract_images_from_hwpx(
    hwpx_path: str | Path, output_dir: Path, base_name: Optional[str] = None
) -> dict[str, str]:
    """HWPX 파일에서 이미지 추출.

    Args:
        hwpx_path: HWPX 파일 경로
        output_dir: 이미지를 저장할 디렉토리
        base_name: 이미지 폴더 이름

    Returns:
        dict: 원본 경로 -> 새 경로 매핑
    """
    if base_name is None:
        base_name = settings.converter.images_dir_name

    hwpx_path = Path(hwpx_path)
    images_dir = output_dir / base_name
    path_mapping = {}

    try:
        with zipfile.ZipFile(hwpx_path, "r") as zf:
            for name in zf.namelist():
                if name.startswith("BinData/") and not name.endswith("/"):
                    images_dir.mkdir(parents=True, exist_ok=True)
                    img_name = Path(name).name
                    img_path = images_dir / img_name
                    img_path.write_bytes(zf.read(name))
                    path_mapping[f"BinData/{img_name}"] = f"{base_name}/{img_name}"
    except Exception:
        pass  # 이미지 추출 실패는 무시

    return path_mapping
