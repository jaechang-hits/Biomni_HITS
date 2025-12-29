#!/bin/bash
# Docker 이미지 빌드 스크립트
# 
# 사용법: 
#   ./biomni_env/docker/build.sh              # 기본 빌드 (conda-lock)
#   ./biomni_env/docker/build.sh --pixi       # Pixi 기반 빌드 (권장)
#   ./biomni_env/docker/build.sh --no-cache   # 캐시 없이 새로 빌드
#   ./biomni_env/docker/build.sh --pixi --no-cache

set -e

# 프로젝트 루트로 이동 (스크립트 위치 기준 2단계 상위)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

cd "${PROJECT_ROOT}"

# 기본 설정
USE_PIXI=false
IMAGE_NAME="biomni-hits"
IMAGE_TAG="latest"
DOCKERFILE="biomni_env/docker/Dockerfile"

# 빌드 옵션 처리
BUILD_OPTS="--progress=plain"  # 중간 빌드 출력 표시
for arg in "$@"; do
    case $arg in
        --pixi)
            USE_PIXI=true
            IMAGE_NAME="biomni-hits-pixi"
            DOCKERFILE="biomni_env/docker/Dockerfile.pixi"
            ;;
        --no-cache)
            BUILD_OPTS="${BUILD_OPTS} --no-cache"
            echo "Building without cache..."
            ;;
        --quiet)
            BUILD_OPTS=""  # progress=plain 제거
            ;;
    esac
done

echo "====================================="
if [ "$USE_PIXI" = true ]; then
    echo "Biomni HITS Docker Image Build (Pixi)"
else
    echo "Biomni HITS Docker Image Build (Conda)"
fi
echo "====================================="
echo "Project root: ${PROJECT_ROOT}"
echo "Dockerfile: ${DOCKERFILE}"
echo ""

# Pixi 빌드 시 linux-64 플랫폼 확인
if [ "$USE_PIXI" = true ]; then
    if ! grep -q "linux-64" pixi.toml 2>/dev/null; then
        echo "⚠️  경고: pixi.toml에 linux-64 플랫폼이 없습니다!"
        echo ""
        echo "pixi.toml의 platforms를 다음과 같이 수정하세요:"
        echo '  platforms = ["osx-arm64", "linux-64"]'
        echo ""
        echo "그리고 lock 파일을 업데이트하세요:"
        echo "  pixi install"
        echo ""
    fi
fi

echo "Building Docker image: ${IMAGE_NAME}:${IMAGE_TAG}"
echo ""

# Docker 이미지 빌드 (linux/amd64 플랫폼 지정 - Apple Silicon 호환)
docker build ${BUILD_OPTS} \
    --platform linux/amd64 \
    -t ${IMAGE_NAME}:${IMAGE_TAG} \
    -f ${DOCKERFILE} \
    .

echo ""
echo "====================================="
echo "Build completed successfully!"
echo "====================================="
echo ""
echo "이미지 실행 방법:"
echo ""
echo "  1. 기본 실행 (인터랙티브 쉘):"
echo "     docker run -it --rm ${IMAGE_NAME}:${IMAGE_TAG}"
echo ""
echo "  2. 현재 디렉토리 마운트:"
echo "     docker run -it --rm -v \$(pwd):/workspace ${IMAGE_NAME}:${IMAGE_TAG}"
echo ""
echo "  3. Jupyter 서버 실행:"
echo "     docker run -it --rm -p 8888:8888 -v \$(pwd):/workspace ${IMAGE_NAME}:${IMAGE_TAG} \\"
echo "       jupyter notebook --ip=0.0.0.0 --allow-root"
echo ""
echo "  4. Chainlit 서버 실행:"
echo "     docker run -it --rm -p 8000:8000 -v \$(pwd):/workspace ${IMAGE_NAME}:${IMAGE_TAG} \\"
echo "       chainlit run app.py"
echo ""

if [ "$USE_PIXI" = true ]; then
    echo "💡 Pixi 환경에서 명령 실행:"
    echo "     docker run -it --rm ${IMAGE_NAME}:${IMAGE_TAG} python your_script.py"
    echo ""
fi

