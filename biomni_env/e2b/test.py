from dotenv import load_dotenv
from e2b import Sandbox
import os
import e2b
import time

os.environ["E2B_API_KEY"] = "e2b_f308d8e737cc8ae69cd41343bd3d2fca2639ea22"

load_dotenv()

# Create a new Sandbox from the development template
t1 = time.time()
sbx = Sandbox.create("jaechang-test")
t2 = time.time()
print(f"Sandbox creation time: {t2 - t1:.2f}s")

# pixi run을 사용해서 langchain_aws import 및 print("hello") 실행
print("\n=== pixi run: import langchain_aws and print hello ===")
t1 = time.time()
result = sbx.commands.run(
    "cd /app && pixi run python -c \"import rdkit; print('hello')\"", timeout=60
)
t2 = time.time()
print(f"pixi run1 time: {t2 - t1:.2f}s")

t1 = time.time()
result = sbx.commands.run(
    "cd /app && pixi run python -c \"import rdkit; print('hello')\"", timeout=60
)
t2 = time.time()
print(f"pixi run2 time: {t2 - t1:.2f}s")

print(f"stdout: {result.stdout}")
print(f"stderr: {result.stderr}")
print(f"exit_code: {result.exit_code}")

# Sandbox 종료
# sbx.kill()
