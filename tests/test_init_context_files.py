"""Tests for kalibr init context file writing (CLAUDE.md and .cursorrules)."""

import os
import tempfile

import pytest
from typer.testing import CliRunner

from kalibr.cli.main import app
from kalibr.cli.init_cmd import _write_context_files


class TestWriteContextFiles:
    """Unit tests for _write_context_files helper."""

    def test_creates_claude_md_when_missing(self, tmp_path):
        """Creates CLAUDE.md in target dir when it doesn't exist."""
        _write_context_files(str(tmp_path))
        claude_file = tmp_path / "CLAUDE.md"
        assert claude_file.exists(), "CLAUDE.md should be created"
        content = claude_file.read_text()
        assert "Kalibr" in content
        assert "Router" in content

    def test_creates_cursorrules_when_missing(self, tmp_path):
        """Creates .cursorrules in target dir when it doesn't exist."""
        _write_context_files(str(tmp_path))
        cursorrules_file = tmp_path / ".cursorrules"
        assert cursorrules_file.exists(), ".cursorrules should be created"
        content = cursorrules_file.read_text()
        assert "Kalibr" in content

    def test_does_not_overwrite_existing_claude_md(self, tmp_path):
        """Does NOT overwrite CLAUDE.md if it already exists."""
        claude_file = tmp_path / "CLAUDE.md"
        original_content = "# My custom CLAUDE.md\nDo not overwrite me."
        claude_file.write_text(original_content)

        _write_context_files(str(tmp_path))

        assert claude_file.read_text() == original_content, "CLAUDE.md should not be overwritten"

    def test_does_not_overwrite_existing_cursorrules(self, tmp_path):
        """Does NOT overwrite .cursorrules if it already exists."""
        cursorrules_file = tmp_path / ".cursorrules"
        original_content = "# My custom rules\nDo not overwrite me."
        cursorrules_file.write_text(original_content)

        _write_context_files(str(tmp_path))

        assert cursorrules_file.read_text() == original_content, ".cursorrules should not be overwritten"

    def test_creates_both_files(self, tmp_path):
        """Creates both CLAUDE.md and .cursorrules when neither exists."""
        _write_context_files(str(tmp_path))
        assert (tmp_path / "CLAUDE.md").exists()
        assert (tmp_path / ".cursorrules").exists()

    def test_skips_gracefully_when_both_exist(self, tmp_path):
        """No error when both files already exist."""
        (tmp_path / "CLAUDE.md").write_text("existing claude")
        (tmp_path / ".cursorrules").write_text("existing cursor")

        # Should not raise
        _write_context_files(str(tmp_path))

        assert (tmp_path / "CLAUDE.md").read_text() == "existing claude"
        assert (tmp_path / ".cursorrules").read_text() == "existing cursor"


class TestInitCommandContextFiles:
    """Integration tests: kalibr init CLI writes context files."""

    def test_init_creates_context_files_in_empty_dir(self, tmp_path):
        """kalibr init on an empty dir creates CLAUDE.md and .cursorrules."""
        runner = CliRunner()
        result = runner.invoke(app, ["init", str(tmp_path)])

        assert (tmp_path / "CLAUDE.md").exists(), "CLAUDE.md should be created by kalibr init"
        assert (tmp_path / ".cursorrules").exists(), ".cursorrules should be created by kalibr init"

    def test_init_reports_created_files(self, tmp_path):
        """kalibr init prints confirmation messages for created files."""
        runner = CliRunner()
        result = runner.invoke(app, ["init", str(tmp_path)])

        assert "Created CLAUDE.md" in result.output
        assert "Created .cursorrules" in result.output

    def test_init_reports_skipped_when_files_exist(self, tmp_path):
        """kalibr init prints skip messages when context files already exist."""
        (tmp_path / "CLAUDE.md").write_text("existing")
        (tmp_path / ".cursorrules").write_text("existing")

        runner = CliRunner()
        result = runner.invoke(app, ["init", str(tmp_path)])

        assert "already exists, skipping" in result.output

    def test_init_does_not_overwrite_existing_context_files(self, tmp_path):
        """kalibr init never overwrites existing CLAUDE.md or .cursorrules."""
        (tmp_path / "CLAUDE.md").write_text("my custom claude")
        (tmp_path / ".cursorrules").write_text("my custom rules")

        runner = CliRunner()
        runner.invoke(app, ["init", str(tmp_path)])

        assert (tmp_path / "CLAUDE.md").read_text() == "my custom claude"
        assert (tmp_path / ".cursorrules").read_text() == "my custom rules"
