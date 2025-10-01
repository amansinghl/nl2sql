import re
import json
import hashlib
from typing import List, Dict, Set, Optional, Tuple, Any
from dataclasses import dataclass
from pathlib import Path
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import asyncio
from functools import lru_cache

from .graph_builder import schema_graph
from .llm_handler import LLMHandler
from .query_validator import QueryValidator
from .error_codes import create_validation_error, ErrorCodes
from .user_context import UserContext, permission_manager
from .loggery import access_logger, query_logger
from .config import settings
from .schema_index import schema_index
from .plan_validator import plan_validator
from .projection_advisor import projection_advisor

@dataclass
class TableScore:
    """Represents a table with its relevance score"""
    table_name: str
    score: float
    reason: str

@dataclass
class QueryContext:
    """Context information for query processing"""
    query: str
    entity_id: str
    relevant_tables: List[str]
    schema_context: str
    complexity_score: float
    requires_code_mappings: bool
    requires_relationships: bool

class SchemaCache:
    """Cache for schema descriptions and embeddings"""
    
    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self.schema_descriptions = {}
        self.table_embeddings = {}
        self.vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
        self._fitted = False
        # Example RAG store
        self.example_vectorizer: Optional[TfidfVectorizer] = None
        self.example_embeddings: List[Tuple[str, int, np.ndarray]] = []  # (table_name, example_index, embedding)
        self.examples_loaded: bool = False
    
    def _get_cache_key(self, table_names: List[str], query_context: str = "") -> str:
        """Generate cache key for table combination"""
        key_data = sorted(table_names) + [query_context]
        return hashlib.md5(str(key_data).encode()).hexdigest()
    
    def get_cached_schema_description(self, table_names: List[str], query_context: str = "") -> Optional[str]:
        """Get cached schema description"""
        key = self._get_cache_key(table_names, query_context)
        return self.schema_descriptions.get(key)
    
    def cache_schema_description(self, table_names: List[str], description: str, query_context: str = ""):
        """Cache schema description"""
        if len(self.schema_descriptions) >= self.max_size:
            # Remove oldest entry
            oldest_key = next(iter(self.schema_descriptions))
            del self.schema_descriptions[oldest_key]
        
        key = self._get_cache_key(table_names, query_context)
        self.schema_descriptions[key] = description
    
    def get_table_embedding(self, table_name: str) -> Optional[np.ndarray]:
        """Get cached table embedding"""
        return self.table_embeddings.get(table_name)
    
    def cache_table_embedding(self, table_name: str, embedding: np.ndarray):
        """Cache table embedding"""
        self.table_embeddings[table_name] = embedding
    
    def fit_vectorizer(self, table_descriptions: List[str]):
        """Fit the TF-IDF vectorizer"""
        if not self._fitted:
            self.vectorizer.fit(table_descriptions)
            self._fitted = True
    
    def transform_text(self, text: str) -> np.ndarray:
        """Transform text to embedding"""
        if not self._fitted:
            raise ValueError("Vectorizer not fitted yet")
        return self.vectorizer.transform([text]).toarray()[0]

    def fit_example_vectorizer(self, example_texts: List[str]):
        """Fit a dedicated TF-IDF vectorizer for examples"""
        self.example_vectorizer = TfidfVectorizer(max_features=2000, stop_words='english')
        self.example_vectorizer.fit(example_texts)
        self.examples_loaded = True

    def transform_example_text(self, text: str) -> np.ndarray:
        if not self.example_vectorizer:
            raise ValueError("Example vectorizer not fitted yet")
        return self.example_vectorizer.transform([text]).toarray()[0]

class IntelligentSQLGenerator:
    """Intelligent SQL generator with multi-stage approach for accuracy and cost optimization"""
    
    def __init__(self, llm_handler: LLMHandler, validator: QueryValidator):
        self.llm_handler = llm_handler
        self.validator = validator
        self.schema_graph = schema_graph
        self.cache = SchemaCache()
        
        # Configuration
        self.MAX_TABLES_PER_QUERY = 10
        self.MAX_SCHEMA_TOKENS = 8000
        self.MAX_VALIDATION_ATTEMPTS = 3
        self.SEMANTIC_SIMILARITY_THRESHOLD = 0.3
        
        # Initialize keyword mappings (may be absent)
        self.keyword_mappings = self.schema_graph.graph_data.get('keyword_mappings', {})
        # Initialize code mappings from schema
        self.code_mappings: Dict[str, Dict[str, Any]] = self.schema_graph.graph_data.get('code_mappings', {})
        
        # Query templates are now generated dynamically based on user role
        
        # Initialize embeddings
        self._initialize_embeddings()
        self._initialize_example_embeddings()
    
    
    # Removed column alias/join mapping helpers - deprecated with new schema
    
    def _initialize_embeddings(self):
        """Initialize table embeddings for semantic similarity"""
        table_descriptions = []
        table_names = []
        
        for table_name, table_info in self.schema_graph.tables.items():
            description = table_info.get('description', '')
            columns_text = ' '.join(table_info.get('columns', []))
            full_text = f"{table_name} {description} {columns_text}"
            table_descriptions.append(full_text)
            table_names.append(table_name)
        
        # Fit vectorizer and cache embeddings
        self.cache.fit_vectorizer(table_descriptions)
        for table_name, description in zip(table_names, table_descriptions):
            embedding = self.cache.transform_text(description)
            self.cache.cache_table_embedding(table_name, embedding)

    def _initialize_example_embeddings(self):
        """Initialize example embeddings for RAG from schema examples"""
        example_records: List[Tuple[str, Dict[str, str]]] = []
        example_texts: List[str] = []
        for table_name, table_info in self.schema_graph.tables.items():
            for idx, ex in enumerate(table_info.get('examples', []) or []):
                q = ex.get('query', '') or ''
                s = ex.get('sql', '') or ''
                combined = f"{q}\n{s}"
                example_records.append((table_name, ex))
                example_texts.append(combined)
        if not example_texts:
            return
        self.cache.fit_example_vectorizer(example_texts)
        # Store embeddings aligned with example_records order
        self._examples_index: List[Tuple[str, Dict[str, str]]] = example_records
        self.cache.example_embeddings = []
        for idx, text in enumerate(example_texts):
            emb = self.cache.transform_example_text(text)
            table_name = example_records[idx][0]
            self.cache.example_embeddings.append((table_name, idx, emb))
    
    async def generate_accurate_sql(self, user_query: str, scoping_value: str, user_context: UserContext = None) -> Dict[str, Any]:
        """Main entry point for intelligent SQL generation with user context support"""
        try:
            # Validate user access if context is provided
            if user_context:
                access_validation = permission_manager.validate_query_access(user_context)
                if not access_validation['allowed']:
                    return {
                        "success": False,
                        "error": access_validation['error'],
                        "error_code": access_validation.get('error_code'),
                        "sql": "",
                        "tables_used": [],
                        "attempts": 0
                    }
            
            # Removed legacy template fast-path to avoid incorrect intent matches
            
            # Stage 1: Smart Table Selection
            relevant_tables = await self._intelligent_table_selection(user_query)
            
            # Stage 2: Schema Context Optimization + RAG examples
            query_context = self._analyze_query_context(user_query, relevant_tables)
            contextual_examples = self._retrieve_contextual_examples(user_query, relevant_tables, top_k=8, threshold=0.2)
            schema_context = self._build_rag_optimized_schema_context(relevant_tables, query_context, user_context, contextual_examples)
            
            # Stage 3: SQL Generation with Validation Loop
            sql_result = await self._generate_with_validation_loop(
                user_query, scoping_value, relevant_tables, schema_context, query_context, user_context
            )
            
            # Log access if user context is provided
            if user_context and sql_result.get('success', False):
                access_logger.log_query_access(
                    user_context, 
                    user_query, 
                    sql_result.get('tables_used', []),
                    success=True
                )
            # Query event logging (success or failure)
            try:
                query_logger.log_event(
                    user_context,
                    user_query,
                    self.llm_handler.provider_name,
                    relevant_tables,
                    schema_tokens=len(schema_context.split()) if schema_context else 0,
                    attempts=sql_result.get('attempts', 0),
                    success=bool(sql_result.get('success', False)),
                    sql=sql_result.get('sql', ''),
                    error=sql_result.get('error')
                )
            except Exception:
                pass
            
            return sql_result
            
        except Exception as e:
            # Log error if user context is provided
            if user_context:
                access_logger.log_query_access(
                    user_context, 
                    user_query, 
                    success=False,
                    error_message=str(e)
                )
            # Query event logging (failure)
            try:
                query_logger.log_event(
                    user_context,
                    user_query,
                    self.llm_handler.provider_name,
                    [],
                    schema_tokens=0,
                    attempts=0,
                    success=False,
                    sql='',
                    error=str(e)
                )
            except Exception:
                pass
            
            return {
                "success": False,
                "error": f"SQL generation failed: {str(e)}",
                "sql": "",
                "tables_used": [],
                "attempts": 0
            }
    
    # Phase 1: Enhanced Keyword Matching
    async def _intelligent_table_selection(self, user_query: str) -> List[str]:
        """Schema-driven table selection with robust fallbacks"""
        
        # Use the new schema index for table retrieval
        table_scores = schema_index.search_tables(user_query, top_k=self.MAX_TABLES_PER_QUERY)
        
        if table_scores:
            # Return tables ordered by relevance score
            return [table for table, score in table_scores]
        
        # Fallback: use centrality-based selection
        fallback_tables = []
        for table_name in self.schema_graph.tables.keys():
            priority = schema_index.get_table_priority(table_name)
            fallback_tables.append((table_name, priority))
        
        # Sort by priority and return top tables
        fallback_tables.sort(key=lambda x: x[1], reverse=True)
        return [table for table, priority in fallback_tables[:self.MAX_TABLES_PER_QUERY]]
    
    def _enhanced_keyword_matching(self, user_query: str) -> List[str]:
        """Enhanced keyword matching using schema-based mappings with simplified logic"""
        query_lower = user_query.lower()
        matched_tables = set()
        
        # 1. Direct keyword matching (highest priority)
        for keyword, tables in self.keyword_mappings.items():
            if keyword in query_lower:
                matched_tables.update(tables)
        
        # 2. Table name matching (high priority)
        for table_name in self.schema_graph.tables.keys():
            if table_name in query_lower:
                matched_tables.add(table_name)
        
        # 3. Partial keyword matching (lower priority, only for longer words)
        query_words = re.findall(r'\b\w+\b', query_lower)
        for word in query_words:
            if len(word) > 4:  # Only match words longer than 4 characters
                for keyword, tables in self.keyword_mappings.items():
                    if (keyword in word or word in keyword):
                        matched_tables.update(tables)
        
        # Apply simplified priority logic
        prioritized_tables = self._apply_simplified_priority(list(matched_tables), user_query)
        
        return prioritized_tables
    
    async def _semantic_table_selection(self, user_query: str, top_k: int = 8) -> List[str]:
        """Semantic similarity-based table selection with priority logic"""
        try:
            query_embedding = self.cache.transform_text(user_query)
            table_scores = []
            
            for table_name in self.schema_graph.tables.keys():
                table_embedding = self.cache.get_table_embedding(table_name)
                if table_embedding is not None:
                    similarity = cosine_similarity([query_embedding], [table_embedding])[0][0]
                    if similarity > self.SEMANTIC_SIMILARITY_THRESHOLD:
                        table_scores.append((table_name, similarity))
            
            # Apply priority logic to semantic results
            if table_scores:
                table_names = [table for table, score in table_scores]
                prioritized_tables = self._apply_table_priority(table_names, user_query)
                return prioritized_tables[:top_k]
            else:
                # Fallback to keyword matching if no semantic matches
                return self._enhanced_keyword_matching(user_query)
            
        except Exception as e:
            # Fallback to keyword matching if semantic matching fails
            return self._enhanced_keyword_matching(user_query)
    
    def _expand_by_relationships(self, seed_tables: List[str], max_depth: int = 1) -> List[str]:
        """Expand table list based on foreign key relationships"""
        related_tables = set(seed_tables)
        
        for depth in range(max_depth):
            current_tables = list(related_tables)
            for table in current_tables:
                # Find tables that reference this table or are referenced by this table
                for rel in self.schema_graph.relationships:
                    if rel['from'] == table and rel['to'] not in related_tables:
                        related_tables.add(rel['to'])
                    elif rel['to'] == table and rel['from'] not in related_tables:
                        related_tables.add(rel['from'])
        
        return list(related_tables - set(seed_tables))
    
    def _apply_simplified_priority(self, tables: List[str], user_query: str) -> List[str]:
        """Apply simplified priority logic to prefer core tables over relationship tables"""
        if not tables:
            return tables
        
        # Core tables (highest priority)
        core_tables = {'users', 'entities', 'shipments', 'orders', 'locations', 'transactions', 'invoices'}
        
        # Relationship/mapping tables (lower priority)
        relationship_tables = {
            'user_partner_preferences', 'entity_user_mappings', 'supplier_preferences', 
            'advanced_partner_preference_settings', 'tracking_status_mappings'
        }
        
        # Lookup/master tables (lowest priority)
        lookup_tables = {
            'tracking_statuses', 'vamaship_tracking_codes_master', 'partner_tracking_codes'
        }
        
        # Categorize and prioritize
        core_matches = [t for t in tables if t in core_tables]
        relationship_matches = [t for t in tables if t in relationship_tables]
        lookup_matches = [t for t in tables if t in lookup_tables]
        other_matches = [t for t in tables if t not in core_tables and t not in relationship_tables and t not in lookup_tables]
        
        # For simple queries, prefer core tables and avoid relationship tables
        if self._is_simple_query(user_query):
            return core_matches + other_matches + relationship_matches + lookup_matches
        else:
            # For complex queries, include all but still prioritize core tables
            return core_matches + other_matches + relationship_matches + lookup_matches

    def _apply_table_priority(self, tables: List[str], user_query: str) -> List[str]:
        """Apply priority logic to prefer simpler, more direct tables (legacy method)"""
        return self._apply_simplified_priority(tables, user_query)
    
    def _is_direct_table_match(self, table_name: str, query_lower: str, table_info: Dict) -> bool:
        """Check if table directly matches the query intent"""
        # Check for direct table name mentions
        if table_name in query_lower:
            return True
        
        # Check for core entity queries
        if 'customer' in query_lower and table_name == 'users':
            return True
        if 'user' in query_lower and table_name == 'users':
            return True
        if 'entity' in query_lower and table_name == 'entities':
            return True
        
        # Check table description for relevance
        description = table_info.get('description', '').lower()
        query_words = set(re.findall(r'\b\w+\b', query_lower))
        description_words = set(re.findall(r'\b\w+\b', description))
        
        # If query words overlap significantly with description
        overlap = len(query_words.intersection(description_words))
        return overlap >= 2
    
    def _calculate_column_relevance(self, table_name: str, query_lower: str, table_info: Dict) -> int:
        """Calculate how relevant the table's columns are to the query"""
        columns = table_info.get('columns', [])
        query_words = set(re.findall(r'\b\w+\b', query_lower))
        
        relevance_score = 0
        
        # Check for direct column matches
        for column in columns:
            if column.lower() in query_lower:
                relevance_score += 10
        
        # Check for common query patterns
        if 'count' in query_lower and 'id' in columns:
            relevance_score += 15
        if 'active' in query_lower and any('active' in col.lower() for col in columns):
            relevance_score += 20
        if 'distinct' in query_lower and 'id' in columns:
            relevance_score += 10
        
        return relevance_score
    
    def _is_relationship_table(self, table_name: str) -> bool:
        """Check if table is a relationship/mapping table"""
        relationship_indicators = [
            'mapping', 'preference', 'setting', 'tracking_code', 'status_mapping'
        ]
        return any(indicator in table_name.lower() for indicator in relationship_indicators)
    
    def _is_simple_query(self, user_query: str) -> bool:
        """Check if query is simple and doesn't need complex relationships"""
        query_lower = user_query.lower()
        
        # Simple query indicators
        simple_patterns = [
            'count', 'how many', 'number of', 'total', 'active', 'distinct'
        ]
        
        # Complex query indicators
        complex_patterns = [
            'join', 'with', 'related', 'between', 'across', 'multiple tables',
            'relationship', 'mapping', 'preference'
        ]
        
        has_simple = any(pattern in query_lower for pattern in simple_patterns)
        has_complex = any(pattern in query_lower for pattern in complex_patterns)
        
        return has_simple and not has_complex
    
    def _is_complex_query(self, user_query: str) -> bool:
        """Determine if query is complex and needs more context"""
        complex_indicators = [
            'join', 'multiple', 'compare', 'between', 'across', 'all', 'every',
            'aggregate', 'sum', 'count', 'average', 'group by', 'having',
            'subquery', 'nested', 'complex', 'detailed', 'comprehensive'
        ]
        
        query_lower = user_query.lower()
        return any(indicator in query_lower for indicator in complex_indicators)
    
    def _expand_for_complexity(self, candidate_tables: List[str]) -> List[str]:
        """Add more context tables for complex queries"""
        # Add core business tables
        core_tables = ['shipments', 'orders', 'customers', 'entities', 'locations']
        expanded_tables = list(set(candidate_tables + core_tables))
        
        # Add relationship tables
        expanded_tables.extend(self._expand_by_relationships(expanded_tables, max_depth=2))
        
        return list(dict.fromkeys(expanded_tables))[:self.MAX_TABLES_PER_QUERY]
    
    # Phase 2: Schema Context Optimization
    def _analyze_query_context(self, user_query: str, relevant_tables: List[str]) -> QueryContext:
        """Analyze query to determine context requirements"""
        query_lower = user_query.lower()
        
        # Check if query needs code mappings
        status_indicators = ['status', 'delivered', 'pending', 'cancelled', 'tracking', 'code']
        requires_code_mappings = any(indicator in query_lower for indicator in status_indicators)
        
        # Check if query needs relationships
        relationship_indicators = ['join', 'with', 'related', 'associated', 'linked', 'between']
        requires_relationships = any(indicator in query_lower for indicator in relationship_indicators)
        
        # Calculate complexity score
        complexity_score = self._calculate_complexity_score(user_query)
        
        return QueryContext(
            query=user_query,
            entity_id="",  # Will be set later
            relevant_tables=relevant_tables,
            schema_context="",  # Will be set later
            complexity_score=complexity_score,
            requires_code_mappings=requires_code_mappings,
            requires_relationships=requires_relationships
        )
    
    def _calculate_complexity_score(self, user_query: str) -> float:
        """Calculate query complexity score (0-1)"""
        query_lower = user_query.lower()
        
        # Count complexity indicators
        complexity_indicators = [
            'join', 'where', 'group by', 'having', 'order by', 'limit',
            'sum', 'count', 'avg', 'max', 'min', 'distinct',
            'and', 'or', 'not', 'between', 'in', 'like', 'exists'
        ]
        
        indicator_count = sum(1 for indicator in complexity_indicators if indicator in query_lower)
        return min(indicator_count / 10.0, 1.0)  # Normalize to 0-1
    
    def _build_optimized_schema_context(self, relevant_tables: List[str], query_context: QueryContext, user_context: UserContext = None) -> str:
        """Build context-optimized schema description"""
        
        # Check cache first
        cached_schema = self.cache.get_cached_schema_description(
            relevant_tables, query_context.query
        )
        if cached_schema:
            return cached_schema
        
        # Core tables (always include)
        core_tables = self._identify_core_tables(relevant_tables)
        
        # Relationship tables (include based on query context)
        if query_context.requires_relationships:
            relationship_tables = self._get_relationship_context(relevant_tables, query_context.query)
            core_tables.extend(relationship_tables)
        
        # Code mapping tables (include if query mentions status/codes)
        if query_context.requires_code_mappings:
            code_tables = self._get_code_mapping_context(query_context.query)
            core_tables.extend(code_tables)
        
        # Remove duplicates and ensure all tables exist
        all_tables = list(dict.fromkeys(core_tables))
        existing_tables = [t for t in all_tables if t in self.schema_graph.tables]
        
        # Build focused schema description
        schema_desc = self._build_focused_schema_description(existing_tables, query_context, user_context)
        
        # Cache the result
        self.cache.cache_schema_description(existing_tables, schema_desc, query_context.query)
        
        return schema_desc
    
    def _identify_core_tables(self, relevant_tables: List[str]) -> List[str]:
        """Identify core tables that should always be included"""
        core_tables = []
        
        # Always include entity-scoped tables if they're in relevant_tables
        for table in relevant_tables:
            if table in self.schema_graph.tables:
                table_info = self.schema_graph.tables[table]
                if table_info.get('scoped', False):
                    core_tables.append(table)
        
        # Add non-scoped tables that are directly relevant
        for table in relevant_tables:
            if table in self.schema_graph.tables:
                table_info = self.schema_graph.tables[table]
                if not table_info.get('scoped', False):
                    core_tables.append(table)
        
        return core_tables
    
    def _get_relationship_context(self, relevant_tables: List[str], user_query: str) -> List[str]:
        """Get additional tables based on relationships"""
        relationship_tables = []
        
        for table in relevant_tables:
            if table in self.schema_graph.tables:
                # Find tables that have relationships with this table
                for rel in self.schema_graph.relationships:
                    if rel['from'] == table and rel['to'] not in relevant_tables:
                        relationship_tables.append(rel['to'])
                    elif rel['to'] == table and rel['from'] not in relevant_tables:
                        relationship_tables.append(rel['from'])
        
        return relationship_tables
    
    def _get_code_mapping_context(self, user_query: str) -> List[str]:
        """Get tables needed for code mappings"""
        code_tables = []
        
        # Add code mapping tables if they exist
        if 'code_mappings' in self.schema_graph.graph_data:
            code_tables.extend([
                'tracking_statuses',
                'tracking_status_mappings', 
                'vamaship_tracking_codes_master',
                'partner_tracking_codes'
            ])
        
        return [t for t in code_tables if t in self.schema_graph.tables]
    
    def _build_focused_schema_description(self, tables: List[str], query_context: QueryContext, user_context: UserContext = None) -> str:
        """Build focused schema description for specific tables with streamlined information"""
        description = "Database Schema:\n\n"
        
        # Add scoping instructions if required
        if user_context:
            from .user_context import permission_manager
            scoping_requirements = permission_manager.get_scoping_requirements(user_context)
            scoping_required = scoping_requirements.get('scoping_required', True)
            
            if scoping_required:
                scoping_column = settings.security.SCOPING_COLUMN
                description += f"IMPORTANT: Use '{scoping_column} = <scoping_value>' for entity-scoped tables\n\n"
            else:
                description += "NOTE: You have full access to all data. No scoping filters are required.\n\n"
        
        # Add key code mappings (labels -> codes) if relevant
        if query_context.requires_code_mappings and self.code_mappings:
            # Example: invert vamaship_tracking_codes_master.new_code mapping
            tracking_map = self.code_mappings.get('vamaship_tracking_codes_master.new_code', {})
            values = (tracking_map or {}).get('values', {})
            if values:
                # Build label->code for a few common statuses
                description += "Key Status Codes (label -> code):\n"
                # Prefer common statuses
                preferred = ['Delivered', 'Shipment Out for Delivery', 'Shipment In-Transit', 'Received at Destination Hub']
                printed = 0
                # Invert mapping
                label_to_code = {label: code for code, label in values.items()}
                for label in preferred:
                    if label in label_to_code and printed < 6:
                        description += f"- {label} -> {label_to_code[label]}\n"
                        printed += 1
                # If not enough printed, fill first few
                if printed < 4:
                    for code, label in list(values.items())[: 6 - printed]:
                        description += f"- {label} -> {code}\n"
                description += "\n"
        
        # Streamlined table descriptions
        q_lower = query_context.query.lower() if query_context and query_context.query else ""
        for table_name in tables:
            if table_name not in self.schema_graph.tables:
                continue
                
            table_info = self.schema_graph.tables[table_name]
            description += f"Table: {table_name}\n"
            # Provide full column list for each table so the LLM can choose accurately
            selected_columns = table_info.get('columns', [])
            description += f"Columns: {', '.join(selected_columns)}\n"
            
            if table_info.get('scoped', False):
                scoping_column = table_info.get('scoping_column', settings.security.SCOPING_COLUMN)
                # Only show scoped line when it matches entity scoping column
                if scoping_column == settings.security.SCOPING_COLUMN:
                    description += f"Scoped: {scoping_column}\n"
            description += "\n"
        
        # Essential relationships only
        description += "Key Relationships:\n"
        for rel in self.schema_graph.relationships:
            if rel['from'] in tables or rel['to'] in tables:
                # Prefer explicit to_column; otherwise, if the target table has the same column name as 'on', use that; else fallback to id
                explicit_to_col = rel.get('to_column')
                if explicit_to_col:
                    to_column = explicit_to_col
                else:
                    target_table = self.schema_graph.tables.get(rel['to'], {})
                    target_columns = set(target_table.get('columns', []))
                    to_column = rel['on'] if rel['on'] in target_columns else 'id'
                description += f"{rel['from']}.{rel['on']} -> {rel['to']}.{to_column}\n"
        
        return description

    def _retrieve_contextual_examples(self, user_query: str, tables: List[str], top_k: int = 8, threshold: float = 0.2) -> List[Dict[str, str]]:
        """Retrieve top-K example Q/SQL pairs relevant to the query and tables"""
        if not getattr(self.cache, 'examples_loaded', False):
            return []
        try:
            q_emb = self.cache.transform_example_text(user_query)
            candidates: List[Tuple[float, Dict[str, str]]] = []
            tables_set = set(tables or [])
            for table_name, idx, emb in self.cache.example_embeddings:
                if tables_set and table_name not in tables_set:
                    continue
                sim = float(cosine_similarity([q_emb], [emb])[0][0])
                if sim >= threshold:
                    ex = self._examples_index[idx][1]
                    candidates.append((sim, {"table": table_name, "query": ex.get('query', ''), "sql": ex.get('sql', '')}))
            # sort by similarity desc
            candidates.sort(key=lambda x: x[0], reverse=True)
            return [ex for _, ex in candidates[:top_k]]
        except Exception:
            return []

    def _build_rag_optimized_schema_context(self, relevant_tables: List[str], query_context: QueryContext, user_context: UserContext, examples: List[Dict[str, str]]) -> str:
        """Build schema context and append RAG examples section"""
        base = self._build_optimized_schema_context(relevant_tables, query_context, user_context)
        if not examples:
            return base
        # Append examples in a compact format
        base += "\nRelevant Examples (use as patterns, adapt columns/filters precisely):\n"
        for ex in examples:
            q = (ex.get('query') or '').strip()
            s = (ex.get('sql') or '').strip().rstrip(';')
            tbl = ex.get('table', '')
            if q and s:
                base += f"[Table: {tbl}] Q: {q}\nSQL: {s};\n"
        base += "\n"
        return base
    
    def _get_relevant_columns_for_query(self, table_name: str, query_lower: str, columns: List[str]) -> List[str]:
        """Get columns most relevant to the specific query"""
        relevant_columns = []
        
        # Check for common query patterns
        if 'count' in query_lower or 'how many' in query_lower:
            id_columns = [col for col in columns if 'id' in col.lower()]
            relevant_columns.extend(id_columns[:2])  # Limit to 2 most relevant
        
        if 'revenue' in query_lower or 'amount' in query_lower or 'price' in query_lower:
            price_columns = [col for col in columns if any(term in col.lower() for term in ['price', 'amount', 'cost', 'value'])]
            relevant_columns.extend(price_columns[:3])
        
        if 'date' in query_lower or 'day' in query_lower or 'week' in query_lower:
            date_columns = [col for col in columns if any(term in col.lower() for term in ['date', 'created', 'updated'])]
            relevant_columns.extend(date_columns[:2])
        
        if 'status' in query_lower or 'delivered' in query_lower:
            status_columns = [col for col in columns if any(term in col.lower() for term in ['status', 'tracking'])]
            relevant_columns.extend(status_columns)
        
        if 'name' in query_lower or 'customer' in query_lower or 'user' in query_lower:
            name_columns = [col for col in columns if any(term in col.lower() for term in ['name', 'first', 'last', 'entity'])]
            relevant_columns.extend(name_columns[:2])
        
        return list(set(relevant_columns))  # Remove duplicates
    
    # (Removed legacy _check_query_templates implementation)
    
    def _extract_tables_from_sql(self, sql: str) -> List[str]:
        """Extract table names from SQL query"""
        tables = []
        sql_lower = sql.lower()
        
        # Simple extraction of table names after FROM and JOIN
        for table_name in self.schema_graph.tables.keys():
            if f'from {table_name}' in sql_lower or f'join {table_name}' in sql_lower:
                tables.append(table_name)
        
        return tables
    
    def _fix_count_query(self, sql: str, user_query: str) -> str:
        """Fix SQL that should be a count query but isn't"""
        import re
        
        # Extract the main table from FROM clause
        from_match = re.search(r'FROM\s+(\w+)', sql, re.IGNORECASE)
        if not from_match:
            return sql
        
        main_table = from_match.group(1)
        
        # Extract WHERE clause
        where_match = re.search(r'WHERE\s+(.+?)(?:\s+ORDER\s+BY|\s+LIMIT|$)', sql, re.IGNORECASE | re.DOTALL)
        where_clause = where_match.group(1).strip() if where_match else ""
        
        # Build new COUNT query
        new_sql = f"SELECT COUNT(*) FROM {main_table}"
        if where_clause:
            new_sql += f" WHERE {where_clause}"
        
        return new_sql
    
    def _validate_columns_against_schema(self, sql: str, tables: List[str]) -> List[str]:
        """Validate that all columns used in SQL actually exist in the schema"""
        issues = []
        sql_lower = sql.lower()
        
        # Extract column names from SQL (simplified approach)
        # Look for column names in SELECT, WHERE, GROUP BY, ORDER BY clauses
        import re
        
        # Find all potential column references
        column_patterns = [
            r'select\s+([^from]+?)\s+from',  # SELECT clause
            r'where\s+([^group|order|limit]+?)(?:\s+group|\s+order|\s+limit|$)',  # WHERE clause
            r'group\s+by\s+([^order|limit]+?)(?:\s+order|\s+limit|$)',  # GROUP BY clause
            r'order\s+by\s+([^limit]+?)(?:\s+limit|$)',  # ORDER BY clause
        ]
        
        raw_columns = set()
        for pattern in column_patterns:
            matches = re.findall(pattern, sql_lower, re.IGNORECASE | re.DOTALL)
            for match in matches:
                # Split by comma and clean up
                columns = [col.strip().split()[0] for col in match.split(',') if col.strip()]
                raw_columns.update(columns)
        
        # Remove common SQL keywords and normalize/clean tokens
        sql_keywords = {'count', 'sum', 'avg', 'max', 'min', 'distinct', 'case', 'when', 'then', 'else', 'end', 'as', 'and', 'or', 'not', 'in', 'like', 'between', 'is', 'null', 'desc', 'asc'}
        cleaned_columns: Set[str] = set()
        for token in raw_columns:
            if not token or token in sql_keywords or token.isdigit():
                continue
            # ignore star and table.*
            if token == '*' or token.endswith('.*'):
                continue
            # ignore function calls like count(*), sum(x)
            if '(' in token or ')' in token:
                continue
            # strip quotes/backticks
            t = token.strip('`"')
            # if qualified alias.tbl or db.tbl.col -> keep last segment
            if '.' in t:
                parts = t.split('.')
                t = parts[-1]
                if t == '*':
                    # was table.*
                    continue
            t = t.strip()
            if not t or t in sql_keywords:
                continue
            cleaned_columns.add(t)
        
        # Build a union of available columns across used tables
        available_columns: Set[str] = set()
        sample_table_for_msg = None
        sample_cols_for_msg: List[str] = []
        
        for table in tables:
            if table not in self.schema_graph.tables:
                continue
            table_columns = self.schema_graph.tables[table].get('columns', [])
            if sample_table_for_msg is None:
                sample_table_for_msg = table
                sample_cols_for_msg = table_columns[:5]
            available_columns.update(col.lower() for col in table_columns)
        
        for column in cleaned_columns:
            if column not in available_columns:
                if sample_table_for_msg:
                    issues.append(f"❌ Column '{column}' doesn't exist in relevant tables. Example '{sample_table_for_msg}' columns: {', '.join(sample_cols_for_msg)}")
                else:
                    issues.append(f"❌ Column '{column}' doesn't exist in relevant tables.")
        
        
        return issues
    
    # Phase 3: Validation Loop with Iterative Refinement
    async def _generate_with_validation_loop(self, user_query: str, scoping_value: str, 
                                           relevant_tables: List[str], schema_context: str, 
                                           query_context: QueryContext, user_context: UserContext = None) -> Dict[str, Any]:
        """Generate SQL with validation and iterative refinement"""
        
        attempt = 0
        current_schema_context = schema_context
        current_tables = relevant_tables.copy()
        
        while attempt < self.MAX_VALIDATION_ATTEMPTS:
            try:
                # Generate SQL
                sql = await self.llm_handler.generate_sql(
                    user_query, scoping_value, current_tables, current_schema_context
                )
                
                # Intent handling without heuristic projection rewrites
                from .projection_advisor import projection_advisor
                intents = projection_advisor.analyze_intent(user_query)
                sql_stripped_upper = sql.strip().upper()
                if intents.get('is_count', False):
                    if not sql_stripped_upper.startswith('SELECT COUNT('):
                        sql = self._fix_count_query(sql, user_query)
                else:
                    if sql_stripped_upper.startswith('SELECT COUNT('):
                        # Treat incorrect COUNT as a planning/generation error; trigger refinement
                        validation_result = {
                            "valid": False,
                            "error": "LLM returned COUNT but details were requested. Regenerate with detailed projection.",
                            "modified_sql": sql,
                            "tables": current_tables
                        }
                        # Refinement path
                        attempt += 1
                        if attempt < self.MAX_VALIDATION_ATTEMPTS:
                            refinement_result = self._refine_schema_context(
                                current_schema_context, validation_result["error"], 
                                user_query, current_tables
                            )
                            current_schema_context = refinement_result["schema_context"]
                            current_tables = refinement_result["tables"]
                            continue
                        else:
                            return {
                                "success": False,
                                "sql": sql,
                                "tables_used": current_tables,
                                "attempts": attempt,
                                "error": validation_result["error"]
                            }
                
                # Enhanced validation with schema accuracy checks
                validation_result = self._validate_sql_with_schema_accuracy(
                    sql, scoping_value, user_context, current_tables
                )
                
                # Additional check: ensure SQL uses only tables from the plan
                if validation_result["valid"]:
                    sql_tables = self._extract_tables_from_sql(sql)
                    plan_tables = set(current_tables)
                    invalid_sql_tables = set(sql_tables) - plan_tables
                    if invalid_sql_tables:
                        validation_result = {
                            "valid": False,
                            "error": f"SQL uses tables not in plan: {list(invalid_sql_tables)}",
                            "modified_sql": sql,
                            "tables": current_tables
                        }
                
                if validation_result["valid"]:
                    # Optional DB feedback loop via EXPLAIN
                    from .config import settings as _settings
                    if getattr(_settings, 'ENABLE_DB_FEEDBACK_LOOP', False):
                        try:
                            from .db_executor import db_executor
                            explain_sql = f"EXPLAIN {validation_result.get('modified_sql', sql).rstrip(';')}"
                            explain_result = db_executor.execute_query(explain_sql)
                            if not explain_result.get('success', False):
                                validation_result = {
                                    "valid": False,
                                    "error": f"Database error: {explain_result.get('error', 'Unknown DB error')}",
                                    "modified_sql": validation_result.get('modified_sql', sql),
                                    "tables": validation_result.get('tables', current_tables)
                                }
                            else:
                                return {
                                    "success": True,
                                    "sql": validation_result.get("modified_sql", sql),
                                    "tables_used": validation_result.get("tables", current_tables),
                                    "attempts": attempt + 1,
                                    "schema_tokens": len(current_schema_context.split()),
                                    "error": None
                                }
                        except Exception:
                            return {
                                "success": True,
                                "sql": validation_result.get("modified_sql", sql),
                                "tables_used": validation_result.get("tables", current_tables),
                                "attempts": attempt + 1,
                                "schema_tokens": len(current_schema_context.split()),
                                "error": None
                            }
                    else:
                        return {
                            "success": True,
                            "sql": validation_result.get("modified_sql", sql),
                            "tables_used": validation_result.get("tables", current_tables),
                            "attempts": attempt + 1,
                            "schema_tokens": len(current_schema_context.split()),
                            "error": None
                        }
                
                # If validation fails, refine context and retry
                attempt += 1
                if attempt < self.MAX_VALIDATION_ATTEMPTS:
                    refinement_result = self._refine_schema_context(
                        current_schema_context, validation_result["error"], 
                        user_query, current_tables
                    )
                    current_schema_context = refinement_result["schema_context"]
                    current_tables = refinement_result["tables"]
                
            except Exception as e:
                attempt += 1
                if attempt >= self.MAX_VALIDATION_ATTEMPTS:
                    return {
                        "success": False,
                        "sql": "",
                        "tables_used": current_tables,
                        "attempts": attempt,
                        "error": f"SQL generation failed: {str(e)}"
                    }
        
        # If all attempts fail, return error with context
        return {
            "success": False,
            "sql": sql if 'sql' in locals() else "",
            "tables_used": current_tables,
            "attempts": attempt,
            "error": f"Failed to generate valid SQL after {self.MAX_VALIDATION_ATTEMPTS} attempts. Last validation error: {validation_result.get('error', 'Unknown error')}"
        }
    
    def _validate_sql_with_schema_accuracy(self, sql: str, scoping_value: str, user_context: UserContext, tables: List[str]) -> Dict[str, Any]:
        """Enhanced validation with schema accuracy checks"""
        
        # First run standard validation
        validation_result = self.validator.validate_sql(sql, scoping_value, user_context)
        
        if not validation_result["valid"]:
            return validation_result
        
        # Use actually used tables from base validator for subsequent checks
        used_tables = validation_result.get("tables", tables)
        
        # Additional schema accuracy checks
        accuracy_issues = []
        
        # First, validate that all columns used actually exist in the schema
        schema_validation_issues = self._validate_columns_against_schema(sql, used_tables)
        accuracy_issues.extend(schema_validation_issues)
        
        # Additional heuristics
        sql_lower = sql.lower()
        
        # Check for missing JOINs when using supplier/carrier names
        if re.search(r'\bcarrier_name\b', sql_lower) or re.search(r'\bsupplier_name\b', sql_lower):
            if 'join' not in sql_lower or 'suppliers' not in sql_lower:
                accuracy_issues.append("❌ Missing JOIN for carrier/supplier names. ✅ Add: JOIN suppliers s ON shipments.supplier_id = s.id")
        
        # Check for proper status code usage
        if 'delivered' in sql_lower and 'tracking_status' in sql_lower:
            if "'delivered'" in sql_lower.lower():
                accuracy_issues.append("❌ Use tracking_status = '1900' for 'Delivered', not 'delivered'")
        
        # Check for common date column mistakes (only if truly absent in used tables)
        if re.search(r'\bdelivery_date\b', sql_lower):
            has_delivery_date = any(
                'delivery_date' in (col.lower() for col in self.schema_graph.tables.get(t, {}).get('columns', []))
                for t in used_tables
            )
            if not has_delivery_date:
                accuracy_issues.append("❌ Column 'delivery_date' doesn't exist. ✅ Use: shipment_date")
        
        if re.search(r'\border_date\b', sql_lower):
            has_order_date = any(
                'order_date' in (col.lower() for col in self.schema_graph.tables.get(t, {}).get('columns', []))
                for t in used_tables
            )
            if not has_order_date:
                accuracy_issues.append("❌ Column 'order_date' doesn't exist. ✅ Use: shipment_date or created_at")
        
        # Check for missing scoping - only for entity scoping column
        if user_context:
            from .user_context import permission_manager
            scoping_requirements = permission_manager.get_scoping_requirements(user_context)
            scoping_required = scoping_requirements.get('scoping_required', True)
            if scoping_required and scoping_value:
                missing_scope_columns: List[str] = []
                for table in used_tables:
                    table_info = self.schema_graph.tables.get(table, {})
                    # Only enforce entity-level scoping, not other columns used for code mappings
                    if table_info.get('scoped', False):
                        table_scope_col = table_info.get('scoping_column', settings.security.SCOPING_COLUMN)
                        if table_scope_col != settings.security.SCOPING_COLUMN:
                            continue
                        if table_scope_col and table_scope_col.lower() not in sql_lower:
                            missing_scope_columns.append(table_scope_col)
                # If none of the required scoping columns are present in SQL, flag once
                if missing_scope_columns:
                    unique_cols = sorted(set(missing_scope_columns))
                    suggestions = ", ".join(f"{col} = '{scoping_value}'" for col in unique_cols)
                    accuracy_issues.append(
                        f"❌ Missing scoping filter. ✅ Add one of: {suggestions}"
                    )

                # Additional rule: if query touches ONLY non-scoped tables but relates to a scoped parent, recommend joining parent and applying scoping
                if settings.security.SCOPING_COLUMN.lower() not in sql_lower:
                    all_used_are_non_scoped = True
                    for t in used_tables:
                        info = self.schema_graph.tables.get(t, {})
                        if info.get('scoped', False) and info.get('scoping_column', settings.security.SCOPING_COLUMN) == settings.security.SCOPING_COLUMN:
                            all_used_are_non_scoped = False
                            break
                    if all_used_are_non_scoped:
                        # find candidate parent scoped tables reachable by relationships
                        candidate_parents: List[str] = []
                        parent_join_hints: List[str] = []
                        for t in used_tables:
                            for rel in self.schema_graph.relationships:
                                # if non-scoped table t points to a scoped table
                                if rel.get('from') == t:
                                    parent = rel.get('to')
                                    pinfo = self.schema_graph.tables.get(parent, {})
                                    if pinfo.get('scoped', False) and pinfo.get('scoping_column', settings.security.SCOPING_COLUMN) == settings.security.SCOPING_COLUMN:
                                        candidate_parents.append(parent)
                                        on_col = rel.get('on')
                                        to_col = rel.get('to_column', on_col if on_col in pinfo.get('columns', []) else 'id')
                                        parent_join_hints.append(f"JOIN {parent} p ON {t}.{on_col} = p.{to_col} AND p.{settings.security.SCOPING_COLUMN} = '{scoping_value}'")
                                # or if scoped parent points to t (reverse direction)
                                if rel.get('to') == t:
                                    parent = rel.get('from')
                                    pinfo = self.schema_graph.tables.get(parent, {})
                                    if pinfo.get('scoped', False) and pinfo.get('scoping_column', settings.security.SCOPING_COLUMN) == settings.security.SCOPING_COLUMN:
                                        candidate_parents.append(parent)
                                        on_col = rel.get('on')
                                        # here rel.from=parent, rel.to=t, so join hint flips
                                        to_col = rel.get('to_column', on_col if on_col in self.schema_graph.tables.get(t, {}).get('columns', []) else 'id')
                                        parent_join_hints.append(f"JOIN {parent} p ON p.{on_col} = {t}.{to_col} AND p.{settings.security.SCOPING_COLUMN} = '{scoping_value}'")
                        if candidate_parents:
                            # de-duplicate and suggest the most relevant (prefer 'shipments')
                            unique_parents = list(dict.fromkeys(candidate_parents))
                            preferred_parent = 'shipments' if 'shipments' in unique_parents else unique_parents[0]
                            # pick first matching hint for preferred parent
                            hint = next((h for h in parent_join_hints if f"JOIN {preferred_parent} " in h), parent_join_hints[0]) if parent_join_hints else ''
                            msg = f"❌ Missing tenant scoping. ✅ Join '{preferred_parent}' and filter p.{settings.security.SCOPING_COLUMN} = '{scoping_value}'."
                            if hint:
                                msg += f" For example: {hint}"
                            accuracy_issues.append(msg)
        
        
        if accuracy_issues:
            return {
                "valid": False,
                "error": "Schema accuracy issues: " + "; ".join(accuracy_issues),
                "modified_sql": sql,
                "tables": tables
            }
        
        return validation_result
    
    def _refine_schema_context(self, schema_context: str, validation_error: str, 
                             user_query: str, current_tables: List[str]) -> Dict[str, Any]:
        """Refine schema context based on validation errors"""
        
        # Add more tables if scoping issues
        if "scoping" in validation_error.lower():
            additional_tables = self._add_missing_scoped_tables(current_tables)
            current_tables.extend(additional_tables)
            current_tables = list(dict.fromkeys(current_tables))  # Remove duplicates
        
        # Add relationship context if join issues
        if "join" in validation_error.lower() or "relationship" in validation_error.lower():
            relationship_tables = self._get_relationship_context(current_tables, user_query)
            current_tables.extend(relationship_tables)
            current_tables = list(dict.fromkeys(current_tables))
        
        # Rebuild schema context with refined tables
        refined_context = self._build_focused_schema_description(current_tables, 
            QueryContext(user_query, "", current_tables, "", 0.5, True, True))
        
        return {
            "schema_context": refined_context,
            "tables": current_tables
        }
    
    def _add_missing_scoped_tables(self, current_tables: List[str]) -> List[str]:
        """Add missing scoped tables that might be needed"""
        missing_tables = []
        
        # Add core scoped tables that might be missing
        core_scoped_tables = ['entities', 'shipments', 'orders', 'locations', 'transactions']
        for table in core_scoped_tables:
            if table not in current_tables and table in self.schema_graph.tables:
                table_info = self.schema_graph.tables[table]
                if table_info.get('scoped', False):
                    missing_tables.append(table)
        
        return missing_tables

# Factory function for easy integration
def create_intelligent_sql_generator(llm_handler: LLMHandler, validator: QueryValidator) -> IntelligentSQLGenerator:
    """Create an intelligent SQL generator instance"""
    return IntelligentSQLGenerator(llm_handler, validator)
