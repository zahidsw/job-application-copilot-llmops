interface MetricItem {
  label: string
  value: string
  note: string
  tone?: 'neutral' | 'good' | 'watch' | 'risk'
}

interface MetricBandProps {
  items: MetricItem[]
}

export function MetricBand({ items }: MetricBandProps) {
  return (
    <section className="metric-band">
      {items.map((item) => (
        <div key={item.label} className={`metric-slot tone-${item.tone ?? 'neutral'}`}>
          <p className="metric-label">{item.label}</p>
          <strong>{item.value}</strong>
          <small>{item.note}</small>
        </div>
      ))}
    </section>
  )
}
