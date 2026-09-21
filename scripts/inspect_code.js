const fs = require('fs');
const targetFile = process.argv[2] || 'cockpit/cockpit_server.py';
const search = process.argv[3] || '/workspace';
const content = fs.readFileSync(targetFile, 'utf8');
const lines = content.split('\n');

for (let i = 0; i < lines.length; i++) {
  if (lines[i].includes(search)) {
    console.log(`--- Match at line ${i + 1} ---`);
    console.log(lines.slice(Math.max(0, i - 2), Math.min(lines.length, i + 35)).join('\n'));
  }
}
