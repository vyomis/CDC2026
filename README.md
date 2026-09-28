# 🏔️ North Carolina Geospatial Risk Atlas (2000–2027)

An interactive 3D WebGL map and predictive risk modeling system designed to analyze severe weather trends and socio-environmental vulnerability across all 100 North Carolina counties.

The project combines high-resolution terrain elevation (**USGS 3DEP**), 26 years of severe weather history (**NOAA Storm Events**), demographic data (**US Census ACS**), and a **Gradient Boosting machine learning model** to forecast multi-factor risk scores for **2027**.

---

## 📸 Screenshots & Visualizations

3D Interactive Elevation & Boundary Mesh with the 2027 County Predictive Risk Ranking
<img width="1505" height="687" alt="Screenshot 2026-09-27 at 10 53 00 AM" src="https://github.com/user-attachments/assets/d3ab042e-1d4f-477a-9855-9f61fd131fdf" />
*Full 3D WebGL terrain rendering using Three.js with raycasted county selection and a locked overlay table showing composite ML + ACS risk scores* 

---

## ✨ Features

- **3D Digital Elevation Model (DEM):** Renders dynamic terrain heightmaps, natural color spectrum gradients based on elevation, and custom alpha-masked boundaries for North Carolina.
- **Time-Series Analysis (2000–2026):** Interactive year-range slider allowing users to filter storm events, frequency, high-impact incidents, and historical damage metrics over a 26-year timeline.
- **Gradient Boosting Risk Model:** Predicts 2027 county risk probability by synthesizing storm frequency, damage severity, and socioeconomic vulnerability.
- **Real-Time Raycasting & Inspection:** Hover over any county mesh in 3D space to trigger live risk score highlighting and synchronized list navigation.
- **Fixed-Header UI Layout:** Streamlined overlay panel with sticky column headers and scrollable row content for seamless county comparisons.

---

## 🏗️ Architecture & Tech Stack

| Category | Technology |
|---|---|
| **Frontend Framework** | React.js, Vite |
| **3D Graphics & Rendering** | Three.js, OrbitControls, WebGL |
| **Styling & UI** | Custom CSS Modules, Responsive Overlay Panels |
| **Data Engineering** | GeoJSON, Node.js data processing scripts |
| **Machine Learning / Risk Pipeline** | Gradient Boosting Classifier / Regressor, Scikit-Learn, Pandas |

---

## 📊 Data Pipeline & Risk Scoring Model

The overall **2027 Composite Risk Score** (`S_overall`) ranges from **0 to 100** and blends two core components:

Composite Risk Score
=
0.5 * Vulnerability Score
+
0.5 * Predictive Risk Score

### 1. Socioeconomic Vulnerability Index (ACS)

Evaluates underlying community sensitivity using U.S. Census ACS demographic indicators:

- Poverty Rate
- Median Household Income
- Infrastructure exposure metrics

### 2. Predictive Storm Risk (NOAA + Gradient Boosting)

Trained on historical storm features from **2000 to 2026**:

- 5-year rolling storm frequency
- High-impact severe weather event counts
- Average 5-year monetary damage

---

## 🚀 Getting Started

### Prerequisites

Before running the project, make sure you have:

- **Node.js v18.0 or higher**
- **npm** or **yarn**

### Installation

#### 1. Clone the Repository

```bash
git clone https://github.com/your-username/nc-geospatial-risk-atlas.git
cd nc-geospatial-risk-atlas
```

#### 2. Install Frontend Dependencies

```bash
npm install
```

#### 3. Verify Data Files

Ensure the required processed data files exist in:

```text
public/data/
```

Required files:

```text
counties.json
terrain.json
storm_data.json
```

These files should contain:

| File | Description |
|---|---|
| `counties.json` | North Carolina GeoJSON county boundaries |
| `terrain.json` | Processed elevation grid matrix |
| `storm_data.json` | Processed NOAA storm records and metrics from 2000–2026 |

#### 4. Run the Development Server

```bash
npm run dev
```

The development server should start at:

```text
http://localhost:5173
```

Open the URL in your browser to launch the interactive atlas.

---

## 📁 Repository Structure

```text
.
├── public/
│   └── data/
│       ├── counties.json       # North Carolina GeoJSON boundary data
│       ├── storm_data.json     # Processed 2000–2026 storm metrics
│       └── terrain.json        # Terrain elevation grid matrix
│
├── src/
│   ├── components/
│   │   ├── CountyPanel.jsx     # Side drawer displaying county statistics
│   │   └── Legend.jsx          # Color scale and elevation key
│   │
│   ├── lib/
│   │   └── data.js             # Data fetching and processing utilities
│   │
│   ├── App.jsx                 # Main 3D Canvas scene and state orchestration
│   ├── main.jsx                # Application entry point
│   └── index.css               # Global styles and canvas positioning
│
├── package.json
└── README.md
```

---

## 🗺️ System Overview

The **North Carolina Geospatial Risk Atlas** combines spatial visualization, historical severe-weather data, socioeconomic indicators, and machine learning into a single interactive application.

### Data Flow

```text
USGS 3DEP
   │
   ▼
Elevation Data ──────────────┐
                             │
NOAA Storm Events            │
   │                         │
   ▼                         │
Historical Storm Metrics ────┤
                             │
US Census ACS                │
   │                         │
   ▼                         │
Socioeconomic Indicators ────┤
                             ▼
                    Data Processing Pipeline
                             │
                             ▼
                    Feature Engineering
                             │
                             ▼
                    Gradient Boosting Model
                             │
                             ▼
                    2027 Predictive Risk
                             │
                             ▼
                  Composite Risk Calculation
                             │
                             ▼
                    Interactive 3D Atlas
```

---

## 🌎 Geographic Coverage

The atlas covers all **100 counties in North Carolina**.

Each county can be inspected through the interactive 3D environment, allowing users to explore:

- Terrain elevation
- County boundaries
- Historical severe-weather activity
- Storm frequency
- High-impact event counts
- Monetary damage metrics
- Socioeconomic vulnerability indicators
- Predictive risk scores
- Composite 2027 risk scores

---

## ⏱️ Historical Time-Series Analysis

The system analyzes severe-weather records spanning:

**2000 → 2026**

The interactive time-range controls allow users to examine changes in:

- Storm-event frequency
- High-impact events
- Historical damage
- Rolling storm metrics
- County-level risk indicators

The historical data is subsequently used to construct predictive features for the **2027 risk model**.

---

## 🤖 Machine Learning Model

The predictive component uses a **Gradient Boosting** machine learning approach.

Historical county-level features are engineered from NOAA storm-event records and used to estimate future risk.

### Example Feature Groups

| Feature Group | Example Metrics |
|---|---|
| **Storm Frequency** | 5-year rolling event count |
| **Event Severity** | High-impact event count |
| **Financial Impact** | Average 5-year monetary damage |
| **Vulnerability** | Poverty rate |
| **Economic Conditions** | Median household income |
| **Infrastructure** | Infrastructure exposure metrics |

The resulting predictive component is combined with the socioeconomic vulnerability component to produce the final composite score.

---

## 📐 Composite Risk Calculation

The model combines vulnerability and predicted storm risk using equal weighting:

S =
0.5V
+
0.5P

Where:

- `S` = Composite Risk Score
- `V` = Socioeconomic Vulnerability Score
- `P` = Predictive Storm Risk Score

The final score is normalized to a **0–100 scale**.

---

## 🎨 3D Visualization

The frontend uses **Three.js** and **WebGL** to render an interactive representation of North Carolina.

### Terrain Rendering

The digital elevation model provides:

- Dynamic terrain heightmaps
- Elevation-based color gradients
- County boundary overlays
- Interactive mesh geometry
- Camera orbit controls
- Raycast-based county selection

### County Interaction

Users can interact directly with county meshes.

When a county is hovered or selected, the interface can display corresponding county-level risk information and synchronize the selected county with the data panel.

---

## 🖱️ Interactive Features

### County Selection

Raycasting is used to detect intersections between the user's cursor and county meshes within the 3D scene.

This allows users to:

1. Hover over a county.
2. Highlight the corresponding geometry.
3. Inspect county-specific metrics.
4. Synchronize the selected county with the information panel.

### Risk Table

The application includes a fixed-header table designed to make county-level comparisons easier.

The table provides access to relevant:

- Vulnerability scores
- Predictive risk scores
- Composite risk scores
- Historical storm metrics
- County information

---

## 🧰 Technology Stack

### Frontend

- React.js
- Vite
- JavaScript / JSX

### 3D Rendering

- Three.js
- WebGL
- OrbitControls
- Raycasting

### Styling

- CSS Modules
- Responsive CSS
- Overlay-based UI components

### Data Processing

- Node.js
- GeoJSON
- JSON data pipelines

### Machine Learning

- Python
- Pandas
- Scikit-Learn
- Gradient Boosting Classifier / Regressor

---

## 📊 Data Sources & Acknowledgments

This project combines publicly available geospatial, weather, and demographic datasets.

### USGS 3D Elevation Program (3DEP)

Used for terrain and elevation information supporting the 3D visualization.

**Source:** U.S. Geological Survey — 3D Elevation Program (3DEP)

### NOAA Storm Events Database

Used for historical severe-weather event records and associated damage metrics covering **2000–2026**.

**Source:** National Oceanic and Atmospheric Administration — Storm Events Database

### U.S. Census Bureau

Used for demographic and socioeconomic indicators through:

- TIGER/Line Shapefiles
- American Community Survey (ACS) 5-Year Estimates

---

## ⚠️ Data & Model Disclaimer

The predictive risk scores presented by this project are **model-generated estimates**, not official forecasts or determinations of future disaster risk.

Results depend on:

- Historical data quality
- Feature engineering choices
- Model configuration
- Data normalization
- Geographic aggregation
- Assumptions used in the vulnerability index

The **2027 risk scores** should therefore be interpreted as analytical outputs from the project's modeling pipeline rather than definitive predictions of future events.

---

## 🔮 Future Improvements

Potential future development could include:

- Live NOAA data ingestion
- Additional climate and environmental datasets
- Higher-resolution terrain data
- Floodplain and wildfire layers
- Hurricane track visualization
- Tornado-path visualization
- Infrastructure and critical-facility layers
- Real-time weather overlays
- Model explainability using feature importance
- County-level historical trend charts
- Automated data pipeline updates
- GPU-accelerated terrain rendering
- Mobile-optimized 3D interaction

---

## ⭐ Project

### North Carolina Geospatial Risk Atlas

An interactive geospatial platform for exploring the relationship between terrain, severe weather history, socioeconomic vulnerability, and modeled future risk across North Carolina.
