import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator, model_validator
import uvicorn

from .utils.config import settings
from .loaders.graph_builder import schema_graph
from .agents.llm_handler import LLMHandler
from .validators.query_validator import get_query_validator
from .engines.db_executor import db_executor
from .agents.intelligent_sql_generator import create_intelligent_sql_generator
from .utils.middleware import RequestResponseMiddleware, circuit_breaker_middleware
from .utils.error_codes import (
    NL2SQLError, ErrorHandler, ErrorCodes,
    create_database_error, create_llm_error, create_validation_error,
    create_system_error, create_request_error
)
from .utils.error_responses import (
    format_error_response, format_legacy_error_response,
    extract_error_context
)
from .utils.user_context import permission_manager, access_logger


# Initialize FastAPI app
app = FastAPI(
    title="NL2SQL AI Agent",
    description="Intelligent AI Agent for Natural Language to SQL conversion with multi-LLM support",
    version="2.0.0"
)

# Add request/response middleware
request_response_middleware = RequestResponseMiddleware(app, enable_metrics=True, enable_logging=False)
app.add_middleware(RequestResponseMiddleware, enable_metrics=True, enable_logging=False)

# Create API router with versioning
from fastapi import APIRouter

# API v2 router - clean implementation
api_v2 = APIRouter(prefix="/api/v2", tags=["NL2SQL API v2"])

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:7000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Router will be included after endpoints are defined

# Initialize components
llm_handler = None
intelligent_sql_generator = None

# Pydantic models
class QueryRequest(BaseModel):
    query: str = Field(..., description="Natural language query")
    scoping_value: Optional[str] = Field(None, description="Value for data scoping (e.g., entity_id, tenant_id)")
    include_explanation: bool = Field(False, description="Include natural language explanation of results")
    user_context: Optional[Dict[str, Any]] = Field(None, description="Additional user context for scoping")

    # Multi-role access control fields
    user_role: Optional[str] = Field(None, description="User role: 'customer', 'admin'")
    
    # Backward compatibility
    @model_validator(mode='before')
    @classmethod
    def set_scoping_value(cls, values):
        # If entity_id is provided for backward compatibility, use it as scoping_value
        if isinstance(values, dict) and 'entity_id' in values and values['entity_id'] and not values.get('scoping_value'):
            values['scoping_value'] = values['entity_id']
        return values
    
    # Support for legacy entity_id field
    entity_id: Optional[str] = Field(None, description="Entity ID for data scoping (legacy field)")

class QueryResponse(BaseModel):
    success: bool
    sql: str
    results: List[Dict]
    row_count: int
    explanation: Optional[str] = None
    error: Optional[str] = None
    execution_time: float
    tables_used: List[str]

class HealthResponse(BaseModel):
    status: str
    database_connected: bool
    llm_provider_connected: bool
    schema_loaded: bool
    llm_provider_info: Optional[Dict] = None
    circuit_breaker_status: Optional[Dict] = None
    warnings: List[str] = []
    timestamp: str

# Rate limiting
class RateLimiter:
    def __init__(self, max_requests: int = 60):
        self.max_requests = max_requests
        self.requests = {}
    
    def is_allowed(self, client_id: str) -> bool:
        now = time.time()
        if client_id not in self.requests:
            self.requests[client_id] = []
        
        # Remove old requests (older than 1 minute)
        self.requests[client_id] = [req_time for req_time in self.requests[client_id] 
                                  if now - req_time < 60]
        
        if len(self.requests[client_id]) >= self.max_requests:
            return False
        
        self.requests[client_id].append(now)
        return True

rate_limiter = RateLimiter(settings.RATE_LIMIT_PER_MINUTE)

# Dependency for rate limiting
def check_rate_limit(request: Request):
    client_id = request.client.host
    if not rate_limiter.is_allowed(client_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded"
        )

# Startup event
@app.on_event("startup")
async def startup_event():
    global llm_handler, intelligent_sql_generator
    
    try:
        # Test database connection
        if not db_executor.test_connection():
            raise Exception("Database connection failed")
        
        # Initialize LLM handler
        try:
            llm_handler = LLMHandler()
        except Exception as e:
            raise
        
        # Initialize intelligent SQL generator
        try:
            validator = get_query_validator(schema_graph)
            intelligent_sql_generator = create_intelligent_sql_generator(llm_handler, validator)
        except Exception as e:
            raise
        
    except Exception as e:
        raise

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    try:
        # Close LLM handler
        if llm_handler:
            try:
                await llm_handler.close()
            except Exception as e:
                pass
        
        # Close database connection
        try:
            db_executor.close()
        except Exception as e:
            pass
        
    except Exception as e:
        pass

# Health check endpoint
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    warnings = []
    
    # Test LLM provider connection
    llm_provider_connected = False
    llm_provider_info = None
    circuit_breaker_status = None
    if llm_handler:
        try:
            # Test LLM provider by getting provider info
            llm_provider_info = llm_handler.get_provider_info()
            circuit_breaker_status = llm_handler.get_circuit_breaker_status()
            llm_provider_connected = True
        except Exception as e:
            # Still try to get circuit breaker status even if provider is failing
            try:
                circuit_breaker_status = llm_handler.get_circuit_breaker_status()
            except:
                pass
    
    # Check scoping column configuration
    scoping_column = settings.security.SCOPING_COLUMN
    if scoping_column == "entity_id":
        warnings.append(f"Using default scoping column '{scoping_column}'. Consider configuring a more specific scoping column for better security.")
    
    # Check if scoping column is properly configured in schema
    if schema_graph.tables:
        scoped_tables = [table for table, info in schema_graph.tables.items() if info.get('scoped', False)]
        if scoped_tables:
            # Check if any scoped table uses the configured scoping column
            uses_configured_column = any(
                info.get('scoping_column', scoping_column) == scoping_column 
                for table, info in schema_graph.tables.items() 
                if info.get('scoped', False)
            )
            if not uses_configured_column:
                warnings.append(f"Configured scoping column '{scoping_column}' not found in any scoped tables. Check schema configuration.")
    
    return HealthResponse(
        status="healthy",
        database_connected=db_executor.test_connection(),
        llm_provider_connected=llm_provider_connected,
        schema_loaded=schema_graph.tables is not None,
        llm_provider_info=llm_provider_info,
        circuit_breaker_status=circuit_breaker_status,
        warnings=warnings,
        timestamp=datetime.now().isoformat()
    )

# Main query endpoint (v2)
@api_v2.post("/query", response_model=QueryResponse)
async def process_query_v2(
    request: QueryRequest,
    rate_limit: None = Depends(check_rate_limit)
):
    """Process natural language query and return SQL results with multi-role access control"""
    start_time = time.time()
    
    try:
        # Create user context if user information is provided
        user_context = None
        if request.user_role:
            try:
                print(f"Creating user context for role: {request.user_role}")
                user_context = permission_manager.create_user_context(
                    role=request.user_role,
                    scoping_value=request.scoping_value or request.entity_id,
                    request_id=getattr(request, 'request_id', None)
                )
                print(f"User context created: {user_context.permissions}")
            except ValueError as e:
                error = ErrorHandler.create_error(
                    ErrorCodes.AUTH_INSUFFICIENT_PERMISSIONS,
                    {"error": str(e)}
                )
                return QueryResponse(
                    success=False,
                    sql="",
                    results=[],
                    row_count=0,
                    error=error.error_code.message,
                    execution_time=time.time() - start_time
                )
        
        # Get scoping value from request
        scoping_value = request.scoping_value or request.entity_id
        
        # Validate scoping requirements based on user context
        if user_context:
            scoping_requirements = permission_manager.get_scoping_requirements(user_context)
            print(f"Scoping requirements: {scoping_requirements}")
            print(f"Scoping value: {scoping_value}")
            if scoping_requirements.get('scoping_required', True) and not scoping_value:
                error = ErrorHandler.create_error(
                    ErrorCodes.VAL_MISSING_SCOPING_VALUE,
                    {"query": request.query, "role": user_context.role}
                )
                return QueryResponse(
                    success=False,
                    sql="",
                    results=[],
                    row_count=0,
                    error=error.error_code.message,
                    execution_time=time.time() - start_time
                )
        elif not scoping_value:
            # Legacy behavior for backward compatibility
            error = ErrorHandler.create_error(
                ErrorCodes.VAL_MISSING_SCOPING_VALUE,
                {"query": request.query}
            )
            return QueryResponse(
                success=False,
                sql="",
                results=[],
                row_count=0,
                error=error.error_code.message,
                execution_time=time.time() - start_time
            )
        
        # Use intelligent SQL generator with user context support
        sql_result = await intelligent_sql_generator.generate_accurate_sql(
            request.query, 
            scoping_value,
            user_context
        )
        
        if not sql_result["success"]:
            return QueryResponse(
                success=False,
                sql=sql_result.get("sql", ""),
                results=[],
                row_count=0,
                error=sql_result.get("error", "SQL generation failed"),
                execution_time=time.time() - start_time,
                tables_used=sql_result.get("tables_used", [])
            )
        
        final_sql = sql_result["sql"]
        relevant_tables = sql_result["tables_used"]
        
        # Step 4: Execute SQL
        execution_result = db_executor.execute_query(final_sql)
        
        if not execution_result["success"]:
            # Map database error to appropriate error code
            error_msg = execution_result["error"]
            if "syntax" in error_msg.lower():
                error_code = ErrorCodes.DB_INVALID_SQL_SYNTAX
            elif "permission" in error_msg.lower() or "access denied" in error_msg.lower():
                error_code = ErrorCodes.DB_PERMISSION_DENIED
            elif "timeout" in error_msg.lower():
                error_code = ErrorCodes.DB_TIMEOUT
            else:
                error_code = ErrorCodes.DB_QUERY_EXECUTION_FAILED
            
            error = ErrorHandler.create_error(
                error_code,
                {"database_error": error_msg, "sql": final_sql}
            )
            
            return QueryResponse(
                success=False,
                sql=final_sql,
                results=[],
                row_count=0,
                error=error.error_code.message,
                execution_time=time.time() - start_time,
                tables_used=relevant_tables
            )
        
        # Step 5: Generate explanation if requested
        explanation = None
        if request.include_explanation:
            explanation = await llm_handler.explain_results(
                request.query,
                execution_result["data"],
                execution_result["row_count"]
            )
        
        execution_time = time.time() - start_time
        
        return QueryResponse(
            success=True,
            sql=final_sql,
            results=execution_result["data"],
            row_count=execution_result["row_count"],
            explanation=explanation,
            error=None,
            execution_time=execution_time,
            tables_used=relevant_tables
        )
        
    except Exception as e:
        # Create appropriate error based on exception type
        if "llm" in str(type(e)).lower() or "openai" in str(type(e)).lower() or "anthropic" in str(type(e)).lower():
            nl2sql_error = create_llm_error(e, "query_generation")
        elif "database" in str(type(e)).lower() or "sql" in str(type(e)).lower():
            nl2sql_error = create_database_error(e, "query_execution")
        elif "validation" in str(type(e)).lower():
            nl2sql_error = create_validation_error(e, "query_processing")
        else:
            nl2sql_error = create_system_error(e, "query_processing")
        
        return QueryResponse(
            success=False,
            sql="",
            results=[],
            row_count=0,
            error=nl2sql_error.error_code.message,
            execution_time=time.time() - start_time,
            tables_used=[]
        )

# Schema information endpoint (v2)
@api_v2.get("/schema")
async def get_schema_info_v2():
    """Get database schema information"""
    return {
        "tables": schema_graph.tables,
        "relationships": schema_graph.relationships,
        "entity_scoped_tables": list(schema_graph.tables.keys()),
        "description": schema_graph.get_schema_description()
    }

# Table information endpoint (v2)
@api_v2.get("/schema/{table_name}")
async def get_table_info_v2(table_name: str):
    """Get detailed information about a specific table"""
    table_info = schema_graph.get_table_info(table_name)
    if not table_info:
        error = ErrorHandler.create_error(
            ErrorCodes.DB_TABLE_NOT_FOUND,
            {"table_name": table_name}
        )
        raise error.to_http_exception()
    
    # Get additional info from database
    db_schema = db_executor.get_table_schema(table_name)
    row_count = db_executor.get_table_row_count(table_name)
    
    return {
        "table_name": table_name,
        "schema_info": table_info,
        "database_schema": db_schema,
        "row_count": row_count,
        "related_tables": schema_graph.get_related_tables(table_name)
    }

# Error handlers
@app.exception_handler(NL2SQLError)
async def nl2sql_error_handler(request: Request, exc: NL2SQLError):
    """Handle custom NL2SQL errors with standardized formatting"""
    return format_error_response(exc, request, include_debug_info=False)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions with error code system"""
    # Extract context for better error reporting
    context = extract_error_context(request)
    
    # Create system error
    nl2sql_error = create_system_error(exc, f"Unexpected error in {context.get('path', 'unknown')}")
    
    # Add context to error details
    nl2sql_error.details.update(context)
    
    return format_error_response(nl2sql_error, request, include_debug_info=True)

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle FastAPI HTTP exceptions with error code system"""
    # Map common HTTP exceptions to error codes
    if exc.status_code == 404:
        error = ErrorHandler.create_error(
            ErrorCodes.REQ_MALFORMED_REQUEST,
            {"path": request.url.path, "method": request.method}
        )
    elif exc.status_code == 422:
        error = ErrorHandler.create_error(
            ErrorCodes.VAL_INVALID_QUERY_FORMAT,
            {"validation_error": str(exc.detail)}
        )
    elif exc.status_code == 429:
        error = ErrorHandler.create_error(
            ErrorCodes.REQ_RATE_LIMIT_EXCEEDED,
            {"path": request.url.path}
        )
    else:
        error = ErrorHandler.create_error(
            ErrorCodes.REQ_MALFORMED_REQUEST,
            {"http_status": exc.status_code, "detail": str(exc.detail)}
        )
    
    return format_error_response(error, request)

# UI redirect endpoint
@app.get("/ui")
async def ui_redirect():
    """Redirect to the dashboard UI"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/")

# No legacy endpoints - clean v2 API only

# LLM providers endpoint
@app.get("/api/v2/providers")
async def get_llm_providers():
    """Get available LLM providers and current configuration"""
    from .engines.llm_providers import LLMProviderFactory
    
    available_providers = settings.get_available_providers()
    supported_providers = LLMProviderFactory.get_supported_providers()
    current_provider = settings.DEFAULT_LLM_PROVIDER
    
    return {
        "current_provider": current_provider,
        "available_providers": available_providers,
        "supported_providers": supported_providers,
        "provider_configs": {
            provider: {
                "configured": provider in available_providers,
                "model": settings.get_llm_config(provider).model if provider in available_providers else None
            }
            for provider in supported_providers
        }
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "NL2SQL AI Agent",
        "version": "2.0.0",
        "ui": "http://localhost:7000/",
        "api_version": "v2",
        "endpoints": {
            "v2": {
                "POST /api/v2/query": "Process natural language query",
                "GET /api/v2/schema": "Get schema information",
                "GET /api/v2/schema/{table_name}": "Get table information",
                "GET /api/v2/providers": "Get LLM provider information"
            },
            "system": {
                "GET /health": "Health check with circuit breaker status",
                "GET /ui": "Redirect to web interface"
            }
        }
    }

# Include the versioned API router AFTER all endpoints are defined
app.include_router(api_v2)

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        workers=settings.API_WORKERS,
        log_level="info"
    ) 