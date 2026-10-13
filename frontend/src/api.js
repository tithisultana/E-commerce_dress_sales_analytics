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

export async function apiRequest(path, options = {}) {
  let response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
      ...options,
    })
  } catch {
    const target = configuredOrigin || 'http://localhost:8000'
    throw new Error(
      `Cannot reach the analytics API at ${target}. Please verify that the backend is running and accessible.`
    )
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `Analytics request failed (${response.status})`)
  }
  return response.json()
}

export async function loadDashboardData() {
  const [
    overview,
    monthly,
    categories,
    payments,
    locations,
    products,
    customers,
    segments,
    models,
    methodology,
  ] = await Promise.all([
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
  return {
    overview,
    monthly,
    categories,
    payments,
    locations,
    products,
    customers,
    segments,
    models,
    methodology,
  }
}