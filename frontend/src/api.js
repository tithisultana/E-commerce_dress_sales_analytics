const configuredOrigin = (import.meta.env.VITE_API_URL || '').replace(/\/+$/, '')
const API_BASE = configuredOrigin
  ? configuredOrigin.endsWith('/api') ? configuredOrigin : `${configuredOrigin}/api`
  : '/api'

export async function apiRequest(path, options = {}) {
  let response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
      ...options,
    })
  } catch {
    throw new Error(`Cannot reach the analytics API at ${configuredOrigin || 'http://localhost:8000'}. Check that FastAPI is running on port 8000.`)
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `Analytics request failed (${response.status})`)
  }
  return response.json()
}

export async function loadDashboardData() {
  const [overview, monthly, categories, payments, locations, products, customers, segments, models, methodology] = await Promise.all([
    apiRequest('/overview'),
    apiRequest('/sales/monthly'),
    apiRequest('/sales/categories'),
    apiRequest('/sales/payment-methods'),
    apiRequest('/sales/locations'),
    apiRequest('/products/top?limit=30'),
    apiRequest('/customers/analysis'),
    apiRequest('/customers/segments'),
    apiRequest('/prediction/models'),
    apiRequest('/about'),
  ])
  return { overview, monthly, categories, payments, locations, products, customers, segments, models, methodology }
}