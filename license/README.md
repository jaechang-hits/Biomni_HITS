# 라이브러리 라이센스 분석 도구

`pixi.toml`에 정의된 모든 패키지의 라이센스를 자동으로 조사하고, **SaaS** 및 **On-premise** 배포 시나리오별 상업적 이용 가능 여부를 분석합니다.

## 실행 방법

```bash
# Biomni_HITS 폴더 기준
cd Biomni_HITS/license
python check_licenses.py
```

또는

```bash
# Biomni_HITS 폴더에서 직접 실행
python license/check_licenses.py
```

## 출력 파일

- `license/license_report.md`: 상세 분석 보고서

## 라이센스 분류 체계

### 허용적 라이센스 (Permissive)
| 라이센스 | SaaS | On-premise | 설명 |
|---------|------|------------|------|
| MIT | ✅ | ✅ | 저작권 표기만 필요 |
| BSD | ✅ | ✅ | 저작권 표기만 필요 |
| Apache 2.0 | ✅ | ✅ | 저작권 표기 + 변경사항 명시 |
| ISC | ✅ | ✅ | MIT와 유사 |

### 약한 카피레프트 (Weak Copyleft)
| 라이센스 | SaaS | On-premise | 설명 |
|---------|------|------------|------|
| LGPL | ✅ | ⚠️ 조건부 | 동적 링크 시 본인 코드 비공개 가능 |
| MPL | ✅ | ⚠️ 조건부 | 파일 단위로 소스 공개 |

### 강한 카피레프트 (Strong Copyleft)
| 라이센스 | SaaS | On-premise | 설명 |
|---------|------|------------|------|
| GPL | ✅* | ⚠️ 소스 공개 | *SaaS Loophole: 배포가 아니므로 공개 불필요 |

### 네트워크 카피레프트 (Network Copyleft)
| 라이센스 | SaaS | On-premise | 설명 |
|---------|------|------------|------|
| AGPL | ❌ 소스 공개 | ⚠️ 소스 공개 | 네트워크 서비스도 배포로 간주 |

## SaaS vs On-premise 차이점

### SaaS (Software as a Service)
- 소프트웨어가 서버에서 실행되고 사용자는 네트워크로 접근
- 소프트웨어 자체를 "배포"하지 않음
- **GPL 패키지도 소스 공개 없이 사용 가능** (SaaS Loophole)
- ⚠️ **AGPL만 주의 필요** - 네트워크 서비스도 배포로 간주

### On-premise
- 소프트웨어를 고객에게 직접 설치/배포
- "배포"에 해당하여 라이센스 조건 적용
- GPL: 파생 저작물 전체 소스 공개 필요
- LGPL: Python의 `import`는 동적 링크로 간주되어 대부분 문제 없음

## Python과 LGPL

Python에서 LGPL 라이브러리를 `import`하는 것은 일반적으로 **동적 링크**로 간주됩니다:

```python
import lgpl_library  # 동적 링크 - 본인 코드 비공개 가능
```

따라서 대부분의 Python 프로젝트에서 LGPL 라이브러리는 상업적으로 사용 가능합니다.

## GPL 패키지 사용 시 권장사항

On-premise 배포 시 GPL 패키지를 사용해야 하는 경우:

1. **별도 프로세스로 실행**: GPL 코드를 별도 프로세스로 실행하고 IPC로 통신
2. **서비스 분리**: GPL 부분을 별도 마이크로서비스로 분리
3. **대체 라이브러리 검토**: 허용적 라이센스의 대안 찾기
4. **소스 공개 준비**: 비즈니스 모델에 따라 소스 공개도 옵션

## 주의사항

1. 이 도구는 **법적 조언이 아닙니다**
2. 중요한 결정 시 **법률 전문가와 상담** 권장
3. 라이센스는 패키지 버전에 따라 변경될 수 있음
4. **간접 의존성(transitive dependencies)**도 확인 필요
5. 일부 패키지는 API에서 라이센스 정보를 가져오지 못할 수 있음

## 데이터 소스

- **PyPI**: https://pypi.org/pypi/{package}/json
- **Anaconda**: https://api.anaconda.org/package/{channel}/{package}

## 파일 구조

```
Biomni_HITS/
├── pixi.toml                  # 패키지 목록
└── license/
    ├── README.md              # 이 파일
    ├── check_licenses.py      # 분석 스크립트
    └── license_report.md      # 분석 보고서 (자동 생성)
```

