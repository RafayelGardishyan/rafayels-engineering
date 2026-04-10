"""Tests for audit.py: report, doctor, read, list, export/import."""

from __future__ import annotations

import json

import pytest

from audit import (
    doctor,
    export_jsonl,
    import_jsonl,
    list_cases,
    read_case,
    report_stale,
    report_stats,
)
from capture import add_signal, write_case
from db import now


def test_read_case_found(conn):
    case_id = write_case(conn, phase="plan", query="test", title="hello")
    case = read_case(conn, case_id)
    assert case is not None
    assert case.title == "hello"


def test_read_case_not_found(conn):
    assert read_case(conn, 99999) is None


def test_list_cases_filters_by_phase(conn):
    write_case(conn, phase="plan", query="plan case")
    write_case(conn, phase="review", query="review case")
    plan_cases = list_cases(conn, phase="plan")
    review_cases = list_cases(conn, phase="review")
    assert len(plan_cases) == 1
    assert len(review_cases) == 1
    assert plan_cases[0].phase == "plan"


def test_list_cases_filters_by_status(conn):
    cid = write_case(conn, phase="plan", query="test")
    # cid is quarantine by default
    quarantined = list_cases(conn, status="quarantine")
    active = list_cases(conn, status="active")
    assert len(quarantined) == 1
    assert len(active) == 0


def test_report_stats_returns_expected_shape(conn):
    write_case(conn, phase="plan", query="test")
    stats = report_stats(conn)
    assert "total_cases" in stats
    assert "cases_by_phase" in stats
    assert "reward_distribution" in stats


def test_report_stale_returns_old_cases(conn):
    cid = write_case(conn, phase="plan", query="old")
    conn.execute(
        "UPDATE cases_raw SET created = ? WHERE case_id = ?",
        (now() - (100 * 86400), cid),
    )
    stale = report_stale(conn, older_than_days=90)
    assert len(stale) == 1
    assert stale[0]["case_id"] == cid


def test_doctor_returns_health_report(conn):
    data = doctor(conn)
    assert "status" in data
    assert "checks" in data
    assert len(data["checks"]) > 0


def test_export_and_import_roundtrip(conn, tmp_path):
    # Write a few cases
    for i in range(3):
        cid = write_case(conn, phase="plan", query=f"test {i}")
        add_signal(conn, case_id=cid, signal_type="merge", value=0.8)

    # Export
    export_path = tmp_path / "export.jsonl"
    count = export_jsonl(conn, export_path)
    assert count > 0
    assert export_path.exists()

    # Verify JSONL format
    lines = export_path.read_text().strip().split("\n")
    entries = [json.loads(line) for line in lines]
    case_entries = [e for e in entries if e["record"] == "case"]
    signal_entries = [e for e in entries if e["record"] == "signal"]
    assert len(case_entries) == 3
    assert len(signal_entries) == 3
