const fs = require('node:fs/promises');
const path = require('node:path');
const sharp = require('sharp');

async function main() {
  const assets = path.resolve(__dirname, '../assets');
  const logo = await fs.readFile(path.join(assets, 'vard_logo.svg'));
  const symbol = await sharp(logo).resize(300, 440, { fit: 'inside' }).png().toBuffer();
  const foreground = await sharp({ create: { width: 1024, height: 1024, channels: 4, background: '#00000000' } })
    .composite([{ input: symbol, gravity: 'centre' }]).png().toBuffer();
  await sharp(foreground).toFile(path.join(assets, 'android-icon-foreground.png'));
  await sharp(foreground).toFile(path.join(assets, 'android-icon-monochrome.png'));
  await sharp({ create: { width: 1024, height: 1024, channels: 4, background: '#00326D' } })
    .png().toFile(path.join(assets, 'android-icon-background.png'));
  const icon = await sharp({ create: { width: 1024, height: 1024, channels: 4, background: '#00326D' } })
    .composite([{ input: await sharp(logo).resize(440, 650, { fit: 'inside' }).png().toBuffer(), gravity: 'centre' }])
    .png().toBuffer();
  await sharp(icon).toFile(path.join(assets, 'icon.png'));
  await sharp(icon).resize(64, 64).toFile(path.join(assets, 'favicon.png'));
  await sharp(logo).resize(260, 384).png().toFile(path.join(assets, 'splash-vard.png'));
}

main().catch((error) => { console.error(error); process.exitCode = 1; });
