from dotenv import load_dotenv
from e2b_code_interpreter import Sandbox
import os
import time

load_dotenv()

# E2B API 키는 ~/.bashrc에서 환경변수로 설정됨
if not os.environ.get("E2B_API_KEY"):
    raise ValueError(
        "E2B_API_KEY 환경변수가 설정되지 않았습니다. ~/.bashrc를 확인하세요."
    )

# pixi 환경의 실행파일 경로
PIXI_PYTHON = "/app/.pixi/envs/default/bin/python"
PIXI_RSCRIPT = "/app/.pixi/envs/default/bin/Rscript"

print("=" * 60)
print("E2B Sandbox 테스트 시작 (run_code + .pixi 직접 경로 사용)")
print("=" * 60)

# ============================================================
# 1. Sandbox 생성 시간 측정
# ============================================================
print("\n[TEST 1] Sandbox 생성 시간 측정")
print("-" * 40)

t1 = time.time()
sbx = Sandbox.create("jaechang-test", timeout=600)
sandbox_creation_time = time.time() - t1
print(f"✅ Sandbox 생성 시간: {sandbox_creation_time:.2f}s")

# ============================================================
# 1-1. 초기 설정: .pixi 폴더 확인
# ============================================================
print("\n[TEST 1-1] 초기 설정 (.pixi 폴더 확인)")
print("-" * 40)

init_code = f"""
import os
import sys
import glob

# pixi 환경의 site-packages를 sys.path에 추가 (한 번만 실행)
for sp in glob.glob("/app/.pixi/envs/*/lib/python*/site-packages"):
    if sp not in sys.path:
        sys.path.insert(0, sp)
        print(f"sys.path에 추가됨: {{sp}}")

# .pixi 폴더 확인
pixi_python = "{PIXI_PYTHON}"
pixi_rscript = "{PIXI_RSCRIPT}"

print(f"Python 경로: {{pixi_python}}")
print(f"Python 존재: {{os.path.exists(pixi_python)}}")
print(f"Rscript 경로: {{pixi_rscript}}")
print(f"Rscript 존재: {{os.path.exists(pixi_rscript)}}")

# .pixi 폴더 내용 확인
pixi_bin = "/app/.pixi/envs/default/bin"
if os.path.exists(pixi_bin):
    files = os.listdir(pixi_bin)[:10]  # 처음 10개만
    print(f".pixi/bin 폴더 내용 (일부): {{files}}")
"""

t1 = time.time()
init_result = sbx.run_code(init_code)
init_time = time.time() - t1

print(f"초기화 시간: {init_time:.2f}s")
if init_result.logs.stdout:
    print(f"stdout: {''.join(init_result.logs.stdout)}")
if init_result.error:
    print(f"error: {init_result.error}")
else:
    print("✅ 초기 설정 완료!")

# ============================================================
# 2. Python 변수 유지 테스트 (run_code 세션 간 변수 유지 확인)
# ============================================================
print("\n[TEST 2] Python 변수 유지 테스트 (run_code 세션 간)")
print("-" * 40)

# 첫 번째 run_code: 변수 할당
code1 = """
my_var = 42
my_list = [1, 2, 3]
my_dict = {"key": "value"}
print(f"[1차 실행] 변수 설정 완료: my_var={my_var}, my_list={my_list}, my_dict={my_dict}")
"""

t1 = time.time()
result1 = sbx.run_code(code1)
run1_time = time.time() - t1

print(f"1차 실행 시간: {run1_time:.2f}s")
if result1.logs.stdout:
    print(f"stdout: {''.join(result1.logs.stdout)}")
if result1.logs.stderr:
    print(f"stderr: {''.join(result1.logs.stderr)}")
if result1.error:
    print(f"error: {result1.error}")

# 두 번째 run_code: 이전 변수가 유지되는지 확인
code2 = """
print(f"[2차 실행] 이전 변수 확인: my_var={my_var}, my_list={my_list}, my_dict={my_dict}")
my_var += 10
my_list.append(4)
print(f"[2차 실행] 변수 수정 후: my_var={my_var}, my_list={my_list}")
"""

t1 = time.time()
result2 = sbx.run_code(code2)
run2_time = time.time() - t1

print(f"2차 실행 시간: {run2_time:.2f}s")
if result2.logs.stdout:
    print(f"stdout: {''.join(result2.logs.stdout)}")
if result2.logs.stderr:
    print(f"stderr: {''.join(result2.logs.stderr)}")
if result2.error:
    print(f"error: {result2.error}")
    print("❌ Python 변수 유지 테스트 실패!")
else:
    print("✅ Python 변수 유지 테스트 성공!")

python_var_time = run1_time + run2_time

# ============================================================
# 3. RDKit 로드 테스트 (run_code 직접 사용 - pixi site-packages 추가)
# ============================================================
print("\n[TEST 3] RDKit 로드 및 기능 테스트 (run_code 직접)")
print("-" * 40)

# 초기 설정에서 sys.path가 이미 설정되어 있으므로 바로 import 가능
rdkit_code = """
import rdkit
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors

print(f"RDKit 버전: {rdkit.__version__}")

# 간단한 분자 생성 테스트
smiles = "CCO"  # 에탄올
mol = Chem.MolFromSmiles(smiles)
if mol is not None:
    print(f"분자 SMILES: {smiles}")
    print(f"분자량: {Descriptors.MolWt(mol):.2f}")
    print(f"원자 개수: {mol.GetNumAtoms()}")
    print("RDKit 기능 테스트 성공!")
else:
    print("RDKit 분자 파싱 실패!")
"""

t1 = time.time()
result = sbx.run_code(rdkit_code)
rdkit_time = time.time() - t1

print(f"실행 시간: {rdkit_time:.2f}s")
if result.logs.stdout:
    print(f"stdout: {''.join(result.logs.stdout)}")
if result.logs.stderr:
    print(f"stderr: {''.join(result.logs.stderr)}")
if result.error:
    print(f"error: {result.error}")
    print("❌ RDKit 테스트 실패!")
else:
    print("✅ RDKit 테스트 성공!")

# ============================================================
# 4. R 패키지 실행 테스트 (commands.run 사용)
# ============================================================
print("\n[TEST 4] R 기본 실행 테스트 (commands.run)")
print("-" * 40)

# R 스크립트 파일 생성
r_basic_script = """
print("R 버전 정보:")
print(R.version.string)
print("")

# 기본 연산 테스트
x <- c(1, 2, 3, 4, 5)
print(paste("벡터:", paste(x, collapse=", ")))
print(paste("평균:", mean(x)))
print(paste("합계:", sum(x)))
print("")

# 설치된 패키지 확인
installed_packages <- rownames(installed.packages())
print(paste("설치된 패키지 수:", length(installed_packages)))
"""

# 파일 생성
sbx.files.write("/tmp/test_r_basic.R", r_basic_script)

# commands.run으로 R 실행
t1 = time.time()
result = sbx.commands.run(f"{PIXI_RSCRIPT} /tmp/test_r_basic.R", timeout=120)
r_basic_time = time.time() - t1

print(f"R 기본 테스트 실행 시간: {r_basic_time:.2f}s")
print(f"stdout: {result.stdout}")
if result.stderr:
    print(f"stderr: {result.stderr}")
print(f"exit_code: {result.exit_code}")
if result.exit_code == 0:
    print("✅ R 기본 테스트 성공!")
else:
    print("❌ R 기본 테스트 실패!")

# R 패키지 로드 테스트
print("\n[TEST 4-2] R 패키지 로드 테스트 (주요 패키지)")
print("-" * 40)

r_package_script = """
# 패키지 로드 테스트
packages_to_test <- c("ggplot2", "dplyr", "tidyr")

for (pkg in packages_to_test) {
    tryCatch({
        suppressPackageStartupMessages(library(pkg, character.only = TRUE))
        print(paste("✓", pkg, "로드 성공"))
    }, error = function(e) {
        print(paste("✗", pkg, "로드 실패:", e$message))
    })
}

# Seurat 테스트 (설치되어 있다면)
tryCatch({
    suppressPackageStartupMessages(library(Seurat))
    print(paste("✓ Seurat 버전:", packageVersion("Seurat")))
}, error = function(e) {
    print(paste("Seurat 미설치 또는 로드 실패:", e$message))
})
"""

sbx.files.write("/tmp/test_r_packages.R", r_package_script)

# commands.run으로 R 실행
t1 = time.time()
result = sbx.commands.run(f"{PIXI_RSCRIPT} /tmp/test_r_packages.R", timeout=180)
r_package_time = time.time() - t1

print(f"R 패키지 테스트 실행 시간: {r_package_time:.2f}s")
print(f"stdout: {result.stdout}")
if result.stderr:
    print(f"stderr: {result.stderr}")
print(f"exit_code: {result.exit_code}")
if result.exit_code == 0:
    print("✅ R 패키지 테스트 성공!")
else:
    print("❌ R 패키지 테스트 실패!")

# ============================================================
# 5. run_code 캐시 효과 확인 (두 번째 rdkit import - 세션 유지됨)
# ============================================================
print("\n[TEST 5] run_code 두 번째 실행 시간 (캐시 효과)")
print("-" * 40)

# 세션이 유지되어 sys.path가 이미 설정되어 있음
cache_code = """
import rdkit
print("hello from cached run")
print(f"rdkit 버전 (캐시): {rdkit.__version__}")
"""

t1 = time.time()
result = sbx.run_code(cache_code)
python_cached_time = time.time() - t1

print(f"두 번째 실행 시간: {python_cached_time:.2f}s")
if result.logs.stdout:
    print(f"stdout: {''.join(result.logs.stdout)}")
if result.error:
    print(f"error: {result.error}")

# ============================================================
# 결과 요약
# ============================================================
print("\n" + "=" * 60)
print("테스트 결과 요약")
print("=" * 60)
print(f"{'항목':<40} {'시간':>10}")
print("-" * 52)
print(f"{'Sandbox 생성':<40} {sandbox_creation_time:>8.2f}s")
print(f"{'초기 설정 (.pixi 확인)':<40} {init_time:>8.2f}s")
print(f"{'Python 변수 테스트 (1차+2차)':<40} {python_var_time:>8.2f}s")
print(f"  - 1차 실행 (변수 할당)               {run1_time:>8.2f}s")
print(f"  - 2차 실행 (변수 확인)               {run2_time:>8.2f}s")
print(f"{'RDKit 테스트 (run_code 직접)':<40} {rdkit_time:>8.2f}s")
print(f"{'R 기본 테스트 (commands.run)':<40} {r_basic_time:>8.2f}s")
print(f"{'R 패키지 테스트 (commands.run)':<40} {r_package_time:>8.2f}s")
print(f"{'Python 캐시된 실행 (run_code 직접)':<40} {python_cached_time:>8.2f}s")
print("-" * 52)
total_time = (
    sandbox_creation_time
    + init_time
    + python_var_time
    + rdkit_time
    + r_basic_time
    + r_package_time
    + python_cached_time
)
print(f"{'총 시간':<40} {total_time:>8.2f}s")
print("=" * 60)

# Sandbox 종료
# sbx.kill()
print("\n테스트 완료! (Sandbox는 자동 종료됩니다)")
