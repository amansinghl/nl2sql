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
                from ..loaders.graph_builder import schema_graph
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
        """Deprecated: previously suggested heuristic projections. Now returns existing columns unchanged.
        Column choice must be dictated by the LLM plan, not local heuristics.
        """
        existing_columns = existing_columns or {}
        suggestions = {}
        for table in tables:
            suggestions[table] = existing_columns.get(table, [])
        return suggestions


# Global instance
projection_advisor = ProjectionAdvisor()


