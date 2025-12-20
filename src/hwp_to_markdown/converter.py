"""HWP to Markdown 변환 핵심 모듈."""

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup
from markdownify import markdownify as md

from .config import settings


class HwpConversionError(Exception):
    """HWP 변환 중 발생하는 오류."""

    pass


def hwp_to_html(hwp_path: str | Path) -> tuple[str, Path]:
    """HWP 파일을 HTML로 변환.

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

    # 후처리: 불필요한 빈 줄 정리
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    markdown = markdown.strip()

    return markdown


def convert(
    hwp_path: str | Path,
    output: Optional[str | Path] = None,
    images_dir: Optional[str | Path] = None,
) -> str:
    """HWP 파일을 Markdown으로 변환.

    Args:
        hwp_path: HWP 파일 경로
        output: 출력 Markdown 파일 경로 (None이면 문자열만 반환)
        images_dir: 이미지 저장 디렉토리 (None이면 output과 같은 위치에 images/ 생성)

    Returns:
        str: 변환된 Markdown 문자열

    Raises:
        HwpConversionError: 변환 실패 시
        FileNotFoundError: HWP 파일이 없을 경우

    Examples:
        >>> from hwp_to_markdown import convert
        >>> markdown = convert("document.hwp")
        >>> convert("document.hwp", output="document.md")
    """
    hwp_path = Path(hwp_path)
    html_content, tmpdir = hwp_to_html(hwp_path)

    try:
        image_mapping = None

        # 출력 파일이 지정된 경우 이미지 추출
        if output:
            output_path = Path(output)
            output_dir = output_path.parent
            output_dir.mkdir(parents=True, exist_ok=True)

            # 이미지 디렉토리 설정
            if images_dir:
                img_output_dir = Path(images_dir)
            else:
                img_output_dir = output_dir

            image_mapping = extract_images(tmpdir, img_output_dir)

        # Markdown 변환
        markdown = html_to_markdown(html_content, image_mapping)

        # 파일로 저장
        if output:
            output_path.write_text(markdown, encoding="utf-8")

        return markdown

    finally:
        # 임시 디렉토리 정리
        shutil.rmtree(tmpdir, ignore_errors=True)
