.PHONY: help install install-dev install-api sync test test-cov convert-samples local serve clean build

SAMPLE_DIR := docs/sample-data
OUTPUT_DIR := docs/sample-data/markdown

help:  ## 도움말 표시
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## 기본 의존성 설치
	uv sync

install-dev:  ## 개발 의존성 설치
	uv sync --extra dev

install-api:  ## API 의존성 설치
	uv sync --extra api

sync:  ## 모든 의존성 설치
	uv sync --extra dev --extra api

convert-samples:  ## 샘플 HWP 파일을 Markdown으로 변환
	@mkdir -p $(OUTPUT_DIR)
	@echo "Converting sample HWP files to Markdown..."
	@for file in $(SAMPLE_DIR)/*.hwp; do \
		if [ -f "$$file" ]; then \
			echo "  Converting: $$file"; \
			uv run hwp2md "$$file" --output-dir $(OUTPUT_DIR) || true; \
		fi \
	done
	@echo "Output directory: $(OUTPUT_DIR)"

test: convert-samples  ## 테스트 실행 (샘플 변환 포함)
	uv run pytest -v

test-cov:  ## 커버리지 포함 테스트
	uv run pytest --cov=hwp_to_markdown --cov-report=term-missing

local:  ## 로컬 API 서버 실행 (http://localhost:8000)
	@echo "Starting HWP to Markdown API server..."
	@echo "API docs: http://localhost:8000/docs"
	uv run uvicorn hwp_to_markdown.api:app --host 0.0.0.0 --port 8000 --reload

serve:  ## 프로덕션 모드 서버 실행
	uv run uvicorn hwp_to_markdown.api:app --host 0.0.0.0 --port 8000

clean:  ## 캐시 및 빌드 파일 정리
	rm -rf .pytest_cache
	rm -rf __pycache__
	rm -rf src/**/__pycache__
	rm -rf tests/__pycache__
	rm -rf .coverage
	rm -rf htmlcov
	rm -rf dist
	rm -rf *.egg-info

build:  ## 패키지 빌드
	uv build
