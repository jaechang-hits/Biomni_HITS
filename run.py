from biomni.agent import A1_HITS
import os
import shutil
from datetime import datetime
import pytz
import time
from langchain_core.messages import SystemMessage, HumanMessage
from biomni.llm import get_llm
import markdown

os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGSMITH_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGSMITH_PROJECT"] = "jhjeon_test"

from scenario import commands, file_attachments

current_abs_dir = os.path.dirname(os.path.abspath(__file__))

for idx, user_command in enumerate(commands[0:1]):
    # Create directory with current Korean time
    korea_tz = pytz.timezone("Asia/Seoul")
    current_time = datetime.now(korea_tz)
    dir_name = "logs/" + current_time.strftime("%Y%m%d_%H%M%S")

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
        # allow_resources=["proteomics", "support_tools"],
        use_tool_retriever=True,
    )

    # Add file attachments from scenario.py
    if idx < len(file_attachments) and file_attachments[idx]:
        print(f"Adding {len(file_attachments[idx])} file(s) to agent...")
        
        # Copy files to current working directory so agent can find them
        for file_path, description in file_attachments[idx].items():
            if os.path.isabs(file_path):
                source_path = file_path
            else:
                source_path = os.path.join(current_abs_dir, file_path)
            
            # Copy file to current working directory
            filename = os.path.basename(file_path)
            dest_path = os.path.join(os.getcwd(), filename)
            
            if os.path.exists(source_path):
                shutil.copy2(source_path, dest_path)
                print(f"Copied {source_path} to {dest_path}")
            else:
                print(f"Warning: Source file {source_path} not found")
        
        agent.add_data(file_attachments[idx])
        print("Files added successfully!")

    with open("logs.txt", "w") as f1, open("system_prompt.txt", "w") as f2:
        for idx, output in enumerate(agent.go(user_command)):
            print("====================", idx, "====================")
            if idx == 0:
                f2.write(output)
                f2.flush()  # 즉시 파일에 쓰기
            else:
                f1.write(output + "\n")
                f1.flush()  # 즉시 파일에 쓰기
            print(agent.timer)
    print("\n\n\nStart generating report...")

    logs = open("logs.txt", "r").readlines()
    # llm = get_llm(model="us.anthropic.claude-sonnet-4-20250514-v1:0")
    # llm = get_llm(model="grok-4")
    # llm = get_llm(model="us.anthropic.claude-3-7-sonnet-20250219-v1:0")
    llm = get_llm(model="gemini-2.5-pro")
    markdown_content = llm.invoke(
        input=[
            SystemMessage(content="You are a helpful summarizer."),
            HumanMessage(content="\n".join(logs)),
            HumanMessage(
                content="""Make a comprehensive and detailed report of the previous text in markdown format.
    Do not just provide a name of the figure but also add a figure to the report.
    Do not provide a code block in the report.
    Do not mention about biomni or biomni related things such as biomni-hits, biomni-agent, etc.
    리포트는 한글로 작성해줘. 사용자 요청 사항을 리포트 앞쪽에 정리해줘. 답변에는 markdown 포함해줘. 다른 너의 응답은 포함시키지 말아줘.
    리포트가 저장되는 디렉토리에 이미지 파일도 저장해줘.
    이미지의 크기는 가로 15cm 이하로 해줘"""
            ),
        ],
    ).content

    markdown_content = markdown_content.replace("```markdown", "")
    markdown_content = markdown_content.replace("```", "")
    with open("report.md", "w") as f:
        f.write(markdown_content)

    result = markdown.markdown(markdown_content, extensions=["tables"])

    # Add CSS to limit image width to 15cm
    html_with_css = f"""
    <style>
    img {{
        max-width: 15cm;
        height: auto;
    }}
    </style>
    {result}
    """

    with open("report.html", "w") as f:
        f.write(html_with_css)

    t2 = time.time()
    print(f"Elapsed time: {t2 - t1:.2f} seconds")

    os.chdir(current_abs_dir)