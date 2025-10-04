from typing import List, Dict, Optional, Any
import pandas as pd
from sqlalchemy import create_engine, text, exc
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool
from ..utils.config import settings
from ..utils.error_codes import create_database_error, ErrorCodes

class DatabaseExecutor:
    def __init__(self):
        self.engine: Optional[Engine] = None
        self._create_engine()
    
    def _create_engine(self):
        """Create database engine with read-only configuration"""
        try:
            self.engine = create_engine(
                settings.DB_URL,
                poolclass=QueuePool,
                pool_size=settings.DB_POOL_SIZE,
                max_overflow=settings.DB_MAX_OVERFLOW,
                pool_pre_ping=True,
                pool_recycle=3600
            )
            # Database engine created successfully
        except Exception as e:
            # Error creating database engine
            raise create_database_error(e, "engine_creation")
    
    def test_connection(self) -> bool:
        """Test database connection"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                result.fetchone()
            # Database connection test successful
            return True
        except Exception as e:
            # Database connection test failed
            return False
    
    def execute_query(self, sql: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute SQL query safely"""
        try:
            # Validate SQL before execution
            if not self._validate_sql_for_execution(sql):
                return {
                    "success": False,
                    "error": "SQL validation failed",
                    "data": None,
                    "row_count": 0
                }
            
            # Apply LIMIT guardrail if needed
            sql_to_run = self._apply_limit_guardrail(sql)
            
            with self.engine.connect() as conn:
                # Optional: Run EXPLAIN first for safety (disabled)
                
                # Execute the actual query
                if params:
                    result = conn.execute(text(sql_to_run), params)
                else:
                    result = conn.execute(text(sql_to_run))
                
                # Fetch results
                rows = result.fetchall()
                columns = result.keys()
                
                # Convert to list of dictionaries
                data = [dict(zip(columns, row)) for row in rows]
                
                # Query executed successfully
                
                return {
                    "success": True,
                    "data": data,
                    "row_count": len(data),
                    "columns": list(columns),
                    "error": None
                }
                
        except exc.SQLAlchemyError as e:
            # Database error occurred
            error = create_database_error(e, "query_execution")
            return {
                "success": False,
                "error": error.error_code.message,
                "data": None,
                "row_count": 0,
                "error_code": error.error_code.code
            }
        except Exception as e:
            # Unexpected error occurred
            error = create_database_error(e, "query_execution")
            return {
                "success": False,
                "error": error.error_code.message,
                "data": None,
                "row_count": 0,
                "error_code": error.error_code.code
            }
    
    def _validate_sql_for_execution(self, sql: str) -> bool:
        """Additional validation before execution"""
        import re
        sql_upper = sql.upper()
        
        # Check for read-only operations only
        allowed_keywords = ['SELECT', 'WITH', 'EXPLAIN', 'SHOW', 'DESCRIBE', 'DESC']
        dangerous_keywords = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 'TRUNCATE']
        
        # Check for dangerous operations - use word boundaries to avoid false positives
        for keyword in dangerous_keywords:
            pattern = r'\b' + keyword + r'\b'
            if re.search(pattern, sql_upper):
                # Blocked dangerous operation
                return False
        
        # Ensure it's a SELECT query - use word boundaries for allowed keywords too
        for keyword in allowed_keywords:
            pattern = r'\b' + keyword + r'\b'
            if re.search(pattern, sql_upper):
                return True
        
        # Query must be a SELECT operation
        return False
    
    def _apply_limit_guardrail(self, sql: str) -> str:
        """Apply LIMIT guardrail to prevent large result sets"""
        import re
        from ..utils.config import settings
        
        try:
            sql_upper = sql.upper()
            
            # Check if query already has LIMIT
            has_limit = bool(re.search(r'\bLIMIT\s+\d+', sql_upper))
            if has_limit:
                return sql
            
            # Check if query is aggregate-only (COUNT, SUM, AVG, etc.)
            is_aggregate = bool(re.search(r'\b(COUNT|SUM|AVG|MIN|MAX|GROUP_CONCAT)\s*\(', sql_upper))
            if is_aggregate:
                return sql
            
            # Apply default LIMIT
            default_limit = getattr(settings.security, 'DEFAULT_LIMIT', 10)
            sql_with_limit = f"{sql.rstrip(';')} LIMIT {default_limit}"
            
            return sql_with_limit
            
        except Exception:
            # If anything goes wrong, return original SQL
            return sql
    
    def get_table_schema(self, table_name: str) -> Optional[Dict]:
        """Get schema information for a table"""
        try:
            sql = """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = %s
            ORDER BY ordinal_position;
            """
            
            result = self.execute_query(sql, {"table_name": table_name})
            if result["success"]:
                return {
                    "table_name": table_name,
                    "columns": result["data"]
                }
            return None
            
        except Exception as e:
            # Error getting table schema
            return None
    
    def get_table_row_count(self, table_name: str, scoping_value: Optional[str] = None) -> Optional[int]:
        """Get row count for a table (with optional scoping value filter)"""
        try:
            if scoping_value:
                from ..utils.config import settings
                scoping_column = settings.security.SCOPING_COLUMN
                sql = f"SELECT COUNT(*) as count FROM {table_name} WHERE {scoping_column} = %s;"
                result = self.execute_query(sql, {scoping_column: scoping_value})
            else:
                sql = f"SELECT COUNT(*) as count FROM {table_name};"
                result = self.execute_query(sql)
            
            if result["success"] and result["data"]:
                return result["data"][0]["count"]
            return None
            
        except Exception as e:
            # Error getting table row count
            return None
    
    def execute_with_pandas(self, sql: str, params: Optional[Dict] = None) -> Optional[pd.DataFrame]:
        """Execute query and return pandas DataFrame"""
        try:
            if params:
                df = pd.read_sql(sql, self.engine, params=params)
            else:
                df = pd.read_sql(sql, self.engine)
            
            # Query executed with pandas
            return df
            
        except Exception as e:
            # Error executing query with pandas
            return None
    
    def close(self):
        """Close database connections"""
        if self.engine:
            self.engine.dispose()
            # Database connections closed

# Global instance
db_executor = DatabaseExecutor()


