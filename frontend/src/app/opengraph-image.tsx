import { ImageResponse } from "next/og";
import { readFileSync } from "node:fs";
import { join } from "node:path";

export const alt = "Remote Atlas — candidate-first job discovery";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const logo = readFileSync(join(process.cwd(), "public/icon-192.png"));

export default function OpenGraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          height: "100%",
          width: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: "#0B1F1A",
          padding: "64px",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          <img
            src={`data:image/png;base64,${logo.toString("base64")}`}
            width={72}
            height={72}
            alt=""
          />
          <div
            style={{
              display: "flex",
              fontSize: 28,
              letterSpacing: "0.28em",
              fontWeight: 700,
              color: "#5EEAD4",
            }}
          >
            REMOTE ATLAS
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <div
            style={{
              fontSize: 64,
              fontWeight: 650,
              color: "#F7F4EF",
              lineHeight: 1.1,
              maxWidth: 900,
            }}
          >
            A job search engine built for candidates.
          </div>
          <div style={{ fontSize: 28, color: "rgba(247,244,239,0.72)", maxWidth: 820 }}>
            Fresh roles from authentic career systems. Apply on the employer&apos;s official page.
          </div>
        </div>
        <div style={{ display: "flex", fontSize: 22, color: "rgba(247,244,239,0.5)" }}>
          remoteatlas.dev
        </div>
      </div>
    ),
    { ...size },
  );
}
