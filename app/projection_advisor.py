"""
Intent-aware projection advisor for SQL generation.
Analyzes query intent and suggests appropriate column projections.
"""
import re
from typing import Dict, List, Set, Optional


class ProjectionAdvisor:
    """Intent-aware projection advisor for SQL queries"""
    
    def __init__(self, schema_graph=None):
        self.schema_graph = schema_graph
        self._schema_loaded = False
    
    def _ensure_schema(self):
        """Lazy-load the schema graph if needed"""
        if not self._schema_loaded:
            if self.schema_graph is None:
                from .graph_builder import schema_graph
                self.schema_graph = schema_graph
            self._schema_loaded = True
    
    def analyze_intent(self, user_query: str) -> Dict[str, bool]:
        """Analyze query intent and return intent flags"""
        query_lower = user_query.lower()
        
        intents = {
            'is_count': any(word in query_lower for word in ['how many', 'count', 'number of', 'total']),
            'is_aggregate': any(word in query_lower for word in ['sum', 'average', 'avg', 'max', 'min', 'total']),
            'is_list': any(word in query_lower for word in ['list', 'show', 'get', 'find', 'display']),
            'is_detail': any(word in query_lower for word in ['details', 'information', 'complete']),
            'is_time_based': any(word in query_lower for word in ['today', 'yesterday', 'week', 'month', 'day', 'last']),
            'is_grouped': any(word in query_lower for word in ['by', 'group', 'per', 'each']),
            'is_join_needed': any(word in query_lower for word in ['with', 'including', 'and', 'join'])
        }
        
        return intents
    
    def suggest_projections(self, user_query: str, tables: List[str], existing_columns: Dict[str, List[str]] = None) -> Dict[str, List[str]]:
        """Suggest appropriate column projections based on intent and tables"""
        self._ensure_schema()
        intents = self.analyze_intent(user_query)
        existing_columns = existing_columns or {}
        
        suggestions = {}
        
        for table in tables:
            if table not in self.schema_graph.tables:
                continue
            
            table_info = self.schema_graph.tables.get(table, {})
            columns = table_info.get('columns', [])
            
            # Start with existing columns
            suggested_cols = existing_columns.get(table, []).copy()
            
            # Count/aggregate queries
            if intents['is_count'] or intents['is_aggregate']:
                # Don't add extra columns for count/aggregate queries
                # The existing columns should already be appropriate
                pass
            
            # List/browse queries
            elif intents['is_list']:
                suggested_cols = self._add_display_columns(table, columns, suggested_cols)
            
            # Detail queries
            elif intents['is_detail']:
                suggested_cols = self._add_display_columns(table, columns, suggested_cols)
                suggested_cols = self._add_key_columns(table, columns, suggested_cols)
            
            # Time-based queries
            if intents['is_time_based']:
                suggested_cols = self._add_time_columns(table, columns, suggested_cols)
            
            # Always add ID columns for reference
            suggested_cols = self._add_id_columns(table, columns, suggested_cols)
            
            # Remove duplicates while preserving order
            seen = set()
            unique_cols = []
            for col in suggested_cols:
                if col not in seen:
                    unique_cols.append(col)
                    seen.add(col)
            
            suggestions[table] = unique_cols
        
        return suggestions
    
    def _add_display_columns(self, table: str, columns: List[str], existing: List[str]) -> List[str]:
        """Add human-readable display columns"""
        display_columns = []
        
        # Name-like columns (highest priority)
        name_patterns = ['name', 'title', 'entity_name', 'supplier_name', 'channel_name']
        for col in columns:
            if any(pattern in col.lower() for pattern in name_patterns):
                if col not in existing:
                    display_columns.append(col)
        
        # For users table, prefer first_name + last_name
        if table == 'users':
            if 'first_name' in columns and 'first_name' not in existing:
                display_columns.append('first_name')
            if 'last_name' in columns and 'last_name' not in existing:
                display_columns.append('last_name')
        
        # Contact information
        contact_patterns = ['email', 'phone', 'mobile', 'contact']
        for col in columns:
            if any(pattern in col.lower() for pattern in contact_patterns):
                if col not in existing and col not in display_columns:
                    display_columns.append(col)
        
        return existing + display_columns[:3]  # Limit to 3 display columns
    
    def _add_key_columns(self, table: str, columns: List[str], existing: List[str]) -> List[str]:
        """Add key identifying columns"""
        key_columns = []
        
        # ID columns
        id_patterns = ['id', 'no', 'number', 'code']
        for col in columns:
            if any(pattern in col.lower() for pattern in id_patterns):
                if col not in existing and col not in key_columns:
                    key_columns.append(col)
        
        return existing + key_columns[:2]  # Limit to 2 key columns
    
    def _add_time_columns(self, table: str, columns: List[str], existing: List[str]) -> List[str]:
        """Add time-related columns"""
        time_columns = []
        
        # Date/time columns
        time_patterns = ['date', 'created', 'updated', 'time']
        for col in columns:
            if any(pattern in col.lower() for pattern in time_patterns):
                if col not in existing and col not in time_columns:
                    time_columns.append(col)
        
        return existing + time_columns[:2]  # Limit to 2 time columns
    
    def _add_id_columns(self, table: str, columns: List[str], existing: List[str]) -> List[str]:
        """Add primary key columns if not already present"""
        id_columns = []
        
        # Primary key patterns
        pk_patterns = ['id', 'no', 'number']
        for col in columns:
            if col.lower() in pk_patterns and col not in existing:
                id_columns.append(col)
                break  # Only add one primary key
        
        return existing + id_columns
    
    def get_projection_sql(self, table: str, columns: List[str]) -> str:
        """Convert column list to SQL projection with special handling"""
        if not columns:
            return f"{table}.*"
        
        # Special handling for users table
        if table == 'users' and 'first_name' in columns and 'last_name' in columns:
            # Create a display name column
            sql_parts = []
            for col in columns:
                if col == 'first_name':
                    sql_parts.append(f"CONCAT(first_name, ' ', last_name) AS user_name")
                elif col == 'last_name':
                    continue  # Skip last_name as it's included in user_name
                else:
                    sql_parts.append(col)
            return ', '.join(sql_parts)
        
        return ', '.join(columns)
    
    def should_use_count(self, user_query: str) -> bool:
        """Determine if query should use COUNT(*) projection"""
        query_lower = user_query.lower()
        count_indicators = ['how many', 'count', 'number of', 'total']
        return any(indicator in query_lower for indicator in count_indicators)
    
    def get_aggregation_hints(self, user_query: str) -> List[str]:
        """Get aggregation hints based on query intent"""
        query_lower = user_query.lower()
        hints = []
        
        if 'sum' in query_lower or 'total' in query_lower:
            hints.append('SUM')
        if 'average' in query_lower or 'avg' in query_lower:
            hints.append('AVG')
        if 'maximum' in query_lower or 'max' in query_lower:
            hints.append('MAX')
        if 'minimum' in query_lower or 'min' in query_lower:
            hints.append('MIN')
        
        return hints


# Global instance
projection_advisor = ProjectionAdvisor()
