#!/bin/bash

# Chainlit 서버 실행 스크립트
# 
# 연결 끊김 문제 해결 방법:
# 1. 하트비트 간격을 2초로 설정하여 chunk가 안 와도 매우 자주 연결 유지
# 2. 무조건 2초마다 update() 호출하여 HTTP/웹소켓 연결 유지
# 3. 최대 타임아웃을 60분(3600초)으로 증가
# 4. session_timeout을 2시간으로 증가
# 5. 5초 이상 대기 시에만 visible 메시지 표시
#
# 참고: 만약 리버스 프록시나 로드 밸런서를 사용하는 경우,
# 해당 서버의 타임아웃 설정도 확인해야 할 수 있습니다.
# Nginx 예시: proxy_read_timeout 7200;

# 환경 변수 설정
# 웹소켓 타임아웃 증가
export CHAINLIT_WS_TIMEOUT=7200
export CHAINLIT_REQUEST_TIMEOUT=7200

# 비용 추적 기능 (Cost Tracking)
# LLM API 호출 비용을 추적하고 리포트를 생성합니다.
# 값: true/false (기본값: false)
# 활성화 시: 각 세션의 LLM 호출 비용을 추적하고 리포트를 표시합니다.
export COST_TRACKING_ENABLED=true

# 워크플로우 자동 저장 기능 (Workflow Saving)
# Agent 실행 후 분석 워크플로우를 자동으로 Jupyter notebook(.ipynb) 파일로 저장합니다.
# 값: true/false (기본값: false)
# 활성화 시: 실행된 코드 블록들을 순서대로 정리하여 재사용 가능한 워크플로우로 저장합니다.
# 저장 위치: {work_dir}/workflows/workflows/workflow_*.ipynb
export BIOMNI_WORKFLOW_SAVING_ENABLED=true

# Chainlit 서버 실행
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# HTTPS 모드 (마이크 사용을 위해 필요)
# 자체 서명 인증서 사용 - 브라우저에서 "안전하지 않음" 경고가 나타나면 "고급" -> "계속 진행" 클릭
# chainlit run "${SCRIPT_DIR}/run.py" -h --host 0.0.0.0 --port 8001 \
#     --ssl-cert "${SCRIPT_DIR}/ssl_cert.pem" \
#     --ssl-key "${SCRIPT_DIR}/ssl_key.pem"

# HTTP 모드 (마이크 사용 불가, localhost에서만 마이크 작동)
# chainlit run "${SCRIPT_DIR}/run.py" -h --host 0.0.0.0 --port 8001
chainlit run "${SCRIPT_DIR}/run.py" -h --host 0.0.0.0 --port 8005
