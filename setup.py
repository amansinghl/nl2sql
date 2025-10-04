#!/usr/bin/env python3
"""
Setup script for NL2SQL AI Agent
"""

import os
import json
import sys
from pathlib import Path

def create_directories():
    """Create necessary directories"""
    directories = ['graph', 'logs']
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"Created directory: {directory}")

def create_env_file():
    """Create .env file from template"""
    env_file = Path('.env')
    if env_file.exists():
        print(".env file already exists, skipping...")
        return
    
    env_content = """# Database Configuration
DB_URL=mysql+pymysql://readonly:pass@localhost:3306/prod

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Security
SECRET_KEY=your-secret-key-here-change-this-in-production

# Security and Scoping Configuration
SECURITY_SCOPING_COLUMN=accounts_entity_id
SECURITY_SCOPING_VALUE_SOURCE=request
SECURITY_SCOPING_VALUE_FIELD=scoping_value
SECURITY_ENABLE_AUTO_SCOPING=true
SECURITY_CUSTOM_VALIDATION_RULES={"max_tables": 50, "allowed_operations": ["SELECT"]}


# Rate Limiting
RATE_LIMIT_PER_MINUTE=60
"""
    
    with open('.env', 'w') as f:
        f.write(env_content)
    print("Created .env file")

def check_schema_graph():
    """Check if schema graph exists"""
    schema_file = Path('graph/schema_graph.json')
    if schema_file.exists():
        print("Schema graph file exists")
        return True
    else:
        print("Schema graph file not found at graph/schema_graph.json")
        print("  Please create your schema graph file")
        return False

def print_next_steps():
    """Print next steps for setup"""
    print("\n" + "="*50)
    print("NEXT STEPS:")
    print("="*50)
    print("1. Update your schema graph:")
    print("   - Edit graph/schema_graph.json with your actual database schema")
    print("   - Include all tables, columns, and relationships")
    print()
    print("2. Configure database connection:")
    print("   - Update DB_URL in .env with your MySQL connection string")
    print()
    print("3. Build and run the service:")
    print("   docker-compose up -d")
    print("   (This will automatically download the SQLCoder 7B model inside the container)")
    print()
    print("4. Test the service:")
    print("   curl http://localhost:7000/health")
    print("="*50)
    print("\n📊 Service Ports:")
    print("   - Web Interface: http://localhost:7000")
    print("   - API Service: http://localhost:7000/api")

def main():
    print("Setting up NL2SQL AI Agent...")
    print()
    
    create_directories()
    create_env_file()
    
    schema_ok = check_schema_graph()
    
    print_next_steps()
    
    if not schema_ok:
        print("\nSetup incomplete. Please create your schema graph file.")
        sys.exit(1)
    else:
        print("\nSetup completed successfully!")

if __name__ == "__main__":
    main() 