const DATA_BASE = "/data";

async function loadJson(path) {
  const response = await fetch(path);

  if (!response.ok) {
    throw new Error(
      `Unable to load ${path} (${response.status})`
    );
  }

  return response.json();
}

export async function loadAtlasData() {
  const [
    counties,
    stormData,
    terrain,
  ] = await Promise.all([
    loadJson(
      `${DATA_BASE}/nc-counties.geojson`
    ),
    loadJson(
      `${DATA_BASE}/storm-data.json`
    ),
    loadJson(
      `${DATA_BASE}/terrain.json`
    ),
  ]);

  if (
    !Array.isArray(
      stormData.years
    )
  ) {
    throw new Error(
      "Storm data does not contain a valid year list."
    );
  }

  return {
    counties,
    stormData,
    terrain,
  };
}