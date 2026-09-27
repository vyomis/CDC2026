import {
  useEffect,
  useRef,
  useState,
} from "react";

import * as THREE from "three";

import {
  OrbitControls,
} from "three/addons/controls/OrbitControls.js";

import CountyPanel from "./components/CountyPanel.jsx";
import Legend from "./components/Legend.jsx";

import {
  loadAtlasData,
} from "./lib/data.js";


const NC_BOUNDS = [
  -84.35,
  33.75,
  -75.40,
  36.59,
];

const TERRAIN_WIDTH = 720;
const TERRAIN_DEPTH = 470;
const TERRAIN_HEIGHT = 115;


function project(
  longitude,
  latitude
) {
  const x =
    (
      (
        longitude -
        NC_BOUNDS[0]
      ) /
      (
        NC_BOUNDS[2] -
        NC_BOUNDS[0]
      ) -
      0.5
    ) *
    TERRAIN_WIDTH;

  const z =
    -(
      (
        (
          latitude -
          NC_BOUNDS[1]
        ) /
        (
          NC_BOUNDS[3] -
          NC_BOUNDS[1]
        )
      ) -
      0.5
    ) *
    TERRAIN_DEPTH;

  return [
    x,
    z,
  ];
}


function unproject(
  x,
  z
) {
  const longitude =
    NC_BOUNDS[0] +
    (
      x /
        TERRAIN_WIDTH +
      0.5
    ) *
    (
      NC_BOUNDS[2] -
      NC_BOUNDS[0]
    );

  const latitude =
    NC_BOUNDS[1] +
    (
      -z /
        TERRAIN_DEPTH +
      0.5
    ) *
    (
      NC_BOUNDS[3] -
      NC_BOUNDS[1]
    );

  return [
    longitude,
    latitude,
  ];
}


function heightColor(
  value
) {
  const color =
    new THREE.Color();

  const normalized =
    THREE.MathUtils.clamp(
      value,
      0,
      1
    );

  if (
    normalized < 0.2
  ) {
    color.setHSL(
      0.53,
      0.48,
      0.30 +
        normalized *
          0.45
    );
  } else if (
    normalized < 0.45
  ) {
    color.setHSL(
      0.30,
      0.40,
      0.34 +
        (
          normalized -
          0.2
        ) *
          0.25
    );
  } else if (
    normalized < 0.7
  ) {
    color.setHSL(
      0.19,
      0.42,
      0.38 +
        (
          normalized -
          0.45
        ) *
          0.35
    );
  } else {
    color.setHSL(
      0.08,
      0.38,
      0.48 +
        (
          normalized -
          0.7
        ) *
          0.65
    );
  }

  return color;
}


function getTerrainValue(
  terrain,
  row,
  column
) {
  if (
    !terrain ||
    !Array.isArray(
      terrain.elevation
    )
  ) {
    return 0;
  }

  const width =
    Number(
      terrain.width
    );

  const height =
    Number(
      terrain.height
    );

  const safeRow =
    Math.max(
      0,
      Math.min(
        height - 1,
        row
      )
    );

  const safeColumn =
    Math.max(
      0,
      Math.min(
        width - 1,
        column
      )
    );

  const rowData =
    terrain.elevation[
      safeRow
    ];

  if (
    !Array.isArray(
      rowData
    )
  ) {
    return 0;
  }

  const value =
    Number(
      rowData[
        safeColumn
      ]
    );

  if (
    !Number.isFinite(
      value
    )
  ) {
    return 0;
  }

  return THREE.MathUtils.clamp(
    value,
    0,
    1
  );
}


function drawRing(
  context,
  ring,
  canvasWidth,
  canvasHeight
) {
  if (
    !ring ||
    ring.length < 3
  ) {
    return;
  }

  ring.forEach(
    (
      coordinate,
      index
    ) => {
      const longitude =
        Number(
          coordinate[0]
        );

      const latitude =
        Number(
          coordinate[1]
        );

      const x =
        (
          longitude -
          NC_BOUNDS[0]
        ) /
        (
          NC_BOUNDS[2] -
          NC_BOUNDS[0]
        ) *
        canvasWidth;

      const y =
        (
          NC_BOUNDS[3] -
          latitude
        ) /
        (
          NC_BOUNDS[3] -
          NC_BOUNDS[1]
        ) *
        canvasHeight;

      if (
        index === 0
      ) {
        context.moveTo(
          x,
          y
        );
      } else {
        context.lineTo(
          x,
          y
        );
      }
    }
  );

  context.closePath();
}


function createNorthCarolinaMask(
  geojson
) {
  const canvas =
    document.createElement(
      "canvas"
    );

  const canvasWidth =
    720;

  const canvasHeight =
    470;

  canvas.width =
    canvasWidth;

  canvas.height =
    canvasHeight;

  const context =
    canvas.getContext(
      "2d"
    );

  if (
    !context
  ) {
    return null;
  }

  context.clearRect(
    0,
    0,
    canvasWidth,
    canvasHeight
  );

  context.fillStyle =
    "#ffffff";

  context.beginPath();

  geojson?.features?.forEach(
    feature => {
      const geometry =
        feature.geometry;

      if (
        !geometry
      ) {
        return;
      }

      if (
        geometry.type ===
        "Polygon"
      ) {
        geometry.coordinates.forEach(
          ring => {
            drawRing(
              context,
              ring,
              canvasWidth,
              canvasHeight
            );
          }
        );
      }

      if (
        geometry.type ===
        "MultiPolygon"
      ) {
        geometry.coordinates.forEach(
          polygon => {
            polygon.forEach(
              ring => {
                drawRing(
                  context,
                  ring,
                  canvasWidth,
                  canvasHeight
                );
              }
            );
          }
        );
      }
    }
  );

  context.fill(
    "evenodd"
  );

  return canvas;
}


function buildTerrain(
  scene,
  terrain,
  counties
) {
  if (
    !terrain ||
    !Array.isArray(
      terrain.elevation
    )
  ) {
    throw new Error(
      "Terrain data has an invalid elevation grid."
    );
  }

  const width =
    Math.max(
      2,
      Number(
        terrain.width
      )
    );

  const height =
    Math.max(
      2,
      Number(
        terrain.height
      )
    );

  const geometry =
    new THREE.PlaneGeometry(
      TERRAIN_WIDTH,
      TERRAIN_DEPTH,
      width - 1,
      height - 1
    );

  const positions =
    geometry.attributes.position;

  const colors = [];

  for (
    let i = 0;
    i < positions.count;
    i += 1
  ) {
    const column =
      i % width;

    const row =
      Math.floor(
        i / width
      );

    const normalized =
      getTerrainValue(
        terrain,
        row,
        column
      );

    const elevation =
      Math.pow(
        normalized,
        1.15
      ) *
      TERRAIN_HEIGHT;

    positions.setZ(
      i,
      elevation
    );

    const color =
      heightColor(
        normalized
      );

    colors.push(
      color.r,
      color.g,
      color.b
    );
  }

  geometry.setAttribute(
    "color",
    new THREE.Float32BufferAttribute(
      colors,
      3
    )
  );

  geometry.computeVertexNormals();

  const maskCanvas =
    createNorthCarolinaMask(
      counties
    );

  const maskTexture =
    maskCanvas
      ? new THREE.CanvasTexture(
          maskCanvas
        )
      : null;

  if (
    maskTexture
  ) {
    maskTexture.colorSpace =
      THREE.NoColorSpace;

    maskTexture.wrapS =
      THREE.ClampToEdgeWrapping;

    maskTexture.wrapT =
      THREE.ClampToEdgeWrapping;

    maskTexture.needsUpdate =
      true;
  }

  const material =
    new THREE.MeshStandardMaterial({
      vertexColors:
        true,

      roughness:
        0.88,

      metalness:
        0.04,

      side:
        THREE.DoubleSide,

      transparent:
        Boolean(
          maskTexture
        ),

      alphaMap:
        maskTexture,

      alphaTest:
        maskTexture
          ? 0.5
          : 0,

      depthWrite:
        true,
    });

  const mesh =
    new THREE.Mesh(
      geometry,
      material
    );

  mesh.rotation.x =
    -Math.PI / 2;

  mesh.position.y =
    -8;

  mesh.receiveShadow =
    true;

  mesh.castShadow =
    true;

  scene.add(
    mesh
  );

  return mesh;
}


function eachRing(
  feature,
  callback
) {
  const geometry =
    feature.geometry;

  if (
    !geometry
  ) {
    return;
  }

  if (
    geometry.type ===
    "Polygon"
  ) {
    geometry.coordinates.forEach(
      (
        ring,
        index
      ) => {
        callback(
          ring,
          index === 0
        );
      }
    );
  }

  if (
    geometry.type ===
    "MultiPolygon"
  ) {
    geometry.coordinates.forEach(
      polygon => {
        polygon.forEach(
          (
            ring,
            index
          ) => {
            callback(
              ring,
              index === 0
            );
          }
        );
      }
    );
  }
}


function buildBoundaries(
  scene,
  geojson
) {
  const group =
    new THREE.Group();

  geojson?.features?.forEach(
    feature => {
      eachRing(
        feature,
        ring => {
          const points =
            ring.map(
              coordinate => {
                const [
                  longitude,
                  latitude,
                ] = coordinate;

                const [
                  x,
                  z,
                ] =
                  project(
                    longitude,
                    latitude
                  );

                return new THREE.Vector3(
                  x,
                  2,
                  z
                );
              }
            );

          if (
            points.length < 2
          ) {
            return;
          }

          const geometry =
            new THREE.BufferGeometry()
              .setFromPoints(
                points
              );

          const material =
            new THREE.LineBasicMaterial({
              color:
                "#dce8ef",

              transparent:
                true,

              opacity:
                0.30,
            });

          const line =
            new THREE.LineLoop(
              geometry,
              material
            );

          group.add(
            line
          );
        }
      );
    }
  );

  scene.add(
    group
  );

  return group;
}


function pointInRing(
  point,
  ring
) {
  let inside =
    false;

  const [
    x,
    y,
  ] = point;

  for (
    let i = 0,
      j = ring.length - 1;
    i < ring.length;
    j = i++
  ) {
    const [
      xi,
      yi,
    ] =
      ring[i];

    const [
      xj,
      yj,
    ] =
      ring[j];

    const intersects =
      (
        yi > y
      ) !==
      (
        yj > y
      ) &&
      x <
        (
          (
            xj -
            xi
          ) *
          (
            y -
            yi
          )
        ) /
          (
            yj -
            yi
          ) +
          xi;

    if (
      intersects
    ) {
      inside =
        !inside;
    }
  }

  return inside;
}


function pointInFeature(
  longitude,
  latitude,
  feature
) {
  const point = [
    longitude,
    latitude,
  ];

  if (
    feature.geometry.type ===
    "Polygon"
  ) {
    const [
      outer,
      ...holes
    ] =
      feature.geometry.coordinates;

    return (
      pointInRing(
        point,
        outer
      ) &&
      !holes.some(
        ring =>
          pointInRing(
            point,
            ring
          )
      )
    );
  }

  if (
    feature.geometry.type ===
    "MultiPolygon"
  ) {
    return feature.geometry.coordinates.some(
      polygon => {
        const [
          outer,
          ...holes
        ] = polygon;

        return (
          pointInRing(
            point,
            outer
          ) &&
          !holes.some(
            ring =>
              pointInRing(
                point,
                ring
              )
          )
        );
      }
    );
  }

  return false;
}


function findCountyAt(
  longitude,
  latitude,
  features
) {
  if (
    !Array.isArray(
      features
    )
  ) {
    return null;
  }

  return (
    features.find(
      feature =>
        pointInFeature(
          longitude,
          latitude,
          feature
        )
    ) ||
    null
  );
}


export default function App() {
  const mountRef =
    useRef(null);

  const [
    atlas,
    setAtlas
  ] =
    useState(null);

  const [
    selectedId,
    setSelectedId
  ] =
    useState(null);

  const [
    selectedYear,
    setSelectedYear
  ] =
    useState(2026);

  const [
    showAverage,
    setShowAverage
  ] =
    useState(false);

  const [
    loading,
    setLoading
  ] =
    useState(true);

  const [
    error,
    setError
  ] =
    useState("");


  useEffect(
    () => {
      loadAtlasData()
        .then(
          data => {
            setAtlas(
              data
            );

            if (
              data.stormData?.years?.length
            ) {
              setSelectedYear(
                Math.max(
                  ...data.stormData.years
                )
              );
            }
          }
        )
        .catch(
          loadError => {
            console.error(
              loadError
            );

            setError(
              loadError.message
            );
          }
        )
        .finally(
          () => {
            setLoading(
              false
            );
          }
        );
    },
    []
  );


  useEffect(
    () => {
      if (
        !atlas ||
        !mountRef.current
      ) {
        return;
      }

      const mount =
        mountRef.current;

      mount.innerHTML =
        "";

      const scene =
        new THREE.Scene();

      scene.background =
        new THREE.Color(
          "#07131f"
        );

      scene.fog =
        new THREE.Fog(
          "#07131f",
          650,
          1250
        );


      const camera =
        new THREE.PerspectiveCamera(
          48,
          mount.clientWidth /
            Math.max(
              1,
              mount.clientHeight
            ),
          0.1,
          3000
        );

      camera.position.set(
        0,
        430,
        560
      );


      const renderer =
        new THREE.WebGLRenderer({
          antialias:
            true,

          powerPreference:
            "high-performance"
        });

      renderer.setPixelRatio(
        Math.min(
          window.devicePixelRatio,
          2
        )
      );

      renderer.setSize(
        mount.clientWidth,
        mount.clientHeight
      );

      renderer.shadowMap.enabled =
        true;

      renderer.shadowMap.type =
        THREE.PCFSoftShadowMap;

      mount.appendChild(
        renderer.domElement
      );


      const controls =
        new OrbitControls(
          camera,
          renderer.domElement
        );

      controls.enableDamping =
        true;

      controls.dampingFactor =
        0.055;

      controls.target.set(
        0,
        35,
        0
      );

      controls.minDistance =
        260;

      controls.maxDistance =
        1000;

      controls.maxPolarAngle =
        Math.PI / 2.05;


      const hemisphere =
        new THREE.HemisphereLight(
          "#cfe7ff",
          "#24331f",
          2.2
        );

      scene.add(
        hemisphere
      );


      const sun =
        new THREE.DirectionalLight(
          "#fff5dc",
          3.2
        );

      sun.position.set(
        -300,
        700,
        250
      );

      sun.castShadow =
        true;

      sun.shadow.mapSize.width =
        2048;

      sun.shadow.mapSize.height =
        2048;

      scene.add(
        sun
      );


      let terrain;

      try {
        terrain =
          buildTerrain(
            scene,
            atlas.terrain,
            atlas.counties
          );
      } catch (
        terrainError
      ) {
        console.error(
          terrainError
        );

        setError(
          terrainError.message
        );

        return undefined;
      }


      const boundaries =
        buildBoundaries(
          scene,
          atlas.counties
        );


      const water =
        new THREE.Mesh(
          new THREE.PlaneGeometry(
            735,
            485
          ),
          new THREE.MeshStandardMaterial({
            color:
              "#174e69",

            transparent:
              true,

            opacity:
              0.35,

            roughness:
              0.2,

            metalness:
              0.25
          })
        );

      water.rotation.x =
        -Math.PI / 2;

      water.position.y =
        -7;

      scene.add(
        water
      );


      const base =
        new THREE.Mesh(
          new THREE.PlaneGeometry(
            1100,
            820
          ),
          new THREE.MeshStandardMaterial({
            color:
              "#040b12",

            roughness:
              1
          })
        );

      base.rotation.x =
        -Math.PI / 2;

      base.position.y =
        -13;

      base.receiveShadow =
        true;

      scene.add(
        base
      );


      const raycaster =
        new THREE.Raycaster();

      const mouse =
        new THREE.Vector2(
          999,
          999
        );

      let pointerInside =
        false;

      let currentCountyId =
        null;


      const getCountyFromPointer =
        () => {
          if (
            !pointerInside
          ) {
            return null;
          }

          raycaster.setFromCamera(
            mouse,
            camera
          );

          const hit =
            raycaster.intersectObject(
              terrain,
              false
            )[0];

          if (
            !hit
          ) {
            return null;
          }

          const [
            longitude,
            latitude,
          ] =
            unproject(
              hit.point.x,
              hit.point.z
            );

          return findCountyAt(
            longitude,
            latitude,
            atlas.counties?.features
          );
        };


      const move =
        event => {
          const rect =
            renderer.domElement
              .getBoundingClientRect();

          if (
            rect.width === 0 ||
            rect.height === 0
          ) {
            return;
          }

          mouse.x =
            (
              (
                event.clientX -
                rect.left
              ) /
              rect.width
            ) *
              2 -
            1;

          mouse.y =
            -(
              (
                event.clientY -
                rect.top
              ) /
              rect.height
            ) *
              2 +
            1;

          pointerInside =
            true;
        };


      const leave =
        () => {
          pointerInside =
            false;

          currentCountyId =
            null;
        };


      renderer.domElement.addEventListener(
        "pointermove",
        move
      );

      renderer.domElement.addEventListener(
        "pointerleave",
        leave
      );


      const resize =
        () => {
          const width =
            mount.clientWidth;

          const height =
            Math.max(
              1,
              mount.clientHeight
            );

          camera.aspect =
            width /
            height;

          camera.updateProjectionMatrix();

          renderer.setSize(
            width,
            height
          );
        };

      window.addEventListener(
        "resize",
        resize
      );


      let animationFrame;

      const animate =
        () => {
          animationFrame =
            requestAnimationFrame(
              animate
            );

          const feature =
            getCountyFromPointer();

          const geoid =
            feature?.properties?.GEOID ||
            feature?.properties?.geoid ||
            feature?.id ||
            null;

          if (
            geoid !==
            currentCountyId
          ) {
            currentCountyId =
              geoid;

            setSelectedId(
              geoid
            );
          }

          controls.update();

          renderer.render(
            scene,
            camera
          );
        };

      animate();


      return () => {
        cancelAnimationFrame(
          animationFrame
        );

        renderer.domElement.removeEventListener(
          "pointermove",
          move
        );

        renderer.domElement.removeEventListener(
          "pointerleave",
          leave
        );

        window.removeEventListener(
          "resize",
          resize
        );

        controls.dispose();

        if (
          mount.contains(
            renderer.domElement
          )
        ) {
          mount.removeChild(
            renderer.domElement
          );
        }

        renderer.dispose();

        terrain.geometry.dispose();
        terrain.material.dispose();

        if (
          terrain.material.alphaMap
        ) {
          terrain.material.alphaMap.dispose();
        }

        boundaries.children.forEach(
          object => {
            object.geometry.dispose();
            object.material.dispose();
          }
        );

        water.geometry.dispose();
        water.material.dispose();

        base.geometry.dispose();
        base.material.dispose();
      };
    },
    [
      atlas,
    ]
  );


  const selectedFeature =
    atlas?.counties?.features?.find(
      (f) =>
        (f.properties?.GEOID || f.properties?.geoid || f.id) === selectedId
    );


  const selectedData =
    selectedId &&
    atlas
      ? {
          id:
            selectedId,

          name:
            selectedFeature?.properties?.NAME ||
            selectedFeature?.properties?.NAME10 ||
            selectedFeature?.properties?.NAMELSAD ||
            "County",

          ...(
            atlas.stormData?.counties?.[
              selectedId
            ] || {}
          ),
        }
      : null;


  const years =
    atlas?.stormData?.years ||
    Array.from(
      {
        length: 27,
      },
      (_, index) =>
        2000 + index
    );


  const firstYear =
    years[0] || 2000;

  const lastYear =
    years[
      years.length - 1
    ] || 2026;


  function handleYearChange(
    event
  ) {
    setSelectedYear(
      Number(
        event.target.value
      )
    );

    setShowAverage(
      false
    );
  }


  function handleAverage() {
    setShowAverage(
      (prev) => !prev
    );
  }


  if (
    loading
  ) {
    return (
      <div className="loading">
        <div className="loader" />

        <span>
          Building North Carolina
          terrain atlas…
        </span>
      </div>
    );
  }


  if (
    error
  ) {
    return (
      <div className="loading">
        <h2>
          Atlas data unavailable
        </h2>

        <p>
          {error}
        </p>

        <p>
          Check the generated files in
          {" "}
          <code>
            frontend/public/data
          </code>
        </p>
      </div>
    );
  }


  return (
    <main className="app">
      <div
        ref={mountRef}
        className="scene"
      />

      <header className="topbar">
        <div>
          <div className="eyebrow">
            GEOSPATIAL DATA ATLAS · 2000–2026
          </div>

          <h1>
            NORTH CAROLINA
          </h1>

          <p>
            Terrain, communities &
            severe weather
          </p>
        </div>

        <div className="controls">
          <button
            className="active"
          >
            Terrain
          </button>
        </div>
      </header>


      <section className="time-control">
        <div className="time-header">
          <div>
            <span className="time-label">
              STORM DATA YEAR
            </span>

            <strong>
              {showAverage
                ? "OVERALL AVERAGE"
                : selectedYear}
            </strong>
          </div>

          <button
            className={
              showAverage
                ? "average-button active"
                : "average-button"
            }
            onClick={
              handleAverage
            }
          >
            {showAverage
              ? "Viewing Average"
              : "Overall Average"}
          </button>
        </div>

        <div className="slider-wrap">
          <span>
            {firstYear}
          </span>

          <input
            className="year-slider"
            type="range"
            min={firstYear}
            max={lastYear}
            step="1"
            value={selectedYear}
            onChange={
              handleYearChange
            }
          />

          <span>
            {lastYear}
          </span>
        </div>

        <div className="selected-year">
          {showAverage
            ? `Average annual conditions across ${firstYear}–${lastYear}`
            : `${selectedYear} storm data`}
        </div>
      </section>


      <div className="help">
        Hover over the terrain to inspect counties ·
        Drag to orbit ·
        Scroll to zoom
      </div>


      <Legend
        mode="elevation"
      />


      <CountyPanel
        county={
          selectedData
        }
        year={
          selectedYear
        }
        average={
          showAverage
        }
        startYear={
          firstYear
        }
        endYear={
          lastYear
        }
        onClose={() =>
          setSelectedId(
            null
          )
        }
      />


      <div className="source-badge">
        USGS 3DEP · NOAA Storm Events ·
        Census TIGER/Line
      </div>
    </main>
  );
}