export default function Legend({
    mode
  }) {
  
    const items =
      mode === "elevation"
        ? [
            "Lowland",
            "Foothills",
            "Mountains"
          ]
        : [
            "Lower activity",
            "Moderate activity",
            "Higher activity"
          ];
  
    return (
  
      <div className="legend">
  
        <div className="legend-title">
  
          {mode === "elevation"
            ? "ELEVATION"
            : "STORM ACTIVITY"}
  
        </div>
  
        <div className="legend-row">
  
          <i className="swatch low" />
  
          <span>
            {items[0]}
          </span>
  
        </div>
  
        <div className="legend-row">
  
          <i className="swatch mid" />
  
          <span>
            {items[1]}
          </span>
  
        </div>
  
        <div className="legend-row">
  
          <i className="swatch high" />
  
          <span>
            {items[2]}
          </span>
  
        </div>
  
      </div>
  
    );
  
  }