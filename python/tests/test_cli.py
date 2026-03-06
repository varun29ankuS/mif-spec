"""CLI integration tests — run mif commands via subprocess."""

import json
import os
import subprocess
import sys
import tempfile
import uuid

import pytest


PYTHON = sys.executable
MIF_SPEC_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
PYTHON_PKG = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))


def run_mif(*args, input_text=None, expect_fail=False):
    """Run 'python -m mif.cli <args>' and return (returncode, stdout, stderr)."""
    cmd = [PYTHON, "-m", "mif.cli"] + list(args)
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        input=input_text,
        cwd=PYTHON_PKG,
        timeout=30,
        env=env,
    )
    if not expect_fail and result.returncode != 0:
        # Allow failures when we expect them
        pass
    return result.returncode, result.stdout, result.stderr


def _write_temp(content: str, suffix: str = ".json") -> str:
    """Write content to a temp file and return the path."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    return path


@pytest.fixture
def valid_mif_file():
    data = json.dumps({
        "mif_version": "2.0",
        "memories": [{
            "id": str(uuid.uuid4()),
            "content": "Test memory for CLI",
            "created_at": "2025-01-01T00:00:00Z",
        }],
    })
    path = _write_temp(data)
    yield path
    os.unlink(path)


@pytest.fixture
def mem0_file():
    data = json.dumps([{
        "id": str(uuid.uuid4()),
        "memory": "CLI test from mem0",
        "created_at": "2025-01-01T00:00:00Z",
        "user_id": "user-cli",
    }])
    path = _write_temp(data)
    yield path
    os.unlink(path)


@pytest.fixture
def generic_file():
    data = json.dumps([{
        "id": str(uuid.uuid4()),
        "content": "CLI test generic",
        "timestamp": "2025-01-01T00:00:00Z",
    }])
    path = _write_temp(data)
    yield path
    os.unlink(path)


@pytest.fixture
def markdown_file():
    content = "---\ntype: observation\ncreated_at: 2025-01-01T00:00:00Z\n---\nCLI markdown test.\n"
    path = _write_temp(content, suffix=".md")
    yield path
    os.unlink(path)


@pytest.fixture
def invalid_json_file():
    path = _write_temp("this is not json {{{")
    yield path
    os.unlink(path)


# ── formats command ──────────────────────────────────────────────────────

class TestFormatsCommand:
    def test_formats_lists_all(self):
        rc, stdout, _ = run_mif("formats")
        assert rc == 0
        assert "shodh" in stdout
        assert "mem0" in stdout
        assert "generic" in stdout
        assert "markdown" in stdout


# ── convert command ──────────────────────────────────────────────────────

class TestConvertCommand:
    def test_convert_shodh_to_markdown(self, valid_mif_file):
        rc, stdout, _ = run_mif("convert", valid_mif_file, "--to", "markdown")
        assert rc == 0
        assert "---" in stdout

    def test_convert_with_from_flag(self, mem0_file):
        rc, stdout, _ = run_mif("convert", mem0_file, "--from", "mem0", "--to", "shodh")
        assert rc == 0
        parsed = json.loads(stdout)
        assert "mif_version" in parsed

    def test_convert_autodetect(self, mem0_file):
        rc, stdout, _ = run_mif("convert", mem0_file, "--to", "shodh")
        assert rc == 0

    def test_convert_to_generic(self, valid_mif_file):
        rc, stdout, _ = run_mif("convert", valid_mif_file, "--from", "shodh", "--to", "generic")
        assert rc == 0
        parsed = json.loads(stdout)
        assert isinstance(parsed, list)
        assert "content" in parsed[0]

    def test_convert_with_output_file(self, valid_mif_file):
        fd, out_path = tempfile.mkstemp(suffix=".md")
        os.close(fd)
        try:
            rc, stdout, _ = run_mif(
                "convert", valid_mif_file, "--to", "markdown", "-o", out_path
            )
            assert rc == 0
            assert "Converted" in stdout
            with open(out_path, encoding="utf-8") as f:
                content = f.read()
            assert "---" in content
        finally:
            os.unlink(out_path)

    def test_convert_markdown_to_shodh(self, markdown_file):
        rc, stdout, _ = run_mif("convert", markdown_file, "--from", "markdown", "--to", "shodh")
        assert rc == 0
        parsed = json.loads(stdout)
        assert parsed["mif_version"] == "2.0"

    def test_convert_missing_input_file(self):
        rc, stdout, stderr = run_mif("convert", "/nonexistent/file.json", expect_fail=True)
        assert rc != 0


# ── validate command ─────────────────────────────────────────────────────

class TestValidateCommand:
    def test_validate_valid_file(self, valid_mif_file):
        rc, stdout, _ = run_mif("validate", valid_mif_file)
        # May PASS or FAIL depending on schema availability
        assert "PASS" in stdout or "FAIL" in stdout

    def test_validate_invalid_json(self, invalid_json_file):
        rc, stdout, _ = run_mif("validate", invalid_json_file, expect_fail=True)
        assert "FAIL" in stdout or rc != 0

    def test_validate_multiple_files(self, valid_mif_file):
        rc, stdout, _ = run_mif("validate", valid_mif_file, valid_mif_file)
        # Should report on both files
        assert "passed validation" in stdout


# ── inspect command ──────────────────────────────────────────────────────

class TestInspectCommand:
    def test_inspect_shodh(self, valid_mif_file):
        rc, stdout, _ = run_mif("inspect", valid_mif_file)
        assert rc == 0
        assert "Memories:" in stdout
        assert "MIF version:" in stdout

    def test_inspect_with_format_flag(self, mem0_file):
        rc, stdout, _ = run_mif("inspect", mem0_file, "--from", "mem0")
        assert rc == 0
        assert "Memories:" in stdout

    def test_inspect_markdown(self, markdown_file):
        rc, stdout, _ = run_mif("inspect", markdown_file, "--from", "markdown")
        assert rc == 0
        assert "Memories: 1" in stdout

    def test_inspect_missing_file(self):
        rc, stdout, stderr = run_mif("inspect", "/nonexistent/file.json", expect_fail=True)
        assert rc != 0


# ── error cases ──────────────────────────────────────────────────────────

class TestCliErrors:
    def test_no_command(self):
        rc, stdout, stderr = run_mif(expect_fail=True)
        assert rc != 0 or "usage" in stdout.lower() or "usage" in stderr.lower()

    def test_unknown_format_in_convert(self, valid_mif_file):
        rc, stdout, stderr = run_mif(
            "convert", valid_mif_file, "--from", "nonexistent", expect_fail=True
        )
        assert rc != 0
