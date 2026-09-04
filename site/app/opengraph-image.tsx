import { ImageResponse } from "next/og";

export const alt = "NYC Events — curated things to do across New York City";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const dynamic = "force-static";

export default function OpenGraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          alignItems: "center",
          background: "#f8f3e8",
          color: "#173c35",
          display: "flex",
          height: "100%",
          justifyContent: "center",
          padding: "76px",
          width: "100%",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", maxWidth: "1048px", width: "100%" }}>
          <div style={{ color: "#9a684e", display: "flex", fontSize: 28, letterSpacing: "0.16em", textTransform: "uppercase" }}>
            Updated continuously
          </div>
          <div style={{ display: "flex", fontFamily: "serif", fontSize: 92, fontWeight: 700, lineHeight: 1.02, marginTop: 24 }}>
            What&apos;s happening in NYC
          </div>
          <div style={{ color: "#52645e", display: "flex", fontSize: 34, lineHeight: 1.35, marginTop: 30 }}>
            Genuinely good things to do across the city.
          </div>
        </div>
      </div>
    ),
    size,
  );
}
