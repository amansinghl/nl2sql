'use client'

import { useState, useEffect } from 'react'
import toast from 'react-hot-toast'
import { Heart, Database, Server, Activity, RefreshCw, CheckCircle, XCircle, AlertCircle, Clock, Brain, Zap, Globe, Wrench } from 'lucide-react'
import { ApiClient, HealthStatus, ProviderInfo } from '@/lib/api'

// HealthStatus interface is now imported from @/lib/api

interface ServiceMetrics {
  responseTime: number
  lastCheck: string
  uptime: string
  errorCount: number
}

export function HealthDashboard() {
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null)
  const [providerInfo, setProviderInfo] = useState<ProviderInfo | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [metrics, setMetrics] = useState<ServiceMetrics>({
    responseTime: 0,
    lastCheck: '',
    uptime: '',
    errorCount: 0,
  })

  useEffect(() => {
    checkHealth()
    
    if (autoRefresh) {
      const interval = setInterval(checkHealth, 30000) // Check every 30 seconds
      return () => clearInterval(interval)
    }
  }, [autoRefresh])

  const checkHealth = async () => {
    setIsLoading(true)
    const startTime = Date.now()
    
    try {
      const [health, providers] = await Promise.all([
        ApiClient.getHealth(),
        ApiClient.getProviders()
      ])
      
      setHealthStatus(health)
      setProviderInfo(providers)
      
      const responseTime = Date.now() - startTime
      setMetrics(prev => ({
        ...prev,
        responseTime,
        lastCheck: new Date().toISOString(),
        errorCount: health.status === 'healthy' ? 0 : prev.errorCount + 1,
      }))
      
      if (health.status !== 'healthy') {
        toast.error('Service health check failed')
      }
    } catch (error) {
      console.error('Health check error:', error)
      setHealthStatus(null)
      setProviderInfo(null)
      setMetrics(prev => ({
        ...prev,
        responseTime: Date.now() - startTime,
        lastCheck: new Date().toISOString(),
        errorCount: prev.errorCount + 1,
      }))
      toast.error('Failed to check service health')
    } finally {
      setIsLoading(false)
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle className="h-5 w-5 text-green-500" />
      case 'degraded':
        return <AlertCircle className="h-5 w-5 text-yellow-500" />
      case 'unhealthy':
        return <XCircle className="h-5 w-5 text-red-500" />
      default:
        return <AlertCircle className="h-5 w-5 text-gray-500 dark:text-gray-400" />
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'status-healthy'
      case 'degraded':
        return 'status-warning'
      case 'unhealthy':
        return 'status-error'
      default:
        return 'status-warning'
    }
  }

  const getServiceStatus = (connected: boolean) => {
    return connected ? (
      <div className="flex items-center space-x-2">
        <CheckCircle className="h-4 w-4 text-green-500" />
        <span className="text-sm text-green-700">Connected</span>
      </div>
    ) : (
      <div className="flex items-center space-x-2">
        <XCircle className="h-4 w-4 text-red-500" />
        <span className="text-sm text-red-700">Disconnected</span>
      </div>
    )
  }

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleString()
  }

  const formatUptime = (timestamp: string) => {
    const now = new Date()
    const lastCheck = new Date(timestamp)
    const diffMs = now.getTime() - lastCheck.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    
    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    const diffHours = Math.floor(diffMins / 60)
    if (diffHours < 24) return `${diffHours}h ago`
    const diffDays = Math.floor(diffHours / 24)
    return `${diffDays}d ago`
  }

  const getProviderIcon = (provider: string) => {
    switch (provider) {
      case 'openai':
        return <Zap className="h-5 w-5 text-blue-600" />
      case 'anthropic':
        return <Brain className="h-5 w-5 text-purple-600" />
      case 'google':
        return <Globe className="h-5 w-5 text-green-600" />
      case 'custom':
        return <Wrench className="h-5 w-5 text-orange-600" />
      default:
        return <Brain className="h-5 w-5 text-gray-600" />
    }
  }

  const getProviderDisplayName = (provider: string) => {
    switch (provider) {
      case 'openai':
        return 'OpenAI'
      case 'anthropic':
        return 'Anthropic Claude'
      case 'google':
        return 'Google Gemini'
      case 'custom':
        return 'Custom/Self-hosted'
      default:
        return provider
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="card">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Health Monitoring Dashboard</h2>
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
              Monitor the health and status of NL2SQL AI Agent
            </p>
          </div>
          <div className="flex items-center space-x-2">
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
              />
              <span className="text-sm text-gray-700 dark:text-gray-300 dark:text-gray-300">Auto-refresh</span>
            </label>
            <button
              onClick={checkHealth}
              disabled={isLoading}
              className="btn-secondary flex items-center space-x-2"
            >
              <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
              <span>Refresh</span>
            </button>
          </div>
        </div>
      </div>

      {/* Overall Status */}
      {healthStatus && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600 dark:text-gray-400">Overall Status</p>
                <div className="flex items-center space-x-2 mt-1">
                  {getStatusIcon(healthStatus.status)}
                  <span className={`status-indicator ${getStatusColor(healthStatus.status)}`}>
                    {healthStatus.status.toUpperCase()}
                  </span>
                </div>
              </div>
              <Heart className="h-8 w-8 text-gray-400" />
            </div>
          </div>

          <div className="card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600 dark:text-gray-400">Response Time</p>
                <p className="text-2xl font-semibold text-gray-900 dark:text-white">
                  {metrics.responseTime}ms
                </p>
              </div>
              <Clock className="h-8 w-8 text-gray-400" />
            </div>
          </div>

          <div className="card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600 dark:text-gray-400">Last Check</p>
                <p className="text-sm text-gray-900 dark:text-white">
                  {formatUptime(metrics.lastCheck)}
                </p>
              </div>
              <Activity className="h-8 w-8 text-gray-400" />
            </div>
          </div>

          <div className="card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600 dark:text-gray-400">Error Count</p>
                <p className="text-2xl font-semibold text-gray-900 dark:text-white">
                  {metrics.errorCount}
                </p>
              </div>
              <AlertCircle className="h-8 w-8 text-gray-400" />
            </div>
          </div>
        </div>
      )}

      {/* Warnings Section */}
      {healthStatus && healthStatus.warnings && healthStatus.warnings.length > 0 && (
        <div className="card">
          <div className="flex items-center space-x-3 mb-4">
            <AlertCircle className="h-6 w-6 text-yellow-500" />
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Configuration Warnings</h3>
          </div>
          <div className="space-y-3">
            {healthStatus.warnings.map((warning, index) => (
              <div key={index} className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4">
                <div className="flex items-start space-x-3">
                  <AlertCircle className="h-5 w-5 text-yellow-500 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-yellow-800 dark:text-yellow-200">{warning}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Service Status Details */}
      {healthStatus && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Database Service */}
          <div className="card">
            <div className="flex items-center space-x-3 mb-4">
              <Database className="h-6 w-6 text-primary-600" />
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Database Service</h3>
            </div>
            
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Connection Status</span>
                {getServiceStatus(healthStatus.database_connected)}
              </div>
              
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Schema Loaded</span>
                {getServiceStatus(healthStatus.schema_loaded)}
              </div>
              
              <div className="pt-3 border-t border-gray-200">
                <div className="text-xs text-gray-500 dark:text-gray-400">
                  Last updated: {formatTimestamp(healthStatus.timestamp)}
                </div>
              </div>
            </div>
          </div>

          {/* LLM Provider Service */}
          <div className="card">
            <div className="flex items-center space-x-3 mb-4">
              <Brain className="h-6 w-6 text-primary-600" />
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">LLM Provider</h3>
            </div>
            
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Connection Status</span>
                {getServiceStatus(healthStatus.llm_provider_connected)}
              </div>
              
              {healthStatus.llm_provider_info && (
                <>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Provider</span>
                    <div className="flex items-center space-x-2">
                      {getProviderIcon(healthStatus.llm_provider_info.provider)}
                      <span className="text-sm text-gray-900 dark:text-white">
                        {getProviderDisplayName(healthStatus.llm_provider_info.provider)}
                      </span>
                    </div>
                  </div>
                  
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Model</span>
                    <span className="text-sm text-gray-900 dark:text-white font-mono">
                      {healthStatus.llm_provider_info.model}
                    </span>
                  </div>
                </>
              )}
              
              <div className="pt-3 border-t border-gray-200">
                <div className="text-xs text-gray-500 dark:text-gray-400">
                  Last updated: {formatTimestamp(healthStatus.timestamp)}
                </div>
              </div>
            </div>
          </div>

          {/* Provider Configuration Overview */}
          {providerInfo && (
            <div className="card">
              <div className="flex items-center space-x-3 mb-4">
                <Activity className="h-6 w-6 text-primary-600" />
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Provider Status</h3>
              </div>
              
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Available Providers</span>
                  <span className="text-sm text-gray-900 dark:text-white">
                    {providerInfo.available_providers.length} / {providerInfo.supported_providers.length}
                  </span>
                </div>
                
                <div className="space-y-2">
                  {providerInfo.supported_providers.map((provider) => {
                    const config = providerInfo.provider_configs[provider]
                    const isActive = provider === providerInfo.current_provider
                    const isConfigured = config.configured
                    
                    return (
                      <div key={provider} className="flex items-center justify-between text-xs">
                        <div className="flex items-center space-x-2">
                          {getProviderIcon(provider)}
                          <span className="text-gray-600 dark:text-gray-400">
                            {getProviderDisplayName(provider)}
                          </span>
                        </div>
                        <div className="flex items-center space-x-1">
                          {isActive ? (
                            <CheckCircle className="h-3 w-3 text-green-500" />
                          ) : isConfigured ? (
                            <AlertCircle className="h-3 w-3 text-blue-500" />
                          ) : (
                            <XCircle className="h-3 w-3 text-gray-400" />
                          )}
                          <span className={`text-xs ${
                            isActive ? 'text-green-600' : 
                            isConfigured ? 'text-blue-600' : 'text-gray-500'
                          }`}>
                            {isActive ? 'Active' : isConfigured ? 'Ready' : 'Not configured'}
                          </span>
                        </div>
                      </div>
                    )
                  })}
                </div>
                
                <div className="pt-3 border-t border-gray-200">
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    Configuration managed via environment variables
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Service Architecture */}
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">AI Agent Architecture</h3>
        <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-6">
          <div className="flex items-center justify-center space-x-8">
            {/* Client */}
            <div className="text-center">
              <div className="w-16 h-16 bg-blue-100 rounded-lg flex items-center justify-center mb-2">
                <Activity className="h-8 w-8 text-blue-600" />
              </div>
              <p className="text-sm font-medium text-gray-900 dark:text-white">Client</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Next.js UI</p>
            </div>

            {/* Arrow */}
            <div className="text-gray-400">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </div>

            {/* NL2SQL App */}
            <div className="text-center">
              <div className={`w-16 h-16 rounded-lg flex items-center justify-center mb-2 ${
                healthStatus?.status === 'healthy' ? 'bg-green-100' : 'bg-red-100'
              }`}>
                <Server className={`h-8 w-8 ${
                  healthStatus?.status === 'healthy' ? 'text-green-600' : 'text-red-600'
                }`} />
              </div>
              <p className="text-sm font-medium text-gray-900 dark:text-white">NL2SQL App</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Port 8000</p>
            </div>

            {/* Arrow */}
            <div className="text-gray-400">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </div>

            {/* Database */}
            <div className="text-center">
              <div className={`w-16 h-16 rounded-lg flex items-center justify-center mb-2 ${
                healthStatus?.database_connected ? 'bg-green-100' : 'bg-red-100'
              }`}>
                <Database className={`h-8 w-8 ${
                  healthStatus?.database_connected ? 'text-green-600' : 'text-red-600'
                }`} />
              </div>
              <p className="text-sm font-medium text-gray-900 dark:text-white">MySQL</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Database</p>
            </div>
          </div>
          
          {/* LLM Provider Section */}
          <div className="mt-8 pt-6 border-t border-gray-200 dark:border-gray-700">
            <div className="text-center">
              <div className="flex items-center justify-center space-x-4 mb-4">
                <div className="flex items-center space-x-2">
                  <Brain className="h-5 w-5 text-primary-600" />
                  <span className="text-sm font-medium text-gray-900 dark:text-white">LLM Provider</span>
                </div>
                <div className="flex items-center space-x-2">
                  {healthStatus?.llm_provider_info ? (
                    <>
                      {getProviderIcon(healthStatus.llm_provider_info.provider)}
                      <span className="text-sm text-gray-600 dark:text-gray-400">
                        {getProviderDisplayName(healthStatus.llm_provider_info.provider)}
                      </span>
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        ({healthStatus.llm_provider_info.model})
                      </span>
                    </>
                  ) : (
                    <span className="text-sm text-gray-500 dark:text-gray-400">Not configured</span>
                  )}
                </div>
              </div>
              
              <div className="text-xs text-gray-500 dark:text-gray-400">
                {healthStatus?.llm_provider_connected ? (
                  <span className="text-green-600 dark:text-green-400">Connected</span>
                ) : (
                  <span className="text-red-600 dark:text-red-400">Disconnected</span>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Error Log */}
      {metrics.errorCount > 0 && (
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Recent Issues</h3>
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
            <div className="flex items-center space-x-2">
              <AlertCircle className="h-5 w-5 text-red-500" />
              <span className="text-sm font-medium text-red-800 dark:text-red-200">
                {metrics.errorCount} error{metrics.errorCount !== 1 ? 's' : ''} detected
              </span>
            </div>
            <p className="text-sm text-red-700 dark:text-red-300 mt-2">
              Check the service logs for more details about the issues.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
