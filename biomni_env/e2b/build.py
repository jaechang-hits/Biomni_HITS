from e2b import Template, default_build_logger
import os
from pathlib import Path

# E2B API 키는 ~/.bashrc에서 환경변수로 설정됨
if not os.environ.get("E2B_API_KEY"):
    raise ValueError(
        "E2B_API_KEY 환경변수가 설정되지 않았습니다. ~/.bashrc를 확인하세요."
    )

# GitHub 설정
GITHUB_REPO = "jaechang-hits/Biomni_HITS"
GITHUB_BRANCH = "e2b"


def get_github_token():
    """~/.git-credentials에서 GitHub 토큰 읽기"""
    credentials_path = os.path.expanduser("~/.git-credentials")
    with open(credentials_path) as f:
        for line in f:
            line = line.strip()
            if "github.com" in line:
                # 형식: https://TOKEN@github.com
                return line.split("://")[1].split("@")[0]
    raise ValueError("GitHub token not found in ~/.git-credentials")


GITHUB_TOKEN = get_github_token()

template = (
    Template()
    # e2b code-interpreter 템플릿 상속 (start_cmd 포함 모든 설정 상속)
    # from_image()는 이미지만 복사하고 start_cmd는 상속 안됨
    .from_template("code-interpreter-v1")
    # root 사용자로 설정
    .set_user("root")
    # 환경 변수 설정
    .set_envs(
        {
            "DEBIAN_FRONTEND": "noninteractive",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "KMP_AFFINITY": "disabled",
            "OMP_NUM_THREADS": "1",
            "PIXI_HOME": "/opt/pixi",
            "PATH": "${PIXI_HOME}/bin:${PATH}",
            "PIXI_CONCURRENT_DOWNLOADS": "20",
        }
    )
    # 시스템 패키지 설치
    .apt_install(
        [
            "build-essential",
            "curl",
            "wget",
            "git",
            "ca-certificates",
            "bzip2",
            "libcurl4-openssl-dev",
            "libssl-dev",
            "libxml2-dev",
            "libfontconfig1-dev",
            "libharfbuzz-dev",
            "libfribidi-dev",
            "libfreetype6-dev",
            "libpng-dev",
            "libtiff5-dev",
            "libjpeg-dev",
            "liblzma-dev",
            "libbz2-dev",
            "libpcre2-dev",
            "libreadline-dev",
        ]
    )
    # Pixi 설치 (PATH에 추가)
    .run_cmd("curl -fsSL https://pixi.sh/install.sh | PIXI_HOME=/opt/pixi bash")
    .run_cmd("echo 'export PATH=/opt/pixi/bin:$PATH' >> /etc/profile.d/pixi.sh")
    .run_cmd("echo 'eval \"$(pixi completion --shell bash)\"' >> ~/.bashrc")
    # 작업 디렉토리 생성 및 설정
    .set_workdir("/app")
    # GitHub에서 프로젝트 클론
    .git_clone(
        f"https://{GITHUB_TOKEN}@github.com/{GITHUB_REPO}.git",
        path="/app",
        branch=GITHUB_BRANCH,
        depth=1,  # shallow clone으로 빠르게
    )
    # Pixi 환경 설치 (Python 3.12 - E2B Jupyter 커널과 동일 버전)
    .run_cmd("export PATH=/opt/pixi/bin:$PATH && pixi install --frozen")
    # 프로젝트를 pip install (pixi 환경 내에서 실행)
    .run_cmd("export PATH=/opt/pixi/bin:$PATH && pixi run pip install .")
    .run_cmd("export PATH=/opt/pixi/bin:$PATH && pixi clean cache --yes")
    .run_cmd("rm -rf ~/.cache/rattler")
    # # R 패키지 설치
    # .run_cmd(
    #     "export PATH=/opt/pixi/bin:$PATH && pixi run Rscript biomni_env/omics/install_r_packages.R"
    # )
    # # pixi shell 진입용 alias 설정 (자동 실행하지 않음 - code interpreter 호환)
    # .run_cmd(
    #     'echo \'alias pixi-shell="cd /app && export PATH=/opt/pixi/bin:\\$PATH && eval \\"\\$(pixi shell-hook)\\""\' >> ~/.bashrc'
    # )
)

Template.build(
    template,
    alias="jaechang-test",
    cpu_count=1,
    memory_mb=4096,  # R 패키지 설치에 메모리 필요
    # skip_cache=True,  # 캐시 없이 빌드
    on_build_logs=default_build_logger(),
)
