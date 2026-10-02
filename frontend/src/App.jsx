import { useEffect, useState } from 'react'
import {
  Activity, ArrowDownWideNarrow, ArrowUpRight, BarChart3, Boxes, CircleHelp,
  Clock3, CreditCard, Database, Download, Layers3, LoaderCircle, MapPin,
  Menu, Package, RotateCw, Search, Shirt, Sparkles, Star, Users, Wallet,
  X,
} from 'lucide-react'
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ComposedChart,
  Legend, Line, Pie, PieChart, ResponsiveContainer, Scatter, ScatterChart,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import { apiRequest, loadDashboardData } from './api.js'

const navigation = [
  { id: 'overview', label: 'Dashboard / Overview', icon: Layers3 },
  { id: 'sales', label: 'Sales Analytics', icon: BarChart3 },
  { id: 'products', label: 'Product Analytics', icon: Shirt },
  { id: 'customers', label: 'Customer Analytics', icon: Users },
  { id: 'segments', label: 'Customer Segmentation', icon: Sparkles },
  { id: 'prediction', label: 'Sales Prediction', icon: Activity },
  { id: 'methodology', label: 'Methodology', icon: CircleHelp },
]
const segmentColors = ['#d96e50', '#638575', '#d4ae55', '#7587a4', '#b27870']
const colors = ['#d96e50', '#9daf63', '#638575', '#d4ae55', '#8086a0', '#b27870', '#63a0a0']
const pageCopy = {
  overview: ['Dashboard / Overview', 'A measured view of sales, products, and customers.'],
  sales: ['Sales Analytics', 'Revenue, units, payment mix, and sales geography.'],
  products: ['Product Analytics', 'Explore best sellers, discount levels, and product performance.'],
  customers: ['Customer Analytics', 'Understand customer value, loyalty, and location.'],
  segments: ['Customer Segmentation', 'Explore data-driven groups from purchase behaviour.'],
  prediction: ['Sales Prediction', 'Estimate order quantity with the trained regression models.'],
  methodology: ['Methodology', 'Dataset, analytical definitions, and model evaluation.'],
}
const currency = value => `৳${Number(value || 0).toLocaleString('en-BD', { maximumFractionDigits: 0 })}`
const numeric = value => Number(value || 0).toLocaleString('en-US', { maximumFractionDigits: 1 })

function Panel({ title, subtitle, action, className = '', children }) {
  return <section className={`panel ${className}`}>
    <div className="panel-heading"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>{action}</div>
    {children}
  </section>
}

function Metric({ label, value, note, icon: Icon, tone = 'coral' }) {
  return <article className="metric-card">
    <div className={`metric-icon ${tone}`}><Icon size={18} strokeWidth={1.8} /></div>
    <div className="metric-copy"><span>{label}</span><strong>{value}</strong><small>{note}</small></div>
  </article>
}

function ChartTooltip({ active, payload, label, money = true }) {
  if (!active || !payload?.length) return null
  return <div className="chart-tooltip"><strong>{label}</strong>{payload.map(item => <span key={item.dataKey}>
    <i style={{ background: item.color || item.fill }} />{item.name || item.dataKey}: {money ? currency(item.value) : numeric(item.value)}
  </span>)}</div>
}

function ChartLegend({ payload }) {
  if (!payload?.length) return null
  return <div className="dashboard-legend">{payload.map(item => <span key={item.value}><i style={{ background: item.color }} />{item.value}</span>)}</div>
}

function Table({ columns, rows, empty = 'No matching records.', rowKey }) {
  return <div className="table-wrap"><table><thead><tr>{columns.map(column => <th key={column.key}>{column.label}</th>)}</tr></thead>
    <tbody>{rows.length ? rows.map((row, index) => <tr key={rowKey ? rowKey(row) : row.Product_ID || row.Customer_ID || index}>
      {columns.map(column => <td key={column.key}>{column.render ? column.render(row[column.key], row) : row[column.key]}</td>)}
    </tr>) : <tr><td className="empty-cell" colSpan={columns.length}>{empty}</td></tr>}</tbody>
  </table></div>
}

function SearchField({ value, onChange, placeholder }) {
  return <label className="search-field"><Search size={15} /><input value={value} onChange={event => onChange(event.target.value)} placeholder={placeholder} /></label>
}

function Overview({ data }) {
  const kpis = data.overview.kpis
  return <>
    <div className="metric-grid six-metrics">
      <Metric label="Total Revenue" value={currency(kpis.revenue)} note="Net of discounts" icon={Wallet} />
      <Metric label="Total Orders" value={numeric(kpis.orders)} note="Unique order IDs" icon={Package} tone="olive" />
      <Metric label="Total Items Sold" value={numeric(kpis.units)} note="Units across all orders" icon={Boxes} tone="green" />
      <Metric label="Average Order Value" value={currency(kpis.average_order_value)} note="Revenue per order" icon={CreditCard} tone="gold" />
      <Metric label="Average Rating" value={`${Number(kpis.average_rating).toFixed(2)} / 5`} note="Customer product rating" icon={Star} tone="coral" />
      <Metric label="Total Customers" value={numeric(kpis.customers)} note="Unique customer IDs" icon={Users} tone="green" />
    </div>
    <div className="content-grid overview-grid">
      <Panel title="Monthly Revenue Trend" subtitle={`${data.overview.date_range.start} — ${data.overview.date_range.end}`} className="span-two">
        <div className="chart-area"><ResponsiveContainer width="100%" height="100%"><AreaChart data={data.overview.monthly_revenue} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <defs><linearGradient id="overviewRevenue" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#d96e50" stopOpacity={0.25} /><stop offset="95%" stopColor="#d96e50" stopOpacity={0.01} /></linearGradient></defs>
          <CartesianGrid vertical={false} stroke="#e9ece6" /><XAxis dataKey="Period" tickLine={false} axisLine={false} tick={{ fill: '#878e86', fontSize: 10 }} minTickGap={25} /><YAxis tickLine={false} axisLine={false} tick={{ fill: '#878e86', fontSize: 10 }} tickFormatter={value => `${Math.round(value / 1000)}k`} width={40} /><Tooltip content={<ChartTooltip />} /><Area name="Revenue" type="monotone" dataKey="revenue" stroke="#d96e50" strokeWidth={2.5} fill="url(#overviewRevenue)" activeDot={{ r: 4 }} /></AreaChart></ResponsiveContainer></div>
      </Panel>
      <Panel title="Category-wise Revenue" subtitle="Net revenue by category">
        <div className="chart-area compact"><ResponsiveContainer width="100%" height="100%"><BarChart data={data.categories} layout="vertical" margin={{ top: 2, right: 10, bottom: 0, left: 0 }}>
          <CartesianGrid horizontal={false} stroke="#e9ece6" /><XAxis type="number" tickLine={false} axisLine={false} tick={{ fill: '#878e86', fontSize: 9 }} tickFormatter={value => `${Math.round(value / 1000)}k`} /><YAxis type="category" dataKey="Category" width={82} tickLine={false} axisLine={false} tick={{ fill: '#59625b', fontSize: 10 }} /><Tooltip content={<ChartTooltip />} /><Bar dataKey="revenue" name="Revenue" radius={[0, 4, 4, 0]} barSize={13}>{data.categories.map((entry, index) => <Cell key={entry.Category} fill={colors[index % colors.length]} />)}</Bar>
        </BarChart></ResponsiveContainer></div>
      </Panel>
      <Panel title="Payment Method Distribution" subtitle="Share of net revenue">
        <div className="split-chart"><div className="donut-wrap"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={data.payments} dataKey="revenue" nameKey="Payment_Method" innerRadius={48} outerRadius={72} paddingAngle={3} stroke="none">{data.payments.map((item, index) => <Cell key={item.Payment_Method} fill={colors[index % colors.length]} />)}</Pie><Tooltip formatter={value => currency(value)} /></PieChart></ResponsiveContainer></div>
          <div className="legend-list">{data.payments.map((item, index) => {
            const revenueTotal = data.payments.reduce((sum, payment) => sum + Number(payment.revenue || 0), 0)
            const share = item.share ?? (revenueTotal ? item.revenue / revenueTotal * 100 : 0)
            return <div key={item.Payment_Method}><span><i style={{ background: colors[index % colors.length] }} />{item.Payment_Method}</span><b>{Number(share).toFixed(1)}%</b></div>
          })}</div></div>
      </Panel>
      <Panel title="Location-wise Sales" subtitle="Net revenue by customer location">
        <div className="chart-area compact"><ResponsiveContainer width="100%" height="100%"><BarChart data={data.locations} layout="vertical" margin={{ top: 0, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid horizontal={false} stroke="#e9ece6" /><XAxis type="number" tickLine={false} axisLine={false} tick={{ fill: '#878e86', fontSize: 9 }} tickFormatter={value => `${Math.round(value / 1000)}k`} /><YAxis type="category" dataKey="Location" width={83} tickLine={false} axisLine={false} tick={{ fill: '#59625b', fontSize: 10 }} /><Tooltip content={<ChartTooltip />} /><Bar dataKey="revenue" name="Revenue" fill="#638575" radius={[0, 4, 4, 0]} barSize={13} />
        </BarChart></ResponsiveContainer></div>
      </Panel>
    </div>
  </>
}

function SalesAnalytics({ data }) {
  const [range, setRange] = useState('all')
  const [unit, setUnit] = useState('revenue')
  const monthly = range === 'all' ? data.monthly.monthly : data.monthly.monthly.slice(-Number(range))
  return <div className="content-grid two-column">
    <Panel title="Monthly Sales & Quantity" subtitle="Filter the period and measure" className="span-two" action={<div className="panel-filters"><select aria-label="Sales measure" value={unit} onChange={event => setUnit(event.target.value)}><option value="revenue">Revenue & quantity</option><option value="orders">Orders & quantity</option></select><select aria-label="Time period" value={range} onChange={event => setRange(event.target.value)}><option value="all">All months</option><option value="12">Last 12 months</option><option value="6">Last 6 months</option></select></div>}>
      <div className="chart-area tall"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={monthly} margin={{ top: 10, right: 12, bottom: 0, left: 0 }}>
        <CartesianGrid vertical={false} stroke="#e9ece6" /><XAxis dataKey="Period" tickLine={false} axisLine={false} tick={{ fill: '#878e86', fontSize: 10 }} minTickGap={18} /><YAxis yAxisId="main" tickLine={false} axisLine={false} tick={{ fill: '#878e86', fontSize: 10 }} tickFormatter={value => unit === 'revenue' ? `${Math.round(value / 1000)}k` : numeric(value)} /><YAxis yAxisId="quantity" orientation="right" tickLine={false} axisLine={false} tick={{ fill: '#878e86', fontSize: 10 }} /><Tooltip content={<ChartTooltip money={unit === 'revenue'} />} /><Legend content={<ChartLegend />} />
        <Bar yAxisId="main" dataKey={unit === 'revenue' ? 'revenue' : 'orders'} name={unit === 'revenue' ? 'Revenue' : 'Orders'} fill="#d96e50" radius={[3, 3, 0, 0]} /><Line yAxisId="quantity" type="monotone" dataKey="units" name="Quantity sold" stroke="#638575" strokeWidth={2} dot={false} />
      </ComposedChart></ResponsiveContainer></div>
    </Panel>
    <Panel title="Category Performance" subtitle="Sales and units by category">
      <div className="chart-area compact"><ResponsiveContainer width="100%" height="100%"><BarChart data={data.categories} margin={{ top: 8, right: 10, bottom: 0, left: -12 }}><CartesianGrid vertical={false} stroke="#e9ece6" /><XAxis dataKey="Category" tickLine={false} axisLine={false} tick={{ fill: '#777f77', fontSize: 9 }} interval={0} angle={-20} textAnchor="end" height={44} /><YAxis tickLine={false} axisLine={false} tick={{ fill: '#878e86', fontSize: 9 }} tickFormatter={value => `${Math.round(value / 1000)}k`} /><Tooltip content={<ChartTooltip />} /><Bar dataKey="revenue" name="Revenue" fill="#9daf63" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div>
    </Panel>
    <Panel title="Payment Method Distribution" subtitle="Revenue and order count"><div className="chart-area compact"><ResponsiveContainer width="100%" height="100%"><BarChart data={data.payments} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}><CartesianGrid vertical={false} stroke="#e9ece6" /><XAxis dataKey="Payment_Method" tickLine={false} axisLine={false} tick={{ fill: '#777f77', fontSize: 9 }} interval={0} angle={-15} textAnchor="end" height={42} /><YAxis tickLine={false} axisLine={false} tick={{ fill: '#878e86', fontSize: 9 }} tickFormatter={value => `${Math.round(value / 1000)}k`} /><Tooltip content={<ChartTooltip />} /><Bar dataKey="revenue" name="Revenue" fill="#d4ae55" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div></Panel>
    <Panel title="Location-wise Revenue" subtitle="Net sales by location" className="span-two"><div className="chart-area tall"><ResponsiveContainer width="100%" height="100%"><BarChart data={data.locations} layout="vertical" margin={{ top: 4, right: 16, bottom: 0, left: 4 }}><CartesianGrid horizontal={false} stroke="#e9ece6" /><XAxis type="number" tickLine={false} axisLine={false} tick={{ fill: '#878e86', fontSize: 10 }} tickFormatter={value => `${Math.round(value / 1000)}k`} /><YAxis type="category" dataKey="Location" width={96} tickLine={false} axisLine={false} tick={{ fill: '#59625b', fontSize: 10 }} /><Tooltip content={<ChartTooltip />} /><Bar dataKey="revenue" name="Revenue" fill="#638575" radius={[0, 4, 4, 0]} barSize={17} /></BarChart></ResponsiveContainer></div></Panel>
  </div>
}

function ProductAnalytics({ data }) {
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
    { key: 'Product_Name', label: 'Product', render: (value, row) => <div className="product-cell"><span className="product-mark"><Shirt size={15} /></span><span><strong>{value}</strong><small>{row.Product_ID}</small></span></div> },
    { key: 'Category', label: 'Category' }, { key: 'Brand', label: 'Brand' },
    { key: 'price', label: 'Avg. price', render: value => currency(value) },
    { key: 'units', label: 'Quantity sold', render: numeric }, { key: 'revenue', label: 'Revenue', render: currency },
    { key: 'rating', label: 'Rating', render: value => <span className="rating"><b>★</b> {Number(value).toFixed(2)}</span> },
    { key: 'discount', label: 'Avg. discount', render: value => `${Number(value).toFixed(1)}%` },
  ]
  return <div className="content-grid two-column">
    <Panel title="Top 10 Selling Products" subtitle="Ranked by quantity sold" className="span-two"><div className="chart-area tall"><ResponsiveContainer width="100%" height="100%"><BarChart data={bestSellers} layout="vertical" margin={{ top: 4, right: 18, bottom: 0, left: 4 }}><CartesianGrid horizontal={false} stroke="#e9ece6" /><XAxis type="number" tickLine={false} axisLine={false} tick={{ fill: '#878e86', fontSize: 10 }} /><YAxis type="category" dataKey="Product_Name" width={132} tickLine={false} axisLine={false} tick={{ fill: '#59625b', fontSize: 9 }} /><Tooltip content={<ChartTooltip money={false} />} /><Bar dataKey="units" name="Quantity sold" fill="#d96e50" radius={[0, 4, 4, 0]} barSize={15} /></BarChart></ResponsiveContainer></div></Panel>
    <Panel title="Revenue by Product" subtitle="Top 10 by net revenue"><div className="chart-area compact"><ResponsiveContainer width="100%" height="100%"><BarChart data={data.products.products.slice(0, 10)} layout="vertical" margin={{ top: 0, right: 12, bottom: 0, left: 4 }}><CartesianGrid horizontal={false} stroke="#e9ece6" /><XAxis type="number" tickLine={false} axisLine={false} tick={{ fill: '#878e86', fontSize: 9 }} tickFormatter={value => `${Math.round(value / 1000)}k`} /><YAxis type="category" dataKey="Product_Name" width={112} tickLine={false} axisLine={false} tick={{ fill: '#59625b', fontSize: 9 }} /><Tooltip content={<ChartTooltip />} /><Bar dataKey="revenue" name="Revenue" fill="#638575" radius={[0, 4, 4, 0]} barSize={12} /></BarChart></ResponsiveContainer></div></Panel>
    <Panel title="Discount Analysis" subtitle="Average applied discount by product">{hasDiscountData ? <div className="chart-area compact"><ResponsiveContainer width="100%" height="100%"><BarChart data={discountLeaders} layout="vertical" margin={{ top: 0, right: 12, bottom: 0, left: 4 }}><CartesianGrid horizontal={false} stroke="#e9ece6" /><XAxis type="number" unit="%" tickLine={false} axisLine={false} tick={{ fill: '#878e86', fontSize: 9 }} /><YAxis type="category" dataKey="Product_Name" width={112} tickLine={false} axisLine={false} tick={{ fill: '#59625b', fontSize: 9 }} /><Tooltip formatter={value => `${Number(value).toFixed(1)}%`} /><Bar dataKey="discount" name="Average discount" fill="#d4ae55" radius={[0, 4, 4, 0]} barSize={12} /></BarChart></ResponsiveContainer></div> : <div className="data-unavailable"><ArrowDownWideNarrow size={17} /><span>Average discount is not included in the current product API response.</span></div>}</Panel>
    <Panel title="Product Catalogue" subtitle={`${filtered.length} products match the current filters`} className="span-two" action={<div className="table-filters"><SearchField value={search} onChange={setSearch} placeholder="Search product or brand" /><select aria-label="Filter by category" value={category} onChange={event => setCategory(event.target.value)}><option>All categories</option>{categoryOptions.map(option => <option key={option}>{option}</option>)}</select></div>}>
      <Table columns={columns} rows={filtered} empty="No products match the search and category filters." />
    </Panel>
  </div>
}

function CustomerAnalytics({ data }) {
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(0)
  const pageSize = 12
  const allCustomers = data.customers.customers || data.customers.top_customers
  const fullCustomerRecordsAvailable = Boolean(data.customers.customers)
  const filtered = allCustomers.filter(customer => `${customer.Customer_ID} ${customer.location}`.toLowerCase().includes(search.toLowerCase()))
  const visible = filtered.slice(page * pageSize, (page + 1) * pageSize)
  const pageCount = Math.ceil(filtered.length / pageSize)
  const columns = [
    { key: 'Customer_ID', label: 'Customer', render: value => <strong className="mono">{value}</strong> },
    { key: 'location', label: 'Location' }, { key: 'orders', label: 'Orders', render: numeric },
    { key: 'items', label: 'Items', render: numeric }, { key: 'spend', label: 'Net spend', render: currency },
    { key: 'rating', label: 'Avg. rating', render: value => Number(value).toFixed(2) },
  ]
  return <>
    <div className="metric-grid four-metrics">
      <Metric label="Total Customers" value={numeric(data.customers.customer_count)} note="Unique buyers" icon={Users} />
      <Metric label="Average Customer Spending" value={currency(data.customers.average_customer_value)} note="Net sales per customer" icon={Wallet} tone="green" />
      <Metric label="Average Orders / Customer" value={data.customers.average_orders_per_customer == null ? '—' : numeric(data.customers.average_orders_per_customer)} note={data.customers.average_orders_per_customer == null ? 'Not returned by active API' : 'Unique orders per buyer'} icon={RotateCw} tone="olive" />
      <Metric label="Repeat Customers" value={numeric(data.customers.repeat_customers)} note="Customers with multiple orders" icon={ArrowUpRight} tone="gold" />
    </div>
    <div className="content-grid two-column">
      <Panel title="Customer Location Distribution" subtitle="Unique customers by location"><div className="chart-area tall"><ResponsiveContainer width="100%" height="100%"><BarChart data={data.customers.locations} layout="vertical" margin={{ top: 4, right: 14, bottom: 0, left: 0 }}><CartesianGrid horizontal={false} stroke="#e9ece6" /><XAxis type="number" tickLine={false} axisLine={false} tick={{ fill: '#878e86', fontSize: 10 }} /><YAxis type="category" dataKey="Location" width={94} tickLine={false} axisLine={false} tick={{ fill: '#59625b', fontSize: 10 }} /><Tooltip formatter={(value, name) => [numeric(value), name]} /><Bar dataKey="customers" name="Customers" fill="#638575" radius={[0, 4, 4, 0]} barSize={16} /></BarChart></ResponsiveContainer></div></Panel>
      <Panel title="Top Customers by Spending" subtitle="Highest customer net sales"><div className="rank-list">{data.customers.top_customers.slice(0, 7).map((customer, index) => <div className="rank-row" key={customer.Customer_ID}><span className="rank-index">{String(index + 1).padStart(2, '0')}</span><div className="rank-name"><strong>{customer.Customer_ID}</strong><small>{customer.location} · {numeric(customer.orders)} orders</small></div><b>{currency(customer.spend)}</b></div>)}</div></Panel>
      <Panel title="Customer Records" subtitle={fullCustomerRecordsAvailable ? `${filtered.length.toLocaleString()} records` : `Top ${filtered.length} customer records returned by API`} className="span-two" action={<SearchField value={search} onChange={value => { setSearch(value); setPage(0) }} placeholder="Search customer or location" />}>
        <Table columns={columns} rows={visible} empty="No customers match the search." />
        <div className="table-pagination"><span>Showing {filtered.length ? page * pageSize + 1 : 0}–{Math.min((page + 1) * pageSize, filtered.length)} of {filtered.length.toLocaleString()}</span><div><button disabled={page === 0} onClick={() => setPage(current => current - 1)}>Previous</button><button disabled={page + 1 >= pageCount} onClick={() => setPage(current => current + 1)}>Next</button></div></div>
      </Panel>
    </div>
  </>
}

function CustomerSegmentation({ data }) {
  const summary = data.segments.summary
  const segmentName = cluster => `Segment ${cluster}`
  return <div className="content-grid two-column">
    <Panel title="Segment Distribution" subtitle="Customer count produced by the backend K-Means model"><div className="segment-overview"><div className="segment-donut"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={summary} dataKey="customers" nameKey="cluster" innerRadius={58} outerRadius={88} paddingAngle={3} stroke="none">{summary.map((item, index) => <Cell key={item.cluster} fill={segmentColors[index % segmentColors.length]} />)}</Pie><Tooltip formatter={(value, name) => [`${numeric(value)} customers`, segmentName(name)]} /></PieChart></ResponsiveContainer></div><div className="legend-list segment-distribution">{summary.map((item, index) => <div key={item.cluster}><span><i style={{ background: segmentColors[index % segmentColors.length] }} />{segmentName(item.cluster)}</span><b>{numeric(item.customers)} customers</b></div>)}</div></div></Panel>
    <Panel title="Customer Segment Map" subtitle="Each point represents a sampled customer; axes use backend aggregates"><div className="chart-area"><ResponsiveContainer width="100%" height="100%"><ScatterChart margin={{ top: 10, right: 14, bottom: 6, left: 6 }}><CartesianGrid stroke="#e9ece6" /><XAxis type="number" dataKey="spend" name="Gross spending" tickLine={false} axisLine={false} tick={{ fill: '#878e86', fontSize: 9 }} tickFormatter={value => `${Math.round(value / 1000)}k`} /><YAxis type="number" dataKey="orders" name="Orders" tickLine={false} axisLine={false} tick={{ fill: '#878e86', fontSize: 9 }} /><Tooltip formatter={(value, name) => [name === 'Gross spending' ? currency(value) : numeric(value), name]} /><Scatter data={data.segments.customers} name="Customers">{data.segments.customers.map((item, index) => <Cell key={`${item.Customer_ID}-${index}`} fill={segmentColors[Number(item.cluster) % segmentColors.length]} fillOpacity={0.6} />)}</Scatter></ScatterChart></ResponsiveContainer></div></Panel>
    {summary.map((segment, index) => <article className="segment-card" key={segment.cluster}><div className="segment-top"><span className="segment-dot" style={{ background: segmentColors[index % segmentColors.length] }} /><span>{segmentName(segment.cluster)}</span><strong>{numeric(segment.customers)}<small> customers</small></strong></div><div className="segment-stats"><div><small>Average spending</small><b>{currency(segment.spend)}</b></div><div><small>Average orders</small><b>{numeric(segment.orders)}</b></div><div><small>Average items</small><b>{numeric(segment.items)}</b></div></div></article>)}
    <p className="method-note span-two">Segment IDs are shown without business labels. The model uses standardized customer gross spending, order count, and item count with K-Means (k=3).</p>
  </div>
}

function SalesPrediction({ data, onPredict, result, loading, error }) {
  const [form, setForm] = useState({ Category: '', Brand: '', Size: '', Price: '1800', Discount: '10', Rating: '4.5' })
  useEffect(() => {
    if (data.models.categories?.length) setForm(current => ({ ...current, Category: current.Category || data.models.categories[0], Brand: current.Brand || data.models.brands[0], Size: current.Size || data.models.sizes[0] }))
  }, [data.models])
  const update = event => setForm(current => ({ ...current, [event.target.name]: event.target.value }))
  return <div className="content-grid two-column">
    <Panel title="Predict Sales" subtitle="Enter product details to estimate quantity sold">
      <form className="prediction-form" onSubmit={event => { event.preventDefault(); onPredict(form) }}>
        <label>Category<select name="Category" value={form.Category} onChange={update} required>{data.models.categories.map(value => <option key={value}>{value}</option>)}</select></label>
        <div className="form-row"><label>Brand<select name="Brand" value={form.Brand} onChange={update} required>{data.models.brands.map(value => <option key={value}>{value}</option>)}</select></label><label>Size<select name="Size" value={form.Size} onChange={update} required>{data.models.sizes.map(value => <option key={value}>{value}</option>)}</select></label></div>
        <div className="form-row"><label>Price (৳)<input name="Price" type="number" min="0.01" step="any" value={form.Price} onChange={update} required /></label><label>Discount (%)<input name="Discount" type="number" min="0" max="100" step="any" value={form.Discount} onChange={update} required /></label></div>
        <label>Rating (0–5)<input name="Rating" type="number" min="0" max="5" step="0.1" value={form.Rating} onChange={update} required /></label>
        <button className="primary-button" type="submit" disabled={loading}>{loading ? <LoaderCircle size={16} className="spin" /> : <Activity size={16} />}{loading ? 'Predicting…' : 'Predict Sales'}</button>
        {error && <p className="form-error" role="alert">{error}</p>}
        {result && <div className="prediction-result" role="status"><span>Predicted Quantity</span><strong>{Number(result.predicted_quantity).toFixed(2)}</strong><div className="selected-model"><span>Selected Model</span><b>{result.selected_model}</b></div><div className="prediction-metrics"><div><small>MAE</small><b>{Number(result.mae).toFixed(3)}</b></div><div><small>RMSE</small><b>{Number(result.rmse).toFixed(3)}</b></div><div><small>R² Score</small><b>{Number(result.r2).toFixed(3)}</b></div></div></div>}
      </form>
    </Panel>
    <div className="prediction-side">
      <Panel title="Model Evaluation" subtitle={`Holdout data · ${numeric(data.models.testing_rows)} test records`}><div className="selection-callout"><span>Selected from test results</span><strong>{data.models.selected_model}</strong><small>{data.models.selection_method}</small></div><Table columns={[{ key: 'model', label: 'Model', render: value => <span className="model-name">{value}{value === data.models.selected_model && <small>Selected</small>}</span> }, { key: 'mae', label: 'MAE' }, { key: 'rmse', label: 'RMSE' }, { key: 'r2', label: 'R²' }]} rows={data.models.metrics} /></Panel>
      <Panel title="Regression Models" subtitle="Same features and 80/20 split for comparison"><div className="model-notes"><article><span className="model-index">01</span><div><strong>Linear Regression</strong><p>Baseline model estimates quantity from a linear combination of product features.</p></div></article><article><span className="model-index forest">02</span><div><strong>Random Forest Regression</strong><p>Main non-linear model combines 200 decision trees. Both models remain available for test-set comparison; predictions use the better-ranked result.</p></div></article></div></Panel>
    </div>
    <p className="method-note span-two">Features: category, brand, size, price, discount, and rating. Target: quantity. Model selection is automatic from held-out MAE, RMSE, and R² results.</p>
  </div>
}

function Methodology({ data }) {
  const flow = ['Dataset', 'Data Cleaning', 'Exploratory Data Analysis', 'Feature Engineering', 'Linear Regression', 'Random Forest Regression', 'Customer Segmentation', 'Dashboard']
  const explanations = [
    ['MAE', 'Mean Absolute Error: average absolute difference between predicted and observed quantity. Lower is better.'],
    ['RMSE', 'Root Mean Squared Error: square root of mean squared prediction error; larger misses count more. Lower is better.'],
    ['R² Score', 'Coefficient of determination: proportion of target variation explained by the model. Values closer to 1 indicate a stronger fit.'],
    ['K-Means', 'An unsupervised clustering method that groups customers by distance in standardized spending, order-count, and item-count features.'],
  ]
  return <div className="content-grid two-column">
    <Panel title="Project Workflow" subtitle="From transaction data to interpretation" className="span-two"><div className="method-flow">{flow.map((step, index) => <div className="flow-step" key={step}><span>{String(index + 1).padStart(2, '0')}</span><strong>{step}</strong>{index < flow.length - 1 && <i />}</div>)}</div></Panel>
    <Panel title="Dataset & Analytical Definitions" subtitle="Values sourced from the backend"><div className="method-grid">{[
      ['Dataset', 'Synthetic e-commerce dress sales transaction dataset created for academic demonstration and machine learning analysis.'],
      ['Dataset size', `${numeric(data.methodology.rows)} transactions · ${numeric(data.methodology.columns)} fields`],
      ['Coverage', `${data.methodology.date_start} to ${data.methodology.date_end}`],
      ['Quality', `${numeric(data.methodology.missing_values)} missing values · ${numeric(data.methodology.duplicate_rows_removed)} duplicate rows removed`],
      ['Revenue', data.methodology.revenue_definition],
      ['Segmentation', data.methodology.segmentation],
      ['Prediction', data.methodology.prediction],
    ].map(([label, value], index) => <article className="method-item" key={label}><span className="method-number">{String(index + 1).padStart(2, '0')}</span><div><h3>{label}</h3><p>{value}</p></div></article>)}</div></Panel>
    <Panel title="Evaluation & Clustering" subtitle="How to interpret the model output"><div className="explanation-list">{explanations.map(([title, body]) => <article key={title}><h3>{title}</h3><p>{body}</p></article>)}</div></Panel>
    <p className="method-note span-two">Academic evidence is retained in the project notebooks. The dashboard analyzes the supplied synthetic transaction CSV through FastAPI; displayed results are calculated from its rows rather than illustrative values.</p>
  </div>
}

export default function App() {
  const [active, setActive] = useState('overview')
  const [menuOpen, setMenuOpen] = useState(false)
  const [data, setData] = useState(null)
  const [loadError, setLoadError] = useState('')
  const [refreshing, setRefreshing] = useState(false)
  const [prediction, setPrediction] = useState(null)
  const [predictionError, setPredictionError] = useState('')
  const [predictionLoading, setPredictionLoading] = useState(false)

  async function refresh() {
    setRefreshing(true)
    setLoadError('')
    try { setData(await loadDashboardData()) }
    catch (error) { setLoadError(error.message) }
    finally { setRefreshing(false) }
  }

  useEffect(() => { refresh() }, [])

  async function submitPrediction(form) {
    setPredictionLoading(true)
    setPredictionError('')
    setPrediction(null)
    try {
      const body = { ...form, Price: Number(form.Price), Discount: Number(form.Discount), Rating: Number(form.Rating) }
      setPrediction(await apiRequest('/predict', { method: 'POST', body: JSON.stringify(body) }))
    } catch (error) { setPredictionError(error.message) }
    finally { setPredictionLoading(false) }
  }

  const selectPage = id => { setActive(id); setMenuOpen(false) }
  const activePage = pageCopy[active]

  return <div className="app-shell">
    <aside className={`sidebar ${menuOpen ? 'open' : ''}`}>
      <div className="brand-lockup"><div className="brand-symbol"><span /></div><div><strong>Threadline</strong><small>SALES INTELLIGENCE</small></div><button className="mobile-close" onClick={() => setMenuOpen(false)} aria-label="Close navigation"><X size={18} /></button></div>
      <div className="workspace-label">ANALYTICS WORKSPACE</div>
      <nav aria-label="Main navigation">{navigation.map(({ id, label, icon: Icon }) => <button className={`nav-link ${active === id ? 'active' : ''}`} key={id} onClick={() => selectPage(id)}><Icon size={17} strokeWidth={1.8} /><span>{label}</span>{active === id && <i />}</button>)}</nav>
      <div className="sidebar-bottom"><div className="data-status"><span className={`status-dot ${data ? '' : 'loading'}`} /><div><strong>{data ? 'Dataset loaded' : 'Connecting to API'}</strong><small>{data ? `${numeric(data.overview.kpis.orders)} orders loaded` : 'FastAPI · port 8000'}</small></div></div><div className="profile"><div className="avatar">EA</div><div><strong>Academic project</strong><small>Dress sales analytics</small></div><Database size={15} /></div></div>
    </aside>
    {menuOpen && <button className="scrim" aria-label="Close navigation" onClick={() => setMenuOpen(false)} />}
    <main className="main-area">
      <header className="topbar"><div className="topbar-left"><button className="menu-toggle" onClick={() => setMenuOpen(true)} aria-label="Open navigation"><Menu size={19} /></button><span className="breadcrumb">Analytics</span><span className="crumb-slash">/</span><strong>{activePage[0]}</strong></div><div className="topbar-right"><span className="date-pill"><Clock3 size={14} />{data ? `${data.overview.date_range.start} — ${data.overview.date_range.end}` : 'Dataset period'}</span><button className="icon-button" title="Refresh data" aria-label="Refresh data" onClick={refresh}><RotateCw size={16} className={refreshing ? 'spin' : ''} /></button></div></header>
      <div className="page-content"><div className="page-heading"><div><div className="eyebrow"><span />SYNTHETIC DATASET</div><h1>{activePage[0]}</h1><p>{activePage[1]}</p></div><button className="export-button" onClick={() => selectPage('methodology')}><Download size={15} />Method notes</button></div>
        {!data && !loadError && <div className="loading-state"><LoaderCircle className="spin" size={24} /><span>Loading dataset analytics…</span></div>}
        {loadError && <div className="error-state" role="alert"><strong>Analytics API unavailable</strong><p>{loadError}</p><button className="primary-button" onClick={refresh}><RotateCw size={15} />Retry connection</button></div>}
        {data && <div className="page-enter" key={active}>
          {active === 'overview' && <Overview data={data} />}
          {active === 'sales' && <SalesAnalytics data={data} />}
          {active === 'products' && <ProductAnalytics data={data} />}
          {active === 'customers' && <CustomerAnalytics data={data} />}
          {active === 'segments' && <CustomerSegmentation data={data} />}
          {active === 'prediction' && <SalesPrediction data={data} onPredict={submitPrediction} result={prediction} loading={predictionLoading} error={predictionError} />}
          {active === 'methodology' && <Methodology data={data} />}
        </div>}
        <footer className="page-footer"><span>E-Commerce Dress Sales Analytics | Data Analysis &amp; Machine Learning Project</span><span>Source: dress_sales.csv</span></footer>
      </div>
    </main>
  </div>
}
