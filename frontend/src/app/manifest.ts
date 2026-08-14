import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Remote Atlas",
    short_name: "Remote Atlas",
    description:
      "Candidate-first job discovery: fresh tech roles from official career systems. Apply on the employer’s page.",
    start_url: "/",
    display: "standalone",
    background_color: "#0B1F1A",
    theme_color: "#0B1F1A",
    icons: [
      { src: "/icon-48.png", sizes: "48x48", type: "image/png" },
      { src: "/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
    ],
  };
}
