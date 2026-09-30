// Rasteriza SVGs em 16 e 32 px. Uso: node render_svgs.cjs <svg_dir> <names.txt> <out_dir>
// Escala fixa do Blender: 1600 unidades SVG = <size> px (o canvas pode ser maior ou menor).
// Requer @resvg/resvg-js acessível pelo NODE_PATH.
const fs = require('fs');
const path = require('path');
const { Resvg } = require('@resvg/resvg-js');

const [svgDir, listing, outDir] = process.argv.slice(2);
const names = fs.readFileSync(listing, 'utf8').split(/\r?\n/).filter(Boolean);

for (const size of [16, 32]) {
  fs.mkdirSync(path.join(outDir, String(size)), { recursive: true });
  for (const name of names) {
    const svg = fs.readFileSync(path.join(svgDir, name + '.svg'));
    const png = new Resvg(svg, { fitTo: { mode: 'zoom', value: size / 1600 } }).render().asPng();
    fs.writeFileSync(path.join(outDir, String(size), name + '.png'), png);
  }
}
