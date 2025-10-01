#!/usr/bin/env python3
"""
Test script to demonstrate schema accuracy improvements
"""
import asyncio
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from intelligent_sql_generator import IntelligentSQLGenerator
from llm_handler import LLMHandler
from query_validator import QueryValidator

async def test_schema_accuracy():
    """Test the improved schema accuracy"""
    
    # Initialize components
    llm_handler = LLMHandler()
    validator = QueryValidator()
    sql_generator = IntelligentSQLGenerator(llm_handler, validator)
    
    print("=== Testing Schema Accuracy Improvements ===\n")
    
    # Test cases that should now work better
    test_cases = [
        {
            "query": "count active customers",
            "expected_tables": ["users"],
            "description": "Should prefer users table over user_partner_preferences"
        },
        {
            "query": "revenue by day for last 14 days",
            "expected_tables": ["shipments"],
            "description": "Should use shipments table with total_price column"
        },
        {
            "query": "carrier delivery performance",
            "expected_tables": ["shipments", "suppliers"],
            "description": "Should suggest JOIN between shipments and suppliers"
        },
        {
            "query": "delivered shipments count",
            "expected_tables": ["shipments"],
            "description": "Should use tracking_status = '1900' for delivered"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"Test {i}: {test_case['description']}")
        print(f"Query: '{test_case['query']}'")
        
        # Test table selection
        try:
            relevant_tables = await sql_generator._intelligent_table_selection(test_case['query'])
            print(f"Selected tables: {relevant_tables}")
            
            # Check if expected tables are included
            expected_found = any(table in relevant_tables for table in test_case['expected_tables'])
            print(f"Expected tables found: {expected_found}")
            
            # Test column mapping
            print("Column mapping test:")
            for table in relevant_tables[:2]:  # Test first 2 tables
                if table in sql_generator.column_mappings:
                    mappings = sql_generator.column_mappings[table]
                    print(f"  {table}: {list(mappings.keys())[:5]}...")  # Show first 5 mappings
            
        except Exception as e:
            print(f"Error: {e}")
        
        print("-" * 50)
    
    # Test schema validation
    print("\n=== Testing Schema Validation ===")
    
    # Test cases with common mistakes
    validation_tests = [
        {
            "sql": "SELECT carrier_name FROM shipments",
            "issue": "carrier_name doesn't exist, needs JOIN with suppliers"
        },
        {
            "sql": "SELECT delivery_date FROM shipments",
            "issue": "delivery_date doesn't exist, should be shipment_date"
        },
        {
            "sql": "SELECT * FROM shipments WHERE delivery_status = 'delivered'",
            "issue": "delivery_status doesn't exist, should be tracking_status = '1900'"
        }
    ]
    
    for i, test in enumerate(validation_tests, 1):
        print(f"Validation Test {i}: {test['issue']}")
        print(f"SQL: {test['sql']}")
        
        # This would normally be called with proper user context
        # For demo purposes, we'll just show the expected behavior
        print("Expected: Should catch these common mistakes and suggest corrections")
        print("-" * 50)
    
    # Test column mapping functionality
    print("\n=== Testing Column Mapping ===")
    
    common_queries = [
        "delivery_date",
        "carrier_name", 
        "revenue",
        "customer_name",
        "delivery_status"
    ]
    
    for query_term in common_queries:
        print(f"Query term: '{query_term}'")
        print("Available mappings:")
        
        for table_name, mappings in sql_generator.column_mappings.items():
            if query_term in mappings:
                print(f"  {table_name}: {query_term} -> {mappings[query_term]}")
        print()
    
    # Clean up
    await llm_handler.close()
    print("Schema accuracy testing completed!")

if __name__ == "__main__":
    asyncio.run(test_schema_accuracy())
