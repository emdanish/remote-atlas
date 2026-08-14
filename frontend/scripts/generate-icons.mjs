/**
 * Rasterize the brand mark into Google-eligible favicons (48px+ PNG + ICO).
 * Run from frontend/: node scripts/generate-icons.mjs
 */
import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const src = join(root, "public", "icon.svg");
const publicDir = join(root, "public");
mkdirSync(publicDir, { recursive: true });

const pngSizes = [16, 32, 48, 96, 180, 192, 512];

for (const size of pngSizes) {
  const name =
    size === 180 ? "apple-touch-icon.png" : size === 48 ? "icon-48.png" : `icon-${size}.png`;
  await sharp(src).resize(size, size).png().toFile(join(publicDir, name));
  console.log("wrote", name);
}

await sharp(src).resize(32, 32).png().toFile(join(publicDir, "favicon-32.png"));
await sharp(src).resize(16, 16).png().toFile(join(publicDir, "favicon-16.png"));
console.log("pngs ready");
