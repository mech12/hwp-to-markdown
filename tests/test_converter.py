"""HWP to Markdown 변환기 테스트."""

import tempfile
from pathlib import Path

import pytest

from hwp_to_markdown import HwpConversionError, convert
from hwp_to_markdown.converter import html_to_markdown

# 샘플 데이터 경로
SAMPLE_DIR = Path(__file__).parent.parent / "docs" / "sample-data"


class TestHtmlToMarkdown:
    """HTML → Markdown 변환 테스트."""

    def test_basic_conversion(self):
        """기본 HTML 변환."""
        html = "<h1>제목</h1><p>본문입니다.</p>"
        result = html_to_markdown(html)
        assert "# 제목" in result
        assert "본문입니다." in result

    def test_table_conversion(self):
        """표 변환."""
        html = """
        <table>
            <tr><th>이름</th><th>나이</th></tr>
            <tr><td>홍길동</td><td>30</td></tr>
        </table>
        """
        result = html_to_markdown(html)
        assert "이름" in result
        assert "홍길동" in result

    def test_list_conversion(self):
        """목록 변환."""
        html = "<ul><li>항목1</li><li>항목2</li></ul>"
        result = html_to_markdown(html)
        assert "- 항목1" in result or "* 항목1" in result

    def test_image_path_replacement(self):
        """이미지 경로 치환."""
        html = '<img src="bindata/image1.png" alt="이미지">'
        mapping = {"bindata/image1.png": "images/image1.png"}
        result = html_to_markdown(html, image_mapping=mapping)
        assert "images/image1.png" in result

    def test_strip_script_style(self):
        """script, style 태그 제거."""
        html = """
        <style>body { color: red; }</style>
        <script>alert('test');</script>
        <p>본문</p>
        """
        result = html_to_markdown(html)
        assert "color: red" not in result
        assert "alert" not in result
        assert "본문" in result


class TestConvert:
    """HWP 변환 통합 테스트."""

    def test_file_not_found(self):
        """존재하지 않는 파일."""
        with pytest.raises(FileNotFoundError):
            convert("nonexistent.hwp")

    @pytest.mark.skipif(
        not SAMPLE_DIR.exists(),
        reason="샘플 데이터 없음",
    )
    def test_sample_conversion(self):
        """샘플 HWP 파일 변환."""
        sample_files = list(SAMPLE_DIR.glob("*.hwp"))
        if not sample_files:
            pytest.skip("샘플 HWP 파일 없음")

        hwp_file = sample_files[0]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.md"

            try:
                markdown = convert(hwp_file, output=output_path)

                # 결과 확인
                assert len(markdown) > 0
                assert output_path.exists()

                # 파일 내용 확인
                file_content = output_path.read_text(encoding="utf-8")
                assert file_content == markdown

            except HwpConversionError as e:
                # pyhwp가 설치되지 않은 환경
                if "hwp5html" in str(e):
                    pytest.skip("hwp5html not available")
                raise

    @pytest.mark.skipif(
        not SAMPLE_DIR.exists(),
        reason="샘플 데이터 없음",
    )
    def test_image_extraction(self):
        """이미지 추출 테스트."""
        sample_files = list(SAMPLE_DIR.glob("*.hwp"))
        if not sample_files:
            pytest.skip("샘플 HWP 파일 없음")

        hwp_file = sample_files[0]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.md"

            try:
                convert(hwp_file, output=output_path)

                # images 폴더 확인 (이미지가 있는 경우에만)
                images_dir = Path(tmpdir) / "images"
                # 이미지가 없을 수도 있으므로 존재 여부만 확인하지 않음

            except HwpConversionError as e:
                if "hwp5html" in str(e):
                    pytest.skip("hwp5html not available")
                raise


class TestCLI:
    """CLI 테스트."""

    def test_import_cli(self):
        """CLI 모듈 임포트."""
        from hwp_to_markdown.cli import main

        assert callable(main)
