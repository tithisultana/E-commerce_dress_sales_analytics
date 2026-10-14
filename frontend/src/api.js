// Production backend on Render
const PRODUCTION_API_URL = 'https://ecommerce-dress-sales-api.onrender.com'

// Configured origin resolution order:
// 1. import.meta.env.VITE_API_BASE_URL (standard for Render / production deployments)
// 2. import.meta.env.VITE_API_URL (backward compatibility)
// 3. Fallback to Render URL in production builds (import.meta.env.PROD)
// 4. Fallback to empty string in development (Vite proxies '/api' to localhost:8000)
const envApiUrl =
  import.meta.env.VITE_API_BASE_URL ||
  import.meta.env.VITE_API_URL ||
  (import.meta.env.PROD ? PRODUCTION_API_URL : '')

const configuredOrigin = (envApiUrl || '').trim().replace(/\/+$/, '')

// If configuredOrigin ends with '/api', keep it; otherwise append '/api'
// In local/Codespaces dev without env vars, API_BASE is simply '/api'
export const API_BASE = configuredOrigin
  ? configuredOrigin.endsWith('/api')
    ? configuredOrigin
    : `${configuredOrigin}/api`
  : '/api'

/**
 * Robust fetch wrapper with automatic AbortController timeout (default 30s)
 */
export async function apiRequest(path, options = {}) {
  const timeoutMs = options.timeout ?? 30000
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

  let response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      signal: options.signal || controller.signal,
      headers: { 'Content-Type': 'application/json', ...options.headers },
      ...options,
    })
  } catch (err) {
    clearTimeout(timeoutId)
    if (err.name === 'AbortError') {
      throw new Error(
        `Request to ${path} timed out after ${timeoutMs / 1000}s. The server may be waking up, please retry.`
      )
    }
    const target = configuredOrigin || 'http://localhost:8000'
    throw new Error(
      `Cannot reach the analytics API at ${target}. Please verify that the backend is running and accessible.`
    )
  } finally {
    clearTimeout(timeoutId)
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `Analytics request failed (${response.status})`)
  }
  return response.json()
}

/**
 * 1. Initial Startup: Only load the lightweight overview summary
 */
export async function loadOverviewData() {
  const overview = await apiRequest('/overview')
  return {
    overview,
    categories: overview.category_revenue || overview.categories || [],
    payments: overview.payments || [],
    locations: overview.locations || [],
  }
}

/**
 * 2. Sales Analytics Page (Lazy loaded)
 * Uses Promise.allSettled so partial endpoint failures do not crash the view
 */
export async function loadSalesData() {
  const [monthlyRes, categoriesRes, paymentsRes, locationsRes] = await Promise.allSettled([
    apiRequest('/sales/monthly'),
    apiRequest('/sales/categories'),
    apiRequest('/sales/payment-methods'),
    apiRequest('/sales/locations'),
  ])

  const monthly = monthlyRes.status === 'fulfilled' ? monthlyRes.value : { monthly: [], weekday: [] }
  const categories = categoriesRes.status === 'fulfilled' ? categoriesRes.value : []
  const payments = paymentsRes.status === 'fulfilled' ? paymentsRes.value : []
  const locations = locationsRes.status === 'fulfilled' ? locationsRes.value : []

  const errors = [monthlyRes, categoriesRes, paymentsRes, locationsRes]
    .filter(r => r.status === 'rejected')
    .map(r => r.reason?.message)

  return {
    monthly,
    categories,
    payments,
    locations,
    error: errors.length > 0 && monthlyRes.status === 'rejected' ? errors[0] : null,
  }
}

/**
 * 3. Product Analytics Page (Lazy loaded)
 */
export async function loadProductData() {
  const products = await apiRequest('/products/top?limit=30')
  return { products }
}

/**
 * 4. Customer Analytics Page (Lazy loaded)
 * Backend limits full customer table to dashboard-safe sample (200 records)
 */
export async function loadCustomerData() {
  const customers = await apiRequest('/customers/analysis?limit=200')
  return { customers }
}

/**
 * 5. Customer Segmentation Page (Lazy loaded)
 */
export async function loadSegmentData() {
  const segments = await apiRequest('/customers/segments')
  return { segments }
}

/**
 * 6. Sales Prediction Page (Lazy loaded)
 */
export async function loadPredictionData() {
  const models = await apiRequest('/prediction/models')
  return { models }
}

/**
 * 7. Methodology Page (Lazy loaded)
 */
export async function loadMethodologyData() {
  const methodology = await apiRequest('/about')
  return { methodology }
}

/**
 * Full dashboard data loader (fallback using Promise.allSettled)
 */
export async function loadDashboardData() {
  const results = await Promise.allSettled([
    apiRequest('/overview'),
    apiRequest('/sales/monthly'),
    apiRequest('/sales/categories'),
    apiRequest('/sales/payment-methods'),
    apiRequest('/sales/locations'),
    apiRequest('/products/top?limit=30'),
    apiRequest('/customers/analysis?limit=200'),
    apiRequest('/customers/segments'),
    apiRequest('/prediction/models'),
    apiRequest('/about'),
  ])

  const val = (idx, fallback) =>
    results[idx].status === 'fulfilled' ? results[idx].value : fallback

  const overview = val(0, null)
  return {
    overview,
    monthly: val(1, { monthly: [], weekday: [] }),
    categories: val(2, overview?.category_revenue || []),
    payments: val(3, []),
    locations: val(4, []),
    products: val(5, { products: [], materials: [], sizes: [] }),
    customers: val(6, null),
    segments: val(7, { summary: [], customers: [] }),
    models: val(8, { metrics: [], categories: [], brands: [], sizes: [] }),
    methodology: val(9, {}),
  }
}