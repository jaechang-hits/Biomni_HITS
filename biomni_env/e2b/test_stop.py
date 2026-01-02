import threading
from biomni.agent import A1_HITS
from langchain_core.messages import HumanMessage
from biomni.sandbox import E2BCodeInterpreterExecutor
from e2b_code_interpreter import Sandbox
from biomni.config import default_config

LLM_MODEL = "gemini-3-pro-preview"
default_config.llm = LLM_MODEL

sandbox = Sandbox.create("jaechang-test", timeout=600)
executor = E2BCodeInterpreterExecutor(sandbox)

agent = A1_HITS(executor=executor, expected_data_lake_files=[])


# 별도 스레드에서 stop 호출
def stop_after_5_seconds():
    import time

    time.sleep(10)
    agent.stop()  # 🛑 실행 중단!


# stop 스레드 시작
threading.Thread(target=stop_after_5_seconds, daemon=True).start()

# 채팅 시작
for output in agent.go_stream([HumanMessage(content="plot sin(x)")]):
    print(output)  # 5초 후 "[Execution interrupted by user]" 메시지와 함께 종료
