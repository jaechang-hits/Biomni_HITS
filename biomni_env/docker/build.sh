#!/bin/bash
# Docker 이미지 빌드 스크립트 (Pixi 기반)
# 
# 사용법: 
#   ./biomni_env/docker/build.sh                        # 기본 빌드
#   ./biomni_env/docker/build.sh --push                 # 빌드 + Docker Hub push
#   ./biomni_env/docker/build.sh --no-cache             # 캐시 없이 빌드
#
# 예시:
#   ./biomni_env/docker/build.sh --push --tag=jaechang917/biomni_hits:latest

set -e

# 프로젝트 루트로 이동 (스크립트 위치 기준 2단계 상위)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${PROJECT_ROOT}"

# 기본 설정
IMAGE_NAME="biomni-hits"
IMAGE_TAG="latest"
DOCKERFILE="biomni_env/docker/Dockerfile"
DO_PUSH=false
NO_CACHE=""
CUSTOM_TAG=""
BUILD_OPTS="--progress=plain"

# 빌드 옵션 처리
for arg in "$@"; do
    case $arg in
        --push)
            DO_PUSH=true
            ;;
        --no-cache)
            NO_CACHE="--no-cache"
            ;;
        --quiet)
            BUILD_OPTS=""
            ;;
        --tag=*)
            CUSTOM_TAG="${arg#*=}"
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --push       Push to Docker Hub after build"
            echo "  --no-cache   Build without Docker cache"
            echo "  --quiet      Suppress build progress output"
            echo "  --tag=NAME   Custom image tag (e.g., --tag=user/repo:tag)"
            echo "  --help       Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                                    # Local build"
            echo "  $0 --push                             # Build + push"
            echo "  $0 --push --tag=jaechang917/biomni_hits:latest"
            exit 0
            ;;
    esac
done

# 커스텀 태그가 있으면 사용
if [ -n "$CUSTOM_TAG" ]; then
    FULL_TAG="${CUSTOM_TAG}"
else
    FULL_TAG="${IMAGE_NAME}:${IMAGE_TAG}"
fi

echo ""
echo "====================================="
echo "🔬 Biomni HITS Docker Build (Pixi)"
echo "====================================="
echo "Project root: ${PROJECT_ROOT}"
echo "Dockerfile:   ${DOCKERFILE}"
echo "Image tag:    ${FULL_TAG}"
echo "Push:         ${DO_PUSH}"
echo ""

# 빌드 실행
echo "🚀 Starting build..."
echo ""

if [ "$DO_PUSH" = true ]; then
    # Push 모드: buildx 사용하여 빌드 후 push
    if ! docker buildx inspect biomni-builder &>/dev/null; then
        echo "🔨 Creating buildx builder..."
        docker buildx create --name biomni-builder --use
    else
        docker buildx use biomni-builder
    fi
    
    docker buildx build ${BUILD_OPTS} \
        -t ${FULL_TAG} \
        -f ${DOCKERFILE} \
        ${NO_CACHE} \
        --push \
        .
else
    # 로컬 빌드: --load로 로컬에 저장
    docker build ${BUILD_OPTS} \
        -t ${FULL_TAG} \
        -f ${DOCKERFILE} \
        ${NO_CACHE} \
        .
fi

echo ""
echo "====================================="
echo "✅ Build completed successfully!"
echo "====================================="
echo ""

if [ "$DO_PUSH" = true ]; then
    echo "📤 Image pushed to: ${FULL_TAG}"
    echo ""
    echo "E2B에서 사용하려면:"
    echo "  Template.from_image(\"${FULL_TAG}\")"
else
    echo "이미지 실행 방법:"
    echo ""
    echo "  1. 기본 실행 (인터랙티브 쉘):"
    echo "     docker run -it --rm ${FULL_TAG}"
    echo ""
    echo "  2. 현재 디렉토리 마운트:"
    echo "     docker run -it --rm -v \$(pwd):/workspace ${FULL_TAG}"
    echo ""
    echo "  3. Jupyter 서버 실행:"
    echo "     docker run -it --rm -p 8888:8888 -v \$(pwd):/workspace ${FULL_TAG} \\"
    echo "       jupyter notebook --ip=0.0.0.0 --allow-root"
    echo ""
    echo "  4. Chainlit 서버 실행:"
    echo "     docker run -it --rm -p 8000:8000 -v \$(pwd):/workspace ${FULL_TAG} \\"
    echo "       chainlit run app.py"
fi
echo ""

echo "💡 Pixi 환경에서 명령 실행:"
echo "     docker run -it --rm ${FULL_TAG} python your_script.py"
echo ""
