const fs = require('fs');
const html = fs.readFileSync('/home/administrator/projects/hermes-ea/kids-town/index.html', 'utf8');
const m = html.match(/<script>([\s\S]*?)<\/script>/);
if (!m) return console.log('No script tag');
const script = m[1];
const lines = script.split('\n');
console.log('Script has', lines.length, 'lines');

// Count backticks per line to find unbalanced template literals
let tickCount = 0;
for (let i = 0; i < lines.length; i++) {
  const line = lines[i];
  let inString = false;
  let strChar = '';
  let escaped = false;
  let ticksInLine = 0;
  for (let j = 0; j < line.length; j++) {
    const ch = line[j];
    if (escaped) { escaped = false; continue; }
    if (ch === '\\') { escaped = true; continue; }
    if (inString) {
      if (ch === strChar) inString = false;
      continue;
    }
    if (ch === "'" || ch === '"') { inString = true; strChar = ch; continue; }
    if (ch === '`') { ticksInLine++; tickCount++; }
  }
  if (ticksInLine > 0) {
    console.log(`Line ${i+1} (+${ticksInLine}, total=${tickCount}): ${line.trim().substring(0,130)}`);
  }
}

// Now use vm.compileFunction for proper syntax check
try {
  require('vm').compileFunction(script);
  console.log('\n✅ No syntax errors');
} catch(e) {
  console.log(`\n❌ Syntax error: ${e.message}`);
  const msg = e.message;
  // Try to extract line number from error
  const lineMatch = e.stack ? e.stack.match(/:(\d+):/) : null;
  if (lineMatch) {
    const errLine = parseInt(lineMatch[1]);
    const context = lines.slice(Math.max(0,errLine-3), errLine+2);
    console.log(`\nAround line ${errLine} (script line):`);
    context.forEach((l, idx) => {
      const nl = Math.max(0,errLine-3) + idx + 1;
      console.log(`${nl === errLine ? '>' : ' '} ${nl}: ${l.substring(0,150)}`);
    });
  }
}
