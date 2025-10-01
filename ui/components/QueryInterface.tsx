'use client'

import { useState, useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import toast from 'react-hot-toast'
import { Play, Copy, Download, RotateCcw, Info, AlertCircle, Zap, Activity, CheckCircle, Database, Code, Sparkles, TrendingUp, Clock, BarChart3, Eye, EyeOff, Users, UserCheck, Building, Key, Shield } from 'lucide-react'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { tomorrow, vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { ApiClient, QueryResponse } from '@/lib/api'
import { useTheme } from './ThemeProvider'
import { API_CONFIG, getScopingFieldName, getScopingFieldLabel, getScopingFieldPlaceholder } from '@/lib/config'
import { formatValue, isMonetaryColumn } from '@/lib/currency'

// Dynamic schema based on configuration and user role
const createQuerySchema = (userRole: 'customer' | 'admin' = 'customer') => {
  const scopingFieldName = getScopingFieldName()
  // Scoping is required for customers, optional for admins
  const isRequired = API_CONFIG.requireScoping && userRole === 'customer'
  
  const schemaFields: any = {
    query: z.string().min(1, 'Query is required'),
    includeExplanation: z.boolean().default(false),
    userRole: z.enum(['customer', 'admin']).default('customer'),
  }
  
  if (API_CONFIG.legacyEntityIdField && API_CONFIG.showLegacyEntityId) {
    schemaFields.entityId = isRequired 
      ? z.string().min(1, `${getScopingFieldLabel()} is required`)
      : z.string().optional()
  }
  
  if (scopingFieldName !== 'entity_id' || !API_CONFIG.legacyEntityIdField) {
    schemaFields[scopingFieldName] = isRequired
      ? z.string().min(1, `${getScopingFieldLabel()} is required`)
      : z.string().optional()
  }
  
  return z.object(schemaFields)
}

// QueryResponse interface is now imported from @/lib/api

export function QueryInterface() {
  const { theme } = useTheme()
  const [isLoading, setIsLoading] = useState(false)
  const [lastResponse, setLastResponse] = useState<QueryResponse | null>(null)
  const [queryHistory, setQueryHistory] = useState<any[]>([])
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [showResults, setShowResults] = useState(true)
  const [selectedRole, setSelectedRole] = useState<'customer' | 'admin'>('customer')

  // Create dynamic schema based on selected role
  const querySchema = createQuerySchema(selectedRole)
  type QueryFormData = z.infer<typeof querySchema>

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
    watch,
    setValue,
  } = useForm<QueryFormData>({
    resolver: zodResolver(querySchema),
    defaultValues: {
      [getScopingFieldName()]: getScopingFieldPlaceholder(),
      includeExplanation: false,
      userRole: 'customer',
    },
  })

  // Update form validation when role changes
  useEffect(() => {
    // Clear any existing errors when role changes
    reset({
      [getScopingFieldName()]: selectedRole === 'customer' ? getScopingFieldPlaceholder() : '',
      includeExplanation: false,
      userRole: selectedRole,
    })
  }, [selectedRole, reset])

  // Debug form state
  console.log('Form errors:', errors)
  console.log('Form schema:', querySchema)
  console.log('Selected role:', selectedRole)

  const watchedRole = watch('userRole')

  const handleRoleChange = (newRole: 'customer' | 'admin') => {
    setSelectedRole(newRole)
    setValue('userRole', newRole)
    
    // Reset scoping fields when switching roles
    const scopingFieldName = getScopingFieldName()
    setValue(scopingFieldName as any, '')
    setValue('entityId', '')
    
    // Set default values based on role
    if (newRole === 'customer') {
      setValue(scopingFieldName as any, getScopingFieldPlaceholder())
    } else if (newRole === 'admin') {
      // Admin users don't need scoping values
      setValue(scopingFieldName as any, '')
    }
  }

  const onSubmit = async (data: QueryFormData) => {
    console.log('Form submitted with data:', data)
    console.log('Form errors:', errors)
    setIsLoading(true)
    setLastResponse(null)

    try {
      // Prepare request data with flexible scoping
      const requestData: any = {
        query: data.query,
        include_explanation: data.includeExplanation,
        user_role: data.userRole,
      }
      
      // Add scoping value based on configuration and role
      const scopingFieldName = getScopingFieldName()
      const scopingValue = data[scopingFieldName as keyof QueryFormData] || data.entityId
      
      if (scopingValue && data.userRole === 'customer') {
        requestData.scoping_value = scopingValue
      }
      
      // Add legacy entity_id if configured
      if (API_CONFIG.legacyEntityIdField && data.entityId) {
        requestData.entity_id = data.entityId
      }

      console.log('Sending request data:', requestData)
      const result = await ApiClient.postQuery(requestData)
      console.log('Received response:', result)

      setLastResponse(result)
      setQueryHistory(prev => [data, ...prev.slice(0, 9)]) // Keep last 10 queries

      if (result.success) {
        toast.success(`Query executed successfully in ${result.execution_time.toFixed(2)}s`)
      } else {
        toast.error(result.message || result.error || 'Query failed')
      }
    } catch (error) {
      console.error('Query error:', error)
      toast.error('Failed to execute query')
    } finally {
      setIsLoading(false)
    }
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    toast.success('Copied to clipboard')
  }

  const downloadResults = () => {
    if (!lastResponse?.results) return

    const dataStr = JSON.stringify(lastResponse.results, null, 2)
    const dataBlob = new Blob([dataStr], { type: 'application/json' })
    const url = URL.createObjectURL(dataBlob)
    const link = document.createElement('a')
    link.href = url
    link.download = `nl2sql-results-${Date.now()}.json`
    link.click()
    URL.revokeObjectURL(url)
  }

  const loadFromHistory = (query: QueryFormData) => {
    reset(query)
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-white to-gray-100 dark:from-gray-900 dark:via-gray-800 dark:to-gray-900">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Welcome Section */}
        <div className="text-center mb-12">
          <div className="relative inline-block">
            <div className="absolute -inset-1 bg-gradient-to-r from-primary-500 to-purple-600 rounded-2xl blur opacity-30 group-hover:opacity-100 transition duration-1000 group-hover:duration-200"></div>
            <div className="relative flex items-center justify-center space-x-4 mb-6 p-6 bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700">
              <div className="p-3 bg-gradient-to-r from-primary-500 to-primary-600 rounded-xl shadow-lg">
                <Sparkles className="w-8 h-8 text-white" />
              </div>
              <div className="text-left">
                <h1 className="text-4xl font-bold bg-gradient-to-r from-gray-900 to-gray-700 dark:from-white dark:to-gray-300 bg-clip-text text-transparent">
                  Natural Language to SQL
                </h1>
                <p className="text-sm text-gray-500 dark:text-gray-400 font-medium">Powered by AI</p>
              </div>
            </div>
          </div>
          <p className="text-xl text-gray-600 dark:text-gray-400 max-w-3xl mx-auto leading-relaxed">
            Transform your natural language questions into powerful SQL queries. Simply describe what you want to know, and we'll generate the perfect query for you.
          </p>
        </div>

        {/* Role Selector */}
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 p-8 mb-8 hover:shadow-2xl transition-all duration-300">
          <div className="flex items-center space-x-4 mb-6">
            <div className="p-3 bg-gradient-to-r from-indigo-500 to-indigo-600 rounded-xl shadow-lg">
              <Users className="h-6 w-6 text-white" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Access Role</h2>
              <p className="text-gray-600 dark:text-gray-400">Select your access level for this query</p>
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <button
              type="button"
              onClick={() => handleRoleChange('customer')}
              className={`p-6 rounded-xl border-2 transition-all duration-200 ${
                selectedRole === 'customer'
                  ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20 shadow-lg'
                  : 'border-gray-200 dark:border-gray-600 hover:border-blue-300 dark:hover:border-blue-600'
              }`}
            >
              <div className="flex items-center space-x-3 mb-3">
                <UserCheck className={`h-6 w-6 ${selectedRole === 'customer' ? 'text-blue-600' : 'text-gray-500'}`} />
                <h3 className={`text-lg font-bold ${selectedRole === 'customer' ? 'text-blue-900 dark:text-blue-100' : 'text-gray-900 dark:text-white'}`}>
                  Customer
                </h3>
              </div>
              <p className={`text-sm ${selectedRole === 'customer' ? 'text-blue-700 dark:text-blue-300' : 'text-gray-600 dark:text-gray-400'}`}>
                Single entity access with automatic scoping
              </p>
            </button>

            <button
              type="button"
              onClick={() => handleRoleChange('admin')}
              className={`p-6 rounded-xl border-2 transition-all duration-200 ${
                selectedRole === 'admin'
                  ? 'border-purple-500 bg-purple-50 dark:bg-purple-900/20 shadow-lg'
                  : 'border-gray-200 dark:border-gray-600 hover:border-purple-300 dark:hover:border-purple-600'
              }`}
            >
              <div className="flex items-center space-x-3 mb-3">
                <Key className={`h-6 w-6 ${selectedRole === 'admin' ? 'text-purple-600' : 'text-gray-500'}`} />
                <h3 className={`text-lg font-bold ${selectedRole === 'admin' ? 'text-purple-900 dark:text-purple-100' : 'text-gray-900 dark:text-white'}`}>
                  Admin
                </h3>
              </div>
              <p className={`text-sm ${selectedRole === 'admin' ? 'text-purple-700 dark:text-purple-300' : 'text-gray-600 dark:text-gray-400'}`}>
                Full system access to all entities
              </p>
            </button>
          </div>
        </div>

        {/* Query Form */}
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 p-8 mb-8 hover:shadow-2xl transition-all duration-300">
          <div className="flex items-center justify-between mb-8">
            <div className="flex items-center space-x-4">
              <div className="p-3 bg-gradient-to-r from-blue-500 to-blue-600 rounded-xl shadow-lg">
                <Code className="h-6 w-6 text-white" />
              </div>
              <div>
                <div className="flex items-center space-x-3">
                  <h2 className="text-3xl font-bold text-gray-900 dark:text-white">Query Interface</h2>
                  <div className={`px-3 py-1 rounded-full text-sm font-bold ${
                    selectedRole === 'customer' 
                      ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300'
                      : selectedRole === 'employee'
                      ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'
                      : 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300'
                  }`}>
                    {selectedRole.charAt(0).toUpperCase() + selectedRole.slice(1)}
                  </div>
                </div>
                <p className="text-gray-600 dark:text-gray-400 mt-1 text-lg">Ask questions in plain English</p>
              </div>
            </div>
            <div className="flex items-center space-x-3">
              <button
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="btn-secondary flex items-center space-x-2 hover-lift"
              >
                {showAdvanced ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                <span>{showAdvanced ? 'Hide' : 'Show'} Advanced</span>
              </button>
              <button
                onClick={() => reset()}
                className="btn-secondary flex items-center space-x-2 hover-lift"
              >
                <RotateCcw className="h-4 w-4" />
                <span>Reset</span>
              </button>
            </div>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-8">
            <div className="space-y-4">
              <label htmlFor="query" className="block text-lg font-bold text-gray-900 dark:text-white mb-4">
                <div className="flex items-center space-x-2">
                  <Sparkles className="h-5 w-5 text-primary-500" />
                  <span>Natural Language Query</span>
                </div>
              </label>
              <div className="relative">
                <textarea
                  {...register('query')}
                  id="query"
                  rows={5}
                  className="w-full px-6 py-4 text-lg border-2 border-gray-200 dark:border-gray-600 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 resize-none transition-all duration-200 shadow-sm hover:shadow-md focus:shadow-lg"
                  placeholder={
                    selectedRole === 'customer' 
                      ? "e.g., Show me all shipments from last month for my company"
                      : selectedRole === 'employee'
                      ? "e.g., Show me all shipments across all entities from last month"
                      : "e.g., Show me all data across all entities and tables"
                  }
                />
                <div className="absolute bottom-3 right-3 text-xs text-gray-400 dark:text-gray-500">
                  {watch('query')?.length || 0} characters
                </div>
              </div>
              {errors.query && (
                <div className="mt-3 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
                  <p className="text-sm text-red-600 dark:text-red-400 flex items-center space-x-2">
                    <AlertCircle className="h-4 w-4 flex-shrink-0" />
                    <span>{errors.query.message}</span>
                  </p>
                </div>
              )}
              
              {/* Role-specific help text */}
              <div className="mt-3 p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
                <p className="text-sm text-blue-700 dark:text-blue-300 flex items-center space-x-2">
                  <Info className="h-4 w-4 flex-shrink-0" />
                  <span>
                    {selectedRole === 'customer' 
                      ? "As a customer, your queries will be automatically scoped to your specific entity for data security."
                      : selectedRole === 'employee'
                      ? "As an employee, you can query all entities or specify particular entities in the advanced options."
                      : "As an admin, you have full system access and can query all data without restrictions."
                    }
                  </span>
                </p>
              </div>
            </div>

            {/* Advanced Options */}
            <div className={`transition-all duration-300 ${showAdvanced ? 'opacity-100 max-h-screen' : 'opacity-0 max-h-0 overflow-hidden'}`}>
              <div className="bg-gray-50 dark:bg-gray-700 rounded-xl p-6 space-y-6">
                <h3 className="text-lg font-bold text-gray-900 dark:text-white flex items-center space-x-2">
                  <TrendingUp className="h-5 w-5 text-primary-500" />
                  <span>Advanced Options</span>
                </h3>
                
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {API_CONFIG.showScopingField && watchedRole === 'customer' && (
                    <div className="space-y-2">
                      <label htmlFor={getScopingFieldName()} className="block text-sm font-bold text-gray-900 dark:text-white">
                        <div className="flex items-center space-x-2">
                          <Database className="h-4 w-4 text-primary-500" />
                          <span>{getScopingFieldLabel()}</span>
                          {watchedRole === 'customer' && <span className="text-red-500">*</span>}
                        </div>
                      </label>
                      <input
                        {...register(getScopingFieldName() as any)}
                        id={getScopingFieldName()}
                        type="text"
                        className="w-full px-4 py-3 border-2 border-gray-200 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 transition-all duration-200"
                        placeholder={getScopingFieldPlaceholder()}
                      />
                      {watchedRole === 'customer' && (
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          Required for customer access
                        </p>
                      )}
                      {watchedRole === 'employee' && (
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          Optional - leave empty for all entities
                        </p>
                      )}
                      {errors[getScopingFieldName() as keyof typeof errors] && (
                        <div className="mt-2 p-2 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
                          <p className="text-sm text-red-600 dark:text-red-400 flex items-center space-x-2">
                            <AlertCircle className="h-4 w-4 flex-shrink-0" />
                            <span>{(errors[getScopingFieldName() as keyof typeof errors] as any)?.message}</span>
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                  
                  {API_CONFIG.legacyEntityIdField && API_CONFIG.showLegacyEntityId && (
                    <div className="space-y-2">
                      <label htmlFor="entityId" className="block text-sm font-bold text-gray-900 dark:text-white">
                        <div className="flex items-center space-x-2">
                          <Database className="h-4 w-4 text-primary-500" />
                          <span>{API_CONFIG.entityIdFieldLabel}</span>
                        </div>
                      </label>
                      <input
                        {...register('entityId')}
                        id="entityId"
                        type="text"
                        className="w-full px-4 py-3 border-2 border-gray-200 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 transition-all duration-200"
                        placeholder={API_CONFIG.entityIdFieldPlaceholder}
                      />
                      {errors.entityId && (
                        <div className="mt-2 p-2 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
                          <p className="text-sm text-red-600 dark:text-red-400 flex items-center space-x-2">
                            <AlertCircle className="h-4 w-4 flex-shrink-0" />
                            <span>{errors.entityId.message}</span>
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                <div className="flex items-center space-x-4 p-4 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-600">
                  <input
                    {...register('includeExplanation')}
                    id="includeExplanation"
                    type="checkbox"
                    className="h-5 w-5 text-primary-600 focus:ring-primary-500 border-gray-300 dark:border-gray-600 rounded transition-colors duration-200"
                  />
                  <label htmlFor="includeExplanation" className="text-sm font-bold text-gray-900 dark:text-white flex items-center space-x-2">
                    <Info className="h-4 w-4 text-primary-500" />
                    <span>Include AI explanation</span>
                  </label>
                </div>
              </div>
            </div>

            <div className="flex justify-center pt-6">
              <button
                type="submit"
                disabled={isLoading}
                className="group relative px-8 py-4 bg-gradient-to-r from-primary-500 to-primary-600 hover:from-primary-600 hover:to-primary-700 text-white font-bold text-lg rounded-xl shadow-lg hover:shadow-xl transform hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none disabled:hover:scale-100 transition-all duration-200 flex items-center space-x-3"
              >
                <div className="absolute inset-0 bg-gradient-to-r from-primary-600 to-primary-700 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity duration-200"></div>
                <div className="relative flex items-center space-x-3">
                  {isLoading ? (
                    <div className="animate-spin rounded-full h-6 w-6 border-2 border-white border-t-transparent"></div>
                  ) : (
                    <Play className="h-6 w-6" />
                  )}
                  <span>
                    {isLoading ? 'Executing Query...' : 'Execute Query'}
                  </span>
                </div>
              </button>
            </div>
          </form>
        </div>

        {/* Query History */}
        {queryHistory.length > 0 && (
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 p-8 mb-8 hover:shadow-2xl transition-all duration-300">
            <div className="flex items-center space-x-4 mb-8">
              <div className="p-3 bg-gradient-to-r from-accent-500 to-accent-600 rounded-xl shadow-lg">
                <Activity className="h-6 w-6 text-white" />
              </div>
              <div>
                <h3 className="text-2xl font-bold text-gray-900 dark:text-white">Recent Queries</h3>
                <p className="text-gray-600 dark:text-gray-400 text-lg">Quick access to your previous queries</p>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {queryHistory.slice(0, 6).map((query, index) => (
                <div
                  key={index}
                  className="group p-6 bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-700 dark:to-gray-800 rounded-xl border border-gray-200 dark:border-gray-600 hover:border-primary-300 dark:hover:border-primary-600 transition-all duration-300 hover:shadow-lg hover:-translate-y-1 cursor-pointer"
                  onClick={() => loadFromHistory(query)}
                >
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-bold text-gray-900 dark:text-white line-clamp-2 leading-relaxed">
                        {query.query}
                      </p>
                      <div className="mt-3 space-y-1">
                        <div className="flex items-center space-x-2">
                          <div className={`px-2 py-1 rounded text-xs font-bold ${
                            query.userRole === 'customer' 
                              ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300'
                              : 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300'
                          }`}>
                            {query.userRole === 'admin' ? 'Admin' : 'Customer'}
                          </div>
                          {(query[getScopingFieldName() as keyof QueryFormData] || query.entityId) && (
                            <p className="text-xs text-gray-500 dark:text-gray-400">
                              <span className="font-semibold">{getScopingFieldLabel()}:</span> {query[getScopingFieldName() as keyof QueryFormData] || query.entityId}
                            </p>
                          )}
                        </div>
                        {query.includeExplanation && (
                          <p className="text-xs text-primary-600 dark:text-primary-400 font-medium">
                            <Info className="h-3 w-3 inline mr-1" />
                            Explanation included
                          </p>
                        )}
                      </div>
                    </div>
                    <div className="ml-3 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                      <div className="p-2 bg-primary-100 dark:bg-primary-900 rounded-lg">
                        <Play className="h-4 w-4 text-primary-600 dark:text-primary-400" />
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center justify-between text-xs text-gray-400 dark:text-gray-500">
                    <span>Click to load</span>
                    <span>#{index + 1}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Results */}
        {lastResponse && showResults && (
          <div className="space-y-8 animate-fade-in">
            {/* Results Header */}
            <div className="flex items-center justify-between mb-8">
              <div className="flex items-center space-x-4">
                <div className="p-3 bg-gradient-to-r from-emerald-500 to-emerald-600 rounded-xl shadow-lg">
                  <BarChart3 className="h-6 w-6 text-white" />
                </div>
                <div>
                  <h2 className="text-3xl font-bold text-gray-900 dark:text-white">Query Results</h2>
                  <p className="text-gray-600 dark:text-gray-400 text-lg">Analysis and data from your query</p>
                </div>
              </div>
              <button
                onClick={() => setShowResults(!showResults)}
                className="btn-secondary flex items-center space-x-2 hover-lift"
              >
                {showResults ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                <span>{showResults ? 'Hide' : 'Show'} Results</span>
              </button>
            </div>

            {/* Execution Summary */}
            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 p-8 hover:shadow-2xl transition-all duration-300">
              <div className="flex items-center justify-between mb-8">
                <div className="flex items-center space-x-4">
                  <div className={`p-3 rounded-xl shadow-lg ${lastResponse.success ? 'bg-gradient-to-r from-green-500 to-green-600' : 'bg-gradient-to-r from-red-500 to-red-600'}`}>
                    {lastResponse.success ? (
                      <CheckCircle className="h-6 w-6 text-white" />
                    ) : (
                      <AlertCircle className="h-6 w-6 text-white" />
                    )}
                  </div>
                  <div>
                    <h3 className="text-2xl font-bold text-gray-900 dark:text-white">Execution Summary</h3>
                    <p className="text-gray-600 dark:text-gray-400 text-lg">Query performance and results</p>
                  </div>
                </div>
                <div className="flex items-center space-x-4">
                  <div className={`px-4 py-2 rounded-lg font-bold text-sm ${lastResponse.success ? 'bg-green-100 dark:bg-green-900/20 text-green-800 dark:text-green-200' : 'bg-red-100 dark:bg-red-900/20 text-red-800 dark:text-red-200'}`}>
                    {lastResponse.success ? 'Success' : 'Failed'}
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-bold text-gray-900 dark:text-white">
                      {lastResponse.execution_time.toFixed(2)}s
                    </div>
                    <div className="text-sm text-gray-500 dark:text-gray-400">Execution Time</div>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="p-6 bg-gradient-to-br from-blue-50 to-blue-100 dark:from-blue-900/20 dark:to-blue-800/20 rounded-xl border border-blue-200 dark:border-blue-800 hover:shadow-lg transition-all duration-200">
                  <div className="flex items-center space-x-3 mb-4">
                    <div className="p-2 bg-blue-500 rounded-lg">
                      <Database className="h-5 w-5 text-white" />
                    </div>
                    <span className="text-sm font-bold text-blue-800 dark:text-blue-200">Rows Returned</span>
                  </div>
                  <div className="text-3xl font-bold text-blue-900 dark:text-blue-100 mb-2">{lastResponse.row_count}</div>
                  <div className="text-xs text-blue-600 dark:text-blue-400">Data records</div>
                </div>
                <div className="p-6 bg-gradient-to-br from-purple-50 to-purple-100 dark:from-purple-900/20 dark:to-purple-800/20 rounded-xl border border-purple-200 dark:border-purple-800 hover:shadow-lg transition-all duration-200">
                  <div className="flex items-center space-x-3 mb-4">
                    <div className="p-2 bg-purple-500 rounded-lg">
                      <Database className="h-5 w-5 text-white" />
                    </div>
                    <span className="text-sm font-bold text-purple-800 dark:text-purple-200">Tables Used</span>
                  </div>
                  <div className="text-sm font-medium text-purple-900 dark:text-purple-100 mb-2">
                    {lastResponse.tables_used.length} table{lastResponse.tables_used.length !== 1 ? 's' : ''}
                  </div>
                  <div className="text-xs text-purple-600 dark:text-purple-400 truncate">
                    {lastResponse.tables_used.join(', ')}
                  </div>
                </div>
                <div className="p-6 bg-gradient-to-br from-green-50 to-green-100 dark:from-green-900/20 dark:to-green-800/20 rounded-xl border border-green-200 dark:border-green-800 hover:shadow-lg transition-all duration-200">
                  <div className="flex items-center space-x-3 mb-4">
                    <div className="p-2 bg-green-500 rounded-lg">
                      <Clock className="h-5 w-5 text-white" />
                    </div>
                    <span className="text-sm font-bold text-green-800 dark:text-green-200">Performance</span>
                  </div>
                  <div className="text-3xl font-bold text-green-900 dark:text-green-100 mb-2">
                    {lastResponse.execution_time.toFixed(2)}s
                  </div>
                  <div className="text-xs text-green-600 dark:text-green-400">Query speed</div>
                </div>
              </div>

              {lastResponse.error && (
                <div className="mt-8 p-6 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl">
                  <div className="flex items-center space-x-3 mb-4">
                    <AlertCircle className="h-6 w-6 text-red-600 dark:text-red-400" />
                    <span className="text-lg font-bold text-red-800 dark:text-red-200">Error Details</span>
                  </div>
                  
                  {/* Main error message */}
                  <div className="mb-4">
                    <p className="text-red-700 dark:text-red-300 leading-relaxed text-lg font-medium">
                      {lastResponse.message || lastResponse.error}
                    </p>
                  </div>

                  {/* Error details grid */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                    {lastResponse.error_code && (
                      <div className="p-3 bg-red-100 dark:bg-red-900/30 rounded-lg">
                        <div className="text-xs font-semibold text-red-600 dark:text-red-400 uppercase tracking-wide mb-1">
                          Error Code
                        </div>
                        <div className="text-sm font-mono text-red-800 dark:text-red-200">
                          {lastResponse.error_code}
                        </div>
                      </div>
                    )}
                    
                    {lastResponse.category && (
                      <div className="p-3 bg-red-100 dark:bg-red-900/30 rounded-lg">
                        <div className="text-xs font-semibold text-red-600 dark:text-red-400 uppercase tracking-wide mb-1">
                          Category
                        </div>
                        <div className="text-sm font-medium text-red-800 dark:text-red-200">
                          {lastResponse.category}
                        </div>
                      </div>
                    )}
                    
                    {lastResponse.retryable !== undefined && (
                      <div className="p-3 bg-red-100 dark:bg-red-900/30 rounded-lg">
                        <div className="text-xs font-semibold text-red-600 dark:text-red-400 uppercase tracking-wide mb-1">
                          Retryable
                        </div>
                        <div className="text-sm font-medium text-red-800 dark:text-red-200">
                          {lastResponse.retryable ? 'Yes' : 'No'}
                        </div>
                      </div>
                    )}
                    
                    {lastResponse.request_id && (
                      <div className="p-3 bg-red-100 dark:bg-red-900/30 rounded-lg">
                        <div className="text-xs font-semibold text-red-600 dark:text-red-400 uppercase tracking-wide mb-1">
                          Request ID
                        </div>
                        <div className="text-sm font-mono text-red-800 dark:text-red-200">
                          {lastResponse.request_id}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Detailed description if available */}
                  {lastResponse.description && lastResponse.description !== lastResponse.error && (
                    <div className="mt-4 p-4 bg-red-100 dark:bg-red-900/30 rounded-lg border border-red-200 dark:border-red-700">
                      <div className="text-xs font-semibold text-red-600 dark:text-red-400 uppercase tracking-wide mb-2">
                        Technical Details
                      </div>
                      <p className="text-sm text-red-700 dark:text-red-300 leading-relaxed">
                        {lastResponse.description}
                      </p>
                    </div>
                  )}

                  {/* Retry suggestion for retryable errors */}
                  {lastResponse.retryable && (
                    <div className="mt-4 p-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg">
                      <div className="flex items-center space-x-2">
                        <div className="w-2 h-2 bg-yellow-500 rounded-full animate-pulse"></div>
                        <span className="text-sm font-medium text-yellow-800 dark:text-yellow-200">
                          This error is retryable. You can try running the query again.
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Generated SQL */}
            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 p-8 hover:shadow-2xl transition-all duration-300">
              <div className="flex items-center justify-between mb-8">
                <div className="flex items-center space-x-4">
                  <div className="p-3 bg-gradient-to-r from-indigo-500 to-indigo-600 rounded-xl shadow-lg">
                    <Code className="h-6 w-6 text-white" />
                  </div>
                  <div>
                    <h3 className="text-2xl font-bold text-gray-900 dark:text-white">Generated SQL</h3>
                    <p className="text-gray-600 dark:text-gray-400 text-lg">AI-generated query from your natural language</p>
                  </div>
                </div>
                <button
                  onClick={() => copyToClipboard(lastResponse.sql)}
                  className="group px-6 py-3 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 font-semibold rounded-xl transition-all duration-200 flex items-center space-x-2 hover:shadow-lg"
                >
                  <Copy className="h-4 w-4 group-hover:scale-110 transition-transform duration-200" />
                  <span>Copy SQL</span>
                </button>
              </div>
              <div className="relative">
                <div className="absolute top-4 right-4 z-10">
                  <div className="px-3 py-1 bg-gray-800 dark:bg-gray-200 text-white dark:text-gray-800 text-xs font-semibold rounded-lg">
                    SQL
                  </div>
                </div>
                <div className="bg-gray-900 dark:bg-gray-950 rounded-xl border border-gray-700 dark:border-gray-600 overflow-hidden shadow-inner">
                  <SyntaxHighlighter
                    language="sql"
                    style={theme === 'dark' ? vscDarkPlus : tomorrow}
                    customStyle={{
                      margin: 0,
                      background: 'transparent',
                      fontSize: '16px',
                      padding: '24px',
                      lineHeight: '1.6',
                    }}
                  >
                    {lastResponse.sql}
                  </SyntaxHighlighter>
                </div>
              </div>
            </div>

            {/* Results Table */}
            {lastResponse.success && lastResponse.results.length > 0 && (
              <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 p-8 hover:shadow-2xl transition-all duration-300">
                <div className="flex items-center justify-between mb-8">
                  <div className="flex items-center space-x-4">
                    <div className="p-3 bg-gradient-to-r from-emerald-500 to-emerald-600 rounded-xl shadow-lg">
                      <Database className="h-6 w-6 text-white" />
                    </div>
                    <div>
                      <h3 className="text-2xl font-bold text-gray-900 dark:text-white">Query Results</h3>
                      <p className="text-gray-600 dark:text-gray-400 text-lg">
                        {lastResponse.results.length} row{lastResponse.results.length !== 1 ? 's' : ''} returned
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={downloadResults}
                    className="group px-6 py-3 bg-emerald-100 dark:bg-emerald-900/20 hover:bg-emerald-200 dark:hover:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 font-semibold rounded-xl transition-all duration-200 flex items-center space-x-2 hover:shadow-lg"
                  >
                    <Download className="h-4 w-4 group-hover:scale-110 transition-transform duration-200" />
                    <span>Download JSON</span>
                  </button>
                </div>
                <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-700 shadow-inner">
                  <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                    <thead className="bg-gradient-to-r from-gray-50 to-gray-100 dark:from-gray-800 dark:to-gray-700">
                      <tr>
                        {Object.keys(lastResponse.results[0]).map((key) => (
                          <th
                            key={key}
                            className="px-6 py-4 text-left text-sm font-bold text-gray-700 dark:text-gray-300 uppercase tracking-wider"
                          >
                            {key}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                      {lastResponse.results.slice(0, 100).map((row, index) => (
                        <tr key={index} className="hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors duration-150 group">
                          {Object.entries(row).map(([columnName, value], cellIndex) => (
                            <td
                              key={cellIndex}
                              className="px-6 py-4 text-sm text-gray-900 dark:text-gray-100 group-hover:text-gray-700 dark:group-hover:text-gray-200"
                            >
                              {value === null ? (
                                <span className="text-gray-400 dark:text-gray-500 italic font-mono">null</span>
                              ) : (
                                <span className={`font-mono ${isMonetaryColumn(columnName) ? 'text-green-600 dark:text-green-400 font-semibold' : ''}`}>
                                  {formatValue(value, columnName)}
                                </span>
                              )}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {lastResponse.results.length > 100 && (
                    <div className="px-6 py-4 bg-gradient-to-r from-gray-50 to-gray-100 dark:from-gray-800 dark:to-gray-700 text-sm text-gray-600 dark:text-gray-400 border-t border-gray-200 dark:border-gray-700">
                      <div className="flex items-center justify-between">
                        <span className="font-medium">Showing first 100 rows of {lastResponse.results.length} total results</span>
                        <span className="text-xs bg-gray-200 dark:bg-gray-600 px-3 py-1 rounded-full font-semibold">
                          Limited for performance
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Explanation */}
            {lastResponse.explanation && (
              <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 p-8 hover:shadow-2xl transition-all duration-300">
                <div className="flex items-center space-x-4 mb-8">
                  <div className="p-3 bg-gradient-to-r from-amber-500 to-amber-600 rounded-xl shadow-lg">
                    <Info className="h-6 w-6 text-white" />
                  </div>
                  <div>
                    <h3 className="text-2xl font-bold text-gray-900 dark:text-white">AI Explanation</h3>
                    <p className="text-gray-600 dark:text-gray-400 text-lg">How the AI interpreted your query</p>
                  </div>
                </div>
                <div className="p-8 bg-gradient-to-br from-amber-50 to-amber-100 dark:from-amber-900/20 dark:to-amber-800/20 rounded-xl border border-amber-200 dark:border-amber-800">
                  <div className="flex items-start space-x-4">
                    <div className="flex-shrink-0">
                      <div className="w-8 h-8 bg-amber-500 rounded-full flex items-center justify-center">
                        <Sparkles className="h-4 w-4 text-white" />
                      </div>
                    </div>
                    <div className="flex-1">
                      <p className="text-gray-800 dark:text-gray-200 leading-relaxed text-lg font-medium">
                        {lastResponse.explanation}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
