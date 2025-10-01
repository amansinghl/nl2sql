/**
 * Currency formatting utilities for displaying monetary values with rupee symbol
 */

// List of monetary column names that should be formatted as currency
const MONETARY_COLUMNS = [
  'cod_value',
  'total_price',
  'supplier_cost',
  'pre_gst_total_price',
  'pre_gst_total_partner_cost',
  'product_value',
  'transaction_amount',
  'received_amount',
  'credit_amount',
  'debit_amount',
  'cod_amount',
  'paid_amount',
  'pending_amount',
  'total_without_tax',
  'tax',
  'service_tax',
  'swachh_bharat_cess',
  'krishi_kalyan_cess',
  'igst',
  'sgst',
  'cgst',
  'tax_total',
  'duty_amount',
  'total',
  'paid',
  'pending',
  'qb_amount',
  'amount',
  'discount_amount',
  'refund_amount',
  'total_amount',
  'price',
  'per_slab_cost',
  'fuel_surcharge',
  'cod_tax',
  'extra_charges',
  'invoice_amount',
  'vama_bill',
  'vama_cost',
  'rto_cost',
  'rto_pending_cost'
]

/**
 * Check if a column name represents a monetary value
 */
export function isMonetaryColumn(columnName: string): boolean {
  return MONETARY_COLUMNS.includes(columnName.toLowerCase())
}

/**
 * Format a value as currency with rupee symbol
 */
export function formatCurrency(value: any): string {
  if (value === null || value === undefined || value === '') {
    return '₹0'
  }

  // Convert to number if it's a string
  const numValue = typeof value === 'string' ? parseFloat(value) : Number(value)
  
  // Check if it's a valid number
  if (isNaN(numValue)) {
    return String(value)
  }

  // Format with Indian number system (lakhs, crores)
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 0,
    maximumFractionDigits: 2
  }).format(numValue)
}

/**
 * Format a value for display, applying currency formatting if it's a monetary column
 */
export function formatValue(value: any, columnName?: string): string {
  if (columnName && isMonetaryColumn(columnName)) {
    return formatCurrency(value)
  }
  
  // For non-monetary values, return as string
  return value === null ? 'null' : String(value)
}

/**
 * Get the currency symbol
 */
export function getCurrencySymbol(): string {
  return '₹'
}
