from e2b import Template, default_build_logger
import os

os.environ["E2B_API_KEY"] = "e2b_f308d8e737cc8ae69cd41343bd3d2fca2639ea22"


template = Template().from_image(
    image="public.ecr.aws/k4o7y1i6/jaechang-test:latest",
    # username="user",
    # password="pass",
)

Template.build(
    template,
    alias="jaechang-test",
    cpu_count=1,
    memory_mb=1024,
    on_build_logs=default_build_logger(),
)
