"""
Error Response Utilities

This module provides utilities for formatting error responses in a consistent manner
across the NL2SQL AI Agent.
"""

from typing import Dict, Any, Optional
from fastapi import Request
from fastapi.responses import JSONResponse
from .error_codes import NL2SQLError, ErrorHandler, ErrorCodes


def format_error_response(
    error: NL2SQLError,
    request: Optional[Request] = None,
    include_debug_info: bool = False
) -> JSONResponse:
    """
    Format an error response with consistent structure
    
    Args:
        error: The NL2SQLError instance
        request: FastAPI request object for additional context
        include_debug_info: Whether to include debug information
    
    Returns:
        JSONResponse with formatted error data
    """
    # Get request ID if available
    request_id = getattr(request.state, 'request_id', 'unknown') if request else 'unknown'
    
    # Base error response
    response_data = {
        "success": False,
        "error_code": error.error_code.code,
        "message": error.error_code.message,
        "description": error.error_code.description,
        "category": error.error_code.category.value,
        "retryable": error.error_code.retryable,
        "request_id": request_id,
        "error": error.error_code.message  # Add error field for UI compatibility
    }
    
    # Add user-friendly message if available
    if error.error_code.user_friendly:
        response_data["user_message"] = error.error_code.message
    else:
        response_data["user_message"] = "An error occurred while processing your request"
    
    # Add details if available
    if error.details:
        response_data["details"] = error.details
    
    # Add debug information if requested and available
    if include_debug_info:
        debug_info = {
            "original_exception": str(error.original_exception) if error.original_exception else None,
            "error_type": type(error.original_exception).__name__ if error.original_exception else None
        }
        response_data["debug"] = debug_info
    
    return JSONResponse(
        status_code=error.error_code.http_status,
        content=response_data
    )


def format_legacy_error_response(
    message: str,
    status_code: int = 500,
    request: Optional[Request] = None,
    error_type: Optional[str] = None
) -> JSONResponse:
    """
    Format a legacy error response for backward compatibility
    
    Args:
        message: Error message
        status_code: HTTP status code
        request: FastAPI request object
        error_type: Type of error
    
    Returns:
        JSONResponse with legacy format
    """
    request_id = getattr(request.state, 'request_id', 'unknown') if request else 'unknown'
    
    response_data = {
        "success": False,
        "error": message,
        "request_id": request_id
    }
    
    if error_type:
        response_data["error_type"] = error_type
    
    return JSONResponse(
        status_code=status_code,
        content=response_data
    )


def create_health_check_error_response(
    service: str,
    status: str,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a standardized health check error response
    
    Args:
        service: Name of the service that failed
        status: Status of the service
        details: Additional error details
    
    Returns:
        Dictionary with health check error information
    """
    return {
        "service": service,
        "status": status,
        "healthy": False,
        "error_code": ErrorCodes.SYS_RESOURCE_UNAVAILABLE.code,
        "message": f"{service} is {status}",
        "details": details or {}
    }


def create_validation_error_response(
    field: str,
    message: str,
    value: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Create a standardized validation error response
    
    Args:
        field: Field name that failed validation
        message: Validation error message
        value: The value that failed validation
    
    Returns:
        Dictionary with validation error information
    """
    return {
        "field": field,
        "message": message,
        "value": value,
        "error_code": ErrorCodes.VAL_INVALID_QUERY_FORMAT.code
    }


def create_database_error_response(
    operation: str,
    table: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a standardized database error response
    
    Args:
        operation: Database operation that failed
        table: Table name involved in the operation
        details: Additional error details
    
    Returns:
        Dictionary with database error information
    """
    return {
        "operation": operation,
        "table": table,
        "error_code": ErrorCodes.DB_QUERY_EXECUTION_FAILED.code,
        "message": f"Database operation '{operation}' failed",
        "details": details or {}
    }


def create_llm_error_response(
    provider: str,
    operation: str,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a standardized LLM error response
    
    Args:
        provider: LLM provider name
        operation: Operation that failed
        details: Additional error details
    
    Returns:
        Dictionary with LLM error information
    """
    return {
        "provider": provider,
        "operation": operation,
        "error_code": ErrorCodes.LLM_INVALID_RESPONSE.code,
        "message": f"LLM operation '{operation}' failed for provider '{provider}'",
        "details": details or {}
    }


def extract_error_context(request: Request) -> Dict[str, Any]:
    """
    Extract context information from a FastAPI request for error reporting
    
    Args:
        request: FastAPI request object
    
    Returns:
        Dictionary with request context information
    """
    context = {
        "method": request.method,
        "url": str(request.url),
        "path": request.url.path,
        "query_params": dict(request.query_params),
        "client_ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
        "request_id": getattr(request.state, 'request_id', 'unknown')
    }
    
    # Add request body info if available
    if hasattr(request, '_body'):
        context["body_size"] = len(request._body) if request._body else 0
    
    return context


