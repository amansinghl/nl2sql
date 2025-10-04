"""
Schema-driven retrieval index for table selection and context building.
Uses BM25 lexical scoring + graph centrality for robust table ranking.
"""
import re
import json
from typing import List, Dict, Tuple, Set, Optional
from collections import Counter
import math


class SchemaIndex:
    """Schema-driven retrieval index for intelligent table selection"""
    
    def __init__(self, schema_graph=None):
        self.schema_graph = schema_graph
        self.table_docs = []
        self.table_names = []
        self._index_built = False
        # Dense/lexical hybrid components
        self._tfidf_vectorizer = None
        self._doc_matrix = None
    
    def _ensure_index(self):
        """Lazy-load the schema graph and build index if needed"""
        if not self._index_built:
            if self.schema_graph is None:
                from ..loaders.graph_builder import schema_graph
                self.schema_graph = schema_graph
            self._build_index()
            self._index_built = True
    
    def _build_index(self):
        """Build BM25 index from schema metadata"""
        self.table_docs = []
        self.table_names = []
        
        for table_name, table_info in self.schema_graph.tables.items():
            # Build comprehensive document for each table
            doc_parts = []
            
            # Table name (highest weight)
            doc_parts.extend([table_name] * 3)
            
            # Description
            if 'description' in table_info:
                doc_parts.extend(self._tokenize(table_info['description']))
            
            # Column names
            for col in table_info.get('columns', []):
                doc_parts.extend(self._tokenize(col))
            
            # Example queries (lower weight)
            for example in table_info.get('examples', []):
                query = example.get('query', '')
                doc_parts.extend(self._tokenize(query))
            
            # Keyword mappings (if table is mapped)
            keyword_mappings = self.schema_graph.graph_data.get('keyword_mappings', {})
            for keyword, tables in keyword_mappings.items():
                if table_name in tables:
                    doc_parts.extend(self._tokenize(keyword))
            
            self.table_docs.append(' '.join(doc_parts))
            self.table_names.append(table_name)
        # Build TF-IDF vectors lazily here to avoid repeated fitting
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            if self.table_docs:
                self._tfidf_vectorizer = TfidfVectorizer(max_features=4000, stop_words='english')
                self._doc_matrix = self._tfidf_vectorizer.fit_transform(self.table_docs)
        except Exception:
            # If sklearn not available or any issue, skip dense component
            self._tfidf_vectorizer = None
            self._doc_matrix = None
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization for BM25"""
        if not text:
            return []
        # Extract words, convert to lowercase
        tokens = re.findall(r'\b\w+\b', text.lower())
        return tokens
    
    def _compute_bm25_score(self, query_tokens: List[str], doc_tokens: List[str]) -> float:
        """Compute BM25 score for query against document"""
        if not query_tokens or not doc_tokens:
            return 0.0
        
        # BM25 parameters
        k1 = 1.2
        b = 0.75
        avg_doc_length = sum(len(doc.split()) for doc in self.table_docs) / len(self.table_docs)
        
        doc_length = len(doc_tokens)
        doc_counter = Counter(doc_tokens)
        
        score = 0.0
        for term in query_tokens:
            if term in doc_counter:
                tf = doc_counter[term]
                idf = math.log(len(self.table_docs) / sum(1 for doc in self.table_docs if term in doc.split()))
                score += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (doc_length / avg_doc_length)))
        
        return score
    
    def _compute_centrality_score(self, table_name: str) -> float:
        """Compute graph centrality score for table"""
        if not hasattr(self.schema_graph, 'nx_graph') or not self.schema_graph.nx_graph:
            return 0.0
        
        try:
            import networkx as nx
            # Use degree centrality as a simple measure
            centrality = nx.degree_centrality(self.schema_graph.nx_graph)
            return centrality.get(table_name, 0.0)
        except ImportError:
            return 0.0

    def _compute_tfidf_score(self, query: str, doc_index: int) -> float:
        """Compute cosine similarity using TF-IDF embeddings if available"""
        try:
            if not self._tfidf_vectorizer or self._doc_matrix is None:
                return 0.0
            if not query:
                return 0.0
            import numpy as np
            from sklearn.metrics.pairwise import cosine_similarity
            q_vec = self._tfidf_vectorizer.transform([query])
            sim = cosine_similarity(q_vec, self._doc_matrix[doc_index]).ravel()[0]
            # Ensure finite
            return float(sim) if np.isfinite(sim) else 0.0
        except Exception:
            return 0.0
    
    def search_tables(self, query: str, top_k: int = 10, min_score: float = 0.1) -> List[Tuple[str, float]]:
        """Search for relevant tables using BM25 + TF-IDF cosine + centrality + keyword boosts"""
        self._ensure_index()
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []
        
        # Get keyword mapping boost
        keyword_mappings = self.schema_graph.graph_data.get('keyword_mappings', {})
        keyword_boost = {}
        for token in query_tokens:
            for keyword, tables in keyword_mappings.items():
                if keyword in token or token in keyword:
                    for table in tables:
                        keyword_boost[table] = keyword_boost.get(table, 0) + 2.0
        
        # Score each table
        scores = []
        for i, table_name in enumerate(self.table_names):
            doc_tokens = self._tokenize(self.table_docs[i])
            
            # BM25 score
            bm25_score = self._compute_bm25_score(query_tokens, doc_tokens)
            
            # Centrality score
            centrality_score = self._compute_centrality_score(table_name)
            
            # TF-IDF cosine score
            tfidf_score = self._compute_tfidf_score(query, i)
            
            # Keyword boost
            boost = keyword_boost.get(table_name, 0.0)
            
            # Combined score (weighted)
            combined_score = (bm25_score * 1.0) + (tfidf_score * 0.8) + (centrality_score * 0.3) + boost
            
            if combined_score >= min_score:
                scores.append((table_name, combined_score))
        
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]
    
    def get_table_priority(self, table_name: str) -> float:
        """Get priority score for a table (higher = more important)"""
        self._ensure_index()
        core_tables = {'entities', 'shipments', 'orders', 'users', 'locations', 'transactions'}
        if table_name in core_tables:
            return 1.0
        relationship_indicators = ['mapping', 'preference', 'setting', 'tracking_code', 'status_mapping']
        if any(indicator in table_name.lower() for indicator in relationship_indicators):
            return 0.3
        lookup_indicators = ['master', 'code', 'status']
        if any(indicator in table_name.lower() for indicator in lookup_indicators):
            return 0.2
        return 0.5


# Global instance
schema_index = SchemaIndex()


