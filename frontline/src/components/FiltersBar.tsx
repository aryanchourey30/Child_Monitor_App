interface FiltersValue {
  risk: string;
  babyVisible: string;
  activity: string;
  start: string;
  end: string;
}

interface FiltersBarProps {
  value: FiltersValue;
  onChange: (value: FiltersValue) => void;
}

export function FiltersBar({ value, onChange }: FiltersBarProps) {
  const setField = (field: keyof FiltersValue, next: string) => onChange({ ...value, [field]: next });

  return (
    <section className="card filters-grid">
      <label>
        Risk Level
        <select value={value.risk} onChange={(e) => setField("risk", e.target.value)}>
          <option value="">All</option>
          <option value="low">Low</option>
          <option value="medium">Medium</option>
          <option value="high">High</option>
          <option value="critical">Critical</option>
        </select>
      </label>
      <label>
        Baby Visible
        <select value={value.babyVisible} onChange={(e) => setField("babyVisible", e.target.value)}>
          <option value="">All</option>
          <option value="true">Yes</option>
          <option value="false">No</option>
        </select>
      </label>
      <label>
        Activity
        <input value={value.activity} onChange={(e) => setField("activity", e.target.value)} placeholder="playing, calm..." />
      </label>
      <label>
        Start Time
        <input type="datetime-local" value={value.start} onChange={(e) => setField("start", e.target.value)} />
      </label>
      <label>
        End Time
        <input type="datetime-local" value={value.end} onChange={(e) => setField("end", e.target.value)} />
      </label>
    </section>
  );
}
