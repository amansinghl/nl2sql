#!/usr/bin/env python3
"""
Minimal evaluation harness for NL2SQL accuracy.

Metrics per golden case:
- table_recall: |expected ∩ selected[:K]| / |expected|
- table_precision: |expected ∩ selected[:K]| / |selected[:K]|
- sql_match: True/False/None (None when no expected_sql provided)

Usage:
  python tools/eval_runner.py --goldens tests/eval/goldens.json --top-k 8 --use-mock-llm 1

Writes JSON report to logs/eval_report.json
"""

import os
import sys
import json
import argparse
from typing import List, Dict, Any

# Ensure app is importable when run from repo root
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from app.graph_builder import schema_graph
from app.query_validator import get_query_validator
from app.intelligent_sql_generator import IntelligentSQLGenerator


class MockLLMHandler:
    """A very small mock that produces deterministic SQL for basic intents.
    It is NOT meant to replace provider quality, only to let the pipeline run end-to-end for eval.
    """

    provider_name = "mock"

    async def generate_sql(self, user_query: str, scoping_value: str, relevant_tables: List[str], schema_context: str = None) -> str:
        q = (user_query or "").lower()
        tables = relevant_tables or []
        main = tables[0] if tables else "entities"
        # Count intent heuristic
        is_count = any(k in q for k in ["how many", "count", "number of", "total"])
        if is_count:
            where = f" WHERE accounts_entity_id = '{scoping_value}'" if scoping_value else ""
            return f"SELECT COUNT(*) FROM {main}{where};"
        # List intent heuristic
        where = f" WHERE accounts_entity_id = '{scoping_value}'" if scoping_value and schema_graph.tables.get(main, {}).get('scoped', False) else ""
        return f"SELECT * FROM {main}{where} LIMIT 10;"

    async def explain_results(self, query: str, results: List[Dict], row_count: int) -> str:
        return f"Returned {row_count} rows."

    async def close(self):
        return


def normalize_sql(sql: str) -> str:
    s = (sql or "").strip().rstrip(";")
    s = " ".join(s.split())
    return s.lower()


async def evaluate_golden_case(gen: IntelligentSQLGenerator, case: Dict[str, Any], top_k: int, use_mock_llm: bool) -> Dict[str, Any]:
    question = case.get("question")
    expected_tables: List[str] = case.get("expected_tables", [])
    expected_sql = case.get("expected_sql")
    expected_regex = case.get("expected_sql_regex")
    scope = case.get("scoping_value")

    selected = await gen._intelligent_table_selection(question)
    selected_top = selected[:top_k]
    selected_set = set(selected_top)
    expected_set = set(expected_tables)
    intersection = selected_set.intersection(expected_set)
    recall = (len(intersection) / len(expected_set)) if expected_set else 1.0
    precision = (len(intersection) / len(selected_top)) if selected_top else 1.0

    sql_result = None
    sql_ok = None
    try:
        out = await gen.generate_accurate_sql(question, scope or "test_entity")
        sql_result = out.get("sql") if isinstance(out, dict) else None
        if expected_sql:
            sql_ok = normalize_sql(sql_result) == normalize_sql(expected_sql)
        elif expected_regex:
            import re
            sql_ok = bool(re.search(expected_regex, sql_result or "", flags=re.IGNORECASE))
    except Exception as e:
        sql_ok = False

    return {
        "question": question,
        "expected_tables": expected_tables,
        "selected": selected_top,
        "table_recall": recall,
        "table_precision": precision,
        "sql_generated": sql_result,
        "sql_match": sql_ok,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--goldens", default="tests/eval/goldens.json")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--use-mock-llm", type=int, default=1)
    args = parser.parse_args()

    # Initialize components
    validator = get_query_validator(schema_graph)
    llm = MockLLMHandler() if args.use_mock_llm else None
    gen = IntelligentSQLGenerator(llm, validator)

    with open(args.goldens, "r") as f:
        goldens = json.load(f)

    import asyncio
    results = asyncio.run(_run_all(gen, goldens, args.top_k, bool(args.use_mock_llm)))

    # Aggregate metrics
    num = len(results)
    avg_recall = sum(r["table_recall" ] for r in results) / max(1, num)
    avg_precision = sum(r["table_precision"] for r in results) / max(1, num)
    sql_with_labels = [r for r in results if r.get("sql_match") is not None]
    sql_acc = sum(1 for r in sql_with_labels if r.get("sql_match") is True) / max(1, len(sql_with_labels))

    report = {
        "cases": results,
        "summary": {
            "num_cases": num,
            "avg_table_recall": avg_recall,
            "avg_table_precision": avg_precision,
            "sql_accuracy": sql_acc if sql_with_labels else None,
        }
    }

    os.makedirs("logs", exist_ok=True)
    with open("logs/eval_report.json", "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report["summary"], indent=2))


async def _run_all(gen: IntelligentSQLGenerator, goldens: List[Dict[str, Any]], top_k: int, use_mock_llm: bool):
    out = []
    for case in goldens:
        r = await evaluate_golden_case(gen, case, top_k, use_mock_llm)
        out.append(r)
    return out


if __name__ == "__main__":
    main()


