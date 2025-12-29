# Biomni HITS Docker Image
# Base: Ubuntu with Micromamba installed for lightweight conda package management
#
# 빌드 방법: 프로젝트 루트에서 실행
#   docker build -t biomni-hits:latest -f biomni_env/docker/Dockerfile .
#   docker build -t biomni-hits:latest -f biomni_env/docker/Dockerfile --build-arg CONDA_ENV=myenv .
#
# 컨테이너 실행:
#   docker run -it --rm biomni-hits:latest
#   docker run -it --rm -v $(pwd):/workspace biomni-hits:latest

FROM ubuntu:22.04

# ============================================
# 가상환경 이름 설정 (빌드 시 --build-arg로 변경 가능)
# ============================================
ARG CONDA_ENV=biomni_hits
ENV CONDA_ENV=${CONDA_ENV}

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# Micromamba 설치 경로 설정
ENV MAMBA_ROOT_PREFIX=/opt/micromamba
ENV PATH="${MAMBA_ROOT_PREFIX}/bin:$PATH"

# Install system dependencies (needed for R and some bioinformatics tools)
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
# Micromamba 설치
# ============================================
RUN curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xvj -C /usr/local/bin --strip-components=1 bin/micromamba && \
    mkdir -p ${MAMBA_ROOT_PREFIX} && \
    micromamba shell init -s bash -r ${MAMBA_ROOT_PREFIX} && \
    echo "micromamba activate base" >> ~/.bashrc

# Set working directory
WORKDIR /app

# Install conda-lock for reproducible environment creation
RUN micromamba install -y -n base -c conda-forge conda-lock && \
    micromamba clean -afy

# Copy lock files first (for Docker layer caching)
COPY biomni_env/docker/conda-lock.yml .
COPY biomni_env/omics/install_r_packages.R .

# ============================================
# 새 가상환경 생성 및 패키지 설치 (Lock 파일 사용)
# ============================================

# Create new conda environment from base lock file (재현성 보장, 빌드 빠름)
RUN conda-lock install -n ${CONDA_ENV} conda-lock.yml --micromamba && \
    micromamba clean -afy

# Install R packages via Rscript (가상환경 내에서 실행)
RUN micromamba run -n ${CONDA_ENV} Rscript install_r_packages.R

# Copy the entire project source code
COPY . /app/biomni_hits/

# Install the main package in editable mode (가상환경 내에서 실행)
RUN micromamba run -n ${CONDA_ENV} pip install -e /app/biomni_hits/ && \
    micromamba run -n ${CONDA_ENV} pip cache purge

# ============================================
# 컨테이너 시작 시 자동으로 가상환경 활성화
# ============================================
# PATH 설정으로 가상환경 바이너리 우선 사용
ENV PATH="${MAMBA_ROOT_PREFIX}/envs/${CONDA_ENV}/bin:$PATH"
ENV CONDA_DEFAULT_ENV=${CONDA_ENV}

# Interactive bash 세션을 위한 설정
RUN echo "micromamba activate ${CONDA_ENV}" >> ~/.bashrc

# Entrypoint 스크립트 생성 (비-interactive 실행도 지원)
RUN echo '#!/bin/bash\n\
eval "$(micromamba shell hook --shell bash)"\n\
micromamba activate ${CONDA_ENV}\n\
exec "$@"' > /entrypoint.sh && chmod +x /entrypoint.sh

# Expose common ports (Jupyter, Chainlit, etc.)
EXPOSE 8888 8000 7860

# Entrypoint로 환경 활성화 후 명령 실행
ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
