import re
from typing import List, Dict, Set, Optional
from sqlparse import parse, tokens
from sqlparse.sql import Statement, Identifier, Where
from ..utils.config import settings
from ..utils.error_codes import create_validation_error, ErrorCodes
from ..utils.user_context import UserContext, permission_manager

class QueryValidator:
    def __init__(self, schema_graph=None):
        self.schema_graph = schema_graph
        self.security_config = settings.security
        self.scoped_tables = settings.get_scoped_tables(schema_graph)
    
    def validate_sql(self, sql: str, scoping_value: str = None, user_context: UserContext = None) -> Dict:
        """Validate SQL and ensure proper scoping filtering based on user context"""
        try:
            # Optional: AST-level validation using sqlglot for precise alias/column checks
            ast_result = self._ast_validate(sql, scoping_value, user_context)
            if ast_result and not ast_result.get("valid", True):
                # Ensure the caller knows AST validation was used
                ast_result["ast_used"] = True
                return ast_result
            # Parse the SQL
            parsed = parse(sql)
            if not parsed:
                return {"valid": False, "error": "Invalid SQL syntax"}
            
            statement = parsed[0]
            
            # Extract tables used in the query
            used_tables = self._extract_tables(statement)
            
            # Check for scoped tables
            scoped_tables = [table for table in used_tables if table in self.scoped_tables]
            
            # Determine scoping requirements based on user context
            if user_context:
                scoping_requirements = permission_manager.get_scoping_requirements(user_context)
                scoping_required = scoping_requirements.get('scoping_required', True)
                scoping_column = scoping_requirements.get('scoping_column')
                accessible_entities = scoping_requirements.get('accessible_entities')
            else:
                # Fallback to legacy behavior
                scoping_required = True
                scoping_column = self.security_config.SCOPING_COLUMN
                accessible_entities = [scoping_value] if scoping_value else None
            
            # Validate scoping filtering based on requirements
            if scoping_required and scoped_tables:
                validation_result = self._validate_scoping_filtering_with_context(
                    statement, scoped_tables, scoping_value, scoping_column, accessible_entities
                )
            else:
                # No scoping required (e.g., admin with full access)
                validation_result = {"valid": True, "scoping_applied": False}
            
            if not validation_result["valid"]:
                return validation_result
            
            # Additional safety checks
            safety_checks = self._perform_safety_checks(statement)
            if not safety_checks["valid"]:
                return safety_checks
            
            # Custom validation rules
            custom_checks = self._perform_custom_validation(statement, used_tables)
            if not custom_checks["valid"]:
                return custom_checks
            
            return {
                "valid": True,
                "tables": list(used_tables),
                "scoped_tables": scoped_tables,
                "modified_sql": validation_result.get("modified_sql", sql),
                "scoping_applied": validation_result.get("scoping_applied", scoping_required),
                "ast_used": bool(ast_result)
            }
            
        except Exception as e:
            # Error validating SQL
            error = create_validation_error(e, "sql_validation")
            return {"valid": False, "error": error.error_code.message, "error_code": error.error_code.code}

    def _ast_validate(self, sql: str, scoping_value: str = None, user_context: UserContext = None) -> Optional[Dict]:
        """Use sqlglot to validate columns and enforce scoping on correct aliases.
        Falls back silently if sqlglot is unavailable or parsing fails.
        """
        try:
            import sqlglot
            from sqlglot import exp
            # Parse and build mapping of table aliases to base tables
            parsed = sqlglot.parse_one(sql)
            alias_to_table: Dict[str, str] = {}
            used_tables: Set[str] = set()
            for t in parsed.find_all(exp.Table):
                name = (t.name or '').lower()
                alias = (t.alias_or_name or '').lower()
                base = name
                if base:
                    used_tables.add(base)
                if alias:
                    alias_to_table[alias] = base or alias
            # Collect SELECT-list aliases to allow usage in ORDER BY / GROUP BY
            select_aliases: Set[str] = set()
            try:
                for sel in getattr(parsed, 'expressions', []) or []:
                    alias_expr = getattr(sel, 'alias', None)
                    if alias_expr is not None:
                        alias_name = (getattr(alias_expr, 'name', None) or str(alias_expr) or '').strip('`').lower()
                        if alias_name:
                            select_aliases.add(alias_name)
            except Exception:
                # Best-effort collection of aliases; proceed if unavailable
                pass
            # Validate column references
            for col in parsed.find_all(exp.Column):
                parts = [p for p in col.parts if isinstance(p, str)]
                col_name = (parts[-1] if parts else col.name or '').lower()
                tbl_qual = (parts[-2] if len(parts) > 1 else col.table or '').lower()
                if tbl_qual:
                    base_tbl = alias_to_table.get(tbl_qual, tbl_qual)
                    if base_tbl in self.schema_graph.tables:
                        if col_name and col_name not in set(c.lower() for c in self.schema_graph.tables[base_tbl].get('columns', [])):
                            return {"valid": False, "error": f"Column '{col_name}' not in table '{base_tbl}'"}
                else:
                    # Allow unqualified references to SELECT aliases (e.g., ORDER BY alias)
                    if col_name in select_aliases:
                        continue
                    # Unqualified: allow if column exists in any used table uniquely
                    candidates = []
                    for tname in used_tables:
                        cols = set(c.lower() for c in self.schema_graph.tables.get(tname, {}).get('columns', []))
                        if col_name in cols:
                            candidates.append(tname)
                    if len(candidates) == 0:
                        return {"valid": False, "error": f"Column '{col_name}' not found in used tables"}
            # Enforce scoping on aliases of scoped tables if required
            if user_context:
                scoping_requirements = permission_manager.get_scoping_requirements(user_context)
                scoping_required = scoping_requirements.get('scoping_required', True)
                scope_col_global = scoping_requirements.get('scoping_column') or self.security_config.SCOPING_COLUMN
            else:
                scoping_required = True
                scope_col_global = self.security_config.SCOPING_COLUMN
            if scoping_required and scoping_value:
                # For every scoped table alias present, ensure a predicate exists: alias.scope_col = value
                pred_sql = parsed.sql(dialect="mysql").lower()
                missing = []
                for alias, base in alias_to_table.items():
                    info = self.schema_graph.tables.get(base, {})
                    if info.get('scoped', False):
                        scope_col = info.get('scoping_column', scope_col_global).lower()
                        pattern = rf"\b{alias}\.{scope_col}\s*=\s*['\"]?{scoping_value}['\"]?"
                        import re
                        if not re.search(pattern, pred_sql):
                            # Also allow unqualified scope col if no alias used for that table in predicates
                            pattern2 = rf"\b{scope_col}\s*=\s*['\"]?{scoping_value}['\"]?"
                            if not re.search(pattern2, pred_sql):
                                missing.append(f"{alias}.{scope_col}")
                if missing:
                    return {"valid": False, "error": f"Missing scoping filter on: {', '.join(sorted(set(missing)))}"}
            return {"valid": True}
        except Exception:
            return None
    
    def _extract_tables(self, statement: Statement) -> Set[str]:
        """Extract table names from SQL, robustly and without miscounting column names."""
        sql_text = str(statement)
        sql_norm = re.sub(r'\s+', ' ', sql_text).strip()
        tables: Set[str] = set()

        # Patterns to capture table identifiers after FROM, JOIN, UPDATE, INTO, DELETE FROM
        patterns = [
            r"\bFROM\s+([`\w\.]+)",
            r"\bJOIN\s+([`\w\.]+)",
            r"\bUPDATE\s+([`\w\.]+)",
            r"\bINTO\s+([`\w\.]+)",
            r"\bDELETE\s+FROM\s+([`\w\.]+)"
        ]
        for pat in patterns:
            for m in re.finditer(pat, sql_norm, flags=re.IGNORECASE):
                raw = m.group(1)
                # Strip qualifiers and backticks
                name = raw.split('.')[-1].strip('`').lower()
                # Filter obvious column-like names (heuristic): exclude names appearing with '=' or in select list fragments
                if name and not re.match(r"^(id|count|sum|avg|min|max)$", name):
                    tables.add(name)

        return tables
    
    def _extract_tables_from_tokens(self, tokens_list) -> Set[str]:
        """Deprecated: kept for compatibility but returns empty set to avoid overcounting."""
        return set()
    
    def _validate_scoping_filtering(self, statement: Statement, scoped_tables: List[str], scoping_value: str) -> Dict:
        """Validate that scoped tables have proper scoping filtering"""
        if not scoped_tables:
            return {"valid": True}
        
        # Check if scoping filtering exists
        scoping_filter_exists = self._check_scoping_filter_exists(statement, scoped_tables, scoping_value)
        
        if not scoping_filter_exists:
            if not self.security_config.ENABLE_AUTO_SCOPING:
                return {
                    "valid": False,
                    "error": f"Scoped tables {scoped_tables} must include proper scoping filter"
                }
            
            # Try to auto-append scoping filter
            modified_sql = self._append_scoping_filter(statement, scoped_tables, scoping_value)
            if modified_sql:
                return {
                    "valid": True,
                    "modified_sql": modified_sql,
                    "warning": "Auto-appended scoping filter"
                }
            else:
                return {
                    "valid": False,
                    "error": f"Scoped tables {scoped_tables} must include proper scoping filter"
                }
        
        return {"valid": True}
    
    def _validate_scoping_filtering_with_context(
        self, 
        statement: Statement, 
        scoped_tables: List[str], 
        scoping_value: str,
        scoping_column: str,
        accessible_entities: List[str] = None
    ) -> Dict:
        """Validate scoping filtering with enhanced context awareness"""
        
        if not scoped_tables:
            return {"valid": True, "scoping_applied": False}
        
        # Check if scoping filter exists
        scoping_filter_exists = self._check_scoping_filter_exists_with_context(
            statement, scoped_tables, scoping_value, scoping_column, accessible_entities
        )
        
        if not scoping_filter_exists:
            if not self.security_config.ENABLE_AUTO_SCOPING:
                return {
                    "valid": False,
                    "error": f"Scoped tables {scoped_tables} must include proper scoping filter"
                }
            
            # Try to auto-append scoping filter
            modified_sql = self._append_scoping_filter_with_context(
                statement, scoped_tables, scoping_value, scoping_column, accessible_entities
            )
            if modified_sql:
                return {
                    "valid": True,
                    "modified_sql": modified_sql,
                    "scoping_applied": True,
                    "warning": "Auto-appended scoping filter"
                }
            else:
                return {
                    "valid": False,
                    "error": f"Scoped tables {scoped_tables} must include proper scoping filter"
                }
        
        return {"valid": True, "scoping_applied": True}
    
    def _check_scoping_filter_exists_with_context(
        self, 
        statement: Statement, 
        scoped_tables: List[str], 
        scoping_value: str,
        scoping_column: str,
        accessible_entities: List[str] = None
    ) -> bool:
        """Check if scoping filter exists with context awareness"""
        sql_str = str(statement).lower()
        
        # Check for each scoped table's scoping column
        for table in scoped_tables:
            table_scoping_column = self.scoped_tables.get(table, scoping_column)
            
            # Look for scoping_column = value pattern
            patterns = [
                rf"{table_scoping_column}\s*=\s*['\"]?{scoping_value}['\"]?",
                rf"{table_scoping_column}\s*=\s*%s",  # Parameterized query
                rf"{table_scoping_column}\s*=\s*\?",  # Parameterized query
            ]
            
            # If accessible_entities is provided, also check for IN clause
            if accessible_entities and len(accessible_entities) > 1:
                entities_str = "', '".join(accessible_entities)
                patterns.append(rf"{table_scoping_column}\s+IN\s*\(\s*['\"]?{entities_str}['\"]?\s*\)")
            
            for pattern in patterns:
                if re.search(pattern, sql_str):
                    return True
        
        return False
    
    def _append_scoping_filter_with_context(
        self, 
        statement: Statement, 
        scoped_tables: List[str], 
        scoping_value: str,
        scoping_column: str,
        accessible_entities: List[str] = None
    ) -> Optional[str]:
        """Append scoping filter with context awareness"""
        try:
            sql_str = str(statement)
            
            # Build filter conditions for each scoped table
            filter_conditions = []
            for table in scoped_tables:
                table_scoping_column = self.scoped_tables.get(table, scoping_column)
                
                if accessible_entities and len(accessible_entities) > 1:
                    # Use IN clause for multiple entities
                    entities_str = "', '".join(accessible_entities)
                    filter_conditions.append(f"{table_scoping_column} IN ('{entities_str}')")
                else:
                    # Use equality for single entity
                    filter_conditions.append(f"{table_scoping_column} = '{scoping_value}'")
            
            filter_clause = " AND ".join(filter_conditions)
            
            # Find WHERE clause
            where_match = re.search(r'\bWHERE\b', sql_str, re.IGNORECASE)
            
            if where_match:
                # Add AND scoping filter to existing WHERE
                insert_pos = where_match.end()
                filter_clause = f" AND ({filter_clause})"
                modified_sql = sql_str[:insert_pos] + filter_clause + sql_str[insert_pos:]
            else:
                # Add WHERE clause before ORDER BY, LIMIT, etc.
                from_match = re.search(r'\bFROM\b.*?(?=\b(?:ORDER BY|GROUP BY|LIMIT|OFFSET)\b)', sql_str, re.IGNORECASE | re.DOTALL)
                
                if from_match:
                    insert_pos = from_match.end()
                    filter_clause = f" WHERE {filter_clause}"
                    modified_sql = sql_str[:insert_pos] + filter_clause + sql_str[insert_pos:]
                else:
                    # Fallback: add at the end before semicolon
                    modified_sql = sql_str.rstrip(';') + f" WHERE {filter_clause};"
            
            return modified_sql
            
        except Exception as e:
            # Error appending scoping filter
            return None
    
    def _check_scoping_filter_exists(self, statement: Statement, scoped_tables: List[str], scoping_value: str) -> bool:
        """Check if scoping filter exists in WHERE clause"""
        sql_str = str(statement).lower()
        
        # Check for each scoped table's scoping column
        for table in scoped_tables:
            scoping_column = self.scoped_tables.get(table, self.security_config.SCOPING_COLUMN)
            
            # Look for scoping_column = value pattern
            patterns = [
                rf"{scoping_column}\s*=\s*['\"]?{scoping_value}['\"]?",
                rf"{scoping_column}\s*=\s*%s",  # Parameterized query
                rf"{scoping_column}\s*=\s*\?",  # Parameterized query
            ]
            
            for pattern in patterns:
                if re.search(pattern, sql_str):
                    return True
        
        return False
    
    def _append_scoping_filter(self, statement: Statement, scoped_tables: List[str], scoping_value: str) -> Optional[str]:
        """Append scoping filter to SQL statement"""
        try:
            sql_str = str(statement)
            
            # Build filter conditions for each scoped table
            filter_conditions = []
            for table in scoped_tables:
                scoping_column = self.scoped_tables.get(table, self.security_config.SCOPING_COLUMN)
                filter_conditions.append(f"{scoping_column} = '{scoping_value}'")
            
            filter_clause = " AND ".join(filter_conditions)
            
            # Find WHERE clause
            where_match = re.search(r'\bWHERE\b', sql_str, re.IGNORECASE)
            
            if where_match:
                # Add AND scoping filter to existing WHERE
                insert_pos = where_match.end()
                filter_clause = f" AND ({filter_clause})"
                modified_sql = sql_str[:insert_pos] + filter_clause + sql_str[insert_pos:]
            else:
                # Add WHERE clause before ORDER BY, LIMIT, etc.
                # Find the end of the FROM/JOIN section
                from_match = re.search(r'\bFROM\b.*?(?=\b(?:ORDER BY|GROUP BY|LIMIT|OFFSET)\b)', sql_str, re.IGNORECASE | re.DOTALL)
                
                if from_match:
                    insert_pos = from_match.end()
                    filter_clause = f" WHERE {filter_clause}"
                    modified_sql = sql_str[:insert_pos] + filter_clause + sql_str[insert_pos:]
                else:
                    # Fallback: add at the end before semicolon
                    modified_sql = sql_str.rstrip(';') + f" WHERE {filter_clause};"
            
            return modified_sql
            
        except Exception as e:
            # Error appending scoping filter
            return None
    
    def _perform_safety_checks(self, statement: Statement) -> Dict:
        """Perform additional safety checks on the SQL"""
        sql_str = str(statement).upper()
        
        # Check for dangerous operations - use word boundaries to avoid false positives
        dangerous_keywords = [
            'DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'CREATE', 'INSERT', 'UPDATE'
        ]
        
        for keyword in dangerous_keywords:
            # Use word boundaries to ensure we only match actual SQL keywords, not substrings
            pattern = r'\b' + keyword + r'\b'
            if re.search(pattern, sql_str):
                return {
                    "valid": False,
                    "error": f"Operation '{keyword}' is not allowed for security reasons"
                }
        
        # Check for potential injection patterns
        # Only flag if there are multiple statements (semicolon followed by non-whitespace)
        if re.search(r';\s*[A-Za-z]', sql_str, re.IGNORECASE):
            return {
                "valid": False,
                "error": "Multiple statements detected - potential SQL injection"
            }
        
        # Check for SQL comments (but allow them in certain contexts)
        if re.search(r'--\s*[A-Za-z]', sql_str, re.IGNORECASE):
            return {
                "valid": False,
                "error": "SQL comments detected - potential injection"
            }
        
        # Check for block comments
        if re.search(r'/\*.*?\*/', sql_str, re.IGNORECASE | re.DOTALL):
            return {
                "valid": False,
                "error": "Block comments detected - potential injection"
            }
        
        return {"valid": True}
    
    def _perform_custom_validation(self, statement: Statement, used_tables: List[str]) -> Dict:
        """Perform custom validation based on configuration"""
        custom_rules = self.security_config.get_custom_rules()
        
        # Check max tables rule
        max_tables = custom_rules.get('max_tables')
        print(f"max_tables: {max_tables}")
        print(f"used_tables: {used_tables}")
        if max_tables and len(used_tables) > max_tables:
            return {
                "valid": False,
                "error": f"Query uses too many tables. Maximum allowed: {max_tables}, found: {len(used_tables)}"
            }
        
        # Check allowed operations
        allowed_operations = custom_rules.get('allowed_operations', ['SELECT'])
        sql_str = str(statement).upper()
        
        for operation in ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER']:
            # Use word boundaries to ensure we only match actual SQL keywords, not substrings
            pattern = r'\b' + operation + r'\b'
            if re.search(pattern, sql_str) and operation not in allowed_operations:
                return {
                    "valid": False,
                    "error": f"Operation '{operation}' is not allowed. Allowed operations: {', '.join(allowed_operations)}"
                }
        
        # Validate JOIN columns against schema relationships
        try:
            if self.schema_graph and getattr(self.schema_graph, 'relationships', None):
                sql_lower = str(statement).lower()
                issues = []
                for rel in self.schema_graph.relationships:
                    from_table = rel.get('from')
                    to_table = rel.get('to')
                    on_column = rel.get('on')
                    if not from_table or not to_table or not on_column:
                        continue
                    if from_table not in used_tables or to_table not in used_tables:
                        continue
                    # Determine expected right-side column
                    target_table = self.schema_graph.tables.get(to_table, {})
                    target_columns = set(col.lower() for col in target_table.get('columns', []))
                    to_column = rel.get('to_column')
                    if to_column:
                        expected_right = to_column.lower()
                    else:
                        expected_right = on_column.lower() if on_column.lower() in target_columns else 'id'
                    # If expected_right is not 'id', flag joins that use '.id' instead
                    if expected_right != 'id':
                        wrong_patterns = [
                            rf"{from_table}\.{on_column}\s*=\s*{to_table}\.id",
                            rf"{to_table}\.id\s*=\s*{from_table}\.{on_column}"
                        ]
                        for pat in wrong_patterns:
                            if re.search(pat, sql_lower):
                                issues.append(
                                    f"Incorrect join between {from_table} and {to_table}. Use {from_table}.{on_column} = {to_table}.{expected_right}"
                                )
                if issues:
                    return {"valid": False, "error": "; ".join(issues)}
        except Exception:
            # Best-effort join validation; ignore errors
            pass
        
        return {"valid": True}
    
    def sanitize_sql(self, sql: str) -> str:
        """Basic SQL sanitization"""
        # Remove comments
        sql = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)
        sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
        
        # Remove multiple statements
        sql = sql.split(';')[0] + ';'
        
        # Trim whitespace
        sql = sql.strip()
        
        return sql

# Global instance - will be initialized with schema graph when available
query_validator = None

def get_query_validator(schema_graph=None):
    """Get query validator instance, creating it if needed"""
    global query_validator
    if query_validator is None or (schema_graph is not None and query_validator.schema_graph != schema_graph):
        query_validator = QueryValidator(schema_graph)
    return query_validator


