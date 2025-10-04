import json
import re
import networkx as nx
from typing import Dict, List, Optional, Set
from pathlib import Path
from ..utils.config import SCHEMA_GRAPH_PATH, settings

class SchemaGraph:
    def __init__(self, graph_path: str = SCHEMA_GRAPH_PATH):
        self.graph_path = Path(graph_path)
        self.graph_data = None
        self.nx_graph = None
        self.tables = {}
        self.relationships = []
        self._load_graph()
    
    def _load_graph(self):
        """Load the schema graph from JSON file"""
        try:
            if not self.graph_path.exists():
                # Schema graph file not found
                self._create_default_graph()
                return
            
            with open(self.graph_path, 'r') as f:
                self.graph_data = json.load(f)
            
            self.tables = self.graph_data.get('tables', {})
            self.relationships = self.graph_data.get('relationships', [])
            
            # Build NetworkX graph for path finding
            self._build_nx_graph()
            
            # Loaded schema graph
            
        except Exception as e:
            # Error loading schema graph
            self._create_default_graph()
    
    def _create_default_graph(self):
        """Create a default graph structure if file doesn't exist"""
        scoping_column = settings.security.SCOPING_COLUMN
        self.graph_data = {
            "tables": {
                "shipments": {
                    "columns": ["id", "status", "created_at", scoping_column, "order_id"],
                    "scoping_column": scoping_column,
                    "description": "Shipment tracking information"
                },
                "orders": {
                    "columns": ["id", "customer_id", "total", scoping_column, "created_at"],
                    "scoping_column": scoping_column,
                    "description": "Customer orders"
                },
                "customers": {
                    "columns": ["id", "name", "phone", scoping_column, "email"],
                    "scoping_column": scoping_column,
                    "description": "Customer information"
                }
            },
            "relationships": [
                {"from": "shipments", "to": "orders", "on": "order_id"},
                {"from": "orders", "to": "customers", "on": "customer_id"}
            ]
        }
        self.tables = self.graph_data['tables']
        self.relationships = self.graph_data['relationships']
        self._build_nx_graph()
        
        # Save the default graph
        self.graph_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.graph_path, 'w') as f:
            json.dump(self.graph_data, f, indent=2)
        
        # Created default schema graph
    
    def _build_nx_graph(self):
        """Build NetworkX graph for relationship analysis"""
        self.nx_graph = nx.DiGraph()
        
        # Add nodes (tables)
        for table_name in self.tables.keys():
            self.nx_graph.add_node(table_name)
        
        # Add edges (relationships)
        for rel in self.relationships:
            self.nx_graph.add_edge(rel['from'], rel['to'], key=rel['on'])
    
    def get_table_info(self, table_name: str) -> Optional[Dict]:
        """Get information about a specific table"""
        return self.tables.get(table_name)
    
    def get_related_tables(self, table_name: str) -> List[str]:
        """Get tables directly related to the given table"""
        if table_name not in self.nx_graph:
            return []
        
        related = []
        # Get predecessors (tables that reference this table)
        for pred in self.nx_graph.predecessors(table_name):
            related.append(pred)
        
        # Get successors (tables this table references)
        for succ in self.nx_graph.successors(table_name):
            related.append(succ)
        
        return list(set(related))
    
    def find_path_between_tables(self, table1: str, table2: str) -> Optional[List[str]]:
        """Find the shortest path between two tables"""
        try:
            path = nx.shortest_path(self.nx_graph, table1, table2)
            return path
        except nx.NetworkXNoPath:
            return None
    
    def get_join_path(self, tables: List[str]) -> List[Dict]:
        """Get the optimal join path for a set of tables"""
        if len(tables) <= 1:
            return []
        
        joins = []
        connected_tables = set([tables[0]])
        
        for table in tables[1:]:
            # Find the best path to connect this table
            best_path = None
            best_source = None
            
            for connected_table in connected_tables:
                path = self.find_path_between_tables(connected_table, table)
                if path and (best_path is None or len(path) < len(best_path)):
                    best_path = path
                    best_source = connected_table
            
            if best_path:
                # Create joins for the path
                for i in range(len(best_path) - 1):
                    from_table = best_path[i]
                    to_table = best_path[i + 1]
                    
                    # Find the relationship
                    for rel in self.relationships:
                        if rel['from'] == from_table and rel['to'] == to_table:
                            joins.append({
                                'from_table': from_table,
                                'to_table': to_table,
                                'join_column': rel['on'],
                                'to_column': rel.get('to_column', 'id')
                            })
                            break
                
                connected_tables.add(table)
        
        return joins
    
    def get_schema_description(self) -> str:
        """Generate a human-readable description of the schema"""
        description = "Database Schema:\n\n"
        scoping_column = settings.security.SCOPING_COLUMN
        description += f"CRITICAL: For entity-scoped tables, use the specific scoping column shown for each table (e.g., {scoping_column}, etc.)\n"
        description += f"DO NOT use generic 'accounts_entity_id' - check each table's scoping column!\n\n"
        
        for table_name, table_info in self.tables.items():
            description += f"Table: {table_name}\n"
            if 'description' in table_info:
                description += f"Description: {table_info['description']}\n"
            description += f"Columns: {', '.join(table_info['columns'])}\n"
            description += f"Entity-scoped: {table_info.get('scoped', False)}\n"
            if table_info.get('scoped', False):
                scoping_column = table_info.get('scoping_column', settings.security.SCOPING_COLUMN)
                description += f"IMPORTANT: This table is entity-scoped. Use '{scoping_column} = <scoping_value>' in WHERE clause\n"
            description += "\n"
        
        description += "Relationships:\n"
        for rel in self.relationships:
            to_column = rel.get('to_column', 'id')
            description += f"- {rel['from']}.{rel['on']} -> {rel['to']}.{to_column}\n"
        
        # Add code mappings if they exist
        if 'code_mappings' in self.graph_data:
            description += "\nCode Mappings (use these values directly in WHERE clauses):\n"
            for field_path, mapping in self.graph_data['code_mappings'].items():
                description += f"\n{field_path}:\n"
                description += f"Description: {mapping.get('description', 'N/A')}\n"
                description += "Values:\n"
                for code, label in mapping.get('values', {}).items():
                    description += f"  {code}: {label}\n"
        
        return description
    
    def get_tables_for_query(self, query_keywords: List[str]) -> List[str]:
        """Determine which tables are likely needed for a query based on keywords"""
        relevant_tables = []
        
        # Use keyword mappings from schema configuration
        keyword_mappings = self.graph_data.get('keyword_mappings', {})
        
        for keyword in query_keywords:
            keyword_lower = keyword.lower()
            for k, tables in keyword_mappings.items():
                if k in keyword_lower:
                    for table in tables:
                        if table not in relevant_tables and table in self.tables:
                            relevant_tables.append(table)
        
        return relevant_tables
    
    def get_keyword_mappings(self) -> Dict[str, List[str]]:
        """Get keyword mappings from schema configuration"""
        return self.graph_data.get('keyword_mappings', {})
    
    def get_enhanced_tables_for_query(self, user_query: str) -> List[str]:
        """Enhanced table selection using multiple methods"""
        query_lower = user_query.lower()
        matched_tables = set()
        
        # Get keyword mappings
        keyword_mappings = self.get_keyword_mappings()
        
        # Direct keyword matching
        for keyword, tables in keyword_mappings.items():
            if keyword in query_lower:
                matched_tables.update(tables)
        
        # Partial keyword matching (for plurals, variations)
        query_words = re.findall(r'\b\w+\b', query_lower)
        for word in query_words:
            for keyword, tables in keyword_mappings.items():
                if (keyword in word or word in keyword) and len(word) > 3:
                    matched_tables.update(tables)
        
        # Table name matching
        for table_name in self.tables.keys():
            if table_name in query_lower:
                matched_tables.add(table_name)
        
        # Filter to only existing tables
        return [table for table in matched_tables if table in self.tables]
    
    def get_code_mapping(self, field_path: str) -> Optional[Dict]:
        """Get code mapping for a specific field (e.g., 'shipments.tracking_status')"""
        if 'code_mappings' not in self.graph_data:
            return None
        return self.graph_data['code_mappings'].get(field_path)
    
    def get_code_value(self, field_path: str, label: str) -> Optional[str]:
        """Get the code value for a given label (e.g., 'Delivered' -> '1900')"""
        mapping = self.get_code_mapping(field_path)
        if not mapping:
            return None
        
        # Search for the label (case-insensitive)
        for code, mapped_label in mapping.get('values', {}).items():
            if mapped_label.lower() == label.lower():
                return code
        return None

# Global instance
schema_graph = SchemaGraph()


