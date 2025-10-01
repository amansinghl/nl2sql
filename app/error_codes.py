"""
Error Codes and Error Handling Module

This module provides standardized error codes, error classes, and error handling utilities
for the NL2SQL AI Agent. All errors are categorized and assigned unique codes for
better debugging and user experience.

Error Code Format: NL2SQL-{CATEGORY}-{NUMBER}
- NL2SQL: AI Agent identifier
- CATEGORY: Error category (DB, VAL, LLM, AUTH, SYS, REQ)
- NUMBER: Sequential number within category

Categories:
- DB: Database related errors (1000-1999)
- VAL: Validation errors (2000-2999)
- LLM: LLM provider errors (3000-3999)
- AUTH: Authentication/Authorization errors (4000-4999)
- SYS: System errors (5000-5999)
- REQ: Request processing errors (6000-6999)
"""

from enum import Enum
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass
from fastapi import HTTPException


class ErrorCategory(Enum):
    """Error categories for organizing error codes"""
    DATABASE = "DB"
    VALIDATION = "VAL"
    LLM_PROVIDER = "LLM"
    AUTHENTICATION = "AUTH"
    SYSTEM = "SYS"
    REQUEST = "REQ"


@dataclass
class ErrorCode:
    """Standardized error code definition"""
    code: str
    category: ErrorCategory
    message: str
    description: str
    http_status: int
    user_friendly: bool = True
    retryable: bool = False


class ErrorCodes:
    """Centralized error code definitions"""
    
    # Database Errors (1000-1999)
    DB_CONNECTION_FAILED = ErrorCode(
        code="NL2SQL-DB-1001",
        category=ErrorCategory.DATABASE,
        message="Database connection failed",
        description="Unable to establish connection to the database",
        http_status=503,
        retryable=True
    )
    
    DB_QUERY_EXECUTION_FAILED = ErrorCode(
        code="NL2SQL-DB-1002",
        category=ErrorCategory.DATABASE,
        message="Query execution failed",
        description="SQL query could not be executed due to database error",
        http_status=500,
        retryable=True
    )
    
    DB_INVALID_SQL_SYNTAX = ErrorCode(
        code="NL2SQL-DB-1003",
        category=ErrorCategory.DATABASE,
        message="Invalid SQL syntax",
        description="The generated SQL query contains syntax errors",
        http_status=400
    )
    
    DB_TABLE_NOT_FOUND = ErrorCode(
        code="NL2SQL-DB-1004",
        category=ErrorCategory.DATABASE,
        message="Table not found",
        description="The specified table does not exist in the database",
        http_status=404
    )
    
    DB_COLUMN_NOT_FOUND = ErrorCode(
        code="NL2SQL-DB-1005",
        category=ErrorCategory.DATABASE,
        message="Column not found",
        description="The specified column does not exist in the table",
        http_status=404
    )
    
    DB_PERMISSION_DENIED = ErrorCode(
        code="NL2SQL-DB-1006",
        category=ErrorCategory.DATABASE,
        message="Database permission denied",
        description="Insufficient permissions to access the database resource",
        http_status=403
    )
    
    DB_TIMEOUT = ErrorCode(
        code="NL2SQL-DB-1007",
        category=ErrorCategory.DATABASE,
        message="Database query timeout",
        description="The database query exceeded the maximum execution time",
        http_status=504,
        retryable=True
    )
    
    # Validation Errors (2000-2999)
    VAL_INVALID_QUERY_FORMAT = ErrorCode(
        code="NL2SQL-VAL-2001",
        category=ErrorCategory.VALIDATION,
        message="Invalid query format",
        description="The natural language query format is invalid or empty",
        http_status=400
    )
    
    VAL_MISSING_SCOPING_VALUE = ErrorCode(
        code="NL2SQL-VAL-2002",
        category=ErrorCategory.VALIDATION,
        message="Scoping value is required",
        description="Entity scoping value is required for data isolation",
        http_status=400
    )
    
    VAL_SQL_INJECTION_DETECTED = ErrorCode(
        code="NL2SQL-VAL-2003",
        category=ErrorCategory.VALIDATION,
        message="SQL injection attempt detected",
        description="The query contains potentially malicious SQL code",
        http_status=400,
        user_friendly=False
    )
    
    VAL_INVALID_SCOPING_FILTER = ErrorCode(
        code="NL2SQL-VAL-2004",
        category=ErrorCategory.VALIDATION,
        message="Invalid scoping filter",
        description="The query does not include proper entity scoping filters",
        http_status=400
    )
    
    VAL_TOO_MANY_TABLES = ErrorCode(
        code="NL2SQL-VAL-2005",
        category=ErrorCategory.VALIDATION,
        message="Too many tables in query",
        description="The query references more tables than allowed by security policy",
        http_status=400
    )
    
    VAL_FORBIDDEN_OPERATION = ErrorCode(
        code="NL2SQL-VAL-2006",
        category=ErrorCategory.VALIDATION,
        message="Operation not allowed",
        description="The requested database operation is not permitted",
        http_status=403
    )
    
    VAL_MULTIPLE_STATEMENTS = ErrorCode(
        code="NL2SQL-VAL-2007",
        category=ErrorCategory.VALIDATION,
        message="Multiple statements not allowed",
        description="Only single SQL statements are permitted for security",
        http_status=400
    )
    
    VAL_SCHEMA_GRAPH_INVALID = ErrorCode(
        code="NL2SQL-VAL-2008",
        category=ErrorCategory.VALIDATION,
        message="Schema graph is invalid",
        description="The database schema configuration is invalid or corrupted",
        http_status=500
    )
    
    # LLM Provider Errors (3000-3999)
    LLM_API_KEY_MISSING = ErrorCode(
        code="NL2SQL-LLM-3001",
        category=ErrorCategory.LLM_PROVIDER,
        message="LLM API key missing",
        description="API key for the selected LLM provider is not configured",
        http_status=500
    )
    
    LLM_API_RATE_LIMITED = ErrorCode(
        code="NL2SQL-LLM-3002",
        category=ErrorCategory.LLM_PROVIDER,
        message="LLM API rate limited",
        description="Rate limit exceeded for the LLM provider API",
        http_status=429,
        retryable=True
    )
    
    LLM_API_UNAVAILABLE = ErrorCode(
        code="NL2SQL-LLM-3003",
        category=ErrorCategory.LLM_PROVIDER,
        message="LLM API unavailable",
        description="The LLM provider API is currently unavailable",
        http_status=503,
        retryable=True
    )
    
    LLM_INVALID_RESPONSE = ErrorCode(
        code="NL2SQL-LLM-3004",
        category=ErrorCategory.LLM_PROVIDER,
        message="Invalid LLM response",
        description="The LLM provider returned an invalid or malformed response",
        http_status=502
    )
    
    LLM_QUERY_TOO_LONG = ErrorCode(
        code="NL2SQL-LLM-3005",
        category=ErrorCategory.LLM_PROVIDER,
        message="Query too long for LLM",
        description="The natural language query exceeds the LLM's maximum input length",
        http_status=400
    )
    
    LLM_CIRCUIT_BREAKER_OPEN = ErrorCode(
        code="NL2SQL-LLM-3006",
        category=ErrorCategory.LLM_PROVIDER,
        message="LLM circuit breaker is open",
        description="The LLM provider is temporarily disabled due to repeated failures",
        http_status=503,
        retryable=True
    )
    
    LLM_PROVIDER_NOT_SUPPORTED = ErrorCode(
        code="NL2SQL-LLM-3007",
        category=ErrorCategory.LLM_PROVIDER,
        message="LLM provider not supported",
        description="The requested LLM provider is not supported or configured",
        http_status=400
    )
    
    # Authentication/Authorization Errors (4000-4999) - Simplified
    AUTH_INSUFFICIENT_PERMISSIONS = ErrorCode(
        code="NL2SQL-AUTH-4002",
        category=ErrorCategory.AUTHENTICATION,
        message="Insufficient permissions",
        description="The user does not have sufficient permissions for this operation",
        http_status=403
    )
    
    # System Errors (5000-5999)
    SYS_INTERNAL_ERROR = ErrorCode(
        code="NL2SQL-SYS-5001",
        category=ErrorCategory.SYSTEM,
        message="Internal server error",
        description="An unexpected internal error occurred",
        http_status=500,
        user_friendly=False
    )
    
    SYS_CONFIGURATION_ERROR = ErrorCode(
        code="NL2SQL-SYS-5002",
        category=ErrorCategory.SYSTEM,
        message="Configuration error",
        description="The system configuration is invalid or missing required settings",
        http_status=500
    )
    
    SYS_RESOURCE_UNAVAILABLE = ErrorCode(
        code="NL2SQL-SYS-5003",
        category=ErrorCategory.SYSTEM,
        message="Resource unavailable",
        description="A required system resource is currently unavailable",
        http_status=503,
        retryable=True
    )
    
    SYS_MAINTENANCE_MODE = ErrorCode(
        code="NL2SQL-SYS-5004",
        category=ErrorCategory.SYSTEM,
        message="System maintenance",
        description="The system is currently under maintenance, please try again later",
        http_status=503,
        retryable=True
    )
    
    # Request Processing Errors (6000-6999)
    REQ_MALFORMED_REQUEST = ErrorCode(
        code="NL2SQL-REQ-6001",
        category=ErrorCategory.REQUEST,
        message="Malformed request",
        description="The request format is invalid or missing required fields",
        http_status=400
    )
    
    REQ_REQUEST_TOO_LARGE = ErrorCode(
        code="NL2SQL-REQ-6002",
        category=ErrorCategory.REQUEST,
        message="Request too large",
        description="The request payload exceeds the maximum allowed size",
        http_status=413
    )
    
    REQ_UNSUPPORTED_MEDIA_TYPE = ErrorCode(
        code="NL2SQL-REQ-6003",
        category=ErrorCategory.REQUEST,
        message="Unsupported media type",
        description="The request content type is not supported",
        http_status=415
    )
    
    REQ_TIMEOUT = ErrorCode(
        code="NL2SQL-REQ-6004",
        category=ErrorCategory.REQUEST,
        message="Request timeout",
        description="The request processing exceeded the maximum allowed time",
        http_status=408,
        retryable=True
    )


class NL2SQLError(Exception):
    """Base exception class for NL2SQL errors"""
    
    def __init__(
        self,
        error_code: ErrorCode,
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        self.error_code = error_code
        self.details = details or {}
        self.original_exception = original_exception
        super().__init__(error_code.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary format"""
        return {
            "error_code": self.error_code.code,
            "message": self.error_code.message,
            "description": self.error_code.description,
            "category": self.error_code.category.value,
            "http_status": self.error_code.http_status,
            "retryable": self.error_code.retryable,
            "details": self.details,
            "original_exception": str(self.original_exception) if self.original_exception else None
        }
    
    def to_http_exception(self) -> HTTPException:
        """Convert to FastAPI HTTPException"""
        return HTTPException(
            status_code=self.error_code.http_status,
            detail=self.to_dict()
        )


class ErrorHandler:
    """Centralized error handling utilities"""
    
    @staticmethod
    def create_error(
        error_code: ErrorCode,
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ) -> NL2SQLError:
        """Create a standardized error"""
        return NL2SQLError(error_code, details, original_exception)
    
    @staticmethod
    def handle_database_error(exception: Exception, context: str = "") -> NL2SQLError:
        """Handle database-related errors"""
        details = {"context": context, "original_error": str(exception)}
        
        if "connection" in str(exception).lower():
            return ErrorHandler.create_error(ErrorCodes.DB_CONNECTION_FAILED, details, exception)
        elif "syntax" in str(exception).lower():
            return ErrorHandler.create_error(ErrorCodes.DB_INVALID_SQL_SYNTAX, details, exception)
        elif "permission" in str(exception).lower() or "access denied" in str(exception).lower():
            return ErrorHandler.create_error(ErrorCodes.DB_PERMISSION_DENIED, details, exception)
        elif "timeout" in str(exception).lower():
            return ErrorHandler.create_error(ErrorCodes.DB_TIMEOUT, details, exception)
        else:
            return ErrorHandler.create_error(ErrorCodes.DB_QUERY_EXECUTION_FAILED, details, exception)
    
    @staticmethod
    def handle_llm_error(exception: Exception, provider: str = "") -> NL2SQLError:
        """Handle LLM provider errors"""
        details = {"provider": provider, "original_error": str(exception)}
        
        if "rate limit" in str(exception).lower():
            return ErrorHandler.create_error(ErrorCodes.LLM_API_RATE_LIMITED, details, exception)
        elif "unauthorized" in str(exception).lower() or "api key" in str(exception).lower():
            return ErrorHandler.create_error(ErrorCodes.LLM_API_KEY_MISSING, details, exception)
        elif "timeout" in str(exception).lower() or "unavailable" in str(exception).lower():
            return ErrorHandler.create_error(ErrorCodes.LLM_API_UNAVAILABLE, details, exception)
        else:
            return ErrorHandler.create_error(ErrorCodes.LLM_INVALID_RESPONSE, details, exception)
    
    @staticmethod
    def handle_validation_error(exception: Exception, context: str = "") -> NL2SQLError:
        """Handle validation errors"""
        details = {"context": context, "original_error": str(exception)}
        
        if "injection" in str(exception).lower():
            return ErrorHandler.create_error(ErrorCodes.VAL_SQL_INJECTION_DETECTED, details, exception)
        elif "scoping" in str(exception).lower():
            return ErrorHandler.create_error(ErrorCodes.VAL_INVALID_SCOPING_FILTER, details, exception)
        elif "syntax" in str(exception).lower():
            return ErrorHandler.create_error(ErrorCodes.VAL_INVALID_QUERY_FORMAT, details, exception)
        else:
            return ErrorHandler.create_error(ErrorCodes.VAL_INVALID_QUERY_FORMAT, details, exception)
    
    @staticmethod
    def get_error_by_code(code: str) -> Optional[ErrorCode]:
        """Get error code definition by code string"""
        for attr_name in dir(ErrorCodes):
            if not attr_name.startswith('_'):
                error_code = getattr(ErrorCodes, attr_name)
                if isinstance(error_code, ErrorCode) and error_code.code == code:
                    return error_code
        return None
    
    @staticmethod
    def get_errors_by_category(category: ErrorCategory) -> list[ErrorCode]:
        """Get all error codes for a specific category"""
        errors = []
        for attr_name in dir(ErrorCodes):
            if not attr_name.startswith('_'):
                error_code = getattr(ErrorCodes, attr_name)
                if isinstance(error_code, ErrorCode) and error_code.category == category:
                    errors.append(error_code)
        return errors


# Convenience functions for common error scenarios
def create_database_error(exception: Exception, context: str = "") -> NL2SQLError:
    """Create a database error"""
    return ErrorHandler.handle_database_error(exception, context)


def create_llm_error(exception: Exception, provider: str = "") -> NL2SQLError:
    """Create an LLM provider error"""
    return ErrorHandler.handle_llm_error(exception, provider)


def create_validation_error(exception: Exception, context: str = "") -> NL2SQLError:
    """Create a validation error"""
    return ErrorHandler.handle_validation_error(exception, context)


def create_system_error(exception: Exception, context: str = "") -> NL2SQLError:
    """Create a system error"""
    details = {"context": context, "original_error": str(exception)}
    return ErrorHandler.create_error(ErrorCodes.SYS_INTERNAL_ERROR, details, exception)


def create_request_error(exception: Exception, context: str = "") -> NL2SQLError:
    """Create a request processing error"""
    details = {"context": context, "original_error": str(exception)}
    return ErrorHandler.create_error(ErrorCodes.REQ_MALFORMED_REQUEST, details, exception)
