"""
Plan validation and repair system for SQL generation.
Validates LLM-generated plans against schema and auto-repairs common issues.
"""
import json
import re
from typing import Dict, List, Set, Optional, Any


class PlanValidator:
    """Validates and repairs SQL generation plans against schema"""
    
    def __init__(self, schema_graph=None):
        self.schema_graph = schema_graph
        self._schema_loaded = False
    
    def _extract_json_object(self, text: str) -> str:
        """Extract the first balanced JSON object from arbitrary text.
        - Strips markdown code fences (``` or ```json) if present
        - Returns substring from first '{' to its matching '}' (handles strings/escapes)
        - Falls back to trimmed input on failure
        """
        try:
            if not text:
                return text
            s = text.strip()
            # Strip code fences
            if s.startswith("```"):
                # Remove initial fence (with optional language tag)
                # Find the first newline after opening fence
                first_newline = s.find("\n")
                if first_newline != -1:
                    s = s[first_newline + 1 :]
                else:
                    s = s[3:]
                # Remove trailing fence if present
                if s.endswith("```"):
                    s = s[:-3]
                s = s.strip()
            # Find first JSON object
            start = s.find("{")
            if start == -1:
                return s
            stack = 0
            in_string = False
            escape = False
            end_index = None
            for i in range(start, len(s)):
                ch = s[i]
                if in_string:
                    if escape:
                        escape = False
                    elif ch == "\\":
                        escape = True
                    elif ch == '"':
                        in_string = False
                else:
                    if ch == '"':
                        in_string = True
                    elif ch == '{':
                        stack += 1
                    elif ch == '}':
                        stack -= 1
                        if stack == 0:
                            end_index = i + 1
                            break
            if end_index is not None:
                return s[start:end_index].strip()
            return s[start:].strip()
        except Exception:
            return text

    def _ensure_schema(self):
        """Lazy-load the schema graph if needed"""
        if not self._schema_loaded:
            if self.schema_graph is None:
                from ..loaders.graph_builder import schema_graph
                self.schema_graph = schema_graph
            self._schema_loaded = True
    
    def validate_plan(self, plan_json: str, user_query: str) -> Dict[str, Any]:
        """Validate and repair a plan JSON string"""
        self._ensure_schema()
        # Pre-clean: extract first JSON object if the model wrapped the output
        candidate = self._extract_json_object(plan_json)
        try:
            plan = json.loads(candidate)
        except json.JSONDecodeError as e:
            # Log a truncated preview for debugging
            try:
                from ..utils.loggery import query_logger
                preview = (plan_json or "")[:1000]
                error_details = {
                    "phase": "plan_parse",
                    "raw_plan_preview": preview,
                    "json_error": str(e)
                }
                # Use generic values for unknown fields; user_context is not available here
                query_logger.log_event(
                    user_context=None,
                    question=user_query,
                    provider="unknown",
                    relevant_tables=[],
                    schema_tokens=0,
                    attempts=0,
                    success=False,
                    sql="",
                    error="Invalid JSON plan format",
                    error_details=error_details
                )
            except Exception:
                pass
            return {
                "valid": False,
                "error": "Invalid JSON plan format",
                "repaired_plan": None
            }
        
        # Validate required fields
        required_fields = ["tables", "columns", "joins", "filters", "group_by", "order_by", "limit", "needs_scoping"]
        missing_fields = [field for field in required_fields if field not in plan]
        if missing_fields:
            return {
                "valid": False,
                "error": f"Missing required fields: {missing_fields}",
                "repaired_plan": None
            }

        # Ensure joins that connect all tables exist; if tables are disconnected, synthesize bridging joins via schema graph
        plan = self._synthesize_join_bridges(plan)
        
        # Validate tables exist in schema
        valid_tables = set(self.schema_graph.tables.keys())
        plan_tables = set(plan.get("tables", []))
        invalid_tables = plan_tables - valid_tables
        
        if invalid_tables:
            # Auto-repair: remove invalid tables
            plan["tables"] = list(plan_tables & valid_tables)
            if not plan["tables"]:
                return {
                    "valid": False,
                    "error": f"No valid tables found. Invalid tables: {list(invalid_tables)}",
                    "repaired_plan": None
                }
        
        # Validate columns exist in selected tables
        plan["columns"] = self._validate_columns(plan.get("columns", {}), plan["tables"])
        
        # Validate joins against schema relationships
        plan["joins"] = self._validate_joins(plan.get("joins", []), plan["tables"])
        
        # Validate scoping requirements
        plan["needs_scoping"] = self._validate_scoping(plan["tables"])
        
        # Intent-based validation and repair
        plan = self._apply_intent_repairs(plan, user_query)
        
        return {
            "valid": True,
            "repaired_plan": plan,
            "error": None
        }

    def _synthesize_join_bridges(self, plan: Dict) -> Dict:
        """If the set of tables is disconnected per schema, add bridging tables and implied joins."""
        try:
            tables = plan.get("tables", [])
            if not tables or len(tables) < 2:
                return plan
            # Build a minimal set of joins connecting all tables using schema_graph.get_join_path
            joins: List[Dict] = plan.get("joins", []) or []
            current_pairs = {(j.get('from_table'), j.get('to_table')) for j in joins}
            # For deterministic connectivity, start from the first table and connect others
            connected = {tables[0]}
            for t in tables[1:]:
                if t in connected:
                    continue
                path = self.schema_graph.find_path_between_tables(list(connected)[-1], t)
                if not path:
                    continue
                # Convert path to joins
                for i in range(len(path) - 1):
                    a, b = path[i], path[i+1]
                    if (a, b) in current_pairs:
                        connected.add(b)
                        continue
                    # find relationship details
                    rel = next((r for r in self.schema_graph.relationships if r.get('from') == a and r.get('to') == b), None)
                    if not rel:
                        continue
                    join = {
                        'from_table': a,
                        'to_table': b,
                        'from_column': rel.get('on'),
                        'to_column': rel.get('to_column', 'id'),
                        'type': 'INNER'
                    }
                    joins.append(join)
                    current_pairs.add((a, b))
                    connected.add(b)
            # If any new joins imply missing bridge tables, ensure they are in plan.tables
            implied_tables: List[str] = []
            for j in joins:
                for k in ['from_table', 'to_table']:
                    t = j.get(k)
                    if t and t not in tables:
                        implied_tables.append(t)
            if implied_tables:
                plan['tables'] = list(dict.fromkeys(tables + implied_tables))
            plan['joins'] = joins
            return plan
        except Exception:
            return plan
    
    def _validate_columns(self, columns_dict: Dict[str, List[str]], tables: List[str]) -> Dict[str, List[str]]:
        """Validate that columns exist in their respective tables"""
        validated_columns = {}
        
        for table in tables:
            if table not in self.schema_graph.tables:
                continue
            
            table_columns = set(self.schema_graph.tables[table].get('columns', []))
            plan_columns = columns_dict.get(table, [])
            
            # Filter to only existing columns
            valid_columns = [col for col in plan_columns if col in table_columns]
            validated_columns[table] = valid_columns
        
        return validated_columns
    
    def _validate_joins(self, joins: List[Dict], tables: List[str]) -> List[Dict]:
        """Validate joins against schema relationships"""
        if not joins:
            return joins
        
        # Build relationship map
        relationships = {}
        for rel in self.schema_graph.relationships:
            key = (rel['from'], rel['to'])
            relationships[key] = rel
        
        validated_joins = []
        for join in joins:
            from_table = join.get('from_table')
            to_table = join.get('to_table')
            from_column = join.get('from_column')
            to_column = join.get('to_column')
            join_type = join.get('type', 'INNER')
            
            # Check if tables are in our selected set
            if from_table not in tables or to_table not in tables:
                continue
            
            # Check if relationship exists in schema
            rel_key = (from_table, to_table)
            if rel_key in relationships:
                rel = relationships[rel_key]
                # Use schema-defined columns
                validated_join = {
                    'from_table': from_table,
                    'to_table': to_table,
                    'from_column': rel['on'],
                    'to_column': rel.get('to_column', 'id'),
                    'type': join_type
                }
                validated_joins.append(validated_join)
        
        return validated_joins
    
    def _validate_scoping(self, tables: List[str]) -> bool:
        """Determine if scoping is needed based on selected tables"""
        for table in tables:
            table_info = self.schema_graph.tables.get(table, {})
            if table_info.get('scoped', False):
                return True
        return False
    
    def _apply_intent_repairs(self, plan: Dict, user_query: str) -> Dict:
        """Apply intent-based repairs to the plan"""
        query_lower = user_query.lower()
        
        # Count/aggregate intent
        is_count_intent = any(word in query_lower for word in ['how many', 'count', 'number of', 'total'])
        if is_count_intent:
            # For count queries, clear columns and group_by; do not add time/display columns later
            plan["columns"] = {}
            plan["group_by"] = []
            plan["limit"] = None
        
        # List/browse intent
        elif any(word in query_lower for word in ['list', 'show', 'get', 'find']):
            # Ensure we have display columns for list queries
            plan = self._ensure_display_columns(plan)
        
        # Time-based queries
        if any(word in query_lower for word in ['today', 'yesterday', 'week', 'month', 'day']):
            # Ensure we have time columns, but skip if this is a count intent
            if not is_count_intent:
                plan = self._ensure_time_columns(plan)
        
        return plan
    
    def _ensure_display_columns(self, plan: Dict) -> Dict:
        """Ensure list queries have appropriate display columns"""
        for table in plan.get("tables", []):
            if table not in plan["columns"]:
                plan["columns"][table] = []
            
            table_info = self.schema_graph.tables.get(table, {})
            columns = table_info.get('columns', [])
            
            # Find display columns (name-like fields)
            display_columns = []
            for col in columns:
                if any(term in col.lower() for term in ['name', 'title', 'entity_name']):
                    display_columns.append(col)
            
            # For users table, prefer first_name + last_name
            if table == 'users' and 'first_name' in columns and 'last_name' in columns:
                if 'first_name' not in plan["columns"][table]:
                    plan["columns"][table].append('first_name')
                if 'last_name' not in plan["columns"][table]:
                    plan["columns"][table].append('last_name')
            
            # Add display columns if none exist
            if not plan["columns"][table] and display_columns:
                plan["columns"][table].extend(display_columns[:2])
        
        return plan
    
    def _ensure_time_columns(self, plan: Dict) -> Dict:
        """Ensure time-based queries have appropriate time columns"""
        for table in plan.get("tables", []):
            if table not in plan["columns"]:
                plan["columns"][table] = []
            
            table_info = self.schema_graph.tables.get(table, {})
            columns = table_info.get('columns', [])
            
            # Find time columns
            time_columns = [col for col in columns if 'date' in col.lower() or 'created' in col.lower()]
            
            # Add time columns if none exist
            if not any(col in plan["columns"][table] for col in time_columns):
                if time_columns:
                    plan["columns"][table].append(time_columns[0])
        
        return plan
    
    def get_validation_summary(self, plan: Dict) -> str:
        """Get a human-readable summary of plan validation"""
        summary_parts = []
        
        # Table summary
        tables = plan.get("tables", [])
        if tables:
            summary_parts.append(f"Tables: {', '.join(tables)}")
        
        # Column summary
        columns = plan.get("columns", {})
        if columns:
            col_summary = []
            for table, cols in columns.items():
                if cols:
                    col_summary.append(f"{table}({', '.join(cols[:3])}{'...' if len(cols) > 3 else ''})")
            if col_summary:
                summary_parts.append(f"Columns: {', '.join(col_summary)}")
        
        # Join summary
        joins = plan.get("joins", [])
        if joins:
            join_summary = [f"{j['from_table']}.{j['from_column']} -> {j['to_table']}.{j['to_column']}" for j in joins]
            summary_parts.append(f"Joins: {', '.join(join_summary)}")
        
        # Scoping
        if plan.get("needs_scoping", False):
            summary_parts.append("Scoping: Required")
        
        return " | ".join(summary_parts)


# Global instance
plan_validator = PlanValidator()


