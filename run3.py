from biomni.agent import A1_HITS
from biomni.workflow import WorkflowService
import os
from datetime import datetime
import pytz
import time
from langchain_core.messages import SystemMessage, HumanMessage
from biomni.llm import get_llm
import markdown
from pathlib import Path

os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGSMITH_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGSMITH_PROJECT"] = "hklee"

# Create directory with current Korean time
korea_tz = pytz.timezone("Asia/Seoul")
current_time = datetime.now(korea_tz)
dir_name = "logs/" + current_time.strftime("%Y%m%d_%H%M%S")

os.system("rm -r logs/2025*")
os.makedirs("logs", exist_ok=True)
os.makedirs(dir_name, exist_ok=True)
os.chdir(dir_name)

t1 = time.time()
# llm = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
llm = "gemini-2.5-pro"
# llm = "solar-pro2"
# llm = "mistral-small-2506"
agent = A1_HITS(
    path="./",
    llm=llm,
    use_tool_retriever=True,
)
user_command = """/workdir_efs/jhjeon/Biomni/data/IonTorrent/TCGA-LUAD.star_counts.tsv.gz 파일은 log2가 적용된 데이터야.
이 데이터 사용해서 comprehensive 오믹스 분석 수행해줘.
"""

with open("logs.txt", "w") as f1, open("system_prompt.txt", "w") as f2:
    for idx, output in enumerate(agent.go(user_command)):
        print("====================", idx, "====================")
        if idx == 0:
            f2.write(output)
            f2.flush()  # 즉시 파일에 쓰기
        else:
            f1.write(output + "\n")
            f1.flush()  # 즉시 파일에 쓰기

t2 = time.time()
print(f"Elapsed time: {t2 - t1:.2f} seconds")

# Save workflow after execution using WorkflowService (independent approach)
print("\n" + "="*60)
print("💾 Saving workflow...")
print("="*60)

try:
    # Determine workflows directory from execute_blocks_dir
    if agent.workflow_tracker.execute_blocks_dir:
        workflows_root = agent.workflow_tracker.execute_blocks_dir.parent
        workflows_dir = workflows_root / "workflows"
    else:
        # Fallback: use current directory
        workflows_dir = Path("./workflows")
    
    # Use WorkflowService for independent workflow saving
    workflow_path = WorkflowService.save_workflow_from_tracker(
        tracker=agent.workflow_tracker,
        workflows_dir=str(workflows_dir),
        llm=agent.llm,
        workflow_name=None,
        max_fix_attempts=2
    )
    
    if workflow_path:
        print(f"✅ Workflow saved successfully!")
        print(f"📁 Location: {workflow_path}")
    else:
        print("ℹ️  No workflow to save (no data processing code found)")
        # Debug: Check execution history
        history = agent.workflow_tracker.get_execution_history()
        print(f"   Total executions tracked: {len(history)}")
        if history:
            successful = agent.workflow_tracker.get_successful_executions()
            print(f"   Successful executions: {len(successful)}")
            stats = agent.workflow_tracker.get_statistics()
            print(f"   Statistics: {stats}")
except Exception as e:
    print(f"❌ Error saving workflow: {e}")
    import traceback
    traceback.print_exc()
print("="*60)
