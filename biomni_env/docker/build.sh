#!/bin/bash
# Docker 이미지 빌드 스크립트
# 
# 사용법: 
#   ./biomni_env/docker/build.sh                        # 기본 빌드 (Pixi, 로컬 플랫폼)
#   ./biomni_env/docker/build.sh --amd64                # AMD64 빌드 (E2B/클라우드용)
#   ./biomni_env/docker/build.sh --amd64 --push         # AMD64 빌드 + Docker Hub push
#   ./biomni_env/docker/build.sh --conda                # Conda-lock 기반 빌드
#   ./biomni_env/docker/build.sh --no-cache             # 캐시 없이 빌드
#
# 예시:
#   ./biomni_env/docker/build.sh --amd64 --push --tag=jaechang917/biomni_hits:latest

set -e

# 프로젝트 루트로 이동 (스크립트 위치 기준 2단계 상위)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${PROJECT_ROOT}"

# 현재 시스템 아키텍처 감지
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ]; then
    DEFAULT_PLATFORM="linux/arm64"
else
    DEFAULT_PLATFORM="linux/amd64"
fi

# 기본 설정
PLATFORM="${DEFAULT_PLATFORM}"
USE_PIXI=true
IMAGE_NAME="biomni-hits-pixi"
IMAGE_TAG="latest"
DOCKERFILE="biomni_env/docker/Dockerfile.pixi"
DO_PUSH=false
NO_CACHE=""
CUSTOM_TAG=""
BUILD_OPTS="--progress=plain"

# 빌드 옵션 처리
for arg in "$@"; do
    case $arg in
        --pixi)
            USE_PIXI=true
            IMAGE_NAME="biomni-hits-pixi"
            DOCKERFILE="biomni_env/docker/Dockerfile.pixi"
            ;;
        --conda)
            USE_PIXI=false
            IMAGE_NAME="biomni-hits"
            DOCKERFILE="biomni_env/docker/Dockerfile"
            ;;
        --amd64)
            PLATFORM="linux/amd64"
            ;;
        --arm64)
            PLATFORM="linux/arm64"
            ;;
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
            echo "Build Options:"
            echo "  --pixi       Use Pixi-based Dockerfile (default)"
            echo "  --conda      Use Conda-lock based Dockerfile"
            echo ""
            echo "Platform Options:"
            echo "  --amd64      Build for linux/amd64 (E2B, cloud servers)"
            echo "  --arm64      Build for linux/arm64 (Apple Silicon Mac)"
            echo "               Default: auto-detect (${DEFAULT_PLATFORM})"
            echo ""
            echo "Other Options:"
            echo "  --push       Push to Docker Hub after build"
            echo "  --no-cache   Build without Docker cache"
            echo "  --quiet      Suppress build progress output"
            echo "  --tag=NAME   Custom image tag (e.g., --tag=user/repo:tag)"
            echo "  --help       Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                                    # Local build (auto platform)"
            echo "  $0 --amd64                            # AMD64 build for E2B"
            echo "  $0 --amd64 --push                     # AMD64 build + push"
            echo "  $0 --amd64 --push --tag=jaechang917/biomni_hits:latest"
            echo "  $0 --conda --amd64 --push             # Conda version, AMD64 + push"
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
if [ "$USE_PIXI" = true ]; then
    echo "🔬 Biomni HITS Docker Build (Pixi)"
else
    echo "🔬 Biomni HITS Docker Build (Conda)"
fi
echo "====================================="
echo "Project root: ${PROJECT_ROOT}"
echo "Dockerfile:   ${DOCKERFILE}"
echo "Platform:     ${PLATFORM}"
echo "Image tag:    ${FULL_TAG}"
echo "Push:         ${DO_PUSH}"
echo ""

# Pixi 빌드 시 linux-64 플랫폼 확인
if [ "$USE_PIXI" = true ] && [ "$PLATFORM" = "linux/amd64" ]; then
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

# Apple Silicon에서 크로스 플랫폼 빌드 시 buildx 사용
IS_CROSS_PLATFORM=false
if [ "$ARCH" = "arm64" ] && [ "$PLATFORM" = "linux/amd64" ]; then
    IS_CROSS_PLATFORM=true
elif [ "$ARCH" = "x86_64" ] && [ "$PLATFORM" = "linux/arm64" ]; then
    IS_CROSS_PLATFORM=true
fi

# 빌드 실행
echo "🚀 Starting build..."
echo ""

if [ "$IS_CROSS_PLATFORM" = true ] || [ "$DO_PUSH" = true ]; then
    # Buildx 빌더 확인 및 생성 (크로스 플랫폼 또는 push 시)
    if ! docker buildx inspect biomni-builder &>/dev/null; then
        echo "🔨 Creating buildx builder..."
        docker buildx create --name biomni-builder --use
    else
        docker buildx use biomni-builder
    fi
    
    if [ "$DO_PUSH" = true ]; then
        # Push 모드: 빌드하면서 바로 push
        docker buildx build ${BUILD_OPTS} \
            --platform ${PLATFORM} \
            -t ${FULL_TAG} \
            -f ${DOCKERFILE} \
            ${NO_CACHE} \
            --push \
            .
    elif [ "$IS_CROSS_PLATFORM" = true ]; then
        # 크로스 플랫폼 빌드 (push 없이)
        echo "⚠️  크로스 플랫폼 이미지는 로컬에서 직접 실행할 수 없습니다."
        echo "   --push 옵션을 추가하여 Docker Hub에 push하세요."
        echo ""
        docker buildx build ${BUILD_OPTS} \
            --platform ${PLATFORM} \
            -t ${FULL_TAG} \
            -f ${DOCKERFILE} \
            ${NO_CACHE} \
            .
    fi
else
    # 네이티브 플랫폼 빌드: --load로 로컬에 저장
    docker buildx build ${BUILD_OPTS} \
        --platform ${PLATFORM} \
        -t ${FULL_TAG} \
        -f ${DOCKERFILE} \
        ${NO_CACHE} \
        --load \
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

if [ "$USE_PIXI" = true ]; then
    echo "💡 Pixi 환경에서 명령 실행:"
    echo "     docker run -it --rm ${FULL_TAG} python your_script.py"
    echo ""
fi
