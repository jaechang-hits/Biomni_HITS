#!/usr/bin/env python3
"""
라이브러리 라이센스 조사 스크립트
pixi.toml에 있는 패키지들의 라이센스 정보를 PyPI 및 Conda에서 조회합니다.
SaaS 및 On-premise 시나리오별로 상업적 이용 가능 여부를 분석합니다.
"""

import json
import requests
import re
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed

# 라이센스 타입 분류 (모두 대문자로 저장)
LICENSE_TYPES = {
    # Permissive (허용적) 라이센스
    "permissive": [
        "MIT",
        "BSD",
        "APACHE",
        "ISC",
        "UNLICENSE",
        "PSF",
        "PSFL",
        "PYTHON SOFTWARE FOUNDATION",
        "PYTHON-2.0",  # Python License
        "PYTHON 2.0",
        "ZLIB",
        "CC0",
        "CC-BY",  # Creative Commons Attribution
        "PUBLIC DOMAIN",
        "NCBI-PD",  # NCBI Public Domain
        "PD",  # Public Domain 약어
        "WTFPL",
        "BOOST",
        "ARTISTIC",  # Perl Artistic License
        "BIOPYTHON",  # Biopython License (BSD 계열)
        "LICENSEREF-BIOPYTHON",
        "0BSD",  # Zero-Clause BSD
        "JSON",  # JSON License (MIT와 유사)
        "HPND",  # Historical Permission Notice and Disclaimer
        "UNICODE",  # Unicode License
    ],
    # Weak Copyleft (약한 카피레프트)
    "weak_copyleft": ["LGPL", "MPL", "EPL", "CDDL", "EUPL"],
    # Strong Copyleft (강한 카피레프트)
    "strong_copyleft": ["GPL"],  # LGPL은 제외, AGPL은 별도
    # Network Copyleft (네트워크 카피레프트)
    "network_copyleft": ["AGPL"],
}


@dataclass
class PackageInfo:
    name: str
    source: str  # "conda" or "pypi"
    license: str = "Unknown"
    license_type: str = (
        "unknown"  # permissive, weak_copyleft, strong_copyleft, network_copyleft, unknown
    )
    saas_status: str = "❓ 확인 필요"
    onpremise_status: str = "❓ 확인 필요"
    version: str = ""
    homepage: str = ""
    error: str = ""


def parse_pixi_toml(filepath: str) -> tuple[list[str], list[str]]:
    """pixi.toml 파일에서 conda 및 pypi 패키지 목록 추출"""
    conda_packages = []
    pypi_packages = []

    with open(filepath, "r") as f:
        content = f.read()

    # [dependencies] 섹션 파싱
    deps_match = re.search(r"\[dependencies\](.*?)(?=\[|$)", content, re.DOTALL)
    if deps_match:
        deps_section = deps_match.group(1)
        for line in deps_section.strip().split("\n"):
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                pkg_name = line.split("=")[0].strip().strip('"')
                if pkg_name:
                    conda_packages.append(pkg_name)

    # [pypi-dependencies] 섹션 파싱
    pypi_match = re.search(r"\[pypi-dependencies\](.*?)(?=\[|$)", content, re.DOTALL)
    if pypi_match:
        pypi_section = pypi_match.group(1)
        for line in pypi_section.strip().split("\n"):
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                pkg_name = line.split("=")[0].strip().strip('"')
                if pkg_name:
                    pypi_packages.append(pkg_name)

    return conda_packages, pypi_packages


def classify_license(license_str: str) -> str:
    """라이센스 문자열에서 라이센스 타입 분류"""
    if not license_str or license_str == "Unknown":
        return "unknown"

    license_upper = license_str.upper()

    # AGPL 먼저 체크 (가장 제한적)
    if "AGPL" in license_upper:
        return "network_copyleft"

    # LGPL 체크 (GPL보다 먼저)
    if "LGPL" in license_upper:
        return "weak_copyleft"

    # MPL, EPL 체크
    if any(
        x in license_upper for x in ["MPL", "MOZILLA", "EPL", "ECLIPSE", "CDDL", "EUPL"]
    ):
        return "weak_copyleft"

    # GPL 체크
    if "GPL" in license_upper:
        return "strong_copyleft"

    # Permissive 라이센스 체크 (LICENSE_TYPES는 이미 대문자)
    if any(x in license_upper for x in LICENSE_TYPES["permissive"]):
        return "permissive"

    # 추가 Permissive 패턴 체크 (일반적인 표현들)
    permissive_patterns = [
        "FREE",
        "PERMISSIVE",
        "OPEN SOURCE",
        "NO RESTRICTION",
        "UNRESTRICTED",
    ]
    # Custom 라이센스는 unknown으로 유지 (개별 확인 필요)
    if license_upper == "CUSTOM":
        return "unknown"

    return "unknown"


def get_saas_status(license_type: str, license_str: str) -> str:
    """SaaS 배포 시 상업적 이용 가능 여부 판단

    SaaS 특성:
    - 소프트웨어가 서버에서 실행되고 사용자는 네트워크로 접근
    - 소프트웨어 자체를 "배포"하지 않음
    - GPL: 배포가 아니므로 소스 공개 의무 없음 (SaaS Loophole)
    - AGPL: 네트워크 서비스도 배포로 간주 → 소스 공개 필요
    """
    if license_type == "permissive":
        return "✅ 이용 가능"
    elif license_type == "weak_copyleft":
        return "✅ 이용 가능"
    elif license_type == "strong_copyleft":
        return "✅ 이용 가능 (SaaS Loophole)"
    elif license_type == "network_copyleft":
        return "❌ 소스 공개 필요"
    else:
        return "❓ 확인 필요"


def get_onpremise_status(license_type: str, license_str: str) -> str:
    """On-premise 배포 시 상업적 이용 가능 여부 판단

    On-premise 특성:
    - 소프트웨어를 고객에게 직접 설치/배포
    - "배포"에 해당하여 라이센스 조건 적용
    - GPL: 파생 저작물 전체 소스 공개 필요
    - LGPL: 동적 링크 시 본인 코드 비공개 가능 (Python은 대부분 해당)
    """
    if license_type == "permissive":
        return "✅ 이용 가능"
    elif license_type == "weak_copyleft":
        return "⚠️ 조건부 (동적 링크)"
    elif license_type == "strong_copyleft":
        return "⚠️ 소스 공개 필요"
    elif license_type == "network_copyleft":
        return "⚠️ 소스 공개 필요"
    else:
        return "❓ 확인 필요"


def get_pypi_info(package_name: str) -> PackageInfo:
    """PyPI API에서 패키지 정보 조회"""
    info = PackageInfo(name=package_name, source="pypi")

    try:
        # PyPI JSON API
        url = f"https://pypi.org/pypi/{package_name}/json"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            data = response.json()
            pkg_info = data.get("info", {})

            # 최신 PyPI는 license_expression 필드 사용 (SPDX 형식)
            info.license = (
                pkg_info.get("license_expression", "")
                or pkg_info.get("license", "")
                or "Unknown"
            )
            info.version = pkg_info.get("version", "")
            info.homepage = pkg_info.get("home_page", "") or pkg_info.get(
                "project_url", ""
            )

            # 라이센스가 비어있으면 classifier에서 찾기
            if not info.license or info.license == "Unknown" or len(info.license) > 100:
                classifiers = pkg_info.get("classifiers", [])
                for c in classifiers:
                    if "License ::" in c:
                        info.license = c.split("::")[-1].strip()
                        break

            # 너무 긴 라이센스 텍스트 자르기
            if len(info.license) > 80:
                info.license = info.license[:77] + "..."

            # 라이센스 분류 및 상태 설정
            info.license_type = classify_license(info.license)
            info.saas_status = get_saas_status(info.license_type, info.license)
            info.onpremise_status = get_onpremise_status(
                info.license_type, info.license
            )
        else:
            info.error = f"HTTP {response.status_code}"

    except Exception as e:
        info.error = str(e)[:50]

    return info


def get_conda_info(package_name: str) -> PackageInfo:
    """Conda/Anaconda API에서 패키지 정보 조회"""
    info = PackageInfo(name=package_name, source="conda")

    # 패키지 이름 정규화
    normalized_name = package_name.lower().replace("-", "_")

    channels = ["conda-forge", "bioconda", "main", "r"]

    for channel in channels:
        try:
            # Anaconda API
            url = f"https://api.anaconda.org/package/{channel}/{package_name}"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                info.license = data.get("license", "") or "Unknown"
                info.version = data.get("latest_version", "")
                info.homepage = data.get("home", "") or data.get("dev_url", "")

                # 라이센스 분류 및 상태 설정
                info.license_type = classify_license(info.license)
                info.saas_status = get_saas_status(info.license_type, info.license)
                info.onpremise_status = get_onpremise_status(
                    info.license_type, info.license
                )
                return info

        except Exception:
            continue

    # conda에서 못찾으면 PyPI도 시도
    pypi_info = get_pypi_info(package_name)
    if pypi_info.license != "Unknown":
        pypi_info.source = "conda (via PyPI)"
        return pypi_info

    info.error = "Not found in conda channels"
    return info


def process_package(pkg: str, source: str) -> PackageInfo:
    """패키지 정보 조회 (병렬 처리용)"""
    if source == "pypi":
        return get_pypi_info(pkg)
    else:
        return get_conda_info(pkg)


def generate_markdown_report(
    conda_pkgs: list[PackageInfo], pypi_pkgs: list[PackageInfo], output_file: str
):
    """마크다운 형식의 보고서 생성 (SaaS / On-premise 시나리오별)"""
    all_pkgs = conda_pkgs + pypi_pkgs
    total = len(all_pkgs)

    # SaaS 통계
    saas_ok = len([p for p in all_pkgs if "✅" in p.saas_status])
    saas_conditional = len([p for p in all_pkgs if "⚠️" in p.saas_status])
    saas_not_ok = len([p for p in all_pkgs if "❌" in p.saas_status])
    saas_unknown = len([p for p in all_pkgs if "❓" in p.saas_status])

    # On-premise 통계
    onprem_ok = len([p for p in all_pkgs if "✅" in p.onpremise_status])
    onprem_conditional = len([p for p in all_pkgs if "⚠️" in p.onpremise_status])
    onprem_not_ok = len([p for p in all_pkgs if "❌" in p.onpremise_status])
    onprem_unknown = len([p for p in all_pkgs if "❓" in p.onpremise_status])

    report = f"""# 라이브러리 라이센스 분석 보고서
## 배포 시나리오별 상업적 이용 분석

---

## 📊 요약 비교

### SaaS (클라우드 서비스) 배포 시

| 구분 | 개수 | 비율 |
|------|------|------|
| ✅ 이용 가능 | {saas_ok} | {saas_ok/total*100:.1f}% |
| ⚠️ 조건부 이용 | {saas_conditional} | {saas_conditional/total*100:.1f}% |
| ❌ 소스 공개 필요 | {saas_not_ok} | {saas_not_ok/total*100:.1f}% |
| ❓ 확인 필요 | {saas_unknown} | {saas_unknown/total*100:.1f}% |
| **총계** | **{total}** | **100%** |

### On-premise (고객사 설치) 배포 시

| 구분 | 개수 | 비율 |
|------|------|------|
| ✅ 이용 가능 | {onprem_ok} | {onprem_ok/total*100:.1f}% |
| ⚠️ 조건부 이용 | {onprem_conditional} | {onprem_conditional/total*100:.1f}% |
| ❌ 소스 공개 필요 | {onprem_not_ok} | {onprem_not_ok/total*100:.1f}% |
| ❓ 확인 필요 | {onprem_unknown} | {onprem_unknown/total*100:.1f}% |
| **총계** | **{total}** | **100%** |

---

## 📚 라이센스 유형별 설명

### SaaS vs On-premise 차이점

| 라이센스 유형 | SaaS 배포 | On-premise 배포 | 이유 |
|--------------|-----------|-----------------|------|
| **MIT, BSD, Apache** | ✅ 이용 가능 | ✅ 이용 가능 | 허용적 라이센스, 저작권 표기만 필요 |
| **LGPL** | ✅ 이용 가능 | ⚠️ 조건부 | 동적 링크 시 본인 코드 비공개 가능 (Python은 대부분 해당) |
| **GPL** | ✅ 이용 가능* | ⚠️ 소스 공개 필요 | SaaS는 배포가 아님 (SaaS Loophole), On-premise는 배포에 해당 |
| **AGPL** | ❌ 소스 공개 필요 | ⚠️ 소스 공개 필요 | 네트워크 서비스도 배포로 간주 |

> *SaaS Loophole: GPL은 "배포" 시에만 소스 공개 의무가 발생. 서버에서 실행하고 네트워크로 서비스만 제공하는 SaaS는 법적으로 "배포"가 아니므로 소스 공개 의무 없음.

---

## 🔧 Conda 패키지 목록

| 패키지 | 라이센스 | SaaS | On-premise | 버전 |
|--------|----------|------|------------|------|
"""

    for pkg in sorted(conda_pkgs, key=lambda x: x.name):
        license_short = (
            pkg.license[:35] + "..." if len(pkg.license) > 35 else pkg.license
        )
        report += f"| {pkg.name} | {license_short} | {pkg.saas_status} | {pkg.onpremise_status} | {pkg.version} |\n"

    report += f"""
---

## 📦 PyPI 패키지 목록

| 패키지 | 라이센스 | SaaS | On-premise | 버전 |
|--------|----------|------|------------|------|
"""

    for pkg in sorted(pypi_pkgs, key=lambda x: x.name):
        license_short = (
            pkg.license[:35] + "..." if len(pkg.license) > 35 else pkg.license
        )
        report += f"| {pkg.name} | {license_short} | {pkg.saas_status} | {pkg.onpremise_status} | {pkg.version} |\n"

    # SaaS 주의 패키지
    saas_attention = [p for p in all_pkgs if "❌" in p.saas_status]
    if saas_attention:
        report += f"""
---

## 🚨 SaaS 배포 시 주의가 필요한 패키지

아래 패키지들은 SaaS로 서비스 제공 시 **소스 코드 공개가 필요**합니다:

| 패키지 | 라이센스 | 상태 | 권장 조치 |
|--------|----------|------|-----------|
"""
        for pkg in saas_attention:
            action = "대체 라이브러리 검토 또는 소스 공개 준비"
            report += f"| {pkg.name} | {pkg.license} | {pkg.saas_status} | {action} |\n"
    else:
        report += f"""
---

## ✅ SaaS 배포 시 주의가 필요한 패키지

**AGPL 라이센스 패키지가 없습니다!** SaaS로 서비스 제공 시 소스 공개 없이 이용 가능합니다.
"""

    # On-premise 주의 패키지
    onprem_attention = [
        p for p in all_pkgs if "⚠️" in p.onpremise_status or "❌" in p.onpremise_status
    ]
    if onprem_attention:
        report += f"""
---

## ⚠️ On-premise 배포 시 주의가 필요한 패키지

아래 패키지들은 On-premise로 배포 시 **조건부 이용 또는 소스 공개가 필요**합니다:

| 패키지 | 라이센스 | 상태 | 권장 조치 |
|--------|----------|------|-----------|
"""
        for pkg in onprem_attention:
            if "LGPL" in pkg.license.upper():
                action = "동적 링크 사용 (Python은 대부분 해당)"
            elif "GPL" in pkg.license.upper():
                action = "소스 공개 또는 별도 프로세스 실행"
            else:
                action = "법률 자문 권장"
            report += (
                f"| {pkg.name} | {pkg.license} | {pkg.onpremise_status} | {action} |\n"
            )

    # 확인 필요 패키지
    unknown_pkgs = [
        p for p in all_pkgs if "❓" in p.saas_status or "❓" in p.onpremise_status
    ]
    if unknown_pkgs:
        report += f"""
---

## ❓ 추가 확인이 필요한 패키지

아래 패키지들은 라이센스 정보를 자동으로 확인하지 못했습니다. 수동 확인이 필요합니다:

| 패키지 | 조회 결과 | 비고 |
|--------|----------|------|
"""
        for pkg in unknown_pkgs:
            note = pkg.error if pkg.error else "라이센스 정보 없음"
            report += f"| {pkg.name} | {pkg.license} | {note} |\n"

    report += """
---

## 📋 결론 및 권장사항

### SaaS 배포의 경우
- GPL 라이센스 패키지도 "SaaS Loophole"으로 인해 소스 공개 없이 사용 가능
- **AGPL 패키지만 주의 필요** (현재 목록에 AGPL 패키지가 있다면 위 표 참고)
- 대부분의 패키지가 상업적 이용 가능

### On-premise 배포의 경우
- GPL/LGPL 패키지는 배포에 해당하므로 라이센스 조건 준수 필요
- **LGPL**: Python의 import는 동적 링크로 간주되어 대부분 문제 없음
- **GPL**: 소스 코드 공개 필요. 별도 프로세스로 실행하면 회피 가능한 경우도 있음

### 공통 권장사항
1. 이 보고서는 자동 생성되었으며, **법적 조언이 아닙니다**
2. 중요한 결정을 내리기 전에 **법률 전문가와 상담**하세요
3. 라이센스는 패키지 버전에 따라 변경될 수 있습니다
4. **간접 의존성(transitive dependencies)**도 확인이 필요할 수 있습니다

---

*보고서 생성 도구: check_licenses.py*
"""

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n📄 보고서가 생성되었습니다: {output_file}")


def main():
    # pixi.toml은 상위 폴더에 있음
    pixi_file = Path(__file__).parent.parent / "pixi.toml"
    # 보고서는 현재 폴더(license/)에 저장
    output_file = Path(__file__).parent / "license_report.md"

    print("🔍 pixi.toml 파일 분석 중...")
    conda_packages, pypi_packages = parse_pixi_toml(str(pixi_file))

    print(f"📦 Conda 패키지: {len(conda_packages)}개")
    print(f"📦 PyPI 패키지: {len(pypi_packages)}개")

    conda_results = []
    pypi_results = []

    # 병렬 처리로 패키지 정보 조회
    print("\n🌐 패키지 라이센스 정보 조회 중...")

    with ThreadPoolExecutor(max_workers=10) as executor:
        # Conda 패키지 조회
        conda_futures = {
            executor.submit(process_package, pkg, "conda"): pkg
            for pkg in conda_packages
        }
        # PyPI 패키지 조회
        pypi_futures = {
            executor.submit(process_package, pkg, "pypi"): pkg for pkg in pypi_packages
        }

        # Conda 결과 수집
        for i, future in enumerate(as_completed(conda_futures), 1):
            result = future.result()
            conda_results.append(result)
            print(
                f"  [{i}/{len(conda_packages)}] {result.name}: {result.license[:50]}..."
            )

        # PyPI 결과 수집
        for i, future in enumerate(as_completed(pypi_futures), 1):
            result = future.result()
            pypi_results.append(result)
            print(
                f"  [{i}/{len(pypi_packages)}] {result.name}: {result.license[:50]}..."
            )

    # 보고서 생성
    generate_markdown_report(conda_results, pypi_results, str(output_file))

    # 콘솔에 요약 출력
    all_pkgs = conda_results + pypi_results
    print("\n" + "=" * 70)
    print("📊 요약: SaaS vs On-premise 비교")
    print("=" * 70)

    print("\n🌐 SaaS 배포 시:")
    print(f"  ✅ 이용 가능: {len([p for p in all_pkgs if '✅' in p.saas_status])}개")
    print(f"  ⚠️ 조건부 이용: {len([p for p in all_pkgs if '⚠️' in p.saas_status])}개")
    print(
        f"  ❌ 소스 공개 필요: {len([p for p in all_pkgs if '❌' in p.saas_status])}개"
    )
    print(f"  ❓ 확인 필요: {len([p for p in all_pkgs if '❓' in p.saas_status])}개")

    print("\n🏢 On-premise 배포 시:")
    print(
        f"  ✅ 이용 가능: {len([p for p in all_pkgs if '✅' in p.onpremise_status])}개"
    )
    print(
        f"  ⚠️ 조건부 이용: {len([p for p in all_pkgs if '⚠️' in p.onpremise_status])}개"
    )
    print(
        f"  ❌ 소스 공개 필요: {len([p for p in all_pkgs if '❌' in p.onpremise_status])}개"
    )
    print(
        f"  ❓ 확인 필요: {len([p for p in all_pkgs if '❓' in p.onpremise_status])}개"
    )

    # AGPL 패키지 경고
    agpl_pkgs = [p for p in all_pkgs if "AGPL" in p.license.upper()]
    if agpl_pkgs:
        print("\n⚠️  AGPL 라이센스 패키지 발견 (SaaS에서 주의 필요):")
        for p in agpl_pkgs:
            print(f"    - {p.name}: {p.license}")


if __name__ == "__main__":
    main()
