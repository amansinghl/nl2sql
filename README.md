# NL2SQL AI Agent

<div align="center">

![NL2SQL Logo](https://img.shields.io/badge/NL2SQL-AI%20Agent-blue?style=for-the-badge&logo=mysql&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.9+-green?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-red?style=for-the-badge&logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-14+-black?style=for-the-badge&logo=next.js&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)

**An Intelligent AI Agent for Natural Language to SQL conversion with multi-LLM support, designed for safe, entity-scoped database queries and self-hosting.**

[Quick Start](#-quick-start) • [Documentation](#-documentation) • [Troubleshooting](#-troubleshooting)

</div>

---

## 🎯 Features

- **Multi-LLM Support**: OpenAI, Anthropic, Google, and self-hosted models
- **Enterprise Security**: Entity-scoped security with SQL injection protection
- **Modern Architecture**: AI Agent design with Docker containerization
- **Beautiful Interface**: Next.js web UI with real-time query execution
- **Health Monitoring**: Comprehensive health checks and logging
- **Circuit Breaker Pattern**: Automatic failure protection for LLM providers
- **Request/Response Middleware**: Advanced monitoring and metrics collection

---

## Quick Start

### Prerequisites

- **Docker** and **Docker Compose** installed
- **MySQL** database with read-only access
- **Internet connection** (for LLM API calls)

### 1. Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd nl2sql

# Run the setup script
python3 setup.py
```

### 2. Configure Environment

Copy the example environment file and configure your settings:

```bash
cp env.example .env
```

Edit your `.env` file with your configuration:

```bash
# Database Configuration
DB_URL=mysql+pymysql://readonly:pass@localhost:3306/prod

# LLM Configuration (choose one)
DEFAULT_LLM_PROVIDER=openai  # Options: openai, anthropic, google, custom

# OpenAI Configuration
OPENAI_API_KEY=your-openai-api-key-here
OPENAI_MODEL=gpt-3.5-turbo

# Security and Scoping Configuration
SECURITY_SCOPING_COLUMN=accounts_entity_id
SECRET_KEY=your-secret-key-here-change-this-in-production
```

### 3. Create Schema Graph

Create your schema graph file at `graph/schema_graph.json`:

```json
{
  "tables": {
    "shipments": {
      "columns": ["id", "status", "created_at", "accounts_entity_id", "order_id"],
      "scoped": true,
      "scoping_column": "accounts_entity_id",
      "description": "Shipment tracking information"
    },
    "orders": {
      "columns": ["id", "customer_id", "total", "accounts_entity_id", "created_at"],
      "scoped": true,
      "scoping_column": "accounts_entity_id",
      "description": "Customer orders"
    },
    "customers": {
      "columns": ["id", "name", "phone", "accounts_entity_id", "email"],
      "scoped": true,
      "scoping_column": "accounts_entity_id",
      "description": "Customer information"
    }
  },
  "relationships": [
    {"from": "shipments", "to": "orders", "on": "order_id"},
    {"from": "orders", "to": "customers", "on": "customer_id"}
  ]
}
```

### 4. Start Services

```bash
# Start all services
docker-compose up -d

# Fix logs directory permissions (if needed)
sudo chown -R 1000:1000 ./logs
chmod -R 755 ./logs

# View logs
docker-compose logs -f
```

**Note**: The logs directory permission fix is required because Docker volume mounts create directories with root ownership. This is a one-time setup step.

### 5. Access the Interface

- **Web UI**: http://localhost:7000 (via nginx)
- **API**: http://localhost:7000/api/v2
- **Health Check**: http://localhost:7000/health

---

## 📚 Documentation

For comprehensive documentation including:

- **Architecture Overview**: System design and components
- **API Reference**: Complete endpoint documentation
- **Error Codes**: Standardized error handling and codes
- **Troubleshooting**: Common issues and solutions
- **Best Practices**: Guidelines for optimal usage
- **Technical Challenges**: Understanding system limitations

**Access the full documentation in the web interface at http://localhost:7000**

### Error Code System

The NL2SQL AI Agent uses a standardized error code system for consistent error handling and debugging. All errors follow the format `NL2SQL-{CATEGORY}-{NUMBER}`.

#### Error Categories

- **DB (1000-1999)**: Database-related errors
- **VAL (2000-2999)**: Validation errors
- **LLM (3000-3999)**: LLM provider errors
- **AUTH (4000-4999)**: Authentication/Authorization errors
- **SYS (5000-5999)**: System errors
- **REQ (6000-6999)**: Request processing errors

#### Common Error Codes

| Code | Category | Description | HTTP Status |
|------|----------|-------------|-------------|
| `NL2SQL-DB-1001` | Database | Database connection failed | 503 |
| `NL2SQL-DB-1002` | Database | Query execution failed | 500 |
| `NL2SQL-DB-1003` | Database | Invalid SQL syntax | 400 |
| `NL2SQL-VAL-2002` | Validation | Scoping value is required | 400 |
| `NL2SQL-VAL-2003` | Validation | SQL injection detected | 400 |
| `NL2SQL-LLM-3001` | LLM | API key missing | 500 |
| `NL2SQL-LLM-3002` | LLM | Rate limited | 429 |
| `NL2SQL-SYS-5001` | System | Internal server error | 500 |

#### Error Response Format

```json
{
  "success": false,
  "error_code": "NL2SQL-DB-1001",
  "message": "Database connection failed",
  "description": "Unable to establish connection to the database",
  "category": "DB",
  "retryable": true,
  "request_id": "req_123456",
  "user_message": "Database connection failed",
  "details": {
    "context": "query_execution",
    "original_error": "Connection timeout"
  }
}
```

#### Retryable Errors

Some errors are marked as `retryable: true`, indicating that the client can retry the request after a delay. These typically include:
- Database connection issues
- LLM API rate limits
- Temporary service unavailability
- Request timeouts

---

## 🐛 Troubleshooting

### Common Issues

#### Logs Directory Permission Issues
```bash
# Fix logs directory permissions
sudo chown -R 1000:1000 ./logs
chmod -R 755 ./logs

# Restart services
docker-compose restart queryinator
```

#### Service Won't Start
```bash
# Check Docker status
docker --version
docker-compose --version

# Check container logs
docker-compose logs nl2sql-app
docker-compose logs nginx

# Restart services
docker-compose down
docker-compose up -d
```

#### Database Connection Failed
```bash
# Check database URL
echo $DB_URL

# Test MySQL connection
mysql -u readonly -p -h localhost -e "SELECT 1;"

# Check application logs
docker-compose logs nl2sql-app
```

#### LLM Provider Issues
```bash
# Check API key
echo $OPENAI_API_KEY

# Test API connection
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
     https://api.openai.com/v1/models
```

#### Schema Graph Issues
```bash
# Check schema file exists
ls -la graph/schema_graph.json

# Validate JSON
python3 -m json.tool graph/schema_graph.json
```

#### UI Not Loading
```bash
# Check nginx container
docker-compose ps nginx

# Check nginx logs
docker-compose logs nginx

# Check UI container
docker-compose ps nl2sql-ui

# Restart services
docker-compose restart nginx nl2sql-ui
```

#### Error Code Troubleshooting

When encountering errors, check the error code in the response:

```bash
# Example error response
curl -X POST http://localhost:7000/api/v2/query \
  -H "Content-Type: application/json" \
  -d '{"query": "show me all users"}'

# Response with error code
{
  "success": false,
  "error_code": "NL2SQL-VAL-2002",
  "message": "Scoping value is required",
  "description": "Entity scoping value is required for data isolation"
}
```

**Common Error Solutions:**

- **NL2SQL-VAL-2002**: Add `scoping_value` or `accounts_entity_id` to your request
- **NL2SQL-DB-1001**: Check database connection and credentials
- **NL2SQL-LLM-3001**: Verify API key configuration
- **NL2SQL-LLM-3002**: Wait and retry (rate limited)
- **NL2SQL-VAL-2003**: Review query for potential SQL injection

### Debug Mode

For detailed troubleshooting, check the application logs:

```bash
# Follow logs
docker-compose logs -f
```

---

## 🔧 Development

### Project Structure

```
nl2sql/
├── app/                    # Python FastAPI application
│   ├── main.py            # Main application entry point
│   ├── llm_handler.py     # LLM provider management
│   ├── db_executor.py     # Database execution
│   ├── query_validator.py # SQL validation and security
│   └── graph_builder.py   # Schema graph management
├── ui/                     # Next.js web interface
│   ├── app/               # Next.js app directory
│   ├── components/        # React components
│   └── lib/               # Utility functions
├── docker/                # Docker configuration
├── graph/                 # Schema graph files
├── tests/                 # Test files
└── docker-compose.yml     # Docker Compose configuration
```

### Running in Development

```bash
# Start with hot reload
docker-compose up

# Run tests
python -m pytest tests/

# Check code style
flake8 app/
```

### Database Setup

#### MySQL Setup

```bash
# Install MySQL
sudo apt-get install mysql-server

# Create database and user
sudo mysql -u root -p
CREATE DATABASE nl2sql_prod;
CREATE USER 'readonly'@'%' IDENTIFIED BY 'secure_password';
GRANT SELECT ON nl2sql_prod.* TO 'readonly'@'%';
FLUSH PRIVILEGES;
```

#### Connection String

```bash
# .env file
DB_URL=mysql+pymysql://readonly:secure_password@localhost:3306/nl2sql_prod
```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🆘 Support

### Getting Help

1. **Check the troubleshooting section** above
2. **Review the logs** for error messages
3. **Check the health dashboard** in the web UI
4. **Open an issue** on GitHub

### Community

- **GitHub Issues**: Bug reports and feature requests
- **Discussions**: General questions and discussions

---

<div align="center">

**Ready to transform your natural language into SQL with AI?**

[Get Started](#-quick-start) • [View Documentation](#-documentation) • [Report Issues](https://github.com/your-repo/issues)

Made with love by the NL2SQL AI Agent Team

</div>