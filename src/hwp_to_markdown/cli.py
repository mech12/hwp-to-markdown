"""HWP to Markdown CLI 도구."""

import argparse
import sys
from pathlib import Path

from .converter import HwpConversionError, convert


def main() -> int:
    """CLI 진입점."""
    parser = argparse.ArgumentParser(
        prog="hwp2md",
        description="HWP 파일을 Markdown으로 변환합니다.",
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="변환할 HWP 파일 경로",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="출력 파일 경로 (단일 파일 변환 시)",
    )
    parser.add_argument(
        "--output-dir",
        help="출력 디렉토리 (여러 파일 일괄 변환 시)",
    )
    parser.add_argument(
        "--images-dir",
        help="이미지 저장 디렉토리",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="진행 메시지 숨김",
    )

    args = parser.parse_args()

    # 파일 목록 확장 (glob 패턴 처리)
    files = []
    for pattern in args.files:
        path = Path(pattern)
        if path.exists():
            files.append(path)
        else:
            # glob 패턴으로 시도
            matched = list(Path.cwd().glob(pattern))
            if matched:
                files.extend(matched)
            else:
                print(f"경고: 파일을 찾을 수 없습니다: {pattern}", file=sys.stderr)

    if not files:
        print("오류: 변환할 HWP 파일이 없습니다.", file=sys.stderr)
        return 1

    # 단일 파일 + -o 옵션
    if len(files) == 1 and args.output:
        try:
            hwp_file = files[0]
            if not args.quiet:
                print(f"변환 중: {hwp_file}")

            markdown = convert(
                hwp_file,
                output=args.output,
                images_dir=args.images_dir,
            )

            if not args.output:
                print(markdown)

            if not args.quiet:
                print(f"완료: {args.output}")

            return 0

        except (HwpConversionError, FileNotFoundError) as e:
            print(f"오류: {e}", file=sys.stderr)
            return 1

    # 여러 파일 또는 --output-dir 사용
    output_dir = Path(args.output_dir) if args.output_dir else Path.cwd()
    output_dir.mkdir(parents=True, exist_ok=True)

    success_count = 0
    error_count = 0

    for hwp_file in files:
        try:
            if not args.quiet:
                print(f"변환 중: {hwp_file}")

            # 출력 파일명 생성
            output_file = output_dir / f"{hwp_file.stem}.md"

            convert(
                hwp_file,
                output=output_file,
                images_dir=args.images_dir,
            )

            if not args.quiet:
                print(f"  → {output_file}")

            success_count += 1

        except (HwpConversionError, FileNotFoundError) as e:
            print(f"오류 ({hwp_file}): {e}", file=sys.stderr)
            error_count += 1

    # 결과 요약
    if not args.quiet:
        print(f"\n완료: {success_count}개 성공, {error_count}개 실패")

    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
