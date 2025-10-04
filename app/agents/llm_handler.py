from typing import List, Dict, Optional, Any
from ..utils.config import settings
from ..loaders.graph_builder import schema_graph
from ..engines.llm_providers import LLMProviderFactory
from ..utils.middleware import circuit_breaker_middleware
from ..utils.error_codes import create_llm_error, ErrorCodes

class LLMHandler:
    def __init__(self, provider: str = None):
        """Initialize LLM handler with specified provider"""
        self.provider_name = provider or settings.DEFAULT_LLM_PROVIDER
        self.config = settings.get_llm_config(self.provider_name)
        self.provider = LLMProviderFactory.create_provider(self.config)
        # Initialized LLM handler with provider
    
    async def generate_sql(self, user_query: str, scoping_value: str, relevant_tables: List[str], schema_context: str = None) -> str:
        """Generate SQL using the configured LLM provider with circuit breaker protection (plan-then-generate)."""
        try:
            # Get schema description (use provided context or fall back to full schema)
            if schema_context:
                schema_desc = schema_context
            else:
                schema_desc = schema_graph.get_schema_description()
            
            # Step 1: Generate plan
            # Determine if scoping is required by inspecting schema context tables (best-effort)
            scoping_required = False
            try:
                # crude heuristic: if any relevant table is scoped in the schema graph
                for t in relevant_tables:
                    info = schema_graph.tables.get(t, {})
                    if info.get('scoped', False):
                        scoping_required = True
                        break
            except Exception:
                scoping_required = False
            
            # Build join hints using schema graph join paths for the candidate tables
            join_hints_lines = []
            try:
                from ..loaders.graph_builder import schema_graph as _sg
                # If >1 relevant tables, compute minimal joins across them
                if relevant_tables and len(relevant_tables) > 1:
                    path_joins = _sg.get_join_path(relevant_tables)
                    for j in path_joins:
                        jt = j.get('type', 'INNER') if isinstance(j, dict) else 'INNER'
                        from_t = j.get('from_table')
                        to_t = j.get('to_table')
                        from_c = j.get('join_column') or j.get('from_column')
                        to_c = j.get('to_column', 'id')
                        if from_t and to_t and from_c:
                            join_hints_lines.append(f"{jt} JOIN: {from_t}.{from_c} -> {to_t}.{to_c}")
            except Exception:
                # Best-effort: no hints
                pass
            join_hints_text = "\n".join(join_hints_lines) if join_hints_lines else "(none)"

            plan_json = await circuit_breaker_middleware.execute_with_circuit_breaker(
                self.provider_name,
                self.provider.generate_plan,
                user_query, relevant_tables, schema_desc, scoping_required, join_hints_text
            )
            
            # Step 1.5: Validate and repair plan
            from ..validators.plan_validator import plan_validator
            validation_result = plan_validator.validate_plan(plan_json, user_query)
            if not validation_result["valid"]:
                # If validation fails, try to re-plan with more focused context
                if len(relevant_tables) > 1:
                    # Try with just the top table
                    top_table = relevant_tables[0] if relevant_tables else "entities"
                    plan_json = await circuit_breaker_middleware.execute_with_circuit_breaker(
                        self.provider_name,
                        self.provider.generate_plan,
                        user_query, [top_table], schema_desc, scoping_required, join_hints_text
                    )
                    validation_result = plan_validator.validate_plan(plan_json, user_query)
                
                if not validation_result["valid"]:
                    raise Exception(f"Plan validation failed: {validation_result['error']}")
            
            # Use repaired plan if available
            if validation_result.get("repaired_plan"):
                import json
                plan_json = json.dumps(validation_result["repaired_plan"])
            
            # Step 2: Generate SQL from validated plan
            sql = await circuit_breaker_middleware.execute_with_circuit_breaker(
                self.provider_name,
                self.provider.generate_sql_from_plan,
                plan_json, scoping_value
            )
            
            # Generated SQL for query
            
            return sql
            
        except Exception as e:
            # Error generating SQL
            raise create_llm_error(e, self.provider_name)
    
    async def explain_results(self, query: str, results: List[Dict], row_count: int) -> str:
        """Generate a natural language explanation of the results using the configured LLM provider with circuit breaker protection"""
        try:
            explanation = await circuit_breaker_middleware.execute_with_circuit_breaker(
                self.provider_name,
                self.provider.explain_results,
                query, results, row_count
            )
            return explanation
            
        except Exception as e:
            # Error generating explanation
            raise create_llm_error(e, self.provider_name)
    
    async def close(self):
        """Close the LLM provider"""
        await self.provider.close()
    
    def get_provider_info(self) -> Dict[str, str]:
        """Get information about the current provider"""
        return {
            "provider": self.provider_name,
            "model": self.config.model,
            "type": self.config.provider_type
        }
    
    def get_circuit_breaker_status(self) -> Dict[str, Any]:
        """Get circuit breaker status for this provider"""
        return circuit_breaker_middleware.get_circuit_breaker(self.provider_name).get_state()
    
    def reset_circuit_breaker(self):
        """Reset circuit breaker for this provider"""
        circuit_breaker_middleware.reset_circuit_breaker(self.provider_name)


