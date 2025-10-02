import httpx
from typing import List, Dict, Optional, Any
from abc import ABC, abstractmethod
from .config import LLMProviderConfig, settings

class BaseLLMProvider(ABC):
    """Base class for LLM providers"""
    
    def __init__(self, config: LLMProviderConfig):
        self.config = config
        self.client = httpx.AsyncClient(timeout=config.timeout)
    
    @abstractmethod
    async def generate_sql(self, user_query: str, scoping_value: str, relevant_tables: List[str], schema_description: str) -> str:
        """Generate SQL from natural language query"""
        pass
    
    @abstractmethod
    async def explain_results(self, query: str, results: List[Dict], row_count: int) -> str:
        """Generate natural language explanation of results"""
        pass
    
    # New: plan-then-generate
    @abstractmethod
    async def generate_plan(self, user_query: str, relevant_tables: List[str], schema_description: str, scoping_required: bool) -> str:
        """Generate a JSON plan string from the question and schema."""
        pass
    
    @abstractmethod
    async def generate_sql_from_plan(self, plan_json: str, scoping_value: Optional[str]) -> str:
        """Generate SQL strictly from a given JSON plan string."""
        pass
    
    def build_sql_prompt(self, user_query: str, scoping_value: str, relevant_tables: List[str], schema_description: str) -> str:
        """Build the prompt for SQL generation (config-driven)."""
        relevant_tables_text = "\n".join(f"- {t}" for t in relevant_tables) if relevant_tables else "- (none)"
        header = settings.PROMPT_SQL_RULES_HEADER
        few_shots = settings.PROMPT_SQL_FEW_SHOTS
        return (
            f"{header}\n"
            f"Database Schema (focused):\n{schema_description}\n\n"
            f"Scoping Value: {scoping_value if scoping_value else 'Not required'}\n"
            f"Relevant Tables:\n{relevant_tables_text}\n\n"
            f"{few_shots}\n"
            f"Generate SQL for: \"{user_query}\"\n\n"
            f"SQL:"
        )
    
    def build_plan_prompt(self, user_query: str, relevant_tables: List[str], schema_description: str, scoping_required: bool) -> str:
        relevant_tables_text = "\n".join(f"- {t}" for t in relevant_tables) if relevant_tables else "- (none)"
        header = settings.PROMPT_PLAN_HEADER
        scope_line = f"Scoping Required: {str(scoping_required).lower()}\n"
        return (
            f"{header}\n"
            f"Database Schema (focused):\n{schema_description}\n\n"
            f"{scope_line}"
            f"Relevant Tables:\n{relevant_tables_text}\n\n"
            f"Question: {user_query}\n\n"
            f"JSON Plan:"
        )
    
    def build_sql_from_plan_prompt(self, plan_json: str, scoping_value: Optional[str]) -> str:
        header = settings.PROMPT_SQL_FROM_PLAN_HEADER
        return (
            f"{header}\n"
            f"Scoping Value: {scoping_value if scoping_value else 'Not required'}\n\n"
            f"Plan JSON:\n{plan_json}\n\n"
            f"SQL:"
        )
    
    def build_explanation_prompt(self, user_query: str, results: List[Dict], row_count: int) -> str:
        """Build a concise, query-focused explanation prompt for LLMs.
        The explanation MUST:
        - Directly answer the user's question in 1-3 sentences
        - Reference the query intent, not the SQL or schema
        - Summarize notable patterns/aggregates only if helpful
        - Avoid filler like "the query returns" or restating columns
        - If no rows: explain that succinctly
        """
        preview_rows = results[:3] if results else []
        import json
        rows_preview_text = json.dumps(preview_rows, ensure_ascii=False, default=str)
        header = settings.EXPLANATION_PROMPT_HEADER
        constraints = settings.EXPLANATION_PROMPT_CONSTRAINTS
        rows_section = (
            f"Sample rows (first 3): {rows_preview_text}\n\n" if settings.EXPLANATION_ENABLE_ROWS_PREVIEW else ""
        )
        return (
            f"{header}\n"
            f"{constraints}\n"
            f"User question: {user_query}\n"
            f"Row count: {row_count}\n"
            f"{rows_section}"
            "Answer:"
        )
    
    def _clean_sql(self, sql: str) -> str:
        """Clean and format the generated SQL"""
        # Remove markdown code blocks if present
        if sql.startswith("```sql"):
            sql = sql[6:]
        if sql.startswith("```"):
            sql = sql[3:]
        if sql.endswith("```"):
            sql = sql[:-3]
        
        # Remove leading/trailing whitespace
        sql = sql.strip()
        
        # Ensure it ends with semicolon
        if not sql.endswith(';'):
            sql += ';'
        
        return sql
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

class OpenAIProvider(BaseLLMProvider):
    """OpenAI LLM provider"""
    
    async def generate_sql(self, user_query: str, scoping_value: str, relevant_tables: List[str], schema_description: str) -> str:
        """Generate SQL using OpenAI"""
        try:
            prompt = self.build_sql_prompt(user_query, scoping_value, relevant_tables, schema_description)
            
            headers = {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.config.model,
                "messages": [
                    {"role": "system", "content": "You are an expert SQL generator. Generate only the SQL query, no explanations."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature
            }
            
            response = await self.client.post(
                f"{self.config.base_url}/chat/completions",
                headers=headers,
                json=data
            )
            
            if response.status_code != 200:
                raise Exception(f"OpenAI API error: {response.status_code} - {response.text}")
            
            try:
                result = response.json()
                sql = result['choices'][0]['message']['content'].strip()
                sql = self._clean_sql(sql)
                return sql
            except Exception as parse_err:
                # Attach a short preview of the raw payload for debugging
                raw_preview = response.text[:500] if hasattr(response, 'text') else ''
                raise Exception(f"OpenAI parse error: {parse_err}. Raw preview: {raw_preview}")
        except Exception:
            raise
    
    async def explain_results(self, query: str, results: List[Dict], row_count: int) -> str:
        """Generate explanation using OpenAI"""
        try:
            prompt = self.build_explanation_prompt(query, results, row_count)
            
            headers = {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.config.model,
                "messages": [
                    {"role": "system", "content": settings.EXPLANATION_SYSTEM_MESSAGE},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": settings.EXPLANATION_MAX_TOKENS,
                "temperature": settings.EXPLANATION_TEMPERATURE
            }
            
            response = await self.client.post(
                f"{self.config.base_url}/chat/completions",
                headers=headers,
                json=data
            )
            
            if response.status_code != 200:
                raise Exception(f"OpenAI API error: {response.status_code} - {response.text}")
            
            result = response.json()
            return result['choices'][0]['message']['content'].strip()
        except Exception:
            return f"Query returned {row_count} results."
    
    async def generate_plan(self, user_query: str, relevant_tables: List[str], schema_description: str, scoping_required: bool) -> str:
        try:
            prompt = self.build_plan_prompt(user_query, relevant_tables, schema_description, scoping_required)
            headers = {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json"
            }
            data = {
                "model": self.config.model,
                "messages": [
                    {"role": "system", "content": "You are an expert SQL planner. Output JSON only."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": min(600, self.config.max_tokens),
                "temperature": 0.0
            }
            response = await self.client.post(
                f"{self.config.base_url}/chat/completions",
                headers=headers,
                json=data
            )
            if response.status_code != 200:
                raise Exception(f"OpenAI API error: {response.status_code} - {response.text}")
            result = response.json()
            return result['choices'][0]['message']['content'].strip()
        except Exception:
            raise
    
    async def generate_sql_from_plan(self, plan_json: str, scoping_value: Optional[str]) -> str:
        try:
            prompt = self.build_sql_from_plan_prompt(plan_json, scoping_value)
            headers = {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json"
            }
            data = {
                "model": self.config.model,
                "messages": [
                    {"role": "system", "content": "You are an expert SQL generator. Generate only the SQL query, no explanations."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature
            }
            response = await self.client.post(
                f"{self.config.base_url}/chat/completions",
                headers=headers,
                json=data
            )
            if response.status_code != 200:
                raise Exception(f"OpenAI API error: {response.status_code} - {response.text}")
            try:
                result = response.json()
                sql = result['choices'][0]['message']['content'].strip()
                return self._clean_sql(sql)
            except Exception as parse_err:
                raw_preview = response.text[:500] if hasattr(response, 'text') else ''
                raise Exception(f"OpenAI parse error (sql_from_plan): {parse_err}. Raw preview: {raw_preview}")
        except Exception:
            raise

class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude LLM provider"""
    
    async def generate_sql(self, user_query: str, scoping_value: str, relevant_tables: List[str], schema_description: str) -> str:
        """Generate SQL using Anthropic Claude"""
        try:
            prompt = self.build_sql_prompt(user_query, scoping_value, relevant_tables, schema_description)
            
            headers = {
                "x-api-key": self.config.api_key,
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01"
            }
            
            data = {
                "model": self.config.model,
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
            
            response = await self.client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=data
            )
            
            if response.status_code != 200:
                raise Exception(f"Anthropic API error: {response.status_code} - {response.text}")
            
            result = response.json()
            sql = result['content'][0]['text'].strip()
            sql = self._clean_sql(sql)
            
            # Generated SQL for query
            
            return sql
            
        except Exception as e:
            # Error generating SQL with Anthropic
            raise
    
    async def explain_results(self, query: str, results: List[Dict], row_count: int) -> str:
        """Generate explanation using Anthropic Claude"""
        try:
            prompt = self.build_explanation_prompt(query, results, row_count)
            
            headers = {
                "x-api-key": self.config.api_key,
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01"
            }
            
            data = {
                "model": self.config.model,
                "max_tokens": settings.EXPLANATION_MAX_TOKENS,
                "temperature": settings.EXPLANATION_TEMPERATURE,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
            
            response = await self.client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=data
            )
            
            if response.status_code != 200:
                raise Exception(f"Anthropic API error: {response.status_code} - {response.text}")
            
            result = response.json()
            explanation = result['content'][0]['text'].strip()
            return explanation
            
        except Exception as e:
            # Error generating explanation with Anthropic
            return f"Query returned {row_count} results."

    async def generate_plan(self, user_query: str, relevant_tables: List[str], schema_description: str, scoping_required: bool) -> str:
        try:
            prompt = self.build_plan_prompt(user_query, relevant_tables, schema_description, scoping_required)
            headers = {
                "x-api-key": self.config.api_key,
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01"
            }
            data = {
                "model": self.config.model,
                "max_tokens": min(600, self.config.max_tokens),
                "temperature": 0.0,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
            response = await self.client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=data
            )
            if response.status_code != 200:
                raise Exception(f"Anthropic API error: {response.status_code} - {response.text}")
            result = response.json()
            return result['content'][0]['text'].strip()
        except Exception:
            raise

    async def generate_sql_from_plan(self, plan_json: str, scoping_value: Optional[str]) -> str:
        try:
            prompt = self.build_sql_from_plan_prompt(plan_json, scoping_value)
            headers = {
                "x-api-key": self.config.api_key,
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01"
            }
            data = {
                "model": self.config.model,
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
            response = await self.client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=data
            )
            if response.status_code != 200:
                raise Exception(f"Anthropic API error: {response.status_code} - {response.text}")
            result = response.json()
            return self._clean_sql(result['content'][0]['text'].strip())
        except Exception:
            raise

class GoogleProvider(BaseLLMProvider):
    """Google Gemini LLM provider"""
    
    async def generate_sql(self, user_query: str, scoping_value: str, relevant_tables: List[str], schema_description: str) -> str:
        """Generate SQL using Google Gemini"""
        try:
            prompt = self.build_sql_prompt(user_query, scoping_value, relevant_tables, schema_description)
            
            headers = {
                "Content-Type": "application/json"
            }
            
            data = {
                "contents": [
                    {
                        "parts": [
                            {"text": "You are an expert SQL generator. Generate only the SQL query, no explanations."},
                            {"text": prompt}
                        ]
                    }
                ],
                "generationConfig": {
                    "maxOutputTokens": self.config.max_tokens,
                    "temperature": self.config.temperature,
                    "stopSequences": ["\n\n", "Human:", "Assistant:"]
                }
            }
            
            response = await self.client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{self.config.model}:generateContent?key={self.config.api_key}",
                headers=headers,
                json=data
            )
            
            if response.status_code != 200:
                raise Exception(f"Google API error: {response.status_code} - {response.text}")
            
            result = response.json()
            sql = result['candidates'][0]['content']['parts'][0]['text'].strip()
            sql = self._clean_sql(sql)
            
            # Generated SQL for query
            
            return sql
            
        except Exception as e:
            # Error generating SQL with Google
            raise
    
    async def explain_results(self, query: str, results: List[Dict], row_count: int) -> str:
        """Generate explanation using Google Gemini"""
        try:
            prompt = self.build_explanation_prompt(query, results, row_count)
            
            headers = {
                "Content-Type": "application/json"
            }
            
            data = {
                "contents": [
                    {
                        "parts": [
                            {"text": settings.EXPLANATION_SYSTEM_MESSAGE},
                            {"text": prompt}
                        ]
                    }
                ],
                "generationConfig": {
                    "maxOutputTokens": settings.EXPLANATION_MAX_TOKENS,
                    "temperature": settings.EXPLANATION_TEMPERATURE,
                    "stopSequences": ["\n\n", "Human:", "Assistant:"]
                }
            }
            
            response = await self.client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{self.config.model}:generateContent?key={self.config.api_key}",
                headers=headers,
                json=data
            )
            
            if response.status_code != 200:
                raise Exception(f"Google API error: {response.status_code} - {response.text}")
            
            result = response.json()
            explanation = result['candidates'][0]['content']['parts'][0]['text'].strip()
            return explanation
            
        except Exception as e:
            # Error generating explanation with Google
            return f"Query returned {row_count} results."

    async def generate_plan(self, user_query: str, relevant_tables: List[str], schema_description: str, scoping_required: bool) -> str:
        try:
            prompt = self.build_plan_prompt(user_query, relevant_tables, schema_description, scoping_required)
            headers = {"Content-Type": "application/json"}
            data = {
                "contents": [
                    {"parts": [{"text": "You are an expert SQL planner. Output JSON only."}, {"text": prompt}]}
                ],
                "generationConfig": {
                    "maxOutputTokens": min(600, self.config.max_tokens),
                    "temperature": 0.0
                }
            }
            response = await self.client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{self.config.model}:generateContent?key={self.config.api_key}",
                headers=headers,
                json=data
            )
            if response.status_code != 200:
                raise Exception(f"Google API error: {response.status_code} - {response.text}")
            result = response.json()
            return result['candidates'][0]['content']['parts'][0]['text'].strip()
        except Exception:
            raise

    async def generate_sql_from_plan(self, plan_json: str, scoping_value: Optional[str]) -> str:
        try:
            prompt = self.build_sql_from_plan_prompt(plan_json, scoping_value)
            headers = {"Content-Type": "application/json"}
            data = {
                "contents": [
                    {"parts": [{"text": "You are an expert SQL generator. Output SQL only."}, {"text": prompt}]}
                ],
                "generationConfig": {
                    "maxOutputTokens": self.config.max_tokens,
                    "temperature": self.config.temperature
                }
            }
            response = await self.client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{self.config.model}:generateContent?key={self.config.api_key}",
                headers=headers,
                json=data
            )
            if response.status_code != 200:
                raise Exception(f"Google API error: {response.status_code} - {response.text}")
            result = response.json()
            return self._clean_sql(result['candidates'][0]['content']['parts'][0]['text'].strip())
        except Exception:
            raise

class CustomProvider(BaseLLMProvider):
    """Custom LLM provider for self-hosted models"""
    
    async def generate_sql(self, user_query: str, scoping_value: str, relevant_tables: List[str], schema_description: str) -> str:
        """Generate SQL using custom LLM endpoint"""
        try:
            prompt = self.build_sql_prompt(user_query, scoping_value, relevant_tables, schema_description)
            
            headers = {"Content-Type": "application/json"}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
            
            data = {
                "model": self.config.model,
                "messages": [
                    {"role": "system", "content": "You are an expert SQL generator. Generate only the SQL query, no explanations."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature,
                "stop": ["\n\n", "Human:", "Assistant:"]
            }
            
            response = await self.client.post(
                f"{self.config.base_url}/chat/completions",
                headers=headers,
                json=data
            )
            
            if response.status_code != 200:
                raise Exception(f"Custom LLM API error: {response.status_code} - {response.text}")
            
            result = response.json()
            sql = result['choices'][0]['message']['content'].strip()
            sql = self._clean_sql(sql)
            
            # Generated SQL for query
            
            return sql
            
        except Exception as e:
            # Error generating SQL with custom LLM
            raise
    
    async def explain_results(self, query: str, results: List[Dict], row_count: int) -> str:
        """Generate explanation using custom LLM endpoint"""
        try:
            prompt = self.build_explanation_prompt(query, results, row_count)
            
            headers = {"Content-Type": "application/json"}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
            
            data = {
                "model": self.config.model,
                "messages": [
                    {"role": "system", "content": settings.EXPLANATION_SYSTEM_MESSAGE},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": settings.EXPLANATION_MAX_TOKENS,
                "temperature": settings.EXPLANATION_TEMPERATURE,
                "stop": ["\n\n", "Human:", "Assistant:"]
            }
            
            response = await self.client.post(
                f"{self.config.base_url}/chat/completions",
                headers=headers,
                json=data
            )
            
            if response.status_code != 200:
                raise Exception(f"Custom LLM API error: {response.status_code} - {response.text}")
            
            result = response.json()
            explanation = result['choices'][0]['message']['content'].strip()
            return explanation
            
        except Exception as e:
            # Error generating explanation with custom LLM
            return f"Query returned {row_count} results."

    async def generate_plan(self, user_query: str, relevant_tables: List[str], schema_description: str, scoping_required: bool) -> str:
        try:
            prompt = self.build_plan_prompt(user_query, relevant_tables, schema_description, scoping_required)
            headers = {"Content-Type": "application/json"}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
            data = {
                "model": self.config.model,
                "messages": [
                    {"role": "system", "content": "You are an expert SQL planner. Output JSON only."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": min(600, self.config.max_tokens),
                "temperature": 0.0
            }
            response = await self.client.post(
                f"{self.config.base_url}/chat/completions",
                headers=headers,
                json=data
            )
            if response.status_code != 200:
                raise Exception(f"Custom LLM API error: {response.status_code} - {response.text}")
            result = response.json()
            return result['choices'][0]['message']['content'].strip()
        except Exception:
            raise

    async def generate_sql_from_plan(self, plan_json: str, scoping_value: Optional[str]) -> str:
        try:
            prompt = self.build_sql_from_plan_prompt(plan_json, scoping_value)
            headers = {"Content-Type": "application/json"}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
            data = {
                "model": self.config.model,
                "messages": [
                    {"role": "system", "content": "You are an expert SQL generator. Generate only the SQL query, no explanations."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature
            }
            response = await self.client.post(
                f"{self.config.base_url}/chat/completions",
                headers=headers,
                json=data
            )
            if response.status_code != 200:
                raise Exception(f"Custom LLM API error: {response.status_code} - {response.text}")
            result = response.json()
            return self._clean_sql(result['choices'][0]['message']['content'].strip())
        except Exception:
            raise

class LLMProviderFactory:
    """Factory class to create LLM providers"""
    
    @staticmethod
    def create_provider(config: LLMProviderConfig) -> BaseLLMProvider:
        """Create LLM provider based on configuration"""
        provider_type = config.provider_type.lower()
        
        if provider_type == "openai":
            return OpenAIProvider(config)
        elif provider_type == "anthropic":
            return AnthropicProvider(config)
        elif provider_type == "google":
            return GoogleProvider(config)
        elif provider_type == "custom":
            return CustomProvider(config)
        else:
            raise ValueError(f"Unsupported LLM provider type: {provider_type}")
    
    @staticmethod
    def get_supported_providers() -> List[str]:
        """Get list of supported LLM providers"""
        return ["openai", "anthropic", "google", "custom"]
