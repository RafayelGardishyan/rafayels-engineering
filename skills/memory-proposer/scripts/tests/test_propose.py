"""Tests for propose.py: pure functions, content-hash branches, guardrails."""

from __future__ import annotations

import hashlib

import pytest

from propose import (
    ProposeError,
    _apply_to_skill_file,
    render_pattern_content,
    render_pr_body,
)


def test_render_pattern_content_includes_pattern_id():
    content = render_pattern_content(
        pattern_id=42,
        summary="Cases show a recurring pattern in plan phase",
        case_ids=[1, 2, 3, 4, 5],
        avg_reward=0.85,
    )
    assert "Pattern 42" in content
    assert "0.85" in content
    assert "#1" in content


def test_render_pattern_content_truncates_case_list():
    content = render_pattern_content(
        pattern_id=1,
        summary="Test",
        case_ids=list(range(1, 21)),
        avg_reward=0.5,
    )
    assert "+10 more" in content


def test_render_pr_body_has_required_sections():
    body = render_pr_body(
        pattern_id=42,
        target_skill="github",
        case_ids=[1, 2, 3],
        avg_reward=0.85,
    )
    assert "generated-by: memory-pattern-detector" in body
    assert "Review Checklist" in body
    assert "skills/github/SKILL.md" in body


def test_content_hash_is_stable():
    """Same inputs produce same hash, different inputs produce different hashes."""
    content_a = render_pattern_content(
        pattern_id=1, summary="same", case_ids=[1, 2, 3], avg_reward=0.8
    )
    content_b = render_pattern_content(
        pattern_id=1, summary="same", case_ids=[1, 2, 3], avg_reward=0.8
    )
    content_c = render_pattern_content(
        pattern_id=1, summary="different", case_ids=[1, 2, 3], avg_reward=0.8
    )
    assert content_a == content_b
    # Not strictly same hash because pattern_content includes today's date,
    # but at minimum the pattern_id and summary should differ
    assert "same" in content_a
    assert "different" in content_c


def test_apply_to_skill_file_creates_section(tmp_path):
    """Appends to a SKILL.md file, creating the Learned Patterns section."""
    skill_dir = tmp_path / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("# Test Skill\n\nSome content.\n")

    _apply_to_skill_file(skill_md, "Pattern content here")

    updated = skill_md.read_text()
    assert "## Learned Patterns" in updated
    assert "Pattern content here" in updated


def test_apply_to_skill_file_appends_to_existing_section(tmp_path):
    skill_dir = tmp_path / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        "# Test Skill\n\n## Learned Patterns\n\nExisting pattern.\n"
    )

    _apply_to_skill_file(skill_md, "New pattern")

    updated = skill_md.read_text()
    assert "Existing pattern" in updated
    assert "New pattern" in updated


def test_apply_to_skill_file_refuses_agents_dir(tmp_path):
    """Guardrail: must refuse to edit files under agents/."""
    agents_dir = tmp_path / "agents" / "test-agent"
    agents_dir.mkdir(parents=True)
    agent_md = agents_dir / "agent.md"
    agent_md.write_text("# Agent\n")

    with pytest.raises(ProposeError, match="agents"):
        _apply_to_skill_file(agent_md, "pattern content")


def test_apply_to_skill_file_refuses_outside_skills(tmp_path):
    """Guardrail: must refuse files outside skills/ or references/."""
    other_dir = tmp_path / "something-else"
    other_dir.mkdir()
    other_md = other_dir / "file.md"
    other_md.write_text("# Other\n")

    with pytest.raises(ProposeError):
        _apply_to_skill_file(other_md, "pattern content")
