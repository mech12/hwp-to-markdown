# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-01-02

### Added

#### HWPX 지원
- **HWPX 네이티브 파서** (`hwpx_parser.py`): HWPX 파일을 직접 파싱하여 Markdown으로 변환
  - ZIP 기반 XML 포맷 파싱
  - 문단, 테이블, 이미지 추출 지원
  - 섹션별 자동 처리

- **LibreOffice 변환기** (`libreoffice_converter.py`): LibreOffice를 사용한 HWP/HWPX 변환
  - macOS, Linux, Windows 자동 경로 감지
  - HWP와 HWPX 모두 지원
  - 이미지 자동 추출

#### 변환 방법 선택 옵션
- `ConversionMethod` 열거형 추가:
  - `auto`: 파일 형식 자동 감지 (기본값)
  - `pyhwp`: pyhwp(hwp5html) 사용 (HWP만 지원)
  - `hwpx-native`: HWPX 네이티브 파서 사용
  - `libreoffice`: LibreOffice 사용 (HWP/HWPX 모두 지원)

#### Python API
```python
from hwp_to_markdown import convert, ConversionMethod

# 자동 감지 (기본)
markdown = convert("document.hwpx")

# 명시적 변환 방법 지정
markdown = convert("document.hwpx", method="hwpx-native")
markdown = convert("document.hwpx", method="libreoffice")
markdown = convert("document.hwp", method="pyhwp")
```

#### CLI
```bash
# 자동 감지
hwp2md document.hwpx -o output.md

# 변환 방법 지정
hwp2md -m hwpx-native document.hwpx -o output.md
hwp2md -m libreoffice document.hwpx -o output.md
hwp2md -m pyhwp document.hwp -o output.md
```

#### Web API
- `/convert`, `/convert/file`, `/convert/zip` 엔드포인트에 `method` 쿼리 파라미터 추가
- HWPX 파일 업로드 지원
- API 루트 엔드포인트에 지원 포맷 및 변환 방법 정보 추가

```bash
# 자동 감지
curl -X POST -F "file=@document.hwpx" "http://localhost:8000/convert"

# 변환 방법 지정
curl -X POST -F "file=@document.hwpx" "http://localhost:8000/convert?method=libreoffice"
```

### Changed
- 버전 0.1.0 → 0.2.0
- `convert()` 함수에 `method` 파라미터 추가 (기본값: `"auto"`)
- API 버전 0.1.0 → 0.2.0
- 파일 확장자 검증 로직 확장 (.hwp, .hwpx 모두 허용)
- `make convert-samples`: HWP와 HWPX 파일 모두 변환하도록 수정

### Technical Details

#### HWPX 파일 구조
HWPX는 ZIP 기반 XML 포맷입니다:
```
mimetype                    # MIME 타입 정보
version.xml                 # 버전 정보
Contents/
  header.xml               # 문서 헤더 (폰트, 스타일 등)
  section0.xml             # 본문 내용 (문단, 테이블 등)
  content.hpf              # 콘텐츠 메타데이터
BinData/                   # 이미지 등 바이너리 데이터
Preview/                   # 미리보기 이미지
```

#### 변환 방법별 특징

| 방법 | HWP 지원 | HWPX 지원 | 외부 의존성 |
|------|----------|-----------|-------------|
| pyhwp | ✅ | ❌ | pyhwp 패키지 |
| hwpx-native | ❌ | ✅ | 없음 |
| libreoffice | ✅ | ✅ | LibreOffice 설치 필요 |
| auto | ✅ | ✅ | 파일 형식에 따라 자동 선택 |

## [0.1.0] - 2024-12-20

### Added
- 초기 릴리스
- HWP → HTML → Markdown 2단계 파이프라인 변환
- Python API: `convert()` 함수
- CLI 도구: `hwp2md` 명령어
- FastAPI 웹 API: `/convert`, `/convert/file`, `/convert/zip` 엔드포인트
- 이미지 추출 및 별도 폴더 저장
- 환경 변수 기반 설정 (`config.py`, `.env.example`)
- 테이블 내 이미지 처리 (markdownify 이슈 우회)
