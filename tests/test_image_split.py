"""Community and enterprise images are separate build targets; enterprise code ships only in the enterprise one."""
import os
import re

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCKERFILE = os.path.join(REPO_ROOT, "Dockerfile")


def _stage(name: str) -> str:
    """Return the Dockerfile text from `FROM ... AS <name>` up to the next FROM."""
    src = open(DOCKERFILE).read()
    parts = re.split(r"^(?=FROM )", src, flags=re.MULTILINE)
    for part in parts:
        if re.match(rf"FROM \S+ AS {name}\s*$", part.splitlines()[0]):
            return part
    raise AssertionError(f"Dockerfile has no stage named {name}")


def _all_stages_before(name: str) -> str:
    src = open(DOCKERFILE).read()
    return src.split(f"AS {name}")[0]


def test_dockerfile_defines_community_and_enterprise_targets():
    _stage("community")
    _stage("enterprise")


def test_community_target_does_not_copy_enterprise_code():
    stage = _stage("community")
    assert not re.search(r"^COPY\s+(\S+\s+)*enterprise/", stage, flags=re.MULTILINE)
    assert "enterprise/__init__.py" in stage


def test_shared_stages_do_not_copy_enterprise_code():
    shared = _all_stages_before("community")
    assert not re.search(r"^COPY\s+(\S+\s+)*enterprise/", shared, flags=re.MULTILINE)


def test_enterprise_target_copies_enterprise_code():
    stage = _stage("enterprise")
    assert re.search(r"^COPY\s+(\S+\s+)*enterprise/\s+enterprise/", stage, flags=re.MULTILINE)


RELEASE = os.path.join(REPO_ROOT, ".github", "workflows", "release.yml")


def _job(name: str) -> str:
    """Return the release.yml text of one top-level job."""
    src = open(RELEASE).read()
    m = re.search(rf"^  {name}:\n(.*?)(?=^  \S+:\n|\Z)", src, flags=re.MULTILINE | re.DOTALL)
    assert m, f"release.yml has no job {name}"
    return m.group(1)


def test_release_has_no_build_api_job():
    assert not re.search(r"^  build-api:", open(RELEASE).read(), flags=re.MULTILINE)


def test_build_community_job_targets_community_image_only():
    job = _job("build-community")
    assert "needs: ci" in job
    assert "target: community" in job
    assert "aicontrol-community:latest" in job
    assert "aicontrol-community:${{ steps.date.outputs.DATE }}" in job
    assert "aicontrol-community:${{ github.ref_name }}" in job
    assert "aicontrol-api" not in job


def test_build_enterprise_job_targets_api_image():
    job = _job("build-enterprise")
    assert "needs: ci" in job
    assert "target: enterprise" in job
    assert "aicontrol-api:latest" in job
    assert "aicontrol-api:${{ steps.date.outputs.DATE }}" in job
    assert "aicontrol-api:${{ github.ref_name }}" in job
    assert "aicontrol-community" not in job


COMPOSE_APP = os.path.join(REPO_ROOT, "docker-compose.app.yml")
README = os.path.join(REPO_ROOT, "README.md")


def test_compose_api_image_defaults_to_community_and_honours_override():
    src = open(COMPOSE_APP).read()
    m = re.search(r"^  api:\n\s+image: (\S+)", src, flags=re.MULTILINE)
    assert m
    assert m.group(1) == (
        "${AICONTROL_API_IMAGE:-ghcr.io/alpaaai/aicontrol-community}:${AICONTROL_VERSION:-latest}"
    )


def test_compose_frontend_image_unchanged():
    assert "image: ghcr.io/alpaaai/aicontrol-frontend:${AICONTROL_VERSION:-latest}" in open(COMPOSE_APP).read()


def test_readme_components_table_lists_community_image_and_override():
    src = open(README).read()
    assert "| API (FastAPI) | `ghcr.io/alpaaai/aicontrol-community:latest` |" in src
    assert "AICONTROL_API_IMAGE" in src
    assert "docker login ghcr.io" in src


FRONTEND_DOCKERFILE = os.path.join(REPO_ROOT, "frontend", "Dockerfile")


def test_frontend_dockerfile_strips_demo_page_unless_include_demo_is_true():
    src = open(FRONTEND_DOCKERFILE).read()
    builder = src.split("FROM nginx")[0]
    assert "ARG INCLUDE_DEMO=false" in builder
    strip = re.search(r'RUN if \[ "\$INCLUDE_DEMO" != "true" \]; then (.*?);\s*\\\n\s*fi\n', builder, flags=re.DOTALL)
    assert strip, "no conditional demo strip step"
    body = strip.group(1)
    assert "frontend/src/pages/demo" not in body and "src/pages/demo" in body
    assert "src/api/demo.ts" in body
    assert "src/App.tsx" in body
    # the strip must run after COPY . . and before the build
    assert builder.index("COPY . .") < builder.index("INCLUDE_DEMO\" != ") < builder.index("npm run build")
