#!/usr/bin/env python3

import argparse
import collections
import datetime as dt
import json
import os
import sys
from typing import Any, Dict, Iterable, List, Optional


def _read_jsonl(path: str) -> Iterable[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                # skip malformed lines
                continue


def _parse_datetime(value: Optional[str]) -> Optional[dt.datetime]:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _filter_events(events: Iterable[Dict[str, Any]], role: Optional[str], since: Optional[str]) -> List[Dict[str, Any]]:
    parsed_since = None
    if since:
        try:
            parsed_since = dt.datetime.fromisoformat(since)
        except Exception:
            parsed_since = None

    filtered: List[Dict[str, Any]] = []
    for e in events:
        if role and e.get("role") != role:
            continue
        if parsed_since:
            ts = _parse_datetime(e.get("timestamp"))
            if ts is None or ts < parsed_since:
                continue
        filtered.append(e)
    return filtered


def summarize_query_events(
    file_path: str,
    top_n: int,
    include_questions: bool,
    role: Optional[str],
    since: Optional[str]
) -> None:
    events = list(_read_jsonl(file_path))
    events = _filter_events(events, role, since)

    total = len(events)
    successes = sum(1 for e in events if e.get("success") is True)
    failures = total - successes
    success_rate = (successes / total * 100.0) if total else 0.0

    providers = collections.Counter(e.get("provider") for e in events if e.get("provider"))
    roles = collections.Counter(e.get("role") for e in events if e.get("role"))
    tables = collections.Counter()
    for e in events:
        for t in (e.get("relevant_tables") or []):
            tables[t] += 1

    failure_reasons = collections.Counter()
    for e in events:
        if not e.get("success"):
            err = (e.get("error") or "").strip()
            if not err:
                err = "<unknown>"
            # normalize long errors
            err_short = err.split("\n", 1)[0]
            if len(err_short) > 160:
                err_short = err_short[:157] + "..."
            failure_reasons[err_short] += 1

    # Intents: question hash or plain question (optional)
    intents = collections.Counter()
    if include_questions:
        for e in events:
            q = (e.get("question") or "").strip()
            if q:
                intents[q] += 1
    else:
        for e in events:
            h = e.get("question_hash")
            if h is not None:
                intents[str(h)] += 1

    print("=== Query Events Summary ===")
    print(f"File: {file_path}")
    if role:
        print(f"Role filter: {role}")
    if since:
        print(f"Since: {since}")
    print(f"Total events: {total}")
    print(f"Success: {successes}  Failures: {failures}  Success rate: {success_rate:.1f}%")
    print()

    def _print_top(counter: collections.Counter, title: str):
        print(title)
        for item, count in counter.most_common(top_n):
            print(f"- {item}: {count}")
        if not counter:
            print("- <none>")
        print()

    _print_top(providers, "Top providers:")
    _print_top(roles, "Top roles:")
    _print_top(tables, "Top relevant tables:")
    _print_top(intents, "Top intents (question_hash or question):")
    _print_top(failure_reasons, "Top failure reasons:")


def summarize_access_audit(file_path: str, top_n: int, role: Optional[str], since: Optional[str]) -> None:
    events = list(_read_jsonl(file_path))
    events = _filter_events(events, role, since)

    total = len(events)
    successes = sum(1 for e in events if e.get("success") is True)
    failures = total - successes

    roles = collections.Counter(e.get("role") for e in events if e.get("role"))
    entities = collections.Counter()
    for e in events:
        for ent in (e.get("entities_accessed") or []):
            entities[ent] += 1

    errors = collections.Counter()
    for e in events:
        if not e.get("success"):
            msg = (e.get("error_message") or "").strip()
            if not msg:
                msg = "<unknown>"
            msg = msg.split("\n", 1)[0]
            if len(msg) > 160:
                msg = msg[:157] + "..."
            errors[msg] += 1

    print("=== Access Audit Summary ===")
    print(f"File: {file_path}")
    if role:
        print(f"Role filter: {role}")
    if since:
        print(f"Since: {since}")
    print(f"Total access logs: {total}  Success: {successes}  Failures: {failures}")
    print()

    def _print_top(counter: collections.Counter, title: str):
        print(title)
        for item, count in counter.most_common(top_n):
            print(f"- {item}: {count}")
        if not counter:
            print("- <none>")
        print()

    _print_top(roles, "Top roles:")
    _print_top(entities, "Top entities accessed:")
    _print_top(errors, "Top access errors:")


def main():
    parser = argparse.ArgumentParser(description="Summarize NL2SQL logs (query events and access audit)")
    parser.add_argument("--query-file", default="logs/query_events.jsonl", help="Path to query events JSONL")
    parser.add_argument("--access-file", default="logs/access_audit.jsonl", help="Path to access audit JSONL")
    parser.add_argument("--top", type=int, default=10, help="How many top items to show")
    parser.add_argument("--include-questions", action="store_true", help="Include full question text in intents (PII risk)")
    parser.add_argument("--role", default=None, help="Filter by role (e.g., customer, admin)")
    parser.add_argument("--since", default=None, help="ISO8601 lower bound, e.g., 2025-09-01T00:00:00")
    parser.add_argument("--no-access", action="store_true", help="Skip access audit summary")
    args = parser.parse_args()

    if not os.path.exists(args.query_file) and not os.path.exists(args.access_file):
        print("No log files found. Expected at least one of:")
        print(f"- {args.query_file}")
        print(f"- {args.access_file}")
        sys.exit(1)

    if os.path.exists(args.query_file):
        summarize_query_events(
            file_path=args.query_file,
            top_n=args.top,
            include_questions=args.include_questions,
            role=args.role,
            since=args.since,
        )
    else:
        print(f"(Missing {args.query_file})\n")

    if not args.no_access:
        if os.path.exists(args.access_file):
            summarize_access_audit(
                file_path=args.access_file,
                top_n=args.top,
                role=args.role,
                since=args.since,
            )
        else:
            print(f"(Missing {args.access_file})\n")


if __name__ == "__main__":
    main()


