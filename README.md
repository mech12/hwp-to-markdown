# HWP to Markdown

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

한글 문서(HWP)를 Markdown으로 변환하는 Python 라이브러리입니다.

## 배경

| 패키지 | 기능 | Markdown 지원 |
|--------|------|---------------|
| **pyhwp** | HWP → TXT, HTML, ODT, XML | ❌ |
| **markitdown** | 다양한 Office 포맷 → MD | ❌ HWP 미지원 |
| **md2hml** | Markdown → HWP (반대 방향) | - |

기존에 HWP를 직접 Markdown으로 변환하는 도구가 없어, 2단계 파이프라인 방식으로 해결합니다.

```
HWP → HTML (pyhwp) → Markdown (markdownify)
```

## 설치

```bash
uv add hwp-to-markdown
```

또는 pip 사용:

```bash
pip install hwp-to-markdown
```

### 의존성

- [pyhwp](https://github.com/mete0r/pyhwp) - HWP 파서 및 HTML 변환
- [markdownify](https://github.com/matthewwithanm/python-markdownify) - HTML → Markdown 변환

## 사용법

### Python API

```python
from hwp_to_markdown import convert

# 파일 경로로 변환
markdown = convert("document.hwp")
print(markdown)

# 파일로 저장
convert("document.hwp", output="document.md")
```

### CLI

```bash
# 기본 사용
hwp2md document.hwp

# 출력 파일 지정
hwp2md document.hwp -o document.md

# 여러 파일 일괄 변환
hwp2md *.hwp --output-dir ./markdown/
```

### 웹 API (FastAPI)

웹 API를 사용하려면 추가 의존성을 설치합니다:

```bash
uv add hwp-to-markdown[api]
# 또는
pip install hwp-to-markdown[api]
```

서버 실행:

```bash
uvicorn hwp_to_markdown.api:app --host 0.0.0.0 --port 8000
```

API 엔드포인트:

| 엔드포인트 | 메서드 | 설명 |
|------------|--------|------|
| `/` | GET | API 상태 확인 |
| `/health` | GET | 헬스 체크 |
| `/convert` | POST | HWP → Markdown (JSON 응답) |
| `/convert/file` | POST | HWP → Markdown 파일 다운로드 |
| `/convert/zip` | POST | HWP → Markdown + 이미지 ZIP 다운로드 |

사용 예시 (curl):

```bash
# JSON 응답
curl -X POST -F "file=@document.hwp" http://localhost:8000/convert

# Markdown 파일 다운로드
curl -X POST -F "file=@document.hwp" http://localhost:8000/convert/file -o output.md

# ZIP 다운로드 (이미지 포함)
curl -X POST -F "file=@document.hwp" http://localhost:8000/convert/zip -o output.zip
```

API 문서: `http://localhost:8000/docs` (Swagger UI)

## 기능

- HWP 문서를 Markdown으로 변환
- 표(Table) 지원
- 이미지 추출 및 참조 유지
- 제목 스타일 자동 인식 (ATX 형식)
- CLI 도구 제공
- 일괄 변환 지원

## 제한사항

- HWP 5.0 이상 형식만 지원 (pyhwp 제약)
- 복잡한 레이아웃은 일부 손실될 수 있음
- 수식(Equation)은 이미지로 처리됨

## 개발

```bash
# 저장소 클론
git clone https://github.com/surromind/hwp-to-markdown.git
cd hwp-to-markdown

# 의존성 설치
uv sync

# 테스트 실행
uv run pytest
```

## 기여

기여를 환영합니다! 다음 방법으로 참여할 수 있습니다:

1. 이슈 등록: 버그 리포트 또는 기능 제안
2. Pull Request: 코드 기여
3. 문서 개선: README, 예제 추가

## 라이선스

MIT License - 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

## 관련 프로젝트

- [mete0r/pyhwp](https://github.com/mete0r/pyhwp) - HWP Document Format v5 parser & processor
- [matthewwithanm/python-markdownify](https://github.com/matthewwithanm/python-markdownify) - HTML to Markdown 변환
- [Goldziher/html-to-markdown](https://github.com/Goldziher/html-to-markdown) - 고성능 HTML to Markdown (Rust 기반)
