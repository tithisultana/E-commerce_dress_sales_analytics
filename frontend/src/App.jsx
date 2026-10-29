import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  AlertCircle, ArrowDownWideNarrow, ArrowUpRight, BarChart3, Bot, Boxes, CircleHelp,
  Clock3, CreditCard, Database, Download, Layers3, LoaderCircle,
  Menu, MessageSquare, Package, Paperclip, RotateCw, Search, Send, Shirt, Sparkles, Star,
  Trash2, User, Users, Wallet, X,
} from 'lucide-react'
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ComposedChart,
  Legend, Line, Pie, PieChart, ResponsiveContainer, Scatter, ScatterChart,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import {
  apiRequest,
  loadOverviewData,
  loadSalesData,
  loadProductData,
  loadCustomerData,
  loadSegmentData,
  loadMethodologyData,
  loadNewProductPerformance,
  sendChatMessage,
} from './api.js'
import {
  translateCategory,
  translateLocation,
  translatePayment,
} from './i18n.js'

const navItems = [
  { id: 'overview', icon: Layers3 },
  { id: 'sales', icon: BarChart3 },
  { id: 'products', icon: Shirt },
  { id: 'customers', icon: Users },
  { id: 'segments', icon: Sparkles },
  { id: 'newProducts', icon: Package },
  { id: 'methodology', icon: CircleHelp },
]

// Professional chart color palette: warm copper, teal/emerald, sapphire, amber gold, slate, violet, cyan
const segmentColors = ['#ea580c', '#0d9488', '#d97706', '#6366f1', '#ec4899']
const colors = ['#ea580c', '#0d9488', '#2563eb', '#d97706', '#64748b', '#8b5cf6', '#06b6d4']

const currency = (value, lang = 'en') =>
  `৳${Number(value || 0).toLocaleString(lang === 'bn' ? 'bn-BD' : 'en-BD', { maximumFractionDigits: 0 })}`

const numeric = (value, lang = 'en') =>
  Number(value || 0).toLocaleString(lang === 'bn' ? 'bn-BD' : 'en-US', { maximumFractionDigits: 1 })

function Panel({ title, subtitle, action, className = '', children }) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-heading">
        <div>
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  )
}

function Metric({ label, value, note, icon: Icon, tone = 'copper' }) {
  return (
    <article className="metric-card">
      <div className={`metric-icon ${tone}`}><Icon size={18} strokeWidth={1.8} /></div>
      <div className="metric-copy">
        <span>{label}</span>
        <strong>{value}</strong>
        <small>{note}</small>
      </div>
    </article>
  )
}

function ChartTooltip({ active, payload, label, money = true, lang = 'en' }) {
  if (!active || !payload?.length) return null
  const displayLabel = translateCategory(label, lang) || translateLocation(label, lang) || label
  return (
    <div className="chart-tooltip">
      <strong>{displayLabel}</strong>
      {payload.map(item => (
        <span key={item.dataKey}>
          <i style={{ background: item.color || item.fill }} />
          {item.name || item.dataKey}: {money ? currency(item.value, lang) : numeric(item.value, lang)}
        </span>
      ))}
    </div>
  )
}

function ChartLegend({ payload }) {
  if (!payload?.length) return null
  return (
    <div className="dashboard-legend">
      {payload.map(item => (
        <span key={item.value}>
          <i style={{ background: item.color }} />
          {item.value}
        </span>
      ))}
    </div>
  )
}

function Table({ columns, rows, empty = 'No matching records.', rowKey }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>{columns.map(column => <th key={column.key}>{column.label}</th>)}</tr>
        </thead>
        <tbody>
          {rows.length ? (
            rows.map((row, index) => (
              <tr key={rowKey ? rowKey(row) : row.Product_ID || row.Customer_ID || index}>
                {columns.map(column => (
                  <td key={column.key}>
                    {column.render ? column.render(row[column.key], row) : row[column.key]}
                  </td>
                ))}
              </tr>
            ))
          ) : (
            <tr><td className="empty-cell" colSpan={columns.length}>{empty}</td></tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

function SearchField({ value, onChange, placeholder }) {
  return (
    <label className="search-field">
      <Search size={15} />
      <input value={value} onChange={event => onChange(event.target.value)} placeholder={placeholder} />
    </label>
  )
}

function Overview({ data }) {
  const { t, i18n } = useTranslation()
  const lang = i18n.language || 'en'
  const kpis = data.overview.kpis

  return (
    <>
      <div className="metric-grid six-metrics">
        <Metric label={t('overview.totalRevenue')} value={currency(kpis.revenue, lang)} note={t('overview.totalRevenueNote')} icon={Wallet} tone="copper" />
        <Metric label={t('overview.totalOrders')} value={numeric(kpis.orders, lang)} note={t('overview.totalOrdersNote')} icon={Package} tone="teal" />
        <Metric label={t('overview.totalItemsSold')} value={numeric(kpis.units, lang)} note={t('overview.totalItemsSoldNote')} icon={Boxes} tone="teal" />
        <Metric label={t('overview.averageOrderValue')} value={currency(kpis.average_order_value, lang)} note={t('overview.averageOrderValueNote')} icon={CreditCard} tone="copper" />
        <Metric label={t('overview.averageRating')} value={`${Number(kpis.average_rating).toLocaleString(lang === 'bn' ? 'bn-BD' : 'en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} / 5`} note={t('overview.averageRatingNote')} icon={Star} tone="gold" />
        <Metric label={t('overview.totalCustomers')} value={numeric(kpis.customers, lang)} note={t('overview.totalCustomersNote')} icon={Users} tone="teal" />
      </div>
      <div className="content-grid overview-grid">
        <Panel
          title={t('overview.monthlyRevenueTrajectory')}
          subtitle={`${data.overview.date_range.start} — ${data.overview.date_range.end} (${lang === 'bn' ? '৪১ মাস' : '41 months'}) · ${lang === 'bn' ? `অর্ডার: ${numeric(kpis.orders, lang)} (সম্পূর্ণ ডেটাসেট: ${numeric(kpis.full_dataset_rows || 10000000, lang)})` : `Filtered Orders: ${numeric(kpis.orders, lang)} (Full Dataset: ${numeric(kpis.full_dataset_rows || 10000000, lang)})`}`}
          className="span-two"
        >
          <div className="chart-area">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data.overview.monthly_revenue} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                <defs>
                  <linearGradient id="overviewRevenue" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#ea580c" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#ea580c" stopOpacity={0.01} />
                  </linearGradient>
                </defs>
                <CartesianGrid vertical={false} stroke="#f1f5f9" />
                <XAxis dataKey="Period" tickLine={false} axisLine={false} tick={{ fill: '#64748b', fontSize: 10 }} minTickGap={25} />
                <YAxis tickLine={false} axisLine={false} tick={{ fill: '#64748b', fontSize: 10 }} tickFormatter={value => `${Math.round(value / 1000)}k`} width={45} />
                <Tooltip content={<ChartTooltip lang={lang} />} />
                <Area name={t('common.revenue')} type="monotone" dataKey="revenue" stroke="#ea580c" strokeWidth={2.5} fill="url(#overviewRevenue)" activeDot={{ r: 4, fill: '#ea580c' }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Panel>
        <Panel title={t('overview.categoryRevenueShare')} subtitle={t('overview.categoryRevenueSubtitle')}>
          <div className="chart-area compact">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.categories} layout="vertical" margin={{ top: 2, right: 10, bottom: 0, left: 0 }}>
                <CartesianGrid horizontal={false} stroke="#f1f5f9" />
                <XAxis type="number" tickLine={false} axisLine={false} tick={{ fill: '#64748b', fontSize: 9 }} tickFormatter={value => `${Math.round(value / 1000)}k`} />
                <YAxis type="category" dataKey="Category" width={82} tickLine={false} axisLine={false} tick={{ fill: '#334155', fontSize: 10 }} tickFormatter={val => translateCategory(val, lang)} />
                <Tooltip content={<ChartTooltip lang={lang} />} />
                <Bar dataKey="revenue" name={t('common.revenue')} radius={[0, 4, 4, 0]} barSize={13}>
                  {data.categories.map((entry, index) => <Cell key={entry.Category} fill={colors[index % colors.length]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>
        <Panel title={t('overview.paymentMethodMix')} subtitle={t('overview.paymentMethodSubtitle')}>
          <div className="split-chart">
            <div className="donut-wrap">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={data.payments} dataKey="revenue" nameKey="Payment_Method" innerRadius={48} outerRadius={72} paddingAngle={3} stroke="none">
                    {data.payments.map((item, index) => <Cell key={item.Payment_Method} fill={colors[index % colors.length]} />)}
                  </Pie>
                  <Tooltip formatter={value => currency(value, lang)} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="legend-list">
              {data.payments.map((item, index) => {
                const revenueTotal = data.payments.reduce((sum, payment) => sum + Number(payment.revenue || 0), 0)
                const share = item.share ?? (revenueTotal ? item.revenue / revenueTotal * 100 : 0)
                return (
                  <div key={item.Payment_Method}>
                    <span><i style={{ background: colors[index % colors.length] }} />{translatePayment(item.Payment_Method, lang)}</span>
                    <b>{Number(share).toLocaleString(lang === 'bn' ? 'bn-BD' : 'en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%</b>
                  </div>
                )
              })}
            </div>
          </div>
        </Panel>
        <Panel title={t('overview.regionalDeliveryVolume')} subtitle={t('overview.regionalDeliverySubtitle')}>
          <div className="chart-area compact">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.locations} layout="vertical" margin={{ top: 0, right: 12, bottom: 0, left: 0 }}>
                <CartesianGrid horizontal={false} stroke="#f1f5f9" />
                <XAxis type="number" tickLine={false} axisLine={false} tick={{ fill: '#64748b', fontSize: 9 }} tickFormatter={value => `${Math.round(value / 1000)}k`} />
                <YAxis type="category" dataKey="Location" width={83} tickLine={false} axisLine={false} tick={{ fill: '#334155', fontSize: 10 }} tickFormatter={val => translateLocation(val, lang)} />
                <Tooltip content={<ChartTooltip lang={lang} />} />
                <Bar dataKey="revenue" name={t('common.revenue')} fill="#0d9488" radius={[0, 4, 4, 0]} barSize={13} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>
    </>
  )
}

function SalesAnalytics({ data }) {
  const { t, i18n } = useTranslation()
  const lang = i18n.language || 'en'
  const [range, setRange] = useState('all')
  const [unit, setUnit] = useState('revenue')
  const monthly = range === 'all' ? data.monthly.monthly : data.monthly.monthly.slice(-Number(range))

  return (
    <div className="content-grid two-column">
      <Panel
        title={t('sales.monthlySalesTitle')}
        subtitle={t('sales.monthlySalesSubtitle')}
        className="span-two"
        action={
          <div className="panel-filters">
            <select aria-label={t('sales.measureLabel')} value={unit} onChange={event => setUnit(event.target.value)}>
              <option value="revenue">{t('sales.revAndQty')}</option>
              <option value="orders">{t('sales.ordersAndQty')}</option>
            </select>
            <select aria-label={t('sales.periodLabel')} value={range} onChange={event => setRange(event.target.value)}>
              <option value="all">{t('common.allRecordedMonths')}</option>
              <option value="12">{t('common.last12Months')}</option>
              <option value="6">{t('common.last6Months')}</option>
            </select>
          </div>
        }
      >
        <div className="chart-area tall">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={monthly} margin={{ top: 10, right: 12, bottom: 0, left: 0 }}>
              <CartesianGrid vertical={false} stroke="#f1f5f9" />
              <XAxis dataKey="Period" tickLine={false} axisLine={false} tick={{ fill: '#64748b', fontSize: 10 }} minTickGap={18} />
              <YAxis yAxisId="main" tickLine={false} axisLine={false} tick={{ fill: '#64748b', fontSize: 10 }} tickFormatter={value => unit === 'revenue' ? `${Math.round(value / 1000)}k` : numeric(value, lang)} />
              <YAxis yAxisId="quantity" orientation="right" tickLine={false} axisLine={false} tick={{ fill: '#64748b', fontSize: 10 }} />
              <Tooltip content={<ChartTooltip money={unit === 'revenue'} lang={lang} />} />
              <Legend content={<ChartLegend />} />
              <Bar yAxisId="main" dataKey={unit === 'revenue' ? 'revenue' : 'orders'} name={unit === 'revenue' ? t('common.revenue') : t('common.orders')} fill="#ea580c" radius={[3, 3, 0, 0]} />
              <Line yAxisId="quantity" type="monotone" dataKey="units" name={t('sales.quantitySold')} stroke="#0d9488" strokeWidth={2.2} dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </Panel>
      <Panel title={t('sales.categoryPerformanceTitle')} subtitle={t('sales.categoryPerformanceSubtitle')}>
        <div className="chart-area compact">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.categories} margin={{ top: 8, right: 10, bottom: 0, left: -12 }}>
              <CartesianGrid vertical={false} stroke="#f1f5f9" />
              <XAxis dataKey="Category" tickLine={false} axisLine={false} tick={{ fill: '#64748b', fontSize: 9 }} interval={0} angle={-20} textAnchor="end" height={44} tickFormatter={val => translateCategory(val, lang)} />
              <YAxis tickLine={false} axisLine={false} tick={{ fill: '#64748b', fontSize: 9 }} tickFormatter={value => `${Math.round(value / 1000)}k`} />
              <Tooltip content={<ChartTooltip lang={lang} />} />
              <Bar dataKey="revenue" name={t('common.revenue')} fill="#0d9488" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Panel>
      <Panel title={t('sales.paymentGatewayTitle')} subtitle={t('sales.paymentGatewaySubtitle')}>
        <div className="chart-area compact">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.payments} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
              <CartesianGrid vertical={false} stroke="#f1f5f9" />
              <XAxis dataKey="Payment_Method" tickLine={false} axisLine={false} tick={{ fill: '#64748b', fontSize: 9 }} interval={0} angle={-15} textAnchor="end" height={42} tickFormatter={val => translatePayment(val, lang)} />
              <YAxis tickLine={false} axisLine={false} tick={{ fill: '#64748b', fontSize: 9 }} tickFormatter={value => `${Math.round(value / 1000)}k`} />
              <Tooltip content={<ChartTooltip lang={lang} />} />
              <Bar dataKey="revenue" name={t('common.revenue')} fill="#d97706" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Panel>
      <Panel title={t('sales.territorySalesTitle')} subtitle={t('sales.territorySalesSubtitle')} className="span-two">
        <div className="chart-area tall">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.locations} layout="vertical" margin={{ top: 4, right: 16, bottom: 0, left: 4 }}>
              <CartesianGrid horizontal={false} stroke="#f1f5f9" />
              <XAxis type="number" tickLine={false} axisLine={false} tick={{ fill: '#64748b', fontSize: 10 }} tickFormatter={value => `${Math.round(value / 1000)}k`} />
              <YAxis type="category" dataKey="Location" width={96} tickLine={false} axisLine={false} tick={{ fill: '#334155', fontSize: 10 }} tickFormatter={val => translateLocation(val, lang)} />
              <Tooltip content={<ChartTooltip lang={lang} />} />
              <Bar dataKey="revenue" name={t('common.revenue')} fill="#0d9488" radius={[0, 4, 4, 0]} barSize={17} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Panel>
      <p className="method-note span-two">
        {t('sales.scopeNotice')}
      </p>
    </div>
  )
}

function ProductAnalytics({ data }) {
  const { t, i18n } = useTranslation()
  const lang = i18n.language || 'en'
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('All categories')
  const categoryOptions = [...new Set(data.products.products.map(item => item.Category))].sort()
  const filtered = data.products.products.filter(product =>
    (category === 'All categories' || product.Category === category) &&
    `${product.Product_Name} ${product.Brand} ${product.Category}`.toLowerCase().includes(search.toLowerCase())
  )
  const bestSellers = [...data.products.products].sort((a, b) => b.units - a.units).slice(0, 10)
  const hasDiscountData = data.products.products.some(product => Number.isFinite(Number(product.discount)))
  const discountLeaders = hasDiscountData ? [...data.products.products].sort((a, b) => b.discount - a.discount).slice(0, 10) : []
  const columns = [
    {
      key: 'Product_Name',
      label: t('products.colProduct'),
      render: (value, row) => (
        <div className="product-cell">
          <span className="product-mark"><Shirt size={15} /></span>
          <span>
            <strong>{value}</strong>
            <small>{row.Product_ID}</small>
          </span>
        </div>
      ),
    },
    { key: 'Category', label: t('products.colCategory'), render: value => translateCategory(value, lang) },
    { key: 'Brand', label: t('products.colBrand') },
    { key: 'price', label: t('products.colAvgPrice'), render: value => currency(value, lang) },
    { key: 'units', label: t('products.colUnitsSold'), render: value => numeric(value, lang) },
    { key: 'revenue', label: t('products.colNetRevenue'), render: value => currency(value, lang) },
    { key: 'rating', label: t('products.colRating'), render: value => <span className="rating"><b>★</b> {Number(value).toLocaleString(lang === 'bn' ? 'bn-BD' : 'en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span> },
    { key: 'discount', label: t('products.colAvgDiscount'), render: value => `${Number(value).toLocaleString(lang === 'bn' ? 'bn-BD' : 'en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%` },
  ]

  return (
    <div className="content-grid two-column">
      <Panel title={t('products.top10Bestsellers')} subtitle={t('products.top10Subtitle')} className="span-two">
        <div className="chart-area tall">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={bestSellers} layout="vertical" margin={{ top: 4, right: 18, bottom: 0, left: 4 }}>
              <CartesianGrid horizontal={false} stroke="#f1f5f9" />
              <XAxis type="number" tickLine={false} axisLine={false} tick={{ fill: '#64748b', fontSize: 10 }} />
              <YAxis type="category" dataKey="Product_Name" width={132} tickLine={false} axisLine={false} tick={{ fill: '#334155', fontSize: 9 }} />
              <Tooltip content={<ChartTooltip money={false} lang={lang} />} />
              <Bar dataKey="units" name={t('sales.quantitySold')} fill="#ea580c" radius={[0, 4, 4, 0]} barSize={15} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Panel>
      <Panel title={t('products.revenueLeaders')} subtitle={t('products.revenueLeadersSubtitle')}>
        <div className="chart-area compact">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.products.products.slice(0, 10)} layout="vertical" margin={{ top: 0, right: 12, bottom: 0, left: 4 }}>
              <CartesianGrid horizontal={false} stroke="#f1f5f9" />
              <XAxis type="number" tickLine={false} axisLine={false} tick={{ fill: '#64748b', fontSize: 9 }} tickFormatter={value => `${Math.round(value / 1000)}k`} />
              <YAxis type="category" dataKey="Product_Name" width={112} tickLine={false} axisLine={false} tick={{ fill: '#334155', fontSize: 9 }} />
              <Tooltip content={<ChartTooltip lang={lang} />} />
              <Bar dataKey="revenue" name={t('common.revenue')} fill="#0d9488" radius={[0, 4, 4, 0]} barSize={12} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Panel>
      <Panel title={t('products.discountStrategy')} subtitle={t('products.discountStrategySubtitle')}>
        {hasDiscountData ? (
          <div className="chart-area compact">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={discountLeaders} layout="vertical" margin={{ top: 0, right: 12, bottom: 0, left: 4 }}>
                <CartesianGrid horizontal={false} stroke="#f1f5f9" />
                <XAxis type="number" unit="%" tickLine={false} axisLine={false} tick={{ fill: '#64748b', fontSize: 9 }} />
                <YAxis type="category" dataKey="Product_Name" width={112} tickLine={false} axisLine={false} tick={{ fill: '#334155', fontSize: 9 }} />
                <Tooltip formatter={value => `${Number(value).toLocaleString(lang === 'bn' ? 'bn-BD' : 'en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`} />
                <Bar dataKey="discount" name={t('products.colAvgDiscount')} fill="#d97706" radius={[0, 4, 4, 0]} barSize={12} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="data-unavailable">
            <ArrowDownWideNarrow size={17} />
            <span>{t('products.discountUnavailable')}</span>
          </div>
        )}
      </Panel>
      <Panel
        title={t('products.catalogPerformance')}
        subtitle={t('products.catalogSubtitle', { count: numeric(filtered.length, lang) })}
        className="span-two"
        action={
          <div className="table-filters">
            <SearchField value={search} onChange={setSearch} placeholder={t('products.searchPlaceholder')} />
            <select aria-label={t('products.filterCategoryLabel')} value={category} onChange={event => setCategory(event.target.value)}>
              <option value="All categories">{t('common.allCategories')}</option>
              {categoryOptions.map(option => <option key={option} value={option}>{translateCategory(option, lang)}</option>)}
            </select>
          </div>
        }
      >
        <Table columns={columns} rows={filtered} empty={t('products.noMatch')} />
      </Panel>
      <p className="method-note span-two">
        {t('products.scopeNotice')}
      </p>
    </div>
  )
}

function CustomerAnalytics({ data }) {
  const { t, i18n } = useTranslation()
  const lang = i18n.language || 'en'
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(0)
  const pageSize = 12
  const allCustomers = data.customers.customers || data.customers.top_customers
  const fullCustomerRecordsAvailable = Boolean(data.customers.customers)
  const filtered = allCustomers.filter(customer =>
    `${customer.Customer_ID} ${customer.location}`.toLowerCase().includes(search.toLowerCase())
  )
  const visible = filtered.slice(page * pageSize, (page + 1) * pageSize)
  const pageCount = Math.ceil(filtered.length / pageSize)
  const columns = [
    { key: 'Customer_ID', label: t('customers.colCustomerID'), render: value => <strong className="mono">{value}</strong> },
    { key: 'location', label: t('customers.colRegion'), render: value => translateLocation(value || 'Dhaka', lang) },
    { key: 'orders', label: t('customers.colTotalOrders'), render: value => numeric(value, lang) },
    { key: 'items', label: t('customers.colTotalItems'), render: value => numeric(value, lang) },
    { key: 'spend', label: t('customers.colNetSpend'), render: value => currency(value, lang) },
    { key: 'rating', label: t('customers.colAvgRating'), render: value => (value ? Number(value).toLocaleString(lang === 'bn' ? 'bn-BD' : 'en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—') },
  ]

  return (
    <>
      <div className="metric-grid four-metrics">
        <Metric label={t('customers.totalBase')} value={numeric(data.customers.customer_count, lang)} note={t('customers.totalBaseNote')} icon={Users} tone="teal" />
        <Metric label={t('customers.avgValue')} value={currency(data.customers.average_customer_value, lang)} note={t('customers.avgValueNote')} icon={Wallet} tone="copper" />
        <Metric label={t('customers.orderFreq')} value={data.customers.average_orders_per_customer == null ? '—' : numeric(data.customers.average_orders_per_customer, lang)} note={t('customers.orderFreqNote')} icon={RotateCw} tone="teal" />
        <Metric label={t('customers.repeatCustomers')} value={numeric(data.customers.repeat_customers, lang)} note={t('customers.repeatCustomersNote')} icon={ArrowUpRight} tone="gold" />
      </div>
      <div className="content-grid two-column">
        <Panel title={t('customers.regionalDistTitle')} subtitle={t('customers.regionalDistSubtitle')}>
          <div className="chart-area tall">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.customers.locations} layout="vertical" margin={{ top: 4, right: 14, bottom: 0, left: 0 }}>
                <CartesianGrid horizontal={false} stroke="#f1f5f9" />
                <XAxis type="number" tickLine={false} axisLine={false} tick={{ fill: '#64748b', fontSize: 10 }} />
                <YAxis type="category" dataKey="Location" width={94} tickLine={false} axisLine={false} tick={{ fill: '#334155', fontSize: 10 }} tickFormatter={val => translateLocation(val, lang)} />
                <Tooltip formatter={(value, name) => [numeric(value, lang), t('common.customers')]} />
                <Bar dataKey="customers" name={t('common.customers')} fill="#0d9488" radius={[0, 4, 4, 0]} barSize={16} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>
        <Panel title={t('customers.topSpendersTitle')} subtitle={t('customers.topSpendersSubtitle')}>
          <div className="rank-list">
            {data.customers.top_customers.slice(0, 7).map((customer, index) => (
              <div className="rank-row" key={customer.Customer_ID}>
                <span className="rank-index">{String(index + 1).padStart(2, '0')}</span>
                <div className="rank-name">
                  <strong>{customer.Customer_ID}</strong>
                  <small>{translateLocation(customer.location || 'Dhaka', lang)} · {numeric(customer.orders, lang)} {t('customers.ordersCount')}</small>
                </div>
                <b>{currency(customer.spend, lang)}</b>
              </div>
            ))}
          </div>
        </Panel>
        <Panel
          title={t('customers.accountLedgerTitle')}
          subtitle={fullCustomerRecordsAvailable ? t('customers.totalAccountsSubtitle', { count: numeric(filtered.length, lang) }) : t('customers.priorityAccountsSubtitle', { count: numeric(filtered.length, lang) })}
          className="span-two"
          action={
            <SearchField value={search} onChange={value => { setSearch(value); setPage(0) }} placeholder={t('customers.searchPlaceholder')} />
          }
        >
          <Table columns={columns} rows={visible} empty={t('customers.noMatch')} />
          <div className="table-pagination">
            <span>{t('common.showingPagination', { from: numeric(filtered.length ? page * pageSize + 1 : 0, lang), to: numeric(Math.min((page + 1) * pageSize, filtered.length), lang), total: numeric(filtered.length, lang) })}</span>
            <div>
              <button disabled={page === 0} onClick={() => setPage(current => current - 1)}>{t('common.previous')}</button>
              <button disabled={page + 1 >= pageCount} onClick={() => setPage(current => current + 1)}>{t('common.next')}</button>
            </div>
          </div>
        </Panel>
      </div>
      <p className="method-note span-two" style={{ marginTop: 12 }}>
        {t('customers.scopeNotice')}
      </p>
    </>
  )
}

function CustomerSegmentation({ data }) {
  const { t, i18n } = useTranslation()
  const lang = i18n.language || 'en'
  const summary = data.segments.summary
  const segmentName = cluster => `${t('segments.segmentPrefix')} ${numeric(cluster, lang)}`

  return (
    <div className="content-grid two-column">
      <Panel title={t('segments.cohortDistTitle')} subtitle={t('segments.cohortDistSubtitle')}>
        <div className="segment-overview">
          <div className="segment-donut">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={summary} dataKey="customers" nameKey="cluster" innerRadius={58} outerRadius={88} paddingAngle={3} stroke="none">
                  {summary.map((item, index) => <Cell key={item.cluster} fill={segmentColors[index % segmentColors.length]} />)}
                </Pie>
                <Tooltip formatter={(value, name) => [`${numeric(value, lang)} ${t('common.accounts')}`, segmentName(name)]} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="legend-list segment-distribution">
            {summary.map((item, index) => (
              <div key={item.cluster}>
                <span><i style={{ background: segmentColors[index % segmentColors.length] }} />{segmentName(item.cluster)}</span>
                <b>{numeric(item.customers, lang)} {t('common.accounts')}</b>
              </div>
            ))}
          </div>
        </div>
      </Panel>
      <Panel title={t('segments.scatterTitle')} subtitle={t('segments.scatterSubtitle')}>
        <div className="chart-area">
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 10, right: 14, bottom: 6, left: 6 }}>
              <CartesianGrid stroke="#f1f5f9" />
              <XAxis type="number" dataKey="spend" name={t('segments.grossSpend')} tickLine={false} axisLine={false} tick={{ fill: '#64748b', fontSize: 9 }} tickFormatter={value => `${Math.round(value / 1000)}k`} />
              <YAxis type="number" dataKey="orders" name={t('common.orders')} tickLine={false} axisLine={false} tick={{ fill: '#64748b', fontSize: 9 }} />
              <Tooltip formatter={(value, name) => [name === 'Gross spend' || name === t('segments.grossSpend') ? currency(value, lang) : numeric(value, lang), name]} />
              <Scatter data={data.segments.customers} name={t('common.customers')}>
                {data.segments.customers.map((item, index) => (
                  <Cell key={`${item.Customer_ID}-${index}`} fill={segmentColors[Number(item.cluster) % segmentColors.length]} fillOpacity={0.65} />
                ))}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      </Panel>
      {summary.map((segment, index) => (
        <article className="segment-card" key={segment.cluster}>
          <div className="segment-top">
            <span className="segment-dot" style={{ background: segmentColors[index % segmentColors.length] }} />
            <span>{segmentName(segment.cluster)}</span>
            <strong>{numeric(segment.customers, lang)}<small> {t('common.accounts')}</small></strong>
          </div>
          <div className="segment-stats">
            <div><small>{t('segments.avgSpend')}</small><b>{currency(segment.spend, lang)}</b></div>
            <div><small>{t('segments.avgOrders')}</small><b>{numeric(segment.orders, lang)}</b></div>
            <div><small>{t('segments.avgItems')}</small><b>{numeric(segment.items, lang)}</b></div>
          </div>
        </article>
      ))}
    </div>
  )
}

function NewProductPerformance({ data }) {
  const { t, i18n } = useTranslation()
  const lang = i18n.language || 'en'

  const products = data?.products || []
  const meta = data?.meta || {}
  const [selectedId, setSelectedId] = useState(products[0]?.product_id || 'P016')

  const selectedProduct = products.find(p => p.product_id === selectedId) || products[0]

  if (!products.length || !selectedProduct) {
    return (
      <div className="error-state" role="alert">
        <strong>{t('newProducts.unavailable')}</strong>
        <p>{t('newProducts.noData')}</p>
      </div>
    )
  }

  const { metrics, monthly_trend, category_benchmark, observation_window } = selectedProduct

  const benchmarkRows = [
    {
      metric: lang === 'bn' ? 'বিক্রিত ইউনিট' : 'Units Sold',
      productVal: numeric(metrics.units, lang),
      catVal: numeric(category_benchmark.avg_units, lang),
      diff: category_benchmark.avg_units ? ((metrics.units - category_benchmark.avg_units) / category_benchmark.avg_units * 100) : 0,
    },
    {
      metric: lang === 'bn' ? 'নিট রাজস্ব' : 'Net Revenue',
      productVal: currency(metrics.revenue, lang),
      catVal: currency(category_benchmark.avg_revenue, lang),
      diff: category_benchmark.avg_revenue ? ((metrics.revenue - category_benchmark.avg_revenue) / category_benchmark.avg_revenue * 100) : 0,
    },
    {
      metric: lang === 'bn' ? 'অনন্য ক্রেতা' : 'Unique Buyers',
      productVal: numeric(metrics.unique_customers, lang),
      catVal: numeric(category_benchmark.avg_customers, lang),
      diff: category_benchmark.avg_customers ? ((metrics.unique_customers - category_benchmark.avg_customers) / category_benchmark.avg_customers * 100) : 0,
    },
    {
      metric: lang === 'bn' ? 'পুনঃক্রয় হার' : 'Repeat Purchase Rate',
      productVal: `${numeric(metrics.repeat_rate, lang)}%`,
      catVal: `${numeric(category_benchmark.avg_repeat_rate, lang)}%`,
      diff: metrics.repeat_rate - category_benchmark.avg_repeat_rate,
      isAbsDiff: true,
    },
  ]

  return (
    <div className="new-products-view">
      <Panel
        title={t('newProducts.selectProduct')}
        subtitle={`${t('newProducts.allProductsCount')} · ${meta.global_start || '2023-01-01'} — ${meta.global_cutoff || '2026-05-31'}`}
      >
        <div className="product-selector-bar">
          <label className="selector-label" htmlFor="product-select">
            <Shirt size={16} />
            <span>{t('products.colProduct')}:</span>
          </label>
          <select
            id="product-select"
            className="product-dropdown"
            value={selectedId}
            onChange={e => setSelectedId(e.target.value)}
          >
            {products.map(p => (
              <option key={p.product_id} value={p.product_id}>
                {p.product_id} — {p.product_name} ({translateCategory(p.category, lang)} · {p.brand})
              </option>
            ))}
          </select>
          <span className="first-sale-badge">
            <Clock3 size={14} />
            {t('newProducts.firstSaleBadge', { date: selectedProduct.first_recorded_sale })}
          </span>
          <span className="first-sale-badge" style={{ marginLeft: 8 }}>
            <Clock3 size={14} />
            {t('newProducts.observationWindowBadge', {
              start: observation_window.start,
              end: observation_window.end,
              months: observation_window.months,
            })}
          </span>
        </div>
      </Panel>

      <div className="source-scope-callout" style={{
        margin: '16px 0',
        padding: '12px 16px',
        borderRadius: 8,
        border: '1px solid rgba(13, 148, 136, 0.4)',
        background: 'rgba(13, 148, 136, 0.1)',
        color: '#5eead4',
        display: 'flex',
        alignItems: 'center',
        gap: 10,
      }}>
        <AlertCircle size={18} style={{ flexShrink: 0 }} />
        <div>
          <strong>{t('newProducts.sourceScopeBadge')}</strong>
          <div style={{ fontSize: '0.85rem', marginTop: 3, opacity: 0.9 }}>{t('newProducts.historyLimitationNotice')}</div>
        </div>
      </div>

      <div className="metric-grid six-metrics">
        <Metric
          label={t('newProducts.kpiUniquePurchasers')}
          value={numeric(metrics.unique_customers, lang)}
          note={t('newProducts.kpiUniquePurchasersNote')}
          icon={Users}
          tone="teal"
        />
        <Metric
          label={t('newProducts.kpiTotalOrders')}
          value={numeric(metrics.orders, lang)}
          note={t('newProducts.kpiTotalOrdersNote')}
          icon={Package}
          tone="teal"
        />
        <Metric
          label={t('newProducts.kpiUnitsSold')}
          value={numeric(metrics.units, lang)}
          note={t('newProducts.kpiUnitsSoldNote')}
          icon={Boxes}
          tone="teal"
        />
        <Metric
          label={t('newProducts.kpiNetRevenue')}
          value={currency(metrics.revenue, lang)}
          note={t('newProducts.kpiNetRevenueNote')}
          icon={Wallet}
          tone="copper"
        />
        <Metric
          label={t('newProducts.kpiRepeatBuyers')}
          value={`${numeric(metrics.repeat_customers, lang)} (${numeric(metrics.repeat_rate, lang)}%)`}
          note={t('newProducts.kpiRepeatNote')}
          icon={Sparkles}
          tone="gold"
        />
        <Metric
          label={t('newProducts.kpiAvgUnitsOrder')}
          value={numeric(metrics.avg_units_per_order, lang)}
          note={`${t('newProducts.kpiAvgCustValue')}: ${currency(metrics.avg_revenue_per_customer, lang)}`}
          icon={CreditCard}
          tone="copper"
        />
      </div>

      <div className="content-grid overview-grid">
        <Panel
          title={t('newProducts.trendTitle')}
          subtitle={t('newProducts.trendSubtitle', { cutoff: meta.global_cutoff || '2026-05-31' })}
          className="span-two"
        >
          <div className="chart-area" style={{ height: 320 }}>
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={monthly_trend} margin={{ top: 12, right: 12, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(148, 163, 184, 0.2)" />
                <XAxis dataKey="period" stroke="#94a3b8" tickLine={false} fontSize={12} />
                <YAxis yAxisId="left" stroke="#94a3b8" tickLine={false} fontSize={12} />
                <YAxis yAxisId="right" orientation="right" stroke="#94a3b8" tickLine={false} fontSize={12} />
                <Tooltip
                  formatter={(val, name) => [
                    numeric(val, lang),
                    name === 'units' ? t('newProducts.colUnits')
                      : name === 'monthly_unique_customers' ? t('newProducts.colMonthlyUnique')
                      : t('newProducts.colFirstTime')
                  ]}
                  labelFormatter={lbl => `${t('newProducts.colMonth')}: ${lbl}`}
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: 8, color: '#f8fafc' }}
                />
                <Legend
                  formatter={value => (
                    value === 'units' ? t('newProducts.colUnits')
                      : value === 'monthly_unique_customers' ? t('newProducts.colMonthlyUnique')
                      : t('newProducts.colFirstTime')
                  )}
                />
                <Bar yAxisId="left" dataKey="units" fill="#0d9488" radius={[4, 4, 0, 0]} barSize={20} />
                <Line yAxisId="right" type="monotone" dataKey="monthly_unique_customers" stroke="#2563eb" strokeWidth={2.5} dot={{ r: 3 }} />
                <Line yAxisId="right" type="monotone" dataKey="first_time_buyers" stroke="#ea580c" strokeWidth={2.5} strokeDasharray="4 4" dot={{ r: 3 }} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel
          title={t('newProducts.benchmarkTitle')}
          subtitle={t('newProducts.benchmarkSubtitle', { category: translateCategory(selectedProduct.category, lang), months: observation_window.months })}
          className="span-two"
        >
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t('newProducts.metricLabel')}</th>
                  <th>{t('newProducts.thisProduct', { product: selectedProduct.product_id })}</th>
                  <th>{t('newProducts.categoryAvg', { category: translateCategory(selectedProduct.category, lang) })}</th>
                  <th>{t('newProducts.comparisonVariance')}</th>
                </tr>
              </thead>
              <tbody>
                {benchmarkRows.map(row => {
                  const isPositive = row.diff >= 0
                  return (
                    <tr key={row.metric}>
                      <td><strong>{row.metric}</strong></td>
                      <td>{row.productVal}</td>
                      <td>{row.catVal}</td>
                      <td>
                        <span className={`variance-pill ${isPositive ? 'positive' : 'negative'}`}>
                          {isPositive ? '+' : ''}{row.diff.toFixed(1)}{row.isAbsDiff ? ' pts' : '%'}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>
    </div>
  )
}

function Methodology() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language || 'en'

  const flow = [
    { title: lang === 'bn' ? 'ডেটা সোর্স লেয়ার' : 'Data Source Layer', desc: lang === 'bn' ? 'অর্ডার ডাটাবেজ, POS, CSV, API এবং CRM' : 'Order DB, POS, CSV, APIs & CRM' },
    { title: lang === 'bn' ? 'গুগল ড্রাইভ র ডেটা স্টোরেজ' : 'Google Drive Raw Data Storage', desc: lang === 'bn' ? '১ কোটি র লেনদেনের আর্কাইভ' : '10M raw transaction archive' },
    { title: lang === 'bn' ? 'চাঙ্ক-ভিত্তিক প্রসেসিং' : 'Chunk-wise Processing', desc: lang === 'bn' ? '১ লাখ সারির ব্যাচ-ভিত্তিক ETL' : '100k-row chunk ETL pipeline' },
    { title: lang === 'bn' ? 'প্রসেসড অ্যানালিটিক্স আউটপুট' : 'Processed Analytics Outputs', desc: lang === 'bn' ? 'অপ্টিমাইজড JSON ও CSV ফাইল' : 'Optimized JSON & CSV artifacts' },
    { title: lang === 'bn' ? 'FastAPI ব্যাকএন্ড' : 'FastAPI Backend', desc: lang === 'bn' ? 'সাব-সেকেন্ড গতিতে তথ্য পরিবেশন' : 'Sub-second summary serving' },
    { title: lang === 'bn' ? 'K-Means কাস্টমার সেগমেন্টেশন' : 'K-Means Customer Segmentation', desc: lang === 'bn' ? 'আচরণগত কোহোর্ট ক্লাস্টারিং' : 'Behavioral cohort clustering' },
    { title: lang === 'bn' ? 'React ড্যাশবোর্ড' : 'React Dashboard', desc: lang === 'bn' ? 'ইন্টারঅ্যাক্টিভ ভিজ্যুয়াল ইন্টারফেস' : 'Interactive visual workspace' },
  ]

  const architectureItems = [
    {
      label: lang === 'bn' ? 'ডেটা সোর্স লেয়ার' : 'Data Source Layer',
      value: lang === 'bn'
        ? 'বাস্তব এন্টারপ্রাইজ পরিবেশে ওয়েবসাইট ডাটাবেজ (PostgreSQL/MySQL), পিওএস টার্মিনাল, ম্যানুয়াল এক্সেল/সিএসভি সেলস রিপোর্ট, দারাজ/শপিফাই এর মতো প্ল্যাটফর্মের এপিআই অথবা গ্রাহক সিআরএম ডাটাবেজ থেকে তথ্য সংগৃহীত হয়। এই ড্যাশবোর্ড প্রোটোটাইপে প্রস্তুতকৃত ডেটাসেট ব্যবহার করা হয়েছে।'
        : 'In enterprise environments, transactions originate from website order databases (PostgreSQL/MySQL), physical POS terminals, manual Excel/CSV sales reports, e-commerce platform APIs (Shopify, Daraz, WooCommerce), or customer CRM databases. For this dashboard prototype, analytics are powered by a prepared Dataset.',
    },
    {
      label: lang === 'bn' ? 'গুগল ড্রাইভ র ডেটা স্টোরেজ' : 'Google Drive Raw Data Storage',
      value: lang === 'bn'
        ? 'বিশাল পরিমাণ র ডেটাসেট (১,০০,০০,০০০টি লেনদেন রেকর্ড) গিটহাব রিপোজিটরির বাইরে গুগল ড্রাইভ ক্লাউড স্টোরেজে সংরক্ষিত রাখা হয়েছে। এতে রিপোজিটরি হালকা থাকে এবং সম্পূর্ণ লেনদেনের কেন্দ্রীয় হিস্টোরি ক্লাউডে সুরক্ষিত থাকে।'
        : 'Raw large datasets (10,000,000 transaction records) are stored externally in Google Drive raw data storage. This keeps the GitHub repository lightweight while preserving a central cloud archive of full transactional history.',
    },
    {
      label: lang === 'bn' ? 'চাঙ্ক-ভিত্তিক প্রসেসিং' : 'Chunk-wise Processing',
      value: lang === 'bn'
        ? 'উচ্চ ভলিউমের ডেটা গুগল কোল্যাবে অফলাইনে প্রতি ব্যাচে ১,০০,০০০ রেকর্ড করে প্রসেস করা হয়েছে। মেমোরিতে রানিং অ্যাক্যুমুলেটরের মাধ্যমে গ্রুপ-বাই ও যোগফল হিসাব করা হয় এবং সাথে সাথে র ডেটা মেমোরি থেকে মুক্ত করে র‍্যামের অতিরিক্ত ব্যবহার ঠেকানো হয়।'
        : 'Raw high-volume data is processed chunk-by-chunk (100,000 records per batch) offline in Google Colab. Running accumulators compute totals and group-by metrics in memory, immediately releasing raw chunks to prevent RAM exhaustion.',
    },
    {
      label: lang === 'bn' ? 'প্রসেসড অ্যানালিটিক্স আউটপুট' : 'Processed Analytics Outputs',
      value: lang === 'bn'
        ? 'অফলাইন পাইপলাইন পাঁচটি হালকা ও অপ্টিমাইজড ফাইল তৈরি করে data/processed/ ফোল্ডারে রাখে: dashboard_summary_10M.json (কেপিআই ও সময়ভিত্তিক বিশ্লেষণ), customer_agg_10M.csv (৫ লাখ ক্রেতার প্রোফাইল), prediction_sample_10M.csv (চার্টের নমুনা ডেটা), product_performance.json (নতুন পণ্যের বাজার সাড়া ও কোহোর্ট অ্যানালিটিক্স), এবং manifest.json (উৎপত্তি ও নিরীক্ষা মেটাডেটা)।'
        : 'The offline pipeline produces five lightweight artifacts stored in data/processed/: dashboard_summary_10M.json (KPIs, time series, categorical aggregates), customer_agg_10M.csv (500k unique customer profiles), prediction_sample_10M.csv (stratified sample for visual plotting), product_performance.json (product adoption & cohort analytics), and manifest.json (provenance & reconciliation metadata).',
    },
    {
      label: lang === 'bn' ? 'FastAPI ব্যাকএন্ড পরিবেশন' : 'FastAPI Backend Serving',
      value: lang === 'bn'
        ? 'FastAPI ব্যাকএন্ড সার্ভার ১ কোটি র সারি লোড না করে কেবল অপ্টিমাইজড প্রসেসড সামারি ফাইলগুলো পড়ে। এর ফলে সার্ভার মেমোরির ওপর চাপ পড়ে না এবং সাব-সেকেন্ডে তাৎক্ষণিক রেসপন্স নিশ্চিত হয়।'
        : 'The FastAPI backend reads only the processed analytics outputs rather than loading the raw 10M CSV. This avoids loading raw 10M data in the website, eliminates cold-start latency, and guarantees instantaneous response times.',
    },
    {
      label: lang === 'bn' ? 'React ড্যাশবোর্ড ইন্টারফেস' : 'React Dashboard Presentation',
      value: lang === 'bn'
        ? 'React ফ্রন্টএন্ড সুন্দর ও ইন্টারঅ্যাক্টিভ চার্ট এবং কেপিআই কার্ড মসৃণভাবে পরিবেশন করে। অফলাইন কম্পিউটেশন থেকে ফ্রন্টএন্ড উপস্থাপনা আলাদা থাকায় ড্যাশবোর্ড সবসময় দ্রুত ও কার্যকর থাকে।'
        : 'The React frontend renders interactive visualizations and KPI cards seamlessly. Decoupling storage and offline compute from frontend delivery avoids RAM overload and keeps the dashboard exceptionally fast.',
    },
  ]

  const specifications = [
    [lang === 'bn' ? 'সক্রিয় বিশ্লেষণ সময়সীমা' : 'Active Analysis Scope', lang === 'bn' ? '০১-০১-২০২৩ থেকে ৩১-০৫-২০২৬ (৪১ মাস; ফিল্টারকৃত অর্ডার: ৮৫,৪১,২৫০)' : '2023-01-01 to 2026-05-31 (41 months; filtered orders: 8,541,250)'],
    [lang === 'bn' ? 'সম্পূর্ণ ডেটাসেটের আকার' : 'Full Dataset Scale', lang === 'bn' ? '১,০০,০০,০০০টি লেনদেন (৪৮ মাস, ৩১-১২-২০২৬ পর্যন্ত)' : '10,000,000 transactions (48 months through 2026-12-31)'],
    [lang === 'bn' ? 'গ্রাহক সংখ্যা' : 'Customers', lang === 'bn' ? '৫,০০,০০০ অনন্য নিবন্ধিত ক্রেতা' : '500,000 unique registered buyers'],
    [lang === 'bn' ? 'উদ্দেশ্য' : 'Purpose', lang === 'bn' ? 'বিজনেস অ্যানালিটিক্স ড্যাশবোর্ড প্রোটোটাইপ' : 'Business Analytics Dashboard prototype'],
    [lang === 'bn' ? 'র ডেটা স্টোরেজ' : 'Raw Storage', lang === 'bn' ? 'গুগল ড্রাইভ র ডেটা স্টোরেজ (বাহ্যিক ক্লাউড আর্কাইভ)' : 'Google Drive raw data storage (external archive)'],
    [lang === 'bn' ? 'আর্কিটেকচার' : 'Architecture', lang === 'bn' ? 'প্রসেসড অ্যানালিটিক্স ব্যাকএন্ডসহ FastAPI + React আর্কিটেকচার' : 'FastAPI + React architecture with processed analytics backend'],
    [lang === 'bn' ? 'রাজস্বের সূত্র' : 'Revenue Definition', lang === 'bn' ? 'নিট বিক্রয় = মূল্য × পরিমাণ × (১ − ছাড় / ১০০)' : 'Net Sales = Price × Quantity × (1 − Discount / 100)'],
    [lang === 'bn' ? 'পারফরম্যান্স সুবিধা' : 'Performance Benefit', lang === 'bn' ? 'র‍্যাম ওভারলোড রোধ, সাব-সেকেন্ড কুয়েরি গতি ও স্কেলেবিলিটি' : 'Avoids RAM overload, sub-second query latency, scalable architecture'],
  ]

  const explanations = [
    [
      lang === 'bn' ? 'K-Means ক্লাস্টারিং' : 'K-Means Clustering',
      lang === 'bn'
        ? 'আনসুপারভাইজড সেগমেন্টেশন যা মোট ব্যয়, অর্ডারের সংখ্যা ও আইটেমের পরিমাণের ওপর ভিত্তি করে ৫ লাখ গ্রাহককে ৩টি স্তরে ভাগ করেছে।'
        : 'Unsupervised segmentation grouping 500,000 customer accounts into 3 behavioral tiers based on standardized gross spend, order frequency, and item count.',
    ],
    [
      lang === 'bn' ? 'কোহোর্ট ও বাজার গ্রহণযোগ্যতা ট্র্যাকিং' : 'Cohort Adoption Analysis',
      lang === 'bn'
        ? 'প্রথম বিক্রয় থেকে শুরু করে পণ্যভিত্তিক গ্রাহক গ্রহণযোগ্যতা কার্ভ এবং ক্যাটাগরি বেঞ্চমার্কের সাপেক্ষে সময়ভিত্তিক পারফরম্যান্স বিশ্লেষণ।'
        : 'Tracks customer adoption curves and repeat purchasing patterns across each product\'s observation window against category benchmarks.',
    ],
    [
      lang === 'bn' ? 'নিট বিক্রয় হিসাব পদ্ধতি' : 'Net Sales Accounting',
      lang === 'bn'
        ? 'নিট বিক্রয় = মূল্য × পরিমাণ × (১ − ছাড় / ১০০)। ছাড়-পরবর্তী প্রকৃত বাণিজ্যিক আয় নির্ভুলভাবে প্রতিফলিত করে।'
        : 'Net Sales = Price × Quantity × (1 − Discount / 100). Accurately reflects true realized commercial revenue after promotional discounts.',
    ],
  ]

  return (
    <div className="content-grid two-column">
      <Panel title={t('methodology.workflowTitle')} subtitle={t('methodology.workflowSubtitle')} className="span-two">
        <div className="method-flow">
          {flow.map((step, index) => (
            <div className="flow-step" key={step.title}>
              <span className="flow-step-num">{String(index + 1).padStart(2, '0')}</span>
              <strong>{step.title}</strong>
              <small>{step.desc}</small>
              {index < flow.length - 1 && <i />}
            </div>
          ))}
        </div>
      </Panel>

      <Panel title={t('methodology.pipelineTitle')} subtitle={t('methodology.pipelineSubtitle')}>
        <div className="method-grid-single">
          {architectureItems.map((item, index) => (
            <article className="method-item" key={item.label}>
              <span className="method-number">{String(index + 1).padStart(2, '0')}</span>
              <div>
                <h3>{item.label}</h3>
                <p>{item.value}</p>
              </div>
            </article>
          ))}
        </div>
      </Panel>

      <Panel title={t('methodology.specsTitle')} subtitle={t('methodology.specsSubtitle')}>
        <div className="specs-container">
          <div className="specs-list">
            <h4>{t('methodology.datasetSpecsHeader')}</h4>
            {specifications.map(([label, value]) => (
              <div className="spec-row" key={label}>
                <span className="spec-label">{label}</span>
                <strong className="spec-value">{value}</strong>
              </div>
            ))}
          </div>

          <div className="explanation-list">
            <h4>{t('methodology.evalFrameworkHeader')}</h4>
            {explanations.map(([title, body]) => (
              <article key={title}>
                <h3>{title}</h3>
                <p>{body}</p>
              </article>
            ))}
          </div>
        </div>
      </Panel>
    </div>
  )
}

function formatInlineText(text) {
  const parts = []
  const regex = /(\*\*[^*]+\*\*|`[^`]+`)/g
  let lastIndex = 0
  let match

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index))
    }
    const token = match[0]
    if (token.startsWith('**') && token.endsWith('**')) {
      parts.push(<strong key={match.index}>{token.slice(2, -2)}</strong>)
    } else if (token.startsWith('`') && token.endsWith('`')) {
      parts.push(<code key={match.index}>{token.slice(1, -1)}</code>)
    }
    lastIndex = regex.lastIndex
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex))
  }

  return parts.length > 0 ? parts : text
}

function renderSafeText(text) {
  if (!text) return null
  const paragraphs = text.split(/\n{2,}/)

  return paragraphs.map((para, pIdx) => {
    const lines = para.split('\n')
    const isBulletList = lines.every(line => /^(\*|-|\d+\.)\s+/.test(line.trim()))

    if (isBulletList) {
      return (
        <ul key={pIdx} className="chat-bullet-list">
          {lines.map((line, lIdx) => {
            const clean = line.trim().replace(/^(\*|-|\d+\.)\s+/, '')
            return <li key={lIdx}>{formatInlineText(clean)}</li>
          })}
        </ul>
      )
    }

    return (
      <p key={pIdx} className="chat-paragraph">
        {lines.map((line, lIdx) => (
          <span key={lIdx}>
            {formatInlineText(line)}
            {lIdx < lines.length - 1 && <br />}
          </span>
        ))}
      </p>
    )
  })
}

function Chatbot({ lang }) {
  const { t } = useTranslation()
  const [isOpen, setIsOpen] = useState(false)
  const [messages, setMessages] = useState([])
  const [inputValue, setInputValue] = useState('')
  const [loading, setLoading] = useState(false)
  const [lastFailedQuery, setLastFailedQuery] = useState(null)
  const [selectedImage, setSelectedImage] = useState(null)
  const [imageError, setImageError] = useState(null)
  const [panelPosition, setPanelPosition] = useState(null)
  const [isDragging, setIsDragging] = useState(false)

  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  const triggerRef = useRef(null)
  const fileInputRef = useRef(null)
  const panelRef = useRef(null)
  const dragStartRef = useRef(null)

  const clampPosition = (x, y, width, height) => {
    const pad = 8
    const panelW = width || 390
    const panelH = height || 570
    const maxX = Math.max(0, window.innerWidth - panelW - pad)
    const maxY = Math.max(0, window.innerHeight - panelH - pad)
    return {
      x: Math.min(Math.max(pad, x), maxX),
      y: Math.min(Math.max(pad, y), maxY),
    }
  }

  // Keep panel within visible viewport on window resize
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth <= 600) return
      setPanelPosition((prev) => {
        if (!prev) return null
        const rect = panelRef.current?.getBoundingClientRect()
        const w = rect?.width || 390
        const h = rect?.height || 570
        return clampPosition(prev.x, prev.y, w, h)
      })
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  // Clamp position when panel is reopened during session
  useEffect(() => {
    if (isOpen && panelPosition && window.innerWidth > 600) {
      const rect = panelRef.current?.getBoundingClientRect()
      const w = rect?.width || 390
      const h = rect?.height || 570
      setPanelPosition((prev) => (prev ? clampPosition(prev.x, prev.y, w, h) : null))
    }
  }, [isOpen])

  // Active dragging via Pointer Events
  const handlePointerDown = (e) => {
    if (window.innerWidth <= 600) return
    if (e.button !== 0 && e.pointerType === 'mouse') return
    // Interactive buttons inside header must not initiate dragging
    if (e.target.closest('button, a, input, select, textarea, [data-no-drag]')) {
      return
    }

    if (!panelRef.current) return
    const rect = panelRef.current.getBoundingClientRect()
    const currentX = panelPosition ? panelPosition.x : rect.left
    const currentY = panelPosition ? panelPosition.y : rect.top

    const dragInfo = {
      startX: e.clientX,
      startY: e.clientY,
      initialX: currentX,
      initialY: currentY,
      width: rect.width,
      height: rect.height,
    }
    dragStartRef.current = dragInfo
    setIsDragging(true)

    const onPointerMove = (moveEvt) => {
      if (!dragStartRef.current) return
      const { startX, startY, initialX, initialY, width, height } = dragStartRef.current
      const deltaX = moveEvt.clientX - startX
      const deltaY = moveEvt.clientY - startY
      const clamped = clampPosition(initialX + deltaX, initialY + deltaY, width, height)
      setPanelPosition(clamped)
    }

    const onPointerUp = () => {
      dragStartRef.current = null
      setIsDragging(false)
      window.removeEventListener('pointermove', onPointerMove)
      window.removeEventListener('pointerup', onPointerUp)
      window.removeEventListener('pointercancel', onPointerUp)
    }

    window.addEventListener('pointermove', onPointerMove)
    window.addEventListener('pointerup', onPointerUp)
    window.addEventListener('pointercancel', onPointerUp)

    try {
      e.currentTarget.setPointerCapture(e.pointerId)
    } catch (_) {}
  }

  // Auto-scroll to latest message or indicator
  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, loading, isOpen])

  // Focus input when chat panel opens
  useEffect(() => {
    if (isOpen) {
      const timer = setTimeout(() => {
        inputRef.current?.focus()
      }, 100)
      return () => clearTimeout(timer)
    }
  }, [isOpen])

  // Close panel on Escape key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen) {
        setIsOpen(false)
        triggerRef.current?.focus()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen])

  const processImageFile = (file) => {
    if (!file) return false
    setImageError(null)

    const validMimes = ['image/jpeg', 'image/png', 'image/webp', 'image/jpg']
    const mime = file.type?.toLowerCase() || ''
    if (!validMimes.includes(mime)) {
      setImageError(t('chatbot.invalidFormat'))
      if (fileInputRef.current) fileInputRef.current.value = ''
      return false
    }

    if (file.size > 5 * 1024 * 1024) {
      setImageError(t('chatbot.imageTooLarge'))
      if (fileInputRef.current) fileInputRef.current.value = ''
      return false
    }

    const reader = new FileReader()
    reader.onload = () => {
      setSelectedImage({
        file,
        previewUrl: reader.result,
        dataUrl: reader.result,
        mimeType: mime === 'image/jpg' ? 'image/jpeg' : mime,
        name: file.name || 'clipboard-image.png',
        sizeKb: Math.max(1, Math.round(file.size / 1024)),
      })
    }
    reader.onerror = () => {
      setImageError(t('chatbot.invalidFormat'))
    }
    reader.readAsDataURL(file)
    if (fileInputRef.current) fileInputRef.current.value = ''
    return true
  }

  const handleFileSelect = (e) => {
    const file = e.target.files?.[0]
    if (file) {
      processImageFile(file)
    }
    e.target.value = ''
  }

  const handlePaste = (e) => {
    if (loading) return
    const items = e.clipboardData?.items
    if (!items) return

    let imageFile = null
    for (let i = 0; i < items.length; i++) {
      const item = items[i]
      if (item.kind === 'file' && item.type && item.type.startsWith('image/')) {
        const file = item.getAsFile()
        if (file) {
          imageFile = file
          break
        }
      }
    }

    if (!imageFile) {
      // Ordinary text or no image in clipboard: preserve normal text pasting
      return
    }

    // Image detected in clipboard: validate and attach
    const handled = processImageFile(imageFile)
    if (handled) {
      // Prevent default paste only when an image is successfully handled
      e.preventDefault()
    }
  }

  const handleRemoveImage = () => {
    setSelectedImage(null)
    setImageError(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleSend = async (textToSend) => {
    const query = (textToSend !== undefined ? textToSend : inputValue).trim()
    if ((!query && !selectedImage) || loading) return

    const imageToSend = selectedImage
    const userMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: query,
      image: imageToSend ? { previewUrl: imageToSend.previewUrl } : null,
    }

    const nextMessages = [...messages, userMessage]
    setMessages(nextMessages)
    setInputValue('')
    setSelectedImage(null)
    setImageError(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
    setLoading(true)
    setLastFailedQuery(null)

    // Bounded history: up to 10 non-error messages
    const boundedHistory = nextMessages
      .filter(m => !m.isError)
      .slice(-10)
      .map(m => ({ role: m.role, content: m.content || '(Image attachment)' }))

    try {
      const response = await sendChatMessage(
        query,
        lang,
        boundedHistory,
        imageToSend ? { data: imageToSend.dataUrl, mime_type: imageToSend.mimeType } : null
      )
      const assistantMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.reply || response.message || '',
      }
      setMessages(prev => [...prev, assistantMessage])
    } catch (err) {
      const assistantErrorMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: err.message || t('chatbot.errorMessage'),
        isError: true,
      }
      setMessages(prev => [...prev, assistantErrorMessage])
      setLastFailedQuery({ text: query, image: imageToSend })
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleClear = () => {
    setMessages([])
    setLastFailedQuery(null)
    setSelectedImage(null)
    setImageError(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleRetry = () => {
    if (lastFailedQuery) {
      if (typeof lastFailedQuery === 'object') {
        if (lastFailedQuery.image) {
          setSelectedImage(lastFailedQuery.image)
        }
        handleSend(lastFailedQuery.text)
      } else {
        handleSend(lastFailedQuery)
      }
    }
  }

  return (
    <div className="chatbot-wrapper">
      {!isOpen && (
        <button
          ref={triggerRef}
          className="chatbot-trigger-btn"
          onClick={() => setIsOpen(true)}
          aria-label={t('chatbot.triggerAria')}
          aria-haspopup="dialog"
          aria-expanded="false"
        >
          <span className="chatbot-trigger-icon">
            <Sparkles size={17} />
          </span>
          <span className="chatbot-trigger-label">{t('chatbot.triggerTitle')}</span>
        </button>
      )}

      {isOpen && (
        <div
          ref={panelRef}
          className={`chatbot-panel ${isDragging ? 'is-dragging' : ''}`}
          role="dialog"
          aria-modal="false"
          aria-label={t('chatbot.panelTitle')}
          style={
            panelPosition
              ? {
                  left: `${panelPosition.x}px`,
                  top: `${panelPosition.y}px`,
                  bottom: 'auto',
                  right: 'auto',
                }
              : undefined
          }
        >
          <div
            className={`chatbot-header ${isDragging ? 'is-dragging' : ''}`}
            onPointerDown={handlePointerDown}
          >
            <div className="chatbot-header-info">
              <div className="chatbot-avatar">
                <Bot size={18} />
              </div>
              <div className="chatbot-header-text">
                <h3>{t('chatbot.panelTitle')}</h3>
              </div>
            </div>
            <div className="chatbot-header-actions">
              {messages.length > 0 && (
                <button
                  className="chatbot-icon-btn"
                  onClick={handleClear}
                  title={t('chatbot.clear')}
                  aria-label={t('chatbot.clear')}
                >
                  <Trash2 size={15} />
                </button>
              )}
              <button
                className="chatbot-icon-btn"
                onClick={() => {
                  setIsOpen(false)
                  triggerRef.current?.focus()
                }}
                title={t('chatbot.close')}
                aria-label={t('chatbot.close')}
              >
                <X size={17} />
              </button>
            </div>
          </div>

          <div
            className="chatbot-messages"
            aria-live="polite"
            aria-relevant="additions text"
          >
            {messages.length === 0 && (
              <div className="chatbot-welcome-card">
                <div className="chatbot-welcome-title">
                  <Sparkles size={15} />
                  <span>{t('chatbot.welcomeTitle')}</span>
                </div>
                <p>{t('chatbot.welcomeMessage')}</p>

                <div className="chatbot-suggested-label">
                  {t('chatbot.suggestedTitle')}
                </div>
                <div className="chatbot-chips">
                  {['q1', 'q2', 'q3'].map(qKey => (
                    <button
                      key={qKey}
                      className="chatbot-chip"
                      onClick={() => handleSend(t(`chatbot.${qKey}`))}
                    >
                      <ArrowUpRight size={13} />
                      <span>{t(`chatbot.${qKey}`)}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map(msg => (
              <div
                key={msg.id}
                className={`chat-bubble-row ${msg.role === 'user' ? 'user-row' : 'bot-row'}`}
              >
                {msg.role === 'user' ? (
                  <div className="chat-msg-user">
                    {msg.image?.previewUrl && (
                      <div className="chat-msg-image-thumb">
                        <img src={msg.image.previewUrl} alt="Attached upload" />
                      </div>
                    )}
                    {msg.content && renderSafeText(msg.content)}
                  </div>
                ) : (
                  <div className={`chat-msg-bot ${msg.isError ? 'chat-msg-error' : ''}`}>
                    {renderSafeText(msg.content)}
                    {msg.isError && (
                      <div className="chat-error-actions">
                        <button className="chat-retry-btn" onClick={handleRetry}>
                          <RotateCw size={12} />
                          <span>{t('chatbot.retry')}</span>
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}

            {loading && (
              <div className="chat-bubble-row bot-row">
                <div className="chat-typing-indicator" aria-label={t('chatbot.thinking')}>
                  <span className="chat-typing-dot" />
                  <span className="chat-typing-dot" />
                  <span className="chat-typing-dot" />
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          <div className="chatbot-input-container">
            {imageError && (
              <div className="chat-image-error">
                <AlertCircle size={14} />
                <span>{imageError}</span>
              </div>
            )}

            {selectedImage && (
              <div className="chat-upload-preview">
                <div className="chat-upload-preview-thumb">
                  <img src={selectedImage.previewUrl} alt="Upload preview" />
                  <button
                    type="button"
                    className="chat-remove-preview-btn"
                    onClick={handleRemoveImage}
                    title={t('chatbot.removeImage')}
                    aria-label={t('chatbot.removeImage')}
                  >
                    <X size={12} />
                  </button>
                </div>
                <div className="chat-upload-meta">
                  <span>{selectedImage.name} ({selectedImage.sizeKb} KB)</span>
                </div>
              </div>
            )}

            <form
              className="chatbot-input-bar"
              onSubmit={(e) => {
                e.preventDefault()
                handleSend()
              }}
              onPaste={handlePaste}
            >
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileSelect}
                accept="image/jpeg,image/png,image/webp"
                style={{ display: 'none' }}
                id="chatbot-file-input"
              />
              <button
                type="button"
                className="chatbot-attach-btn"
                onClick={() => fileInputRef.current?.click()}
                title={t('chatbot.attachImage')}
                aria-label={t('chatbot.attachImage')}
                disabled={loading}
              >
                <Paperclip size={18} />
              </button>
              <textarea
                ref={inputRef}
                className="chatbot-textarea"
                rows={1}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                onPaste={handlePaste}
                placeholder={t('chatbot.inputPlaceholder')}
                aria-label={t('chatbot.inputPlaceholder')}
                disabled={loading}
              />
              <button
                type="submit"
                className="chatbot-send-btn"
                disabled={(!inputValue.trim() && !selectedImage) || loading}
                aria-label={t('chatbot.send')}
              >
                <Send size={15} />
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

export default function App() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language || 'en'
  const [active, setActive] = useState(() => (typeof window !== 'undefined' && window.location.hash ? window.location.hash.replace('#', '') : 'overview'))
  const [menuOpen, setMenuOpen] = useState(false)

  // Listen for hash changes to support direct deep linking
  useEffect(() => {
    const handleHash = () => {
      const hash = window.location.hash.replace('#', '')
      if (hash) setActive(hash)
    }
    window.addEventListener('hashchange', handleHash)
    return () => window.removeEventListener('hashchange', handleHash)
  }, [])

  // Sync lang attribute on HTML element
  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])

  const changeLanguage = (newLang) => {
    i18n.changeLanguage(newLang)
    localStorage.setItem('preferred_language', newLang)
    document.documentElement.lang = newLang
  }

  // 1. Startup: Minimum required endpoint (/api/overview)
  const [overviewData, setOverviewData] = useState(null)
  const [initialLoading, setInitialLoading] = useState(true)
  const [initialError, setInitialError] = useState('')
  const [refreshing, setRefreshing] = useState(false)

  // 2. Page-specific data caches, loading, and error states
  const [pageData, setPageData] = useState({})
  const [pageLoading, setPageLoading] = useState({})
  const [pageErrors, setPageErrors] = useState({})

  // Initial startup: Load ONLY /api/overview
  async function loadInitialOverview() {
    setInitialLoading(true)
    setInitialError('')
    try {
      const data = await loadOverviewData()
      setOverviewData(data)
    } catch (error) {
      setInitialError(error.message)
    } finally {
      setInitialLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    loadInitialOverview()
  }, [])

  // Lazy load page-specific data only when user opens that page
  async function loadPage(pageId, force = false) {
    if (pageId === 'overview') {
      if (force) {
        setRefreshing(true)
        await loadInitialOverview()
      }
      return
    }

    if (!force && pageData[pageId]) {
      return
    }

    setPageLoading(prev => ({ ...prev, [pageId]: true }))
    setPageErrors(prev => ({ ...prev, [pageId]: '' }))

    try {
      let result = null
      if (pageId === 'sales') {
        result = await loadSalesData()
        if (result?.error && !result?.monthly?.monthly?.length) {
          throw new Error(result.error)
        }
      } else if (pageId === 'products') {
        result = await loadProductData()
      } else if (pageId === 'customers') {
        result = await loadCustomerData()
      } else if (pageId === 'segments') {
        result = await loadSegmentData()
      } else if (pageId === 'newProducts') {
        result = await loadNewProductPerformance()
      } else if (pageId === 'methodology') {
        result = await loadMethodologyData()
      }

      if (result) {
        setPageData(prev => ({ ...prev, [pageId]: result }))
      }
    } catch (error) {
      setPageErrors(prev => ({ ...prev, [pageId]: error.message }))
    } finally {
      setPageLoading(prev => ({ ...prev, [pageId]: false }))
    }
  }

  // Trigger lazy loading when tab switches
  useEffect(() => {
    if (active !== 'overview') {
      loadPage(active)
    }
  }, [active])

  async function handleRefresh() {
    setRefreshing(true)
    if (active === 'overview') {
      await loadInitialOverview()
    } else {
      await Promise.allSettled([
        loadInitialOverview(),
        loadPage(active, true),
      ])
      setRefreshing(false)
    }
  }

  const selectPage = id => {
    setActive(id)
    if (typeof window !== 'undefined') window.location.hash = id
    setMenuOpen(false)
  }

  const activePageTitle = t(`pages.${active}Title`)
  const activePageDesc = t(`pages.${active}Desc`)

  // Combined data structure matching expected page props
  const combinedData = {
    overview: overviewData?.overview,
    categories: pageData.sales?.categories?.length ? pageData.sales.categories : (overviewData?.categories || []),
    payments: pageData.sales?.payments?.length ? pageData.sales.payments : (overviewData?.payments || []),
    locations: pageData.sales?.locations?.length ? pageData.sales.locations : (overviewData?.locations || []),
    monthly: pageData.sales?.monthly,
    products: pageData.products?.products,
    customers: pageData.customers?.customers,
    segments: pageData.segments?.segments,
    newProducts: pageData.newProducts?.performance,
    methodology: pageData.methodology?.methodology || overviewData?.overview?.methodology || {},
  }

  return (
    <>
      <div className="app-shell">
      <aside className={`sidebar ${menuOpen ? 'open' : ''}`}>
        <div className="brand-lockup">
          <div className="brand-symbol"><span /></div>
          <div className="brand-copy">
            <strong>{t('common.brandTitle')}</strong>
            <small>{t('common.brandSubtitle')}</small>
          </div>
          <button className="mobile-close" onClick={() => setMenuOpen(false)} aria-label="Close navigation"><X size={18} /></button>
        </div>
        <div className="workspace-label">{t('common.workspaceLabel')}</div>
        <nav aria-label="Main navigation">
          {navItems.map(({ id, icon: Icon }) => (
            <button className={`nav-link ${active === id ? 'active' : ''}`} key={id} onClick={() => selectPage(id)}>
              <Icon size={17} strokeWidth={1.8} />
              <span>{t(`nav.${id}`)}</span>
              {active === id && <i />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="data-status">
            <span className={`status-dot ${overviewData ? '' : 'loading'}`} />
            <div>
              <strong>{overviewData ? t('common.datasetLoaded') : t('common.connectingToApi')}</strong>
              <small>{overviewData ? `${numeric(overviewData.overview.kpis.orders, lang)} ${t('common.ordersLoaded')}` : t('common.fastApiRender')}</small>
            </div>
          </div>
          <div className="profile">
            <div className="avatar">BI</div>
            <div>
              <strong>{t('common.biPrototype')}</strong>
              <small>{t('common.analyticsWorkspace')}</small>
            </div>
            <Database size={15} />
          </div>
        </div>
      </aside>

      {menuOpen && <button className="scrim" aria-label="Close navigation" onClick={() => setMenuOpen(false)} />}

      <main className="main-area">
        <header className="topbar">
          <div className="topbar-left">
            <button className="menu-toggle" onClick={() => setMenuOpen(true)} aria-label="Open navigation"><Menu size={19} /></button>
            <span className="breadcrumb">{t('common.brandTitle')}</span>
            <span className="crumb-slash">/</span>
            <strong>{activePageTitle}</strong>
          </div>
          <div className="topbar-right">
            <span className="date-pill">
              <Clock3 size={14} />
              {overviewData ? `${overviewData.overview.date_range.start} — ${overviewData.overview.date_range.end}` : t('common.dateRangePeriod')}
            </span>
            <button className="icon-button" title={t('common.refreshData')} aria-label={t('common.refreshData')} onClick={handleRefresh}>
              <RotateCw size={16} className={refreshing ? 'spin' : ''} />
            </button>
          </div>
        </header>

        <div className="page-content">
          <div className="page-heading">
            <div>
              <div className="eyebrow"><span />{t('common.eyebrow')}</div>
              <h1>{activePageTitle}</h1>
              <p>{activePageDesc}</p>
            </div>
            <div className="page-heading-actions">
              <div className="lang-selector" role="group" aria-label={t('common.language')}>
                <button
                  type="button"
                  className={`lang-selector-btn ${lang === 'en' ? 'active' : ''}`}
                  onClick={() => changeLanguage('en')}
                  aria-pressed={lang === 'en'}
                >
                  English
                </button>
                <span className="lang-divider">|</span>
                <button
                  type="button"
                  className={`lang-selector-btn ${lang === 'bn' ? 'active' : ''}`}
                  onClick={() => changeLanguage('bn')}
                  aria-pressed={lang === 'bn'}
                >
                  বাংলা
                </button>
              </div>
              <button className="export-button" onClick={() => selectPage('methodology')}>
                <Download size={15} />{t('common.architectureAndMethod')}
              </button>
            </div>
          </div>

          {initialLoading && (
            <div className="loading-state">
              <LoaderCircle className="spin" size={24} />
              <span>{t('common.loadingSummaries')}</span>
            </div>
          )}

          {initialError && !overviewData && (
            <div className="error-state" role="alert">
              <strong>{t('common.apiUnavailable')}</strong>
              <p>{initialError}</p>
              <button className="primary-button" onClick={loadInitialOverview}>
                <RotateCw size={15} />{t('common.retryConnection')}
              </button>
            </div>
          )}

          {overviewData && (
            <div className="page-enter" key={active}>
              {active === 'overview' && <Overview data={combinedData} />}

              {active === 'sales' && (
                pageLoading.sales ? (
                  <div className="loading-state"><LoaderCircle className="spin" size={24} /><span>{t('sales.loading')}</span></div>
                ) : pageErrors.sales ? (
                  <div className="error-state" role="alert">
                    <strong>{t('sales.unavailable')}</strong>
                    <p>{pageErrors.sales}</p>
                    <button className="primary-button" onClick={() => loadPage('sales', true)}><RotateCw size={15} />{t('common.retry')}</button>
                  </div>
                ) : combinedData.monthly ? (
                  <SalesAnalytics data={combinedData} />
                ) : null
              )}

              {active === 'products' && (
                pageLoading.products ? (
                  <div className="loading-state"><LoaderCircle className="spin" size={24} /><span>{t('products.loading')}</span></div>
                ) : pageErrors.products ? (
                  <div className="error-state" role="alert">
                    <strong>{t('products.unavailable')}</strong>
                    <p>{pageErrors.products}</p>
                    <button className="primary-button" onClick={() => loadPage('products', true)}><RotateCw size={15} />{t('common.retry')}</button>
                  </div>
                ) : combinedData.products ? (
                  <ProductAnalytics data={combinedData} />
                ) : null
              )}

              {active === 'customers' && (
                pageLoading.customers ? (
                  <div className="loading-state"><LoaderCircle className="spin" size={24} /><span>{t('customers.loading')}</span></div>
                ) : pageErrors.customers ? (
                  <div className="error-state" role="alert">
                    <strong>{t('customers.unavailable')}</strong>
                    <p>{pageErrors.customers}</p>
                    <button className="primary-button" onClick={() => loadPage('customers', true)}><RotateCw size={15} />{t('common.retry')}</button>
                  </div>
                ) : combinedData.customers ? (
                  <CustomerAnalytics data={combinedData} />
                ) : null
              )}

              {active === 'segments' && (
                pageLoading.segments ? (
                  <div className="loading-state"><LoaderCircle className="spin" size={24} /><span>{t('segments.loading')}</span></div>
                ) : pageErrors.segments ? (
                  <div className="error-state" role="alert">
                    <strong>{t('segments.unavailable')}</strong>
                    <p>{pageErrors.segments}</p>
                    <button className="primary-button" onClick={() => loadPage('segments', true)}><RotateCw size={15} />{t('common.retry')}</button>
                  </div>
                ) : combinedData.segments ? (
                  <CustomerSegmentation data={combinedData} />
                ) : null
              )}

              {active === 'newProducts' && (
                pageLoading.newProducts ? (
                  <div className="loading-state"><LoaderCircle className="spin" size={24} /><span>{t('newProducts.loading')}</span></div>
                ) : pageErrors.newProducts ? (
                  <div className="error-state" role="alert">
                    <strong>{t('newProducts.unavailable')}</strong>
                    <p>{pageErrors.newProducts}</p>
                    <button className="primary-button" onClick={() => loadPage('newProducts', true)}><RotateCw size={15} />{t('common.retry')}</button>
                  </div>
                ) : combinedData.newProducts ? (
                  <NewProductPerformance data={combinedData.newProducts} />
                ) : null
              )}

              {active === 'methodology' && (
                pageLoading.methodology ? (
                  <div className="loading-state"><LoaderCircle className="spin" size={24} /><span>{t('methodology.loading')}</span></div>
                ) : pageErrors.methodology ? (
                  <div className="error-state" role="alert">
                    <strong>{t('methodology.unavailable')}</strong>
                    <p>{pageErrors.methodology}</p>
                    <button className="primary-button" onClick={() => loadPage('methodology', true)}><RotateCw size={15} />{t('common.retry')}</button>
                  </div>
                ) : combinedData.methodology ? (
                  <Methodology />
                ) : null
              )}
            </div>
          )}

          <footer className="page-footer">
            <span>{t('common.footerTitle')}</span>
          </footer>
        </div>
      </main>
    </div>
    <Chatbot lang={lang} />
  </>
)
}
