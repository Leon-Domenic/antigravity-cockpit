const fs = require('fs');
const vm = require('vm');

const content = fs.readFileSync('cockpit/cockpit_server.py', 'utf8');
const scriptRegex = /<script>([\s\S]*?)<\/script>/gi;
let match;
let count = 0;
while ((match = scriptRegex.exec(content)) !== null) {
  count++;
  // Replace Python interpolations like """ + json.dumps(AGENTS) + """
  let code = match[1].replace(/"""\s*\+\s*json\.dumps\([^)]+\)\s*\+\s*"""/g, '[]');
  try {
    new vm.Script(code);
    console.log("Script tag " + count + ": Syntax OK! (" + match[1].length + " bytes)");
  } catch (err) {
    console.error("Script tag " + count + " syntax error:", err.message);
    if (err.stack) {
      console.error(err.stack);
    }
    const lines = match[1].split('\n');
    // Try finding the line
    const matchLine = err.stack.match(/evalmachine\.<anonymous>:(\d+)/);
    if (matchLine) {
      const lineNum = parseInt(matchLine[1], 10);
      console.error("Error at line:", lineNum);
      for (let i = Math.max(0, lineNum - 5); i < Math.min(lines.length, lineNum + 5); i++) {
        console.error((i + 1) + ": " + lines[i]);
      }
    }
    process.exit(1);
  }
}
console.log("Verified " + count + " script tag(s) successfully.");
