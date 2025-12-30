#!/bin/bash

# Chainlit 서버 재시작 스크립트
# 워크플로우 저장 기능 개선사항 적용을 위해 사용

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT=8005

echo "🔄 Chainlit 서버 재시작 중..."

# 포트 8005를 사용하는 프로세스 찾기 및 종료
if lsof -ti:${PORT} > /dev/null 2>&1; then
    echo "⏹️  기존 chainlit 서버 종료 중 (포트 ${PORT})..."
    kill $(lsof -ti:${PORT})
    sleep 2
    
    # 강제 종료가 필요한 경우
    if lsof -ti:${PORT} > /dev/null 2>&1; then
        echo "⚠️  강제 종료 중..."
        kill -9 $(lsof -ti:${PORT})
        sleep 1
    fi
    echo "✅ 기존 서버 종료 완료"
else
    echo "ℹ️  실행 중인 chainlit 서버가 없습니다"
fi

# 환경 변수 설정
export CHAINLIT_WS_TIMEOUT=7200
export CHAINLIT_REQUEST_TIMEOUT=7200

# 서버 시작
echo "🚀 Chainlit 서버 시작 중..."
cd "${SCRIPT_DIR}"
chainlit run "${SCRIPT_DIR}/run.py" -h --host 0.0.0.0 --port ${PORT}

