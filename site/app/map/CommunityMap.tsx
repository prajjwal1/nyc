"use client";

import { useEffect, useRef, useState } from "react";
import type { GeoJSONSource, Map as MapLibreMap, MapLayerMouseEvent } from "maplibre-gl";

export interface MappableCommunity {
  id: string;
  name: string;
  slug: string;
  latitude: number;
  longitude: number;
  neighborhood: string;
  type: string;
  approximate: boolean;
}

interface CommunityMapProps {
  communities: MappableCommunity[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

function geojson(communities: MappableCommunity[]): GeoJSON.FeatureCollection<GeoJSON.Point> {
  return {
    type: "FeatureCollection",
    features: communities.map((community) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [community.longitude, community.latitude] },
      properties: { ...community },
    })),
  };
}

export default function CommunityMap({ communities, selectedId, onSelect }: CommunityMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const onSelectRef = useRef(onSelect);
  const [failed, setFailed] = useState(false);

  useEffect(() => { onSelectRef.current = onSelect; }, [onSelect]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    let cancelled = false;
    import("maplibre-gl").then(({ default: maplibregl }) => {
      if (cancelled || !containerRef.current) return;
      const map = new maplibregl.Map({
        container: containerRef.current,
        center: [-73.9654, 40.7084],
        zoom: 10.25,
        minZoom: 8,
        maxZoom: 17,
        attributionControl: false,
        style: {
          version: 8,
          sources: {
            osm: {
              type: "raster",
              tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
              tileSize: 256,
              attribution: "© OpenStreetMap contributors",
              maxzoom: 19,
            },
          },
          layers: [{ id: "osm", type: "raster", source: "osm" }],
        },
      });
      mapRef.current = map;
      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
      map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
      map.on("error", (event) => { if (!event.error) setFailed(true); });
      map.on("load", () => {
        map.addSource("communities", { type: "geojson", data: geojson(communities), cluster: true, clusterMaxZoom: 13, clusterRadius: 48 });
        map.addLayer({ id: "clusters", type: "circle", source: "communities", filter: ["has", "point_count"], paint: { "circle-color": ["step", ["get", "point_count"], "#a5422d", 12, "#733929", 40, "#3d3029"], "circle-radius": ["step", ["get", "point_count"], 19, 12, 25, 40, 32], "circle-stroke-width": 3, "circle-stroke-color": "#fff8eb" } });
        map.addLayer({ id: "cluster-count", type: "symbol", source: "communities", filter: ["has", "point_count"], layout: { "text-field": ["get", "point_count_abbreviated"], "text-size": 12 }, paint: { "text-color": "#fff8eb" } });
        map.addLayer({ id: "communities-unclustered", type: "circle", source: "communities", filter: ["!", ["has", "point_count"]], paint: { "circle-color": ["case", ["==", ["get", "approximate"], true], "#d79f55", "#a5422d"], "circle-radius": 8, "circle-stroke-width": 3, "circle-stroke-color": "#fff8eb" } });
        map.addLayer({ id: "community-selected", type: "circle", source: "communities", filter: ["==", ["get", "id"], ""], paint: { "circle-color": "#fff8eb", "circle-radius": 13, "circle-stroke-width": 4, "circle-stroke-color": "#25231f" } });

        map.on("click", "clusters", async (event: MapLayerMouseEvent) => {
          const feature = map.queryRenderedFeatures(event.point, { layers: ["clusters"] })[0];
          const clusterId = feature?.properties?.cluster_id;
          if (clusterId == null || feature.geometry.type !== "Point") return;
          const source = map.getSource("communities") as GeoJSONSource;
          const zoom = await source.getClusterExpansionZoom(clusterId);
          map.easeTo({ center: feature.geometry.coordinates as [number, number], zoom });
        });
        map.on("click", "communities-unclustered", (event: MapLayerMouseEvent) => {
          const id = event.features?.[0]?.properties?.id;
          if (typeof id === "string") onSelectRef.current(id);
        });
        for (const layer of ["clusters", "communities-unclustered"]) {
          map.on("mouseenter", layer, () => { map.getCanvas().style.cursor = "pointer"; });
          map.on("mouseleave", layer, () => { map.getCanvas().style.cursor = ""; });
        }
      });
    }).catch(() => setFailed(true));
    return () => { cancelled = true; mapRef.current?.remove(); mapRef.current = null; };
    // The source is updated by the effect below once the map has loaded.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const update = () => (map.getSource("communities") as GeoJSONSource | undefined)?.setData(geojson(communities));
    if (map.isStyleLoaded()) update(); else map.once("load", update);
  }, [communities]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.getLayer("community-selected")) return;
    map.setFilter("community-selected", ["==", ["get", "id"], selectedId || ""]);
    const selected = communities.find((community) => community.id === selectedId);
    if (selected) map.easeTo({ center: [selected.longitude, selected.latitude], zoom: Math.max(map.getZoom(), 13), duration: 700 });
  }, [communities, selectedId]);

  if (failed) return <div id="community-map" className="grid min-h-[55vh] place-items-center rounded-3xl border border-[#d9d0c0] bg-[#e7e1d5] px-8 text-center"><div><p className="font-serif text-2xl">Map unavailable</p><p className="mt-2 max-w-sm text-sm text-[#665f54]">Use the synchronized community list to browse every result, including communities without public coordinates.</p></div></div>;
  return <div id="community-map" className="relative min-h-[55vh] overflow-hidden rounded-3xl border border-[#cfc5b5] bg-[#e7e1d5] shadow-sm lg:h-[68vh]" aria-label={`Map showing ${communities.length} communities`}><div ref={containerRef} className="absolute inset-0" /><noscript><p className="absolute inset-0 grid place-items-center bg-[#e7e1d5] p-8 text-center text-sm">JavaScript is needed for the interactive map. The community directory remains available.</p></noscript></div>;
}
