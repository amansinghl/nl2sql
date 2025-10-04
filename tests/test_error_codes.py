"""
Test cases for the error code system
"""

import pytest
from app.utils.error_codes import (
    ErrorCodes, NL2SQLError, ErrorHandler,
    create_database_error, create_llm_error, create_validation_error,
    create_system_error, create_request_error
)
from app.utils.error_responses import format_error_response


class TestErrorCodes:
    """Test error code definitions and functionality"""
    
    def test_error_code_structure(self):
        """Test that error codes have proper structure"""
        error_code = ErrorCodes.DB_CONNECTION_FAILED
        
        assert error_code.code == "NL2SQL-DB-1001"
        assert error_code.category.value == "DB"
        assert error_code.message == "Database connection failed"
        assert error_code.http_status == 503
        assert error_code.retryable is True
    
    def test_error_categories(self):
        """Test error code categories"""
        assert ErrorCodes.DB_CONNECTION_FAILED.category.value == "DB"
        assert ErrorCodes.VAL_MISSING_SCOPING_VALUE.category.value == "VAL"
        assert ErrorCodes.LLM_API_KEY_MISSING.category.value == "LLM"
        assert ErrorCodes.AUTH_INVALID_CREDENTIALS.category.value == "AUTH"
        assert ErrorCodes.SYS_INTERNAL_ERROR.category.value == "SYS"
        assert ErrorCodes.REQ_MALFORMED_REQUEST.category.value == "REQ"
    
    def test_nl2sql_error_creation(self):
        """Test NL2SQLError creation and properties"""
        error = NL2SQLError(
            ErrorCodes.VAL_MISSING_SCOPING_VALUE,
            {"query": "test query"},
            ValueError("test exception")
        )
        
        assert error.error_code == ErrorCodes.VAL_MISSING_SCOPING_VALUE
        assert error.details == {"query": "test query"}
        assert str(error.original_exception) == "test exception"
        assert str(error) == "Scoping value is required"
    
    def test_error_to_dict(self):
        """Test error to dictionary conversion"""
        error = NL2SQLError(
            ErrorCodes.DB_CONNECTION_FAILED,
            {"context": "test"}
        )
        
        error_dict = error.to_dict()
        
        assert error_dict["error_code"] == "NL2SQL-DB-1001"
        assert error_dict["message"] == "Database connection failed"
        assert error_dict["category"] == "DB"
        assert error_dict["http_status"] == 503
        assert error_dict["retryable"] is True
        assert error_dict["details"] == {"context": "test"}
    
    def test_error_to_http_exception(self):
        """Test error to HTTPException conversion"""
        error = NL2SQLError(ErrorCodes.VAL_MISSING_SCOPING_VALUE)
        http_exc = error.to_http_exception()
        
        assert http_exc.status_code == 400
        assert "Scoping value is required" in str(http_exc.detail)


class TestErrorHandlers:
    """Test error handler utilities"""
    
    def test_create_database_error(self):
        """Test database error creation"""
        original_exc = Exception("Connection failed")
        error = create_database_error(original_exc, "test_context")
        
        assert isinstance(error, NL2SQLError)
        assert error.error_code.category.value == "DB"
        assert error.details["context"] == "test_context"
        assert error.original_exception == original_exc
    
    def test_create_llm_error(self):
        """Test LLM error creation"""
        original_exc = Exception("API key missing")
        error = create_llm_error(original_exc, "openai")
        
        assert isinstance(error, NL2SQLError)
        assert error.error_code.category.value == "LLM"
        assert error.details["provider"] == "openai"
        assert error.original_exception == original_exc
    
    def test_create_validation_error(self):
        """Test validation error creation"""
        original_exc = Exception("Invalid SQL")
        error = create_validation_error(original_exc, "sql_validation")
        
        assert isinstance(error, NL2SQLError)
        assert error.error_code.category.value == "VAL"
        assert error.details["context"] == "sql_validation"
        assert error.original_exception == original_exc
    
    def test_create_system_error(self):
        """Test system error creation"""
        original_exc = Exception("Unexpected error")
        error = create_system_error(original_exc, "test_context")
        
        assert isinstance(error, NL2SQLError)
        assert error.error_code.category.value == "SYS"
        assert error.details["context"] == "test_context"
        assert error.original_exception == original_exc
    
    def test_create_request_error(self):
        """Test request error creation"""
        original_exc = Exception("Malformed request")
        error = create_request_error(original_exc, "test_context")
        
        assert isinstance(error, NL2SQLError)
        assert error.error_code.category.value == "REQ"
        assert error.details["context"] == "test_context"
        assert error.original_exception == original_exc


class TestErrorResponseFormatting:
    """Test error response formatting"""
    
    def test_format_error_response(self):
        """Test error response formatting"""
        error = NL2SQLError(
            ErrorCodes.VAL_MISSING_SCOPING_VALUE,
            {"query": "test query"}
        )
        
        # Mock request object
        class MockRequest:
            class State:
                request_id = "test_req_123"
            state = State()
        
        request = MockRequest()
        response = format_error_response(error, request)
        
        assert response.status_code == 400
        content = response.body.decode()
        assert "NL2SQL-VAL-2002" in content
        assert "Scoping value is required" in content
        assert "test_req_123" in content
    
    def test_format_error_response_includes_error_field(self):
        """Test that error response includes error field for UI compatibility"""
        error = NL2SQLError(
            ErrorCodes.DB_CONNECTION_FAILED,
            {"context": "test"}
        )
        
        # Mock request object
        class MockRequest:
            class State:
                request_id = "test_req_456"
            state = State()
        
        request = MockRequest()
        response = format_error_response(error, request)
        
        assert response.status_code == 503
        content = response.body.decode()
        
        # Check that both error_code and error fields are present
        assert "error_code" in content
        assert "error" in content
        assert "NL2SQL-DB-1001" in content
        assert "Database connection failed" in content
        assert "test_req_456" in content


class TestErrorCodeLookup:
    """Test error code lookup functionality"""
    
    def test_get_error_by_code(self):
        """Test getting error code by code string"""
        error_code = ErrorHandler.get_error_by_code("NL2SQL-DB-1001")
        
        assert error_code is not None
        assert error_code.code == "NL2SQL-DB-1001"
        assert error_code.message == "Database connection failed"
    
    def test_get_error_by_invalid_code(self):
        """Test getting error code with invalid code"""
        error_code = ErrorHandler.get_error_by_code("INVALID-CODE")
        
        assert error_code is None
    
    def test_get_errors_by_category(self):
        """Test getting errors by category"""
        from app.utils.error_codes import ErrorCategory
        
        db_errors = ErrorHandler.get_errors_by_category(ErrorCategory.DATABASE)
        
        assert len(db_errors) > 0
        assert all(error.category == ErrorCategory.DATABASE for error in db_errors)
        
        # Check that we have some expected DB errors
        error_codes = [error.code for error in db_errors]
        assert "NL2SQL-DB-1001" in error_codes
        assert "NL2SQL-DB-1002" in error_codes


if __name__ == "__main__":
    pytest.main([__file__])
