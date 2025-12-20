"""FastAPI API 테스트."""

from pathlib import Path

import pytest

# 샘플 데이터 경로
SAMPLE_DIR = Path(__file__).parent.parent / "docs" / "sample-data"


@pytest.fixture
def client():
    """테스트 클라이언트."""
    try:
        from fastapi.testclient import TestClient

        from hwp_to_markdown.api import app

        return TestClient(app)
    except ImportError:
        pytest.skip("FastAPI not installed (install with: uv sync --extra api)")


class TestAPIEndpoints:
    """API 엔드포인트 테스트."""

    def test_root(self, client):
        """루트 엔드포인트."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "hwp-to-markdown"

    def test_health(self, client):
        """헬스 체크."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_convert_invalid_file(self, client):
        """잘못된 파일 형식."""
        response = client.post(
            "/convert",
            files={"file": ("test.txt", b"hello world", "text/plain")},
        )
        assert response.status_code == 400
        assert "HWP" in response.json()["detail"]

    @pytest.mark.skipif(
        not SAMPLE_DIR.exists(),
        reason="샘플 데이터 없음",
    )
    def test_convert_sample(self, client):
        """샘플 HWP 파일 변환."""
        sample_files = list(SAMPLE_DIR.glob("*.hwp"))
        if not sample_files:
            pytest.skip("샘플 HWP 파일 없음")

        hwp_file = sample_files[0]

        with open(hwp_file, "rb") as f:
            response = client.post(
                "/convert",
                files={"file": (hwp_file.name, f, "application/octet-stream")},
            )

        # hwp5html이 없으면 500 에러 (CI 환경)
        if response.status_code == 500:
            if "hwp5html" in response.json().get("detail", ""):
                pytest.skip("hwp5html not available")

        assert response.status_code == 200
        data = response.json()
        assert "markdown" in data
        assert len(data["markdown"]) > 0

    @pytest.mark.skipif(
        not SAMPLE_DIR.exists(),
        reason="샘플 데이터 없음",
    )
    def test_convert_file_download(self, client):
        """Markdown 파일 다운로드."""
        sample_files = list(SAMPLE_DIR.glob("*.hwp"))
        if not sample_files:
            pytest.skip("샘플 HWP 파일 없음")

        hwp_file = sample_files[0]

        with open(hwp_file, "rb") as f:
            response = client.post(
                "/convert/file",
                files={"file": (hwp_file.name, f, "application/octet-stream")},
            )

        if response.status_code == 500:
            if "hwp5html" in response.json().get("detail", ""):
                pytest.skip("hwp5html not available")

        assert response.status_code == 200
        assert "text/markdown" in response.headers["content-type"]
        assert "attachment" in response.headers["content-disposition"]

    @pytest.mark.skipif(
        not SAMPLE_DIR.exists(),
        reason="샘플 데이터 없음",
    )
    def test_convert_zip(self, client):
        """ZIP 파일 다운로드."""
        sample_files = list(SAMPLE_DIR.glob("*.hwp"))
        if not sample_files:
            pytest.skip("샘플 HWP 파일 없음")

        hwp_file = sample_files[0]

        with open(hwp_file, "rb") as f:
            response = client.post(
                "/convert/zip",
                files={"file": (hwp_file.name, f, "application/octet-stream")},
            )

        if response.status_code == 500:
            if "hwp5html" in response.json().get("detail", ""):
                pytest.skip("hwp5html not available")

        assert response.status_code == 200
        assert "application/zip" in response.headers["content-type"]
        assert "attachment" in response.headers["content-disposition"]
