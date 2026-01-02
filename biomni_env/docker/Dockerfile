# Biomni HITS Docker Image (e2b code-interpreter 기반)
# Base: e2b code-interpreter (Jupyter 커널 내장)
#
# 사전 준비:
#   pixi.toml에 linux-64 플랫폼 추가 필요:
#   platforms = ["osx-arm64", "linux-64"]
#
#   그리고 lock 파일 업데이트:
#   pixi install
#
# 빌드 방법: 프로젝트 루트에서 실행
#   docker build -t biomni-hits:latest -f biomni_env/docker/Dockerfile .
#
# 컨테이너 실행:
#   docker run -it --rm biomni-hits:latest
#   docker run -it --rm -v $(pwd):/workspace biomni-hits:latest

# e2b code-interpreter 베이스 이미지 사용 (Jupyter 커널 포함)
FROM e2bdev/code-interpreter:latest

# root로 전환하여 패키지 설치
USER root

# ============================================
# 기본 환경 변수 설정
# ============================================
ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# OpenMP 설정 (QEMU 에뮬레이션에서 빌드 시 필요)
# Apple Silicon에서 linux/amd64 빌드 시 OMP affinity 에러 방지
ENV KMP_AFFINITY=disabled
ENV OMP_NUM_THREADS=1

# Pixi 설치 경로 설정
ENV PIXI_HOME=/opt/pixi
ENV PATH="${PIXI_HOME}/bin:$PATH"

# HTTP2 관련 연결 에러 방지 (동시 다운로드 수 제한으로 연결 안정성 향상)
ENV PIXI_CONCURRENT_DOWNLOADS=20

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    wget \
    git \
    ca-certificates \
    bzip2 \
    libcurl4-openssl-dev \
    libssl-dev \
    libxml2-dev \
    libfontconfig1-dev \
    libharfbuzz-dev \
    libfribidi-dev \
    libfreetype6-dev \
    libpng-dev \
    libtiff5-dev \
    libjpeg-dev \
    liblzma-dev \
    libbz2-dev \
    libpcre2-dev \
    libreadline-dev \
    && rm -rf /var/lib/apt/lists/*

# ============================================
# Pixi 설치
# ============================================
RUN curl -fsSL https://pixi.sh/install.sh | PIXI_HOME=${PIXI_HOME} bash && \
    echo 'eval "$(pixi completion --shell bash)"' >> ~/.bashrc

# Create workdir directory
RUN mkdir -p /workdir

# Set working directory
WORKDIR /app

# ============================================
# 프로젝트 파일 복사 (pixi.toml, pixi.lock 우선)
# ============================================
# Lock 파일을 먼저 복사하여 Docker 레이어 캐싱 활용

COPY pixi.toml pixi.lock ./

# 프로젝트 소스 코드 복사
COPY . .

# ============================================
# Pixi를 이용한 환경 설치
# ============================================
# pixi install로 모든 의존성 설치 (lock 파일 기반)
# 설치 후 캐시 정리로 이미지 크기 최소화
RUN pixi install --frozen && \
    pixi clean cache --yes && \
    rm -rf ~/.cache/rattler

# R 패키지 추가 설치
RUN pixi run Rscript biomni_env/omics/install_r_packages.R

# Shell로 진입 시 pixi shell 사용 설정
RUN echo 'cd /app && eval "$(pixi shell-hook)"' >> ~/.bashrc

# Expose common ports (Jupyter kernel, Jupyter notebook, Chainlit, etc.)
EXPOSE 49999 8888 8000 7860

# e2b code-interpreter의 기본 ENTRYPOINT를 유지 (Jupyter 커널 자동 시작)

