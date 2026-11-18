import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { ReactNode } from 'react'

import type { TicketAnalytics } from '../types/ticket'

interface AnalyticsChartsProps {
  analytics: TicketAnalytics
}

const chartColors = ['#6572d8', '#42a883', '#e3a34f', '#df6f73', '#8870bd', '#53a7bd', '#8492a7']

function ChartPanel({
  title,
  subtitle,
  children,
}: {
  title: string
  subtitle: string
  children: ReactNode
}) {
  return (
    <article className="analytics-chart-card">
      <header>
        <h3>{title}</h3>
        <p>{subtitle}</p>
      </header>
      <div className="analytics-chart-plot">{children}</div>
    </article>
  )
}

export function AnalyticsCharts({ analytics }: AnalyticsChartsProps) {
  return (
    <div className="analytics-chart-grid">
      <ChartPanel title="Tickets by category" subtitle="Incident volume by classification">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={analytics.ticket_categories} margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
            <CartesianGrid stroke="#eef0f5" vertical={false} />
            <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#858da0' }} axisLine={false} tickLine={false} />
            <YAxis allowDecimals={false} tick={{ fontSize: 10, fill: '#858da0' }} axisLine={false} tickLine={false} />
            <Tooltip />
            <Bar dataKey="count" name="Tickets" fill="#6572d8" radius={[5, 5, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartPanel>

      <ChartPanel title="Priority distribution" subtitle="Current ticket priority mix">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={analytics.priority_distribution}
              dataKey="count"
              nameKey="name"
              innerRadius={52}
              outerRadius={83}
              paddingAngle={3}
            >
              {analytics.priority_distribution.map((item, index) => (
                <Cell key={item.name} fill={chartColors[index % chartColors.length]} />
              ))}
            </Pie>
            <Tooltip />
            <Legend iconType="circle" wrapperStyle={{ fontSize: 10 }} />
          </PieChart>
        </ResponsiveContainer>
      </ChartPanel>

      <ChartPanel title="Status distribution" subtitle="Open work and completed incidents">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={analytics.status_distribution}
              dataKey="count"
              nameKey="name"
              innerRadius={52}
              outerRadius={83}
              paddingAngle={3}
            >
              {analytics.status_distribution.map((item, index) => (
                <Cell key={item.name} fill={chartColors[index % chartColors.length]} />
              ))}
            </Pie>
            <Tooltip />
            <Legend iconType="circle" wrapperStyle={{ fontSize: 10 }} />
          </PieChart>
        </ResponsiveContainer>
      </ChartPanel>

      <ChartPanel title="Ticket trend" subtitle="Tickets created in the last 7 days">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={analytics.tickets_created_by_day} margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
            <CartesianGrid stroke="#eef0f5" vertical={false} />
            <XAxis
              dataKey="date"
              tickFormatter={(value: string) => new Date(`${value}T00:00:00`).toLocaleDateString([], { weekday: 'short' })}
              tick={{ fontSize: 10, fill: '#858da0' }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis allowDecimals={false} tick={{ fontSize: 10, fill: '#858da0' }} axisLine={false} tickLine={false} />
            <Tooltip />
            <Bar dataKey="count" name="Tickets" fill="#42a883" radius={[5, 5, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartPanel>

      <ChartPanel title="Assigned group distribution" subtitle="Tickets owned by each support team">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={analytics.assigned_group_distribution}
            layout="vertical"
            margin={{ top: 4, right: 15, bottom: 4, left: 4 }}
          >
            <CartesianGrid stroke="#eef0f5" horizontal={false} />
            <XAxis type="number" allowDecimals={false} tick={{ fontSize: 10, fill: '#858da0' }} axisLine={false} tickLine={false} />
            <YAxis
              type="category"
              dataKey="name"
              width={145}
              tick={{ fontSize: 9, fill: '#858da0' }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip />
            <Bar dataKey="count" name="Tickets" fill="#8870bd" radius={[0, 5, 5, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartPanel>
    </div>
  )
}
