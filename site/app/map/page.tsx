import type { Metadata } from "next";
import "maplibre-gl/dist/maplibre-gl.css";
import MapExplorer from "./MapExplorer";

export const metadata: Metadata = {
  title: "Community map",
  description: "Explore active NYC communities by neighborhood, interest, and meeting place.",
};

export default function CommunityMapPage() {
  return <MapExplorer />;
}
