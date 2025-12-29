# Biomni HITS Docker

Docker 이미지로 Biomni HITS 환경을 빌드하고 실행하는 방법입니다.

## 빌드

프로젝트 루트 디렉토리에서 실행:

```bash
# 방법 1: 빌드 스크립트 사용
chmod +x biomni_env/docker/build.sh
./biomni_env/docker/build.sh

# 방법 2: docker build 직접 실행
docker build -t biomni-hits:latest -f biomni_env/docker/Dockerfile .

# 캐시 없이 새로 빌드
./biomni_env/docker/build.sh --no-cache
```

## 실행

```bash
# 기본 실행 (인터랙티브 쉘)
docker run -it --rm biomni-hits:latest

# 현재 디렉토리 마운트
docker run -it --rm -v $(pwd):/workspace biomni-hits:latest

# Jupyter 서버 실행
docker run -it --rm -p 8888:8888 -v $(pwd):/workspace biomni-hits:latest \
  jupyter notebook --ip=0.0.0.0 --allow-root

# Chainlit 서버 실행
docker run -it --rm -p 8000:8000 -v $(pwd):/workspace biomni-hits:latest \
  chainlit run app.py
```

## Conda Lock 파일 생성

Lock 파일은 재현 가능한 환경을 위해 모든 패키지 버전을 고정합니다.

### conda-lock 설치

```bash
# conda/mamba로 설치
mamba install -c conda-forge conda-lock

# 또는 pip로 설치
pip install conda-lock
```

### Lock 파일 생성 (3개 모두 필요)

```bash
# 1. 기본 환경 lock 파일 (environment.yml → conda-lock.yml)
conda-lock -f ../omics/environment.yml \
    -p linux-64 --mamba \
    --lockfile conda-lock.yml

# 2. 생물정보학 패키지 lock 파일 (bio_env.yml → bio-lock.yml)
conda-lock -f ../omics/bio_env.yml \
    -p linux-64 --mamba \
    --lockfile bio-lock.yml

# 3. R 패키지 lock 파일 (r_packages.yml → r-lock.yml)
conda-lock -f ../omics/r_packages.yml \
    -p linux-64 --mamba \
    --lockfile r-lock.yml
```

### 한 번에 모두 생성 (스크립트)

```bash
cd /path/to/project

for yml in environment bio_env r_packages; do
    if [ "$yml" = "environment" ]; then
        lockfile="conda-lock.yml"
    elif [ "$yml" = "bio_env" ]; then
        lockfile="bio-lock.yml"
    else
        lockfile="r-lock.yml"
    fi
    
    conda-lock -f biomni_env/omics/${yml}.yml \
        -p linux-64 --mamba \
        --lockfile biomni_env/docker/${lockfile}
done
```

### 여러 플랫폼 지원 (선택)

```bash
# Mac과 Linux 모두 지원하려면
conda-lock -f biomni_env/omics/environment.yml \
    -p linux-64 -p osx-64 -p osx-arm64 --mamba \
    --lockfile biomni_env/docker/conda-lock.yml
```

### Lock 파일로 환경 생성 (로컬 테스트)

```bash
# lock 파일들을 순서대로 설치
conda-lock install -n myenv biomni_env/docker/conda-lock.yml --mamba
conda-lock install -n myenv biomni_env/docker/bio-lock.yml --mamba
conda-lock install -n myenv biomni_env/docker/r-lock.yml --mamba
```

---

## Pixi 기반 Docker 빌드 (권장)

Pixi는 더 빠르고 재현 가능한 패키지 관리를 제공합니다.

### 사전 준비: pixi.toml 생성/업데이트

기존 conda environment.yml에서 pixi.toml을 만들거나 업데이트하려면:

```bash
# 1. 프로젝트 루트에 pixi.toml이 없는 경우, 초기화
pixi init

# 2. conda environment.yml에서 의존성 가져오기
pixi add --manifest-path pixi.toml numpy pandas matplotlib scipy ...

# 3. linux-64 플랫폼 지원 추가 (Docker 빌드에 필수)
# pixi.toml의 platforms에 linux-64 추가:
# platforms = ["osx-arm64", "linux-64", "linux-aarch64"]

# 4. lock 파일 생성/업데이트
pixi install
```

### Pixi Docker 빌드

```bash
# 방법 1: 빌드 스크립트 사용 (pixi 옵션)
./biomni_env/docker/build.sh --pixi

# 방법 2: docker build 직접 실행
docker build -t biomni-hits-pixi:latest -f biomni_env/docker/Dockerfile.pixi .

# 캐시 없이 새로 빌드
./biomni_env/docker/build.sh --pixi --no-cache
```

### Pixi 컨테이너 실행

```bash
# 기본 실행 (인터랙티브 쉘)
docker run -it --rm biomni-hits-pixi:latest

# 현재 디렉토리 마운트
docker run -it --rm -v $(pwd):/workspace biomni-hits-pixi:latest

# Jupyter 서버 실행
docker run -it --rm -p 8888:8888 -v $(pwd):/workspace biomni-hits-pixi:latest \
  jupyter notebook --ip=0.0.0.0 --allow-root --port=8888

# 특정 Python 스크립트 실행
docker run -it --rm -v $(pwd):/workspace biomni-hits-pixi:latest \
  python your_script.py
```

### Pixi vs Conda-lock 비교

| 항목 | Pixi | Conda-lock |
|------|------|------------|
| 속도 | ⚡ 빠름 | 보통 |
| Lock 파일 | pixi.lock (자동) | conda-lock.yml (수동 생성) |
| 멀티 플랫폼 | pixi.toml에 선언 | 명령어로 지정 |
| 환경 관리 | 프로젝트 단위 | 글로벌/프로젝트 |
| PyPI 패키지 | pypi-dependencies로 통합 | 별도 requirements.txt |

---

## 파일 구조

```
biomni_env/docker/
├── Dockerfile           # Docker 이미지 정의 (conda-lock 기반)
├── Dockerfile.pixi      # Docker 이미지 정의 (pixi 기반, 권장)
├── build.sh             # 빌드 스크립트 (--pixi 옵션으로 Pixi 빌드)
├── conda-lock.yml       # 기본 환경 lock 파일
├── bio-lock.yml         # 생물정보학 패키지 lock 파일
├── r-lock.yml           # R 패키지 lock 파일
└── README.md            # 이 파일

biomni_env/omics/
├── environment.yml      # Python 기본 패키지
├── bio_env.yml          # 생물정보학 패키지
├── r_packages.yml       # R 기본 패키지 (conda)
└── install_r_packages.R # Bioconductor R 패키지

# 프로젝트 루트
├── pixi.toml            # Pixi 패키지 정의 (권장)
└── pixi.lock            # Pixi lock 파일 (자동 생성)
```

## 빌드 시간

- 첫 빌드: 약 30분~1시간 (R 패키지 포함)
- 캐시 사용 시: 훨씬 빠름

## 포트

| 포트 | 용도 |
|------|------|
| 8888 | Jupyter Notebook |
| 8000 | Chainlit |
| 7860 | Gradio |

