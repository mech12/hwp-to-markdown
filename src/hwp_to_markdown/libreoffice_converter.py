"""LibreOffice를 사용한 HWP/HWPX 변환 모듈.

LibreOffice의 soffice 명령어를 사용하여 HWP/HWPX 파일을 HTML로 변환합니다.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from .config import settings


class LibreOfficeConversionError(Exception):
    """LibreOffice 변환 중 발생하는 오류."""

    pass


def find_libreoffice() -> Optional[str]:
    """LibreOffice 실행 파일 경로 찾기.

    Returns:
        str | None: LibreOffice 실행 파일 경로, 없으면 None
    """
    # 가능한 실행 파일 이름들
    possible_names = ["soffice", "libreoffice", "loffice"]

    # macOS 특정 경로
    mac_paths = [
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        "/opt/homebrew/bin/soffice",
        "/usr/local/bin/soffice",
    ]

    # Linux 특정 경로
    linux_paths = [
        "/usr/bin/soffice",
        "/usr/bin/libreoffice",
        "/usr/lib/libreoffice/program/soffice",
    ]

    # Windows 특정 경로
    windows_paths = [
        "C:\\Program Files\\LibreOffice\\program\\soffice.exe",
        "C:\\Program Files (x86)\\LibreOffice\\program\\soffice.exe",
    ]

    # PATH에서 찾기
    for name in possible_names:
        path = shutil.which(name)
        if path:
            return path

    # 플랫폼별 경로 확인
    import platform

    system = platform.system()

    paths_to_check = []
    if system == "Darwin":
        paths_to_check = mac_paths
    elif system == "Linux":
        paths_to_check = linux_paths
    elif system == "Windows":
        paths_to_check = windows_paths

    for path in paths_to_check:
        if Path(path).exists():
            return path

    return None


def is_libreoffice_available() -> bool:
    """LibreOffice가 사용 가능한지 확인.

    Returns:
        bool: LibreOffice가 사용 가능하면 True
    """
    return find_libreoffice() is not None


def libreoffice_to_html(file_path: str | Path) -> tuple[str, Path]:
    """LibreOffice를 사용하여 HWP/HWPX 파일을 HTML로 변환.

    Args:
        file_path: 변환할 파일 경로 (HWP 또는 HWPX)

    Returns:
        tuple: (HTML 내용, 임시 디렉토리 Path)

    Raises:
        LibreOfficeConversionError: 변환 실패 시
        FileNotFoundError: 파일이 없을 경우
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

    soffice_path = find_libreoffice()
    if not soffice_path:
        raise LibreOfficeConversionError(
            "LibreOffice를 찾을 수 없습니다. "
            "LibreOffice를 설치하고 PATH에 추가하세요."
        )

    # 임시 디렉토리 생성
    tmpdir = tempfile.mkdtemp(prefix="lo2md_")
    tmpdir_path = Path(tmpdir)

    try:
        # LibreOffice를 사용하여 HTML로 변환
        # --headless: GUI 없이 실행
        # --convert-to html: HTML로 변환
        # --outdir: 출력 디렉토리
        result = subprocess.run(
            [
                soffice_path,
                "--headless",
                "--convert-to",
                "html",
                "--outdir",
                str(tmpdir_path),
                str(file_path.absolute()),
            ],
            capture_output=True,
            text=True,
            timeout=120,  # 2분 타임아웃
        )

        if result.returncode != 0:
            raise LibreOfficeConversionError(
                f"LibreOffice 변환 실패: {result.stderr or result.stdout}"
            )

        # 생성된 HTML 파일 찾기
        html_files = list(tmpdir_path.glob("*.html"))
        if not html_files:
            # htm 확장자도 확인
            html_files = list(tmpdir_path.glob("*.htm"))

        if not html_files:
            raise LibreOfficeConversionError(
                f"변환된 HTML 파일을 찾을 수 없습니다: {tmpdir_path}"
            )

        html_file = html_files[0]
        html_content = html_file.read_text(encoding="utf-8", errors="replace")

        # bindata 폴더 생성 (이미지 경로 호환성)
        # LibreOffice는 이미지를 HTML과 같은 폴더에 생성
        bindata_dir = tmpdir_path / "bindata"
        for img_file in tmpdir_path.iterdir():
            if img_file.suffix.lower() in [".png", ".jpg", ".jpeg", ".gif", ".bmp"]:
                bindata_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(img_file, bindata_dir / img_file.name)
                # HTML 내 이미지 경로 수정
                html_content = html_content.replace(
                    f'src="{img_file.name}"', f'src="bindata/{img_file.name}"'
                )
                html_content = html_content.replace(
                    f"src='{img_file.name}'", f"src='bindata/{img_file.name}'"
                )

        return html_content, tmpdir_path

    except subprocess.TimeoutExpired:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise LibreOfficeConversionError("LibreOffice 변환 시간 초과 (120초)")

    except Exception as e:
        shutil.rmtree(tmpdir, ignore_errors=True)
        if isinstance(e, (LibreOfficeConversionError, FileNotFoundError)):
            raise
        raise LibreOfficeConversionError(f"LibreOffice 변환 실패: {e}") from e


def extract_images_libreoffice(
    html_dir: Path, output_dir: Path, base_name: Optional[str] = None
) -> dict[str, str]:
    """LibreOffice가 생성한 HTML 디렉토리에서 이미지 추출.

    Args:
        html_dir: HTML이 생성된 디렉토리
        output_dir: 이미지를 저장할 디렉토리
        base_name: 이미지 폴더 이름

    Returns:
        dict: 원본 경로 -> 새 경로 매핑
    """
    if base_name is None:
        base_name = settings.converter.images_dir_name

    images_dir = output_dir / base_name
    path_mapping = {}

    # bindata 폴더 확인
    bindata_dir = html_dir / "bindata"
    if bindata_dir.exists():
        images_dir.mkdir(parents=True, exist_ok=True)
        for img_file in bindata_dir.iterdir():
            if img_file.is_file():
                new_path = images_dir / img_file.name
                shutil.copy2(img_file, new_path)
                path_mapping[f"bindata/{img_file.name}"] = f"{base_name}/{img_file.name}"

    # 루트 폴더의 이미지도 확인
    for img_file in html_dir.iterdir():
        if img_file.suffix.lower() in [".png", ".jpg", ".jpeg", ".gif", ".bmp"]:
            images_dir.mkdir(parents=True, exist_ok=True)
            new_path = images_dir / img_file.name
            if not new_path.exists():
                shutil.copy2(img_file, new_path)
            path_mapping[img_file.name] = f"{base_name}/{img_file.name}"

    return path_mapping
