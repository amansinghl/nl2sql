import os
import json
from typing import Dict, List, Optional, Any
from pydantic_settings import BaseSettings
from pydantic import Field, validator
from dotenv import load_dotenv

load_dotenv()

class SecurityConfig(BaseSettings):
    """Security and scoping configuration"""
    SCOPING_COLUMN: str = Field(default="accounts_entity_id", description="Default column name for data scoping")
    SCOPING_VALUE_SOURCE: str = Field(default="request", description="Source of scoping value: request, user_context")
    SCOPING_VALUE_FIELD: str = Field(default="scoping_value", description="Field name in request containing scoping value")
    ENABLE_AUTO_SCOPING: bool = Field(default=True, description="Enable automatic scoping for scoped tables")
    CUSTOM_VALIDATION_RULES: str = Field(default="{}", description="Custom validation rules as JSON string")
    
    # Multi-Role Access Control
    ENABLE_MULTI_ROLE_ACCESS: bool = Field(default=True, description="Enable multi-role access control system")
    DEFAULT_USER_ROLE: str = Field(default="customer", description="Default user role when not specified")
    
    # Role Definitions
    ROLES_CONFIG: str = Field(default='{"customer": {"requires_scoping": true, "access_pattern": "single_entity", "description": "Customer access limited to their entity"}, "admin": {"requires_scoping": false, "access_pattern": "all_entities", "can_scope_to_specific": true, "bypass_validation": true, "description": "Admin access to all entities with full privileges"}}', description="Role configuration as JSON")
    
    # Access Control Policies
    ENABLE_ACCESS_LOGGING: bool = Field(default=True, description="Enable access logging for audit purposes")
    ENABLE_QUERY_LOGGING: bool = Field(default=True, description="Enable detailed query/SQL logging for analytics")
    QUERY_LOG_FILE: str = Field(default="logs/query_events.jsonl", description="Path to JSONL file where query events are logged")
    ACCESS_LOG_FILE: str = Field(default="logs/access_audit.jsonl", description="Path to JSONL file where access audit events are logged")
    LOG_BACKUP_COUNT: int = Field(default=14, description="How many daily log files to keep before rotation cleanup")
    
    # Security Policies
    MAX_ENTITIES_PER_QUERY: int = Field(default=10, description="Maximum number of entities that can be queried in a single request")
    ENABLE_CROSS_ENTITY_QUERIES: bool = Field(default=False, description="Allow queries that span multiple entities")
    DEFAULT_LIMIT: int = Field(default=10, description="Default LIMIT for queries that don't specify one")
    
    @validator('CUSTOM_VALIDATION_RULES')
    def validate_custom_rules(cls, v):
        try:
            json.loads(v)
            return v
        except json.JSONDecodeError:
            return "{}"
    
    @validator('ROLES_CONFIG')
    def validate_roles_config(cls, v):
        try:
            roles = json.loads(v)
            # Validate required role structure
            for role_name, role_config in roles.items():
                if not isinstance(role_config, dict):
                    raise ValueError(f"Role {role_name} must be a dictionary")
                required_fields = ['requires_scoping', 'access_pattern', 'description']
                for field in required_fields:
                    if field not in role_config:
                        raise ValueError(f"Role {role_name} missing required field: {field}")
            return v
        except json.JSONDecodeError:
            return '{"customer": {"requires_scoping": true, "access_pattern": "single_entity", "description": "Customer access"}}'
    
    
    def get_custom_rules(self) -> Dict[str, Any]:
        """Get parsed custom validation rules"""
        try:
            return json.loads(self.CUSTOM_VALIDATION_RULES)
        except json.JSONDecodeError:
            return {}
    
    def get_roles_config(self) -> Dict[str, Any]:
        """Get parsed roles configuration"""
        try:
            return json.loads(self.ROLES_CONFIG)
        except json.JSONDecodeError:
            return {"customer": {"requires_scoping": True, "access_pattern": "single_entity", "description": "Customer access"}}
    
    
    def get_role_config(self, role: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific role"""
        roles = self.get_roles_config()
        return roles.get(role)
    
    def is_role_allowed(self, role: str) -> bool:
        """Check if a role is allowed"""
        roles = self.get_roles_config()
        return role in roles
    
    def requires_scoping(self, role: str) -> bool:
        """Check if a role requires scoping"""
        role_config = self.get_role_config(role)
        return role_config.get('requires_scoping', True) if role_config else True
    
    def can_access_all_entities(self, role: str) -> bool:
        """Check if a role can access all entities"""
        role_config = self.get_role_config(role)
        return role_config.get('access_pattern') == 'all_entities' if role_config else False
    
    def can_scope_to_specific(self, role: str) -> bool:
        """Check if a role can scope to specific entities"""
        role_config = self.get_role_config(role)
        return role_config.get('can_scope_to_specific', False) if role_config else False
    
    def can_bypass_validation(self, role: str) -> bool:
        """Check if a role can bypass validation"""
        role_config = self.get_role_config(role)
        return role_config.get('bypass_validation', False) if role_config else False
    
    class Config:
        env_prefix = "SECURITY_"

class LLMProviderConfig(BaseSettings):
    """Configuration for a specific LLM provider"""
    provider_type: str = Field(..., description="Type of LLM provider (openai, anthropic, google, custom)")
    api_key: Optional[str] = Field(None, description="API key for the provider")
    base_url: Optional[str] = Field(None, description="Base URL for the API")
    model: str = Field(..., description="Model name to use")
    temperature: float = Field(0.1, description="Temperature for generation")
    max_tokens: int = Field(1024, description="Maximum tokens to generate")
    timeout: int = Field(60, description="Request timeout in seconds")
    
    class Config:
        env_prefix = ""

class Settings(BaseSettings):
    # Database Configuration
    DB_URL: str = os.getenv("DB_URL", "mysql+pymysql://readonly:pass@localhost:3306/prod")
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    
    # Security Configuration
    security: SecurityConfig = SecurityConfig()
    
    # LLM Configuration
    DEFAULT_LLM_PROVIDER: str = os.getenv("DEFAULT_LLM_PROVIDER", "openai")
    
    # OpenAI Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    OPENAI_TEMPERATURE: float = float(os.getenv("OPENAI_TEMPERATURE", "0.0"))
    OPENAI_MAX_TOKENS: int = int(os.getenv("OPENAI_MAX_TOKENS", "2000"))
    OPENAI_TIMEOUT: int = int(os.getenv("OPENAI_TIMEOUT", "120"))
    
    # Anthropic Configuration
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-3-sonnet-20240229")
    ANTHROPIC_TEMPERATURE: float = float(os.getenv("ANTHROPIC_TEMPERATURE", "0.0"))
    ANTHROPIC_MAX_TOKENS: int = int(os.getenv("ANTHROPIC_MAX_TOKENS", "512"))
    ANTHROPIC_TIMEOUT: int = int(os.getenv("ANTHROPIC_TIMEOUT", "120"))
    
    # Google Configuration
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    GOOGLE_MODEL: str = os.getenv("GOOGLE_MODEL", "gemini-pro")
    GOOGLE_TEMPERATURE: float = float(os.getenv("GOOGLE_TEMPERATURE", "0.0"))
    GOOGLE_MAX_TOKENS: int = int(os.getenv("GOOGLE_MAX_TOKENS", "512"))
    GOOGLE_TIMEOUT: int = int(os.getenv("GOOGLE_TIMEOUT", "120"))
    
    # Custom LLM Configuration
    CUSTOM_LLM_BASE_URL: str = os.getenv("CUSTOM_LLM_BASE_URL", "")
    CUSTOM_LLM_MODEL: str = os.getenv("CUSTOM_LLM_MODEL", "")
    CUSTOM_LLM_API_KEY: str = os.getenv("CUSTOM_LLM_API_KEY", "")
    CUSTOM_LLM_TEMPERATURE: float = float(os.getenv("CUSTOM_LLM_TEMPERATURE", "0.0"))
    CUSTOM_LLM_MAX_TOKENS: int = int(os.getenv("CUSTOM_LLM_MAX_TOKENS", "512"))
    CUSTOM_LLM_TIMEOUT: int = int(os.getenv("CUSTOM_LLM_TIMEOUT", "120"))
    
    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_WORKERS: int = 1
    
    # Security Configuration (simplified)
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    
    # Prompt configuration
    PROMPT_SQL_RULES_HEADER: str = (
        "You are an expert SQL generator for MySQL. Output only valid SQL, no explanations.\n\n"
        "Rules:\n"
        "1) Use ONLY the tables listed under 'Relevant Tables'. Do not invent tables/columns.\n"
        "2) Prefer core tables over relationship/mapping tables unless necessary.\n"
        "3) If the query can be answered from a single table, DO NOT include any JOINs.\n"
        "4) When joining, follow the 'Key Relationships' exactly (columns and directions).\n"
        "5) If the question asks 'how many' or 'count', return a single COUNT(*) (or COUNT(DISTINCT col) when needed) and do NOT select non-aggregated columns.\n"
        "6) If a table is scoped in the schema, filter by the correct scoping column using the scoping value.\n"
        "7) Use correct status code values from mappings (e.g., tracking_status = '1900' for Delivered).\n"
        "8) MySQL only. Use DATE_SUB()/DATE_ADD(), CURDATE(), proper GROUP BY, etc.\n"
        "9) Keep it minimal and readable. Add ORDER BY if it makes sense. LIMIT large result sets (auto-limited to 10 if missing).\n"
    )
    
    # Generation feedback
    ENABLE_DB_FEEDBACK_LOOP: bool = bool(int(os.getenv("ENABLE_DB_FEEDBACK_LOOP", "1")))
    PROMPT_SQL_FEW_SHOTS: str = os.getenv(
        "PROMPT_SQL_FEW_SHOTS",
        (
            "Examples:\n"
            "Q: delivered shipments count\n"
            "SQL: SELECT COUNT(*) AS delivered_count FROM shipments WHERE tracking_status = '1900';\n\n"
            "Q: shipments by supplier name\n"
            "SQL: SELECT s.name, COUNT(sh.id) AS shipment_count FROM shipments sh JOIN suppliers s ON sh.supplier_id = s.id GROUP BY s.name;\n\n"
            "Q: revenue by day last 14 days\n"
            "SQL: SELECT DATE(shipment_date) AS day, SUM(total_price) AS revenue FROM shipments WHERE shipment_date >= DATE_SUB(CURDATE(), INTERVAL 14 DAY) GROUP BY DATE(shipment_date) ORDER BY day DESC;\n"
            "Q: Top 10 customers by orders this month\n"
            "SQL: SELECT customer_id, COUNT(*) AS orders_count FROM orders WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 1 MONTH) GROUP BY customer_id ORDER BY orders_count DESC LIMIT 10;\n"
        )   
    )
    
    # Plan-then-generate prompts
    PROMPT_PLAN_HEADER: str = (
        "You are an expert SQL planner. Given a user question and a focused schema, "
        "produce a minimal JSON plan with these keys only: \n"
        "{\"tables\": [str], \"columns\": {table: [str]}, \"joins\": [{\"from_table\": str, \"from_column\": str, \"to_table\": str, \"to_column\": str, \"type\": \"INNER|LEFT\"}], \"filters\": [str], \"group_by\": [str], \"order_by\": [str], \"limit\": int|null, \"needs_scoping\": bool, \"scoping_columns_used\": [str]}\n"
        "Rules: Use ONLY tables and columns present in the schema. Derive joins from 'Key Relationships'. "
        "For non-count questions, explicitly list the exact columns to SELECT per table in 'columns' (no placeholders). "
        "For count questions ('how many', 'count'), set columns to {} and group_by to []. "
        "Set needs_scoping=true if any used table is scoped. Prefer a single table when sufficient. Return ONLY JSON."
    )
    PROMPT_SQL_FROM_PLAN_HEADER: str = (
        "You are an expert SQL generator for MySQL. Generate SQL strictly from the provided plan. "
        "Use MySQL syntax; follow joins, filters, GROUP BY, ORDER BY exactly. "
        "SELECT must include exactly and only the columns specified in plan.columns (qualified or aliased as needed). "
        "If plan.columns is {}, generate a COUNT(*) query. Do NOT add or remove columns beyond the plan. "
        "If scoping is required, ensure the WHERE includes the correct scoping column with the given value. Output ONLY SQL."
    )
    
    # Explanation generation configuration
    EXPLANATION_SYSTEM_MESSAGE: str = os.getenv(
        "EXPLANATION_SYSTEM_MESSAGE",
        "You write concise, user-facing summaries (1-3 sentences) that directly answer the question based on the returned rows. No SQL or schema talk."
    )
    EXPLANATION_MAX_TOKENS: int = int(os.getenv("EXPLANATION_MAX_TOKENS", "400"))
    EXPLANATION_TEMPERATURE: float = float(os.getenv("EXPLANATION_TEMPERATURE", "0.2"))
    EXPLANATION_ENABLE_ROWS_PREVIEW: bool = bool(int(os.getenv("EXPLANATION_ENABLE_ROWS_PREVIEW", "1")))
    EXPLANATION_PROMPT_HEADER: str = os.getenv(
        "EXPLANATION_PROMPT_HEADER",
        "You are a data analyst. Write a brief answer for the end user based on the returned rows."
    )
    EXPLANATION_PROMPT_CONSTRAINTS: str = os.getenv(
        "EXPLANATION_PROMPT_CONSTRAINTS",
        "Constraints:\n- 1 to 3 sentences.\n- Focus on the user's question and key findings.\n- No SQL, no schema explanations, no steps.\n- If no results, state that clearly and suggest a concise next step.\n"
    )
    
    class Config:
        env_file = ".env"
    
    def get_llm_config(self, provider: str = None) -> LLMProviderConfig:
        """Get configuration for a specific LLM provider"""
        if provider is None:
            provider = self.DEFAULT_LLM_PROVIDER
        
        provider = provider.lower()
        
        if provider == "openai":
            return LLMProviderConfig(
                provider_type="openai",
                api_key=self.OPENAI_API_KEY,
                base_url=self.OPENAI_BASE_URL,
                model=self.OPENAI_MODEL,
                temperature=self.OPENAI_TEMPERATURE,
                max_tokens=self.OPENAI_MAX_TOKENS,
                timeout=self.OPENAI_TIMEOUT
            )
        elif provider == "anthropic":
            return LLMProviderConfig(
                provider_type="anthropic",
                api_key=self.ANTHROPIC_API_KEY,
                model=self.ANTHROPIC_MODEL,
                temperature=self.ANTHROPIC_TEMPERATURE,
                max_tokens=self.ANTHROPIC_MAX_TOKENS,
                timeout=self.ANTHROPIC_TIMEOUT
            )
        elif provider == "google":
            return LLMProviderConfig(
                provider_type="google",
                api_key=self.GOOGLE_API_KEY,
                model=self.GOOGLE_MODEL,
                temperature=self.GOOGLE_TEMPERATURE,
                max_tokens=self.GOOGLE_MAX_TOKENS,
                timeout=self.GOOGLE_TIMEOUT
            )
        elif provider == "custom":
            return LLMProviderConfig(
                provider_type="custom",
                api_key=self.CUSTOM_LLM_API_KEY,
                base_url=self.CUSTOM_LLM_BASE_URL,
                model=self.CUSTOM_LLM_MODEL,
                temperature=self.CUSTOM_LLM_TEMPERATURE,
                max_tokens=self.CUSTOM_LLM_MAX_TOKENS,
                timeout=self.CUSTOM_LLM_TIMEOUT
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
    
    def get_available_providers(self) -> List[str]:
        """Get list of available LLM providers based on configuration"""
        providers = []
        
        if self.OPENAI_API_KEY:
            providers.append("openai")
        if self.ANTHROPIC_API_KEY:
            providers.append("anthropic")
        if self.GOOGLE_API_KEY:
            providers.append("google")
        if self.CUSTOM_LLM_BASE_URL and self.CUSTOM_LLM_MODEL:
            providers.append("custom")
        
        return providers
    
    def get_scoped_tables(self, schema_graph=None) -> Dict[str, str]:
        """Dynamically get scoped tables from schema graph"""
        if schema_graph is None:
            # Fallback to hardcoded configuration for backward compatibility
            return {
                "shipments": "scoping_column",
                "orders": "scoping_column", 
                "customers": "scoping_column",
                "inventory": "scoping_column",
                "products": "scoping_column"
            }
        
        scoped_tables = {}
        for table_name, table_info in schema_graph.tables.items():
            if table_info.get('scoped', False):
                scoping_column = table_info.get('scoping_column', self.security.SCOPING_COLUMN)
                scoped_tables[table_name] = scoping_column
        return scoped_tables

# Graph schema file path
SCHEMA_GRAPH_PATH = "./graph/schema_graph.json"

settings = Settings()


