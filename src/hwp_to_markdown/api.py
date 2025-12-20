"""HWP to Markdown FastAPI 웹 API."""

import io
import shutil
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, File, HTTPException, UploadFile
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
from .converter import HwpConversionError, convert, extract_images, hwp_to_html, html_to_markdown

app = FastAPI(
    title="HWP to Markdown API",
    description="한글 문서(HWP)를 Markdown으로 변환하는 웹 API",
    version="0.1.0",
)


def get_images_dir_name() -> str:
    """이미지 디렉토리 이름 반환."""
    return settings.converter.images_dir_name


@app.get("/")
async def root():
    """API 상태 확인."""
    return {
        "status": "ok",
        "service": "hwp-to-markdown",
        "version": "0.1.0",
    }


@app.get("/health")
async def health():
    """헬스 체크."""
    return {"status": "healthy"}


@app.post("/convert")
async def convert_hwp_to_markdown(file: UploadFile = File(...)):
    """HWP 파일을 Markdown 텍스트로 변환.

    Args:
        file: 업로드된 HWP 파일

    Returns:
        JSON 응답: {"filename": str, "markdown": str}
    """
    if not file.filename or not file.filename.lower().endswith(".hwp"):
        raise HTTPException(
            status_code=400,
            detail="HWP 파일만 업로드 가능합니다.",
        )

    # 임시 파일로 저장
    with tempfile.NamedTemporaryFile(suffix=".hwp", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        content = await file.read()
        tmp.write(content)

    try:
        markdown = convert(tmp_path)
        return {
            "filename": file.filename,
            "markdown": markdown,
        }

    except HwpConversionError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    finally:
        tmp_path.unlink(missing_ok=True)


@app.post("/convert/file")
async def convert_hwp_to_markdown_file(file: UploadFile = File(...)):
    """HWP 파일을 Markdown 파일로 변환하여 다운로드.

    Args:
        file: 업로드된 HWP 파일

    Returns:
        Markdown 파일 다운로드
    """
    if not file.filename or not file.filename.lower().endswith(".hwp"):
        raise HTTPException(
            status_code=400,
            detail="HWP 파일만 업로드 가능합니다.",
        )

    # 임시 파일로 저장
    with tempfile.NamedTemporaryFile(suffix=".hwp", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        content = await file.read()
        tmp.write(content)

    try:
        markdown = convert(tmp_path)

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
async def convert_hwp_to_zip(file: UploadFile = File(...)):
    """HWP 파일을 Markdown + 이미지가 포함된 ZIP으로 변환.

    Args:
        file: 업로드된 HWP 파일

    Returns:
        ZIP 파일 다운로드 (markdown.md + images/ 폴더)
    """
    if not file.filename or not file.filename.lower().endswith(".hwp"):
        raise HTTPException(
            status_code=400,
            detail="HWP 파일만 업로드 가능합니다.",
        )

    # 임시 파일로 저장
    with tempfile.NamedTemporaryFile(suffix=".hwp", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        content = await file.read()
        tmp.write(content)

    tmpdir = None
    try:
        # HWP → HTML 변환
        html_content, tmpdir = hwp_to_html(tmp_path)

        # 임시 출력 디렉토리
        with tempfile.TemporaryDirectory() as output_dir:
            output_path = Path(output_dir)

            # 이미지 추출
            image_mapping = extract_images(tmpdir, output_path)

            # Markdown 변환
            markdown = html_to_markdown(html_content, image_mapping)

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
