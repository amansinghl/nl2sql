// API configuration and client - Clean v2 implementation
const API_BASE_URL = '/api'
const API_VERSION = 'v2'

export const API_ENDPOINTS = {
  // Clean v2 endpoints
  v2: {
    query: `${API_BASE_URL}/${API_VERSION}/query`,
    schema: `${API_BASE_URL}/${API_VERSION}/schema`,
    tableInfo: (tableName: string) => `${API_BASE_URL}/${API_VERSION}/schema/${tableName}`,
    providers: `${API_BASE_URL}/${API_VERSION}/providers`,
    health: '/health', // System endpoint, not versioned
  }
}

// API client with error handling
export class ApiClient {
  private static async request<T>(
    url: string, 
    options: RequestInit = {}
  ): Promise<T> {
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    return response.json()
  }

  static async postQuery(data: {
    query: string
    include_explanation: boolean
    user_role?: string
    scoping_value?: string
  }): Promise<QueryResponse> {
    console.log('Posting query to', API_ENDPOINTS.v2.query)
    return this.request<QueryResponse>(API_ENDPOINTS.v2.query, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  static async getSchema(): Promise<SchemaInfo> {
    return this.request<SchemaInfo>(API_ENDPOINTS.v2.schema)
  }

  static async getTableInfo(tableName: string): Promise<TableInfo> {
    return this.request<TableInfo>(API_ENDPOINTS.v2.tableInfo(tableName))
  }

  static async getHealth(): Promise<HealthStatus> {
    return this.request<HealthStatus>(API_ENDPOINTS.v2.health)
  }

  static async getProviders(): Promise<ProviderInfo> {
    return this.request<ProviderInfo>(API_ENDPOINTS.v2.providers)
  }
}

// Types for API responses
export interface QueryResponse {
  success: boolean
  sql: string
  results: any[]
  row_count: number
  explanation?: string
  error?: string
  error_code?: string
  message?: string
  description?: string
  category?: string
  retryable?: boolean
  request_id?: string
  execution_time: number
  tables_used: string[]
}

export interface HealthStatus {
  status: string
  database_connected: boolean
  llm_provider_connected: boolean
  schema_loaded: boolean
  llm_provider_info?: {
    provider: string
    model: string
    type: string
  }
  warnings: string[]
  timestamp: string
}

export interface ProviderInfo {
  current_provider: string
  available_providers: string[]
  supported_providers: string[]
  provider_configs: Record<string, {
    configured: boolean
    model: string | null
  }>
}

export interface SchemaInfo {
  tables: Record<string, any>
  relationships: any[]
  entity_scoped_tables: string[]
  description: string
}

export interface TableInfo {
  table_name: string
  schema_info: {
    description: string
    columns: Array<{
      name: string
      type: string
      nullable: boolean
      primary_key: boolean
      foreign_key?: {
        table: string
        column: string
      }
    }>
  }
  database_schema: Array<{
    column_name: string
    data_type: string
    is_nullable: string
    column_default: string | null
  }>
  row_count: number
  related_tables: string[]
}
