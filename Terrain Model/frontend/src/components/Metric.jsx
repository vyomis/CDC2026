export default function Metric({
    label,
    value,
    sub
  }) {
  
    return (
  
      <div className="metric">
  
        <span>
          {label}
        </span>
  
        <strong>
          {value ?? "—"}
        </strong>
  
        {sub && (
          <small>
            {sub}
          </small>
        )}
  
      </div>
  
    );
  
  }