'use client'

import { useState } from 'react'
import { QueryInterface } from '@/components/QueryInterface'
import { HealthDashboard } from '@/components/HealthDashboard'
import { QueryHistory } from '@/components/QueryHistory'
import { Documentation } from '@/components/Documentation'
import { ThemeToggle } from '@/components/ThemeToggle'
import { 
  Activity, 
  Heart, 
  BookOpen,
  Sparkles,
  Zap,
  Shield
} from 'lucide-react'

type TabType = 'query' | 'health' | 'history' | 'docs'

export default function Home() {
  const [activeTab, setActiveTab] = useState<TabType>('query')

  const tabs = [
    { id: 'query' as TabType, label: 'Query Interface', icon: Zap},
    { id: 'health' as TabType, label: 'Health Monitor', icon: Heart},
    { id: 'history' as TabType, label: 'Query History', icon: Activity },
    { id: 'docs' as TabType, label: 'Documentation', icon: BookOpen},
  ]

  const renderTabContent = () => {
    switch (activeTab) {
      case 'query':
        return <QueryInterface />
      case 'health':
        return <HealthDashboard />
      case 'history':
        return <QueryHistory />
      case 'docs':
        return <Documentation />
      default:
        return <QueryInterface />
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-white to-gray-100 dark:from-gray-900 dark:via-gray-800 dark:to-gray-900 transition-all duration-300">
      {/* Header */}
      <header className="glass border-b border-gray-200/50 dark:border-gray-700/50 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-20">
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-3">
                <div className="p-2 bg-gradient-to-r from-primary-500 to-primary-600 rounded-xl shadow-lg">
                  <Sparkles className="h-6 w-6 text-white" />
                </div>
                <div>
                  <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                    NL2SQL
                  </h1>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    AI Agent Interface
                  </p>
                </div>
              </div>
              <div className="hidden sm:flex items-center space-x-2">
                <span className="px-3 py-1 bg-gradient-to-r from-primary-100 to-primary-200 dark:from-primary-900 dark:to-primary-800 text-primary-800 dark:text-primary-200 text-xs font-semibold rounded-full">
                  v0.8.2-beta
                </span>
                <span className="px-3 py-1 bg-gradient-to-r from-green-100 to-green-200 dark:from-green-900 dark:to-green-800 text-green-800 dark:text-green-200 text-xs font-semibold rounded-full flex items-center space-x-1">
                  <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                  <span className="animate-pulse-text">Live</span>
                </span>
              </div>
            </div>
            
            <div className="flex items-center space-x-4">
              <div className="hidden md:flex items-center space-x-2 text-sm text-gray-600 dark:text-gray-400">
                <Shield className="h-4 w-4" />
                <span>Enterprise Ready</span>
              </div>
              <ThemeToggle />
            </div>
          </div>
        </div>
      </header>

      {/* Navigation Tabs */}
      <nav className="bg-white/80 dark:bg-gray-800/80 backdrop-blur-md border-b border-gray-200/50 dark:border-gray-700/50 sticky top-20 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex space-x-1 overflow-x-auto">
            {tabs.map((tab) => {
              const Icon = tab.icon
              const isActive = activeTab === tab.id
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`group flex items-center space-x-2 py-4 px-4 rounded-lg font-medium text-sm whitespace-nowrap ${
                    isActive
                      ? 'bg-gradient-to-r from-primary-500 to-primary-600 text-white shadow-lg'
                      : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-700'
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  <span>{tab.label}</span>
                </button>
              )
            })}
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div>
          {renderTabContent()}
        </div>
      </main>

      {/* Floating Action Button for Quick Access */}
      <div className="fixed bottom-8 right-8 z-50">
        <div className="flex flex-col space-y-3">
          <button
            onClick={() => setActiveTab('query')}
            className={`p-4 rounded-full shadow-lg transition-all duration-200 transform hover:scale-110 ${
              activeTab === 'query'
                ? 'bg-gradient-to-r from-primary-500 to-primary-600 text-white'
                : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:text-primary-600 dark:hover:text-primary-400'
            }`}
            title="Quick Query"
          >
            <Zap className="h-5 w-5" />
          </button>
          <button
            onClick={() => setActiveTab('docs')}
            className={`p-4 rounded-full shadow-lg transition-all duration-200 transform hover:scale-110 ${
              activeTab === 'docs'
                ? 'bg-gradient-to-r from-primary-500 to-primary-600 text-white'
                : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:text-primary-600 dark:hover:text-primary-400'
            }`}
            title="Documentation"
          >
            <BookOpen className="h-5 w-5" />
          </button>
        </div>
      </div>
    </div>
  )
}
