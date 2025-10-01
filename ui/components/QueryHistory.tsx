'use client'

import { useState, useEffect } from 'react'
import toast from 'react-hot-toast'
import { History, Trash2, Copy, Download, Search, Filter, Clock, CheckCircle, XCircle } from 'lucide-react'
import { formatValue, isMonetaryColumn } from '@/lib/currency'

interface QueryHistoryItem {
  id: string
  query: string
  entityId: string
  sql: string
  success: boolean
  rowCount: number
  executionTime: number
  tablesUsed: string[]
  timestamp: string
  error?: string
  results?: any[]
}

export function QueryHistory() {
  const [history, setHistory] = useState<QueryHistoryItem[]>([])
  const [filteredHistory, setFilteredHistory] = useState<QueryHistoryItem[]>([])
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState<'all' | 'success' | 'error'>('all')
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    loadHistory()
  }, [])

  useEffect(() => {
    filterHistory()
  }, [history, searchTerm, statusFilter])

  const loadHistory = async () => {
    setIsLoading(true)
    try {
      // In a real implementation, this would load from localStorage or backend
      const savedHistory = localStorage.getItem('nl2sql-query-history')
      if (savedHistory) {
        const parsedHistory = JSON.parse(savedHistory)
        setHistory(parsedHistory)
      }
    } catch (error) {
      console.error('Error loading history:', error)
      toast.error('Failed to load query history')
    } finally {
      setIsLoading(false)
    }
  }

  const filterHistory = () => {
    let filtered = history

    // Filter by search term
    if (searchTerm) {
      filtered = filtered.filter(item =>
        item.query.toLowerCase().includes(searchTerm.toLowerCase()) ||
        item.entityId.toLowerCase().includes(searchTerm.toLowerCase()) ||
        item.sql.toLowerCase().includes(searchTerm.toLowerCase())
      )
    }

    // Filter by status
    if (statusFilter !== 'all') {
      filtered = filtered.filter(item =>
        statusFilter === 'success' ? item.success : !item.success
      )
    }

    setFilteredHistory(filtered)
  }

  const clearHistory = () => {
    if (confirm('Are you sure you want to clear all query history?')) {
      setHistory([])
      localStorage.removeItem('nl2sql-query-history')
      toast.success('Query history cleared')
    }
  }

  const deleteHistoryItem = (id: string) => {
    const updatedHistory = history.filter(item => item.id !== id)
    setHistory(updatedHistory)
    localStorage.setItem('nl2sql-query-history', JSON.stringify(updatedHistory))
    toast.success('Query deleted from history')
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    toast.success('Copied to clipboard')
  }

  const downloadResults = (item: QueryHistoryItem) => {
    if (!item.results) return

    const dataStr = JSON.stringify(item.results, null, 2)
    const dataBlob = new Blob([dataStr], { type: 'application/json' })
    const url = URL.createObjectURL(dataBlob)
    const link = document.createElement('a')
    link.href = url
    link.download = `nl2sql-results-${item.id}.json`
    link.click()
    URL.revokeObjectURL(url)
  }

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleString()
  }

  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms.toFixed(0)}ms`
    return `${(ms / 1000).toFixed(2)}s`
  }

  const getStatusIcon = (success: boolean) => {
    return success ? (
      <CheckCircle className="h-4 w-4 text-green-500" />
    ) : (
      <XCircle className="h-4 w-4 text-red-500" />
    )
  }

  const getStatusColor = (success: boolean) => {
    return success ? 'status-healthy' : 'status-error'
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="card">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Query History</h2>
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
              View and manage your previous NL2SQL queries
            </p>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={clearHistory}
              disabled={history.length === 0}
              className="btn-secondary flex items-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Trash2 className="h-4 w-4" />
              <span>Clear All</span>
            </button>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="card">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search queries, entity IDs, or SQL..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="input-field pl-10"
              />
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <Filter className="h-4 w-4 text-gray-400" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as any)}
              className="input-field"
            >
              <option value="all">All Status</option>
              <option value="success">Success Only</option>
              <option value="error">Errors Only</option>
            </select>
          </div>
        </div>
      </div>

      {/* History List */}
      {isLoading ? (
        <div className="flex items-center justify-center h-32">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
        </div>
      ) : filteredHistory.length === 0 ? (
        <div className="card">
          <div className="text-center py-12">
            <History className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">No Query History</h3>
            <p className="text-gray-500 dark:text-gray-400">
              {history.length === 0
                ? 'Start by running some queries to build your history'
                : 'No queries match your current filters'}
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredHistory.map((item) => (
            <div key={item.id} className="card">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center space-x-3">
                  {getStatusIcon(item.success)}
                  <div>
                    <h3 className="text-sm font-medium text-gray-900 dark:text-white">
                      {item.query.length > 100
                        ? `${item.query.substring(0, 100)}...`
                        : item.query}
                    </h3>
                    <div className="flex items-center space-x-4 mt-1">
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        Entity: {item.entityId}
                      </span>
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        {formatTimestamp(item.timestamp)}
                      </span>
                      <span className={`status-indicator ${getStatusColor(item.success)}`}>
                        {item.success ? 'Success' : 'Failed'}
                      </span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => copyToClipboard(item.query)}
                    className="text-gray-400 hover:text-gray-600"
                    title="Copy query"
                  >
                    <Copy className="h-4 w-4" />
                  </button>
                  {item.results && (
                    <button
                      onClick={() => downloadResults(item)}
                      className="text-gray-400 hover:text-gray-600"
                      title="Download results"
                    >
                      <Download className="h-4 w-4" />
                    </button>
                  )}
                  <button
                    onClick={() => deleteHistoryItem(item.id)}
                    className="text-gray-400 hover:text-red-600"
                    title="Delete from history"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>

              {/* Query Details */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                <div className="flex items-center space-x-2">
                  <Clock className="h-4 w-4 text-gray-400" />
                  <span className="text-sm text-gray-600 dark:text-gray-400">Execution Time:</span>
                  <span className="text-sm font-medium text-gray-900 dark:text-white">
                    {formatDuration(item.executionTime)}
                  </span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="text-sm text-gray-600 dark:text-gray-400">Rows:</span>
                  <span className="text-sm font-medium text-gray-900 dark:text-white">
                    {item.rowCount.toLocaleString()}
                  </span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="text-sm text-gray-600 dark:text-gray-400">Tables:</span>
                  <span className="text-sm font-medium text-gray-900 dark:text-white">
                    {item.tablesUsed.join(', ')}
                  </span>
                </div>
              </div>

              {/* Generated SQL */}
              <div className="mb-4">
                <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Generated SQL:</h4>
                <div className="bg-gray-900 text-gray-100 p-3 rounded-lg overflow-x-auto">
                  <pre className="text-sm font-mono">{item.sql}</pre>
                </div>
              </div>

              {/* Error Message */}
              {!item.success && item.error && (
                <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3">
                  <h4 className="text-sm font-medium text-red-800 dark:text-red-200 mb-1">Error:</h4>
                  <p className="text-sm text-red-700 dark:text-red-300">{item.error}</p>
                </div>
              )}

              {/* Results Preview */}
              {item.success && item.results && item.results.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Results Preview ({item.results.length} rows):
                  </h4>
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                      <thead className="bg-gray-50 dark:bg-gray-800">
                        <tr>
                          {Object.keys(item.results[0]).slice(0, 5).map((key) => (
                            <th
                              key={key}
                              className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider"
                            >
                              {key}
                            </th>
                          ))}
                            {item.results && item.results[0] && Object.keys(item.results[0]).length > 5 && (
                              <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                                ...
                              </th>
                            )}
                        </tr>
                      </thead>
                      <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                        {item.results.slice(0, 3).map((row, index) => (
                          <tr key={index}>
                            {Object.entries(row).slice(0, 5).map(([columnName, value], cellIndex) => (
                              <td
                                key={cellIndex}
                                className="px-3 py-2 whitespace-nowrap text-sm text-gray-900 dark:text-white"
                              >
                                {value === null ? (
                                  <span className="text-gray-400 dark:text-gray-500 italic">null</span>
                                ) : (
                                  <span className={`${isMonetaryColumn(columnName) ? 'text-green-600 dark:text-green-400 font-semibold' : ''}`}>
                                    {formatValue(value, columnName)}
                                  </span>
                                )}
                              </td>
                            ))}
                            {item.results && item.results[0] && Object.keys(item.results[0]).length > 5 && (
                              <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                                ...
                              </td>
                            )}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {item.results.length > 3 && (
                      <div className="px-3 py-2 bg-gray-50 dark:bg-gray-800 text-xs text-gray-500 dark:text-gray-400">
                        Showing first 3 rows of {item.results.length} total results
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Statistics */}
      {history.length > 0 && (
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">History Statistics</h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="text-center">
              <div className="text-2xl font-semibold text-gray-900 dark:text-white">{history.length}</div>
              <div className="text-sm text-gray-600 dark:text-gray-400">Total Queries</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-semibold text-green-600">
                {history.filter(h => h.success).length}
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">Successful</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-semibold text-red-600">
                {history.filter(h => !h.success).length}
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">Failed</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-semibold text-gray-900 dark:text-white">
                {history.length > 0
                  ? (history.reduce((sum, h) => sum + h.executionTime, 0) / history.length).toFixed(0)
                  : 0}ms
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">Avg. Time</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
