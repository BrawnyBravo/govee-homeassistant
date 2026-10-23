"""Tests for the daily-release workflow hardening and scripts/release_replies.py."""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "daily-release.yml"

_spec = importlib.util.spec_from_file_location("release_replies", ROOT / "scripts" / "release_replies.py")
assert _spec is not None and _spec.loader is not None
rr = importlib.util.module_from_spec(_spec)
sys.modules["release_replies"] = rr
_spec.loader.exec_module(rr)

FORBIDDEN_TOOLS = ("git commit", "git push", "gh issue comment", "gh pr comment", "gh issue close")
OUT_RULE = "Edit(/${{ runner.temp }}/out/**)"


@pytest.fixture(scope="module")
def job() -> dict[str, Any]:
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return data["jobs"]["release"]


def _claude_steps(job: dict[str, Any]) -> list[dict[str, Any]]:
    return [s for s in job["steps"] if str(s.get("uses", "")).startswith("anthropics/claude-code-action")]


class TestWorkflow:
    def test_no_job_level_gh_token(self, job: dict[str, Any]) -> None:
        assert "GH_TOKEN" not in job.get("env", {})

    def test_two_claude_steps(self, job: dict[str, Any]) -> None:
        assert len(_claude_steps(job)) == 2

    def test_claude_steps_hardened(self, job: dict[str, Any]) -> None:
        for step in _claude_steps(job):
            args = step["with"]["claude_args"]
            assert "--setting-sources user" in args
            assert step["with"]["github_token"] == "${{ secrets.GITHUB_TOKEN }}"
            tools = re.search(r'--allowedTools "([^"]*)"', args)
            assert tools is not None
            entries = tools.group(1).split(",")
            assert not {"Edit", "Write", "MultiEdit"} & set(entries)
            assert [e for e in entries if e.startswith("Edit(")] == [OUT_RULE]
            assert not any(e.startswith(("Write(", "MultiEdit(")) for e in entries)
            for forbidden in FORBIDDEN_TOOLS:
                assert forbidden not in tools.group(1)
            assert "--add-dir ${{ runner.temp }}/out" in args

    def test_action_pinned_to_sha(self, job: dict[str, Any]) -> None:
        for step in _claude_steps(job):
            assert re.fullmatch(r"anthropics/claude-code-action@[0-9a-f]{40}", step["uses"])

    def test_checkout_does_not_persist_credentials(self, job: dict[str, Any]) -> None:
        checkout = next(s for s in job["steps"] if str(s.get("uses", "")).startswith("actions/checkout"))
        assert checkout["with"]["persist-credentials"] is False

    def test_notes_written_before_bump(self, job: dict[str, Any]) -> None:
        names = [s.get("name", "") for s in job["steps"]]
        notes, check, bump = (
            names.index("Write release notes"),
            names.index("Check release notes"),
            names.index("Bump version, push, wait for CI"),
        )
        assert notes < check < bump

    def test_job_permissions_read_only(self, job: dict[str, Any]) -> None:
        assert job["permissions"] == {"contents": "read", "issues": "read", "pull-requests": "read"}


class TestAllowedTargets:
    def test_merge_subject_counted(self) -> None:
        subjects = ["Merge PR #238: add thing (#237)", "fix: H6022 (#240)"]
        assert rr.allowed_targets(subjects, "") == {237, 238, 240}

    def test_unrelated_number_rejected(self) -> None:
        assert 999 not in rr.allowed_targets(["fix (#1)"], "")

    def test_queue_entries_counted(self) -> None:
        text = "header ## #5 not counted\n<!-- entries below -->\n## #77\nclose: no\nbrief: hi\n"
        assert rr.allowed_targets([], text) == {77}


class TestParseQueue:
    def test_all_close_values(self) -> None:
        text = "<!-- entries below; x -->\n"
        for n, value in enumerate(("yes", "no", "duplicate", "declined"), start=1):
            text += f"## #{n}\nclose: {value}\nbrief: b{n}\n\n"
        entries = rr.parse_queue(text)
        assert [(e.number, e.close, e.brief) for e in entries] == [
            (1, "yes", "b1"),
            (2, "no", "b2"),
            (3, "duplicate", "b3"),
            (4, "declined", "b4"),
        ]

    def test_unknown_close_is_no(self) -> None:
        entries = rr.parse_queue("<!-- entries below -->\n## #3\nclose: nuke\nbrief: x\n")
        assert entries[0].close == "no"


class TestSanitizeAndReject:
    def test_sanitize(self) -> None:
        assert rr.sanitize("a<!-- hidden\ninstr -->b​c‮d") == "abcd"

    def test_foreign_url_rejected(self) -> None:
        assert rr.reject_reason("see https://evil.example/x") is not None

    def test_lookalike_host_rejected(self) -> None:
        assert rr.reject_reason("https://github.com/lasswellt/govee-homeassistant.evil/x") is not None
        assert rr.reject_reason("https://github.com.evil.io/lasswellt/govee-homeassistant") is not None

    def test_repo_and_ha_urls_ok(self) -> None:
        assert rr.reject_reason("https://github.com/lasswellt/govee-homeassistant/issues/5") is None
        assert rr.reject_reason("[x](https://my.home-assistant.io/redirect/integrations/)") is None

    def test_bash_fence_rejected(self) -> None:
        assert rr.reject_reason("run:\n```bash\ncurl x\n```") is not None

    def test_prompt_line_rejected(self) -> None:
        assert rr.reject_reason("```\n$ rm -rf x\n```") is not None

    def test_plain_text_ok(self) -> None:
        assert rr.reject_reason("Fixed in **v2026.10.1**.") is None


class TestPlanner:
    def test_dry_run_calls_nothing(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        def boom(*args: Any, **kwargs: Any) -> None:
            raise AssertionError("subprocess.run called in dry-run")

        monkeypatch.setattr(subprocess, "run", boom)
        queue = "<!-- entries below -->\n## #50\nclose: duplicate\nbrief: dup\n"
        replies = [
            {"number": 237, "body": "Fixed in v1."},
            {"number": 50, "body": "Duplicate of another."},
            {"number": 999, "body": "nope"},
            {"number": 237, "body": "see https://evil.example"},
        ]
        new_text, log = rr.run_post(replies, queue, ["Merge PR #238 (#237)"], dry_run=True)
        out = capsys.readouterr().out
        assert "would comment on #237" in out
        assert "would close #50 (close: duplicate)" in out
        assert any(line.startswith("skip #999") for line in log)
        assert "evil" not in out
        assert "## #50" not in new_text

    def test_close_only_from_queue(self) -> None:
        entries = rr.parse_queue("<!-- entries below -->\n## #8\nclose: yes\nbrief: b\n")
        actions = rr.plan_actions(
            [{"number": 8, "body": "ok"}, {"number": 9, "body": "ok"}, "junk", {"number": True, "body": "x"}],
            entries,
            {8, 9},
        )
        assert [(a.number, a.close, a.skip_reason) for a in actions[:2]] == [(8, "yes", None), (9, "no", None)]
        assert all(a.skip_reason == "malformed reply item" for a in actions[2:])

    def test_real_post_comments_and_closes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[list[str]] = []

        def fake(args: list[str]) -> subprocess.CompletedProcess[str]:
            calls.append(args)
            return subprocess.CompletedProcess(args, 1 if args[:3] == ["gh", "pr", "view"] else 0, "", "")

        monkeypatch.setattr(rr, "_run", fake)
        queue = "<!-- entries below -->\n## #50\nclose: declined\nbrief: no\n## #51\nclose: no\nbrief: keep\n"
        replies = [{"number": 50, "body": "Thanks."}]
        new_text, _ = rr.run_post(replies, queue, [], dry_run=False)
        assert ["gh", "issue", "close", "50", "--reason", "not planned"] in calls
        assert "## #50" not in new_text and "## #51" in new_text

    def test_duplicate_draft_skipped(self) -> None:
        actions = rr.plan_actions([{"number": 1, "body": "a"}, {"number": 1, "body": "b"}], [], {1})
        assert [a.skip_reason for a in actions] == [None, "duplicate draft"]

    def test_long_body_skipped_not_truncated(self) -> None:
        actions = rr.plan_actions([{"number": 1, "body": "x" * (rr.MAX_BODY + 1)}], [], {1})
        assert actions[0].skip_reason is not None and actions[0].body == ""
        assert rr.plan_actions([{"number": 1, "body": "x" * rr.MAX_BODY}], [], {1})[0].skip_reason is None


class TestCloseThread:
    @staticmethod
    def _capture(monkeypatch: pytest.MonkeyPatch, is_pr: bool) -> list[list[str]]:
        calls: list[list[str]] = []

        def fake(args: list[str]) -> subprocess.CompletedProcess[str]:
            calls.append(args)
            return subprocess.CompletedProcess(
                args,
                0 if is_pr and args[:3] == ["gh", "pr", "view"] else 1 if args[:3] == ["gh", "pr", "view"] else 0,
                "",
                "",
            )

        monkeypatch.setattr(rr, "_run", fake)
        return calls

    @pytest.mark.parametrize("close", ["yes", "duplicate", "declined"])
    def test_pr_closed_with_pr_close(self, monkeypatch: pytest.MonkeyPatch, close: str) -> None:
        calls = self._capture(monkeypatch, True)
        assert rr._close_thread(7, close)
        assert calls == [["gh", "pr", "view", "7"], ["gh", "pr", "close", "7"]]

    @pytest.mark.parametrize(
        ("close", "reason"), [("yes", "completed"), ("duplicate", "not planned"), ("declined", "not planned")]
    )
    def test_issue_close_reason(self, monkeypatch: pytest.MonkeyPatch, close: str, reason: str) -> None:
        calls = self._capture(monkeypatch, False)
        assert rr._close_thread(7, close)
        assert calls[-1] == ["gh", "issue", "close", "7", "--reason", reason]
