# E2B Sandbox 환경

이 디렉토리는 [E2B (Execute to Build)](https://e2b.dev/) 클라우드 샌드박스 환경을 구축하고 테스트하기 위한 파일들을 포함합니다.

## 개요

E2B는 클라우드에서 안전하게 코드를 실행할 수 있는 샌드박스 서비스입니다. Biomni HITS 프로젝트에서는 E2B를 사용하여 Python과 R 코드를 격리된 환경에서 실행합니다.

## 파일 설명

| 파일 | 설명 |
|------|------|
| `build.py` | E2B 템플릿 빌드 스크립트 |
| `test.py` | 샌드박스 환경 통합 테스트 스크립트 |

## 사전 요구사항

### 1. E2B API 키 설정

```bash
# ~/.bashrc에 추가
export E2B_API_KEY="your-api-key"
```

### 2. GitHub 토큰 설정 (빌드 시 필요)

```bash
# ~/.git-credentials에 GitHub 토큰 저장
https://YOUR_GITHUB_TOKEN@github.com
```

### 3. Python 의존성

```bash
pip install e2b e2b-code-interpreter python-dotenv
```

## 템플릿 빌드 (build.py)

`build.py`는 E2B 템플릿을 생성하는 스크립트입니다.

### 빌드되는 환경

- **베이스 이미지**: `code-interpreter-v1` (Jupyter 커널 내장)
- **시스템 패키지**: build-essential, curl, wget, git 등
- **Pixi**: Conda 호환 패키지 매니저
- **프로젝트 소스**: GitHub에서 `e2b` 브랜치 클론
- **Python 환경**: pixi.toml에 정의된 Python 패키지들 (RDKit, SciPy 등)

### 빌드 실행

```bash
cd biomni_env/e2b
python build.py
```

### 주요 설정

```python
# GitHub 저장소 설정
GITHUB_REPO = "jaechang-hits/Biomni_HITS"
GITHUB_BRANCH = "e2b"

# 템플릿 빌드 옵션
Template.build(
    template,
    alias="jaechang-test",  # 템플릿 이름
    cpu_count=1,
    memory_mb=4096,
)
```

## 테스트 실행 (test.py)

`test.py`는 빌드된 샌드박스 환경을 종합적으로 테스트합니다.

### 테스트 항목

| 테스트 | 설명 |
|--------|------|
| Sandbox 생성 | 샌드박스 인스턴스 생성 시간 측정 |
| 초기 설정 | .pixi 폴더 및 환경 확인 |
| Python 변수 유지 | run_code 세션 간 변수 유지 테스트 |
| RDKit 테스트 | 분자 구조 분석 라이브러리 로드 및 기능 테스트 |
| SciPy 테스트 | 선형대수, 통계, 최적화 기능 테스트 |
| R 기본 테스트 | R 버전 및 기본 연산 테스트 |
| R 패키지 테스트 | ggplot2, dplyr, Seurat 등 패키지 로드 테스트 |
| 캐시 효과 테스트 | 재실행 시 성능 측정 |

### 테스트 실행

```bash
cd biomni_env/e2b
python test.py
```

### 예상 출력

```
============================================================
E2B Sandbox 테스트 시작 (run_code + .pixi 직접 경로 사용)
============================================================

[TEST 1] Sandbox 생성 시간 측정
----------------------------------------
✅ Sandbox 생성 시간: X.XXs

...

============================================================
테스트 결과 요약
============================================================
항목                                         시간
----------------------------------------------------
Sandbox 생성                                 X.XXs
RDKit 테스트 (run_code 직접)                 X.XXs
SciPy 테스트 (run_code 직접)                 X.XXs
R 기본 테스트 (commands.run)                 X.XXs
...
============================================================
```

## Pixi 환경 경로

샌드박스 내에서 Pixi 환경의 실행 파일 경로:

```python
PIXI_PYTHON = "/app/.pixi/envs/default/bin/python"
PIXI_RSCRIPT = "/app/.pixi/envs/default/bin/Rscript"
```

### Python에서 pixi 패키지 사용하기

```python
import sys
import glob

# pixi 환경의 site-packages를 sys.path에 추가
for sp in glob.glob("/app/.pixi/envs/*/lib/python3.12/site-packages"):
    if sp not in sys.path:
        sys.path.insert(0, sp)

# 이제 pixi 패키지 import 가능
import rdkit
import scipy
```

### R 스크립트 실행

```python
# commands.run을 사용하여 R 실행
result = sbx.commands.run(f"{PIXI_RSCRIPT} /path/to/script.R", timeout=120)
print(result.stdout)
```

## 주의사항

1. **API 키 보안**: `E2B_API_KEY`와 GitHub 토큰을 코드에 직접 포함하지 마세요.

2. **타임아웃**: 샌드박스는 기본 600초(10분) 후 자동 종료됩니다. 필요시 `timeout` 매개변수를 조정하세요.

3. **Python 버전**: E2B Jupyter 커널은 Python 3.12를 사용합니다. pixi.toml에서 동일한 버전을 사용해야 합니다.

4. **캐시 무효화**: 빌드 시 캐시를 무시하려면 `build.py`에서 `skip_cache=True` 옵션을 활성화하세요.

## 관련 문서

- [E2B 공식 문서](https://e2b.dev/docs)
- [E2B Python SDK](https://github.com/e2b-dev/E2B)
- [E2B Code Interpreter](https://github.com/e2b-dev/code-interpreter)

