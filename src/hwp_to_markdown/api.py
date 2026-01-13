"""HWP/HWPX to Markdown FastAPI 웹 API."""

import io
import shutil
import tempfile
import zipfile
from enum import Enum
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response, StreamingResponse


def make_content_disposition(filename: str, disposition: str = "attachment") -> str:
    """RFC 5987 호환 Content-Disposition 헤더 생성.

    한글 등 비ASCII 문자를 포함한 파일명을 안전하게 처리합니다.
    """
    # ASCII 안전 파일명 (fallback)
    ascii_filename = filename.encode("ascii", "ignore").decode("ascii") or "download"
    # UTF-8 인코딩된 파일명
    encoded_filename = quote(filename, safe="")

    return f"{disposition}; filename=\"{ascii_filename}\"; filename*=UTF-8''{encoded_filename}"


from .config import settings
from .converter import (
    ConversionMethod,
    HwpConversionError,
    convert,
    extract_images,
    html_to_markdown,
    hwp_to_html,
)


class APIConversionMethod(str, Enum):
    """API에서 사용하는 변환 방법 열거형."""

    AUTO = "auto"
    PYHWP = "pyhwp"
    HWPX_NATIVE = "hwpx-native"
    LIBREOFFICE = "libreoffice"


app = FastAPI(
    title="HWP/HWPX to Markdown API",
    description="한글 문서(HWP, HWPX)를 Markdown으로 변환하는 웹 API",
    version="0.2.0",
)


def get_images_dir_name() -> str:
    """이미지 디렉토리 이름 반환."""
    return settings.converter.images_dir_name


def _validate_file(filename: Optional[str]) -> None:
    """파일 확장자 검증."""
    if not filename:
        raise HTTPException(
            status_code=400,
            detail="파일명이 필요합니다.",
        )

    ext = filename.lower()
    if not ext.endswith((".hwp", ".hwpx")):
        raise HTTPException(
            status_code=400,
            detail="HWP 또는 HWPX 파일만 업로드 가능합니다.",
        )


def _get_temp_suffix(filename: str) -> str:
    """파일명에서 임시 파일 확장자 추출."""
    if filename.lower().endswith(".hwpx"):
        return ".hwpx"
    return ".hwp"


@app.get("/")
async def root():
    """API 상태 확인."""
    return {
        "status": "ok",
        "service": "hwp-to-markdown",
        "version": "0.2.0",
        "supported_formats": ["hwp", "hwpx"],
        "conversion_methods": ["auto", "pyhwp", "hwpx-native", "libreoffice"],
    }


@app.get("/health")
async def health():
    """헬스 체크."""
    return {"status": "healthy"}


@app.post("/convert")
async def convert_hwp_to_markdown(
    file: UploadFile = File(...),
    method: APIConversionMethod = Query(
        default=APIConversionMethod.AUTO,
        description="변환 방법: auto, pyhwp, hwpx-native, libreoffice",
    ),
):
    """HWP/HWPX 파일을 Markdown 텍스트로 변환.

    Args:
        file: 업로드된 HWP/HWPX 파일
        method: 변환 방법 (auto, pyhwp, hwpx-native, libreoffice)

    Returns:
        JSON 응답: {"filename": str, "markdown": str, "method": str}
    """
    _validate_file(file.filename)

    suffix = _get_temp_suffix(file.filename)

    # 임시 파일로 저장
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = Path(tmp.name)
        content = await file.read()
        tmp.write(content)

    try:
        markdown = convert(tmp_path, method=ConversionMethod(method.value))
        return {
            "filename": file.filename,
            "markdown": markdown,
            "method": method.value,
        }

    except HwpConversionError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    finally:
        tmp_path.unlink(missing_ok=True)


@app.post("/convert/file")
async def convert_hwp_to_markdown_file(
    file: UploadFile = File(...),
    method: APIConversionMethod = Query(
        default=APIConversionMethod.AUTO,
        description="변환 방법: auto, pyhwp, hwpx-native, libreoffice",
    ),
):
    """HWP/HWPX 파일을 Markdown 파일로 변환하여 다운로드.

    Args:
        file: 업로드된 HWP/HWPX 파일
        method: 변환 방법 (auto, pyhwp, hwpx-native, libreoffice)

    Returns:
        Markdown 파일 다운로드
    """
    _validate_file(file.filename)

    suffix = _get_temp_suffix(file.filename)

    # 임시 파일로 저장
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = Path(tmp.name)
        content = await file.read()
        tmp.write(content)

    try:
        markdown = convert(tmp_path, method=ConversionMethod(method.value))

        # 파일명 생성
        md_filename = Path(file.filename).stem + ".md"

        return Response(
            content=markdown.encode("utf-8"),
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": make_content_disposition(md_filename)
            },
        )

    except HwpConversionError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    finally:
        tmp_path.unlink(missing_ok=True)


@app.post("/convert/zip")
async def convert_hwp_to_zip(
    file: UploadFile = File(...),
    method: APIConversionMethod = Query(
        default=APIConversionMethod.AUTO,
        description="변환 방법: auto, pyhwp, hwpx-native, libreoffice",
    ),
):
    """HWP/HWPX 파일을 Markdown + 이미지가 포함된 ZIP으로 변환.

    Args:
        file: 업로드된 HWP/HWPX 파일
        method: 변환 방법 (auto, pyhwp, hwpx-native, libreoffice)

    Returns:
        ZIP 파일 다운로드 (markdown.md + images/ 폴더)
    """
    _validate_file(file.filename)

    suffix = _get_temp_suffix(file.filename)

    # 임시 파일로 저장
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = Path(tmp.name)
        content = await file.read()
        tmp.write(content)

    tmpdir = None
    try:
        # 변환 방법에 따른 처리
        conversion_method = ConversionMethod(method.value)

        # 임시 출력 디렉토리
        with tempfile.TemporaryDirectory() as output_dir:
            output_path = Path(output_dir)
            md_file = output_path / "temp.md"

            # 변환 실행 (이미지 추출 포함)
            markdown = convert(
                tmp_path,
                output=md_file,
                images_dir=output_path,
                method=conversion_method,
            )

            # ZIP 파일 생성
            zip_buffer = io.BytesIO()
            base_name = Path(file.filename).stem

            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                # Markdown 파일 추가
                zf.writestr(f"{base_name}.md", markdown.encode("utf-8"))

                # 이미지 파일 추가
                images_dir = output_path / get_images_dir_name()
                if images_dir.exists():
                    for img_file in images_dir.iterdir():
                        if img_file.is_file():
                            zf.write(img_file, f"images/{img_file.name}")

            zip_buffer.seek(0)

            zip_filename = f"{base_name}.zip"
            return StreamingResponse(
                zip_buffer,
                media_type="application/zip",
                headers={
                    "Content-Disposition": make_content_disposition(zip_filename)
                },
            )

    except HwpConversionError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    finally:
        tmp_path.unlink(missing_ok=True)
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)


def create_app() -> FastAPI:
    """FastAPI 앱 팩토리."""
    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=settings.api.port,
    )
