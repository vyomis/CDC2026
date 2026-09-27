import React from "react";

function isValidNumber(value) {
  return (
    value !== null &&
    value !== undefined &&
    value !== "" &&
    Number.isFinite(Number(value))
  );
}

function number(value) {
  if (!isValidNumber(value)) {
    return "—";
  }

  return new Intl.NumberFormat("en-US").format(Number(value));
}

function currency(value) {
  if (!isValidNumber(value)) {
    return "—";
  }

  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(Number(value));
}

function titleCase(value) {
  if (!value) {
    return "—";
  }

  return String(value)
    .toLowerCase()
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function getCountyName(county) {
  return (
    county.name ||
    county.NAME ||
    county.NAME10 ||
    county.NAMELSAD ||
    county.countyName ||
    "Unknown County"
  );
}

function getGeoid(county) {
  return county.geoid || county.GEOID || county.id || "—";
}

function extractStats(county, year, average) {
  if (!county) {
    return { events: 0, propertyDamage: 0, cropDamage: 0, eventTypes: {} };
  }

  // Handle direct property flattened objects
  if (county.stormEvents !== undefined || county.events !== undefined) {
    return {
      events: county.stormEvents ?? county.events ?? 0,
      propertyDamage: county.propertyDamage ?? county.propertyDamageUsd ?? 0,
      cropDamage: county.cropDamage ?? county.cropDamageUsd ?? 0,
      eventTypes: county.eventTypes || county.eventTypeCounts || {},
    };
  }

  // Average mode across all available years
  if (average && county.yearly) {
    const yearEntries = Object.values(county.yearly);
    const count = yearEntries.length || 1;

    let totalEvents = 0;
    let totalProp = 0;
    let totalCrop = 0;
    const aggregatedTypes = {};

    yearEntries.forEach((yStats) => {
      totalEvents += yStats.events || 0;
      totalProp += yStats.propertyDamage || 0;
      totalCrop += yStats.cropDamage || 0;

      if (yStats.eventTypes) {
        Object.entries(yStats.eventTypes).forEach(([type, cnt]) => {
          aggregatedTypes[type] = (aggregatedTypes[type] || 0) + cnt;
        });
      }
    });

    // Compute annual averages
    const avgTypes = {};
    Object.entries(aggregatedTypes).forEach(([type, cnt]) => {
      avgTypes[type] = Math.round(cnt / count);
    });

    return {
      events: Math.round(totalEvents / count),
      propertyDamage: Math.round(totalProp / count),
      cropDamage: Math.round(totalCrop / count),
      eventTypes: avgTypes,
    };
  }

  // Single year lookup
  if (county.yearly && county.yearly[year]) {
    const yearStats = county.yearly[year];
    return {
      events: yearStats.events ?? 0,
      propertyDamage: yearStats.propertyDamage ?? 0,
      cropDamage: yearStats.cropDamage ?? 0,
      eventTypes: yearStats.eventTypes || {},
    };
  }

  // Fallback feature properties
  if (county.properties) {
    return {
      events: county.properties.events ?? 0,
      propertyDamage: county.properties.propertyDamage ?? 0,
      cropDamage: county.properties.cropDamage ?? 0,
      eventTypes: county.eventTypes || {},
    };
  }

  return { events: 0, propertyDamage: 0, cropDamage: 0, eventTypes: {} };
}

function parseEventTypes(rawTypes) {
  if (!rawTypes) return [];

  if (Array.isArray(rawTypes)) {
    return rawTypes.map((item) =>
      typeof item === "string"
        ? { name: item, count: null }
        : {
            name: item.name || item.eventType || item.type || "Unknown",
            count: item.count ?? item.events ?? null,
          }
    );
  }

  if (typeof rawTypes === "object") {
    return Object.entries(rawTypes)
      .map(([name, count]) => ({
        name,
        count: isValidNumber(count) ? Number(count) : null,
      }))
      .sort((a, b) => (b.count || 0) - (a.count || 0));
  }

  return [];
}

function DataRow({ label, value, emphasis = false }) {
  return (
    <div className={emphasis ? "county-data-row emphasis" : "county-data-row"}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Section({ eyebrow, title, children }) {
  return (
    <section className="county-data-section">
      <div className="county-section-title">
        <div>
          <span className="county-section-eyebrow">{eyebrow}</span>
          <h3>{title}</h3>
        </div>
      </div>
      {children}
    </section>
  );
}

export default function CountyPanel({
  county,
  year,
  average = false,
  onClose,
}) {
  if (!county) {
    return null;
  }

  const name = getCountyName(county);
  const geoid = getGeoid(county);

  const stats = extractStats(county, year, average);
  const eventTypes = parseEventTypes(stats.eventTypes);
  const totalDamage =
    Number(stats.propertyDamage || 0) + Number(stats.cropDamage || 0);

  const displaySubtitle = average ? "ANNUAL AVERAGE" : `${year} STORM DATA`;

  return (
    <aside className="county-panel">
      <div className="county-panel-top">
        <div>
          <span className="county-panel-eyebrow">NORTH CAROLINA COUNTY</span>
          <h2>{name}</h2>
          <div className="county-panel-meta">
            <span>GEOID {geoid}</span>
            <span> · {displaySubtitle}</span>
          </div>
        </div>

        <button
          className="county-close"
          onClick={onClose}
          aria-label="Close county information"
        >
          ×
        </button>
      </div>

      <div className="county-highlight-grid">
        <div className="county-highlight">
          <span>{average ? "Avg Storm Events" : "Storm Events"}</span>
          <strong>{number(stats.events)}</strong>
        </div>

        <div className="county-highlight">
          <span>{average ? "Avg Total Damage" : "Total Damage"}</span>
          <strong>{currency(totalDamage)}</strong>
        </div>

        <div className="county-highlight">
          <span>Property Damage</span>
          <strong>{currency(stats.propertyDamage)}</strong>
        </div>

        <div className="county-highlight">
          <span>Crop Damage</span>
          <strong>{currency(stats.cropDamage)}</strong>
        </div>
      </div>

      <Section eyebrow="SEVERE WEATHER" title="Storm Impact">
        <div className="county-data-table">
          <DataRow
            label={average ? "Avg storm events" : "Storm events"}
            value={number(stats.events)}
            emphasis
          />
          <DataRow
            label="Property damage"
            value={currency(stats.propertyDamage)}
          />
          <DataRow label="Crop damage" value={currency(stats.cropDamage)} />
          <DataRow
            label={average ? "Avg total damage" : "Total reported damage"}
            value={currency(totalDamage)}
            emphasis
          />
        </div>
      </Section>

      <Section eyebrow="EVENT BREAKDOWN" title="Storm Types">
        {eventTypes.length > 0 ? (
          <div className="county-event-list">
            {eventTypes.map((event, index) => (
              <div className="county-event-row" key={`${event.name}-${index}`}>
                <div className="county-event-name">
                  <span className="county-event-dot" />
                  <span>{titleCase(event.name)}</span>
                </div>
                <strong>
                  {event.count === null ? "—" : number(event.count)}
                </strong>
              </div>
            ))}
          </div>
        ) : (
          <div className="county-empty">
            No storm-type breakdown available for this selection
          </div>
        )}
      </Section>

      <div className="county-panel-footer">
        <span>County profile</span>
        <span>NOAA Storm Events · TIGER/Line</span>
      </div>
    </aside>
  );
}