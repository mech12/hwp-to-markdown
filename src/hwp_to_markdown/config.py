"""HWP to Markdown 설정 모듈."""

import os
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class APIConfig:
    """API 서버 설정."""

    host: str = field(default_factory=lambda: os.getenv("API_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("API_PORT", "8000")))


@dataclass
class ConverterConfig:
    """변환기 설정."""

    # Markdown 헤딩 스타일: ATX (#) 또는 SETEXT (underline)
    heading_style: Literal["ATX", "SETEXT"] = field(
        default_factory=lambda: os.getenv("HEADING_STYLE", "ATX")  # type: ignore
    )
    # 리스트 불릿 스타일
    bullet_style: str = field(default_factory=lambda: os.getenv("BULLET_STYLE", "-"))
    # 이미지 디렉토리 이름
    images_dir_name: str = field(
        default_factory=lambda: os.getenv("IMAGES_DIR_NAME", "images")
    )


@dataclass
class LogConfig:
    """로깅 설정."""

    level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))


@dataclass
class Settings:
    """전체 설정."""

    api: APIConfig = field(default_factory=APIConfig)
    converter: ConverterConfig = field(default_factory=ConverterConfig)
    log: LogConfig = field(default_factory=LogConfig)


# 전역 설정 인스턴스
settings = Settings()


def load_dotenv() -> None:
    """환경 변수 파일 로드 (선택적)."""
    try:
        from dotenv import load_dotenv as _load_dotenv

        _load_dotenv()
    except ImportError:
        pass  # python-dotenv가 설치되지 않은 경우 무시


# 모듈 로드 시 .env 파일 로드 시도
load_dotenv()
