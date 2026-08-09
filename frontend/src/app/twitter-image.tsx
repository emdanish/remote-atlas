import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "Remote Atlas";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function TwitterImage() {
  return new ImageResponse(
    (
      <div
        style={{
          height: "100%",
          width: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          background: "#0B1F1A",
          padding: "72px",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <div style={{ fontSize: 26, letterSpacing: "0.24em", color: "#5EEAD4", fontWeight: 700 }}>
          REMOTE ATLAS
        </div>
        <div style={{ marginTop: 24, fontSize: 52, fontWeight: 650, color: "#F7F4EF", maxWidth: 900 }}>
          Candidate-first job discovery
        </div>
      </div>
    ),
    { ...size },
  );
}
