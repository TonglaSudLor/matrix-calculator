const editor = document.querySelector('#editor');
const message = document.querySelector('#message');
const resultMath = document.querySelector('#result-math');
const conditions = document.querySelector('#conditions');
const greek = { theta: 'θ', alpha: 'α', beta: 'β', gamma: 'γ', delta: 'δ', lambda: 'λ', phi: 'φ', pi: 'π' };
const backGreek = Object.fromEntries(Object.entries(greek).map(([name, symbol]) => [symbol, name]));
const subs = '₀₁₂₃₄₅₆₇₈₉';
const supers = '⁰¹²³⁴⁵⁶⁷⁸⁹';
function showPowers(text) {
  const raised = digits => [...digits].map(char => char === '-' ? '⁻' : char === '+' ? '⁺' : supers[Number(char)]).join('');
  return text.replace(/\^([+-]?\d+)/g, (_, exponent) => raised(exponent))
    .replace(/([⁰¹²³⁴⁵⁶⁷⁸⁹])(\d+)/g, (_, first, rest) => first + raised(rest));
}
function sourcePowers(text) {
  return text.replace(/[⁺⁻⁰¹²³⁴⁵⁶⁷⁸⁹]+/g,
    token => '^' + [...token].map(char => char === '⁻' ? '-' : char === '⁺' ? '+' : String(supers.indexOf(char))).join(''));
}
let lastResult = null;
let variables = {};
function loadStored(key, fallback) {
  try { return JSON.parse(sessionStorage.getItem(key)) ?? fallback; }
  catch { return fallback; }
}
let symbolValues = loadStored('matrix-symbol-values', {});
let knownSymbols = new Set(loadStored('matrix-known-symbols', []));
let detectedSymbols = new Set();
function saveSymbols() {
  sessionStorage.setItem('matrix-symbol-values', JSON.stringify(symbolValues));
  sessionStorage.setItem('matrix-known-symbols', JSON.stringify([...knownSymbols]));
}
let theme = sessionStorage.getItem('matrix-theme-v2') || 'light';
let angleUnit = sessionStorage.getItem('matrix-angle-unit') || 'DEG';
let substituteValues = sessionStorage.getItem('matrix-substitute-values') !== 'false';
if (!['DEG', 'RAD'].includes(angleUnit)) angleUnit = 'DEG';

function updateSubstitutionControl() {
  const button = document.querySelector('#substitute-toggle');
  button.textContent = `แทนค่า: ${substituteValues ? 'เปิด' : 'ปิด'}`;
  button.setAttribute('aria-pressed', String(substituteValues));
  sessionStorage.setItem('matrix-substitute-values', String(substituteValues));
}

function updateAngleControls() {
  document.querySelector('#angle-indicator').textContent = angleUnit;
  document.querySelectorAll('[data-angle]').forEach(button => {
    button.setAttribute('aria-pressed', String(button.dataset.angle === angleUnit));
  });
}
function renderSteps(steps) {
  const panel = document.querySelector('#steps-panel');
  panel.replaceChildren();
  if (!steps?.length) {
    panel.textContent = 'ยังไม่มีขั้นตอนย่อยสำหรับสูตรนี้';
    return;
  }
  const list = document.createElement('ol');
  for (const step of steps) {
    const item = document.createElement('li');
    window.katex.render(step.latex, item, { throwOnError: false, strict: 'ignore' });
    list.append(item);
  }
  panel.append(list);
}
function renderVariableFields(symbols) {
  if (symbols) {
    detectedSymbols = new Set(symbols);
    symbols.forEach(symbol => knownSymbols.add(symbol));
    saveSymbols();
  }
  const container = document.querySelector('#variable-fields');
  container.replaceChildren();
  const shown = [...knownSymbols].sort();
  if (!shown.length) {
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = 2;
    cell.textContent = 'ยังไม่มีตัวแปร กดเพิ่มตัวแปรด้านล่าง';
    row.append(cell);
    container.append(row);
    return;
  }
  for (const symbol of shown) {
    const row = document.createElement('tr');
    const name = document.createElement('th');
    name.scope = 'row';
    name.textContent = displaySymbols(symbol);
    if (!detectedSymbols.has(symbol)) {
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'variable-remove';
      remove.textContent = '×';
      remove.setAttribute('aria-label', `ลบ ${displaySymbols(symbol)}`);
      remove.addEventListener('click', () => {
        knownSymbols.delete(symbol);
        delete symbolValues[symbol];
        saveSymbols();
        renderVariableFields();
      });
      name.append(remove);
    }
    const value = document.createElement('td');
    const input = document.createElement('input');
    input.type = 'text';
    input.inputMode = 'decimal';
    input.autocomplete = 'off';
    input.placeholder = 'ค่า เช่น 30 หรือ pi/2';
    input.value = symbolValues[symbol] || '';
    input.dataset.symbol = symbol;
    input.addEventListener('keydown', event => {
      if (event.key === 'Enter') { event.preventDefault(); document.querySelector('#variables-apply').click(); }
    });
    input.setAttribute('aria-label', `ค่า ${displaySymbols(symbol)}`);
    value.append(input);
    row.append(name, value);
    container.append(row);
  }
}

function displaySymbols(text) {
  return text.replace(/\b(theta|alpha|beta|gamma|delta|lambda|phi|pi)(?:_?(\d+))?\b/g, (_, name, digits = '') => greek[name] + [...digits].map(d => subs[Number(d)]).join(''))
    .replace(/([θαβγδλφπ])_?(\d+)/g, (_, symbol, digits) => symbol + [...digits].map(d => subs[Number(d)]).join(''))
    .replace(/\b([a-z])_?(\d+)\b/g, (_, letter, digits) => letter + [...digits].map(d => subs[Number(d)]).join(''));
}
function sourceSymbols(text) {
  return sourcePowers(text.replace(/[θαβγδλφπ][₀-₉]*/g, token => backGreek[token[0]] + [...token.slice(1)].map(d => String(subs.indexOf(d))).join(''))
    .replace(/([a-z])([₀-₉]+)/g, (_, letter, digits) => letter + [...digits].map(d => String(subs.indexOf(d))).join('')));
}
function expandTrigText(text) {
  const source = sourceSymbols(text);
  return showPowers(displaySymbols(source.replace(/(^|[^A-Za-z_])(sin|cos|tan)([A-Za-z_][A-Za-z_0-9]*|\d+(?:\.\d+)?)/g,
    (_, prefix, fn, argument) => `${prefix}${fn}(${argument})`)));
}
function expandTrigInNode(node) {
  if (node?.nodeType !== Node.TEXT_NODE) return;
  const oldText = node.textContent;
  const newText = expandTrigText(oldText);
  if (newText === oldText) return;
  const selection = window.getSelection();
  const caret = selection.isCollapsed && selection.anchorNode === node ? expandTrigText(oldText.slice(0, selection.anchorOffset)).length : null;
  node.textContent = newText;
  if (caret !== null) {
    const range = document.createRange();
    range.setStart(node, Math.min(caret, newText.length)); range.collapse(true);
    selection.removeAllRanges(); selection.addRange(range);
  }
}
function normalizeExpressionDisplay() {
  const walker = document.createTreeWalker(editor, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  nodes.forEach(expandTrigInNode);
  editor.querySelectorAll('.matrix-cell').forEach(input => { input.value = expandTrigText(input.value); });
}
function prettifyField(field) {
  const start = field.selectionStart;
  const before = showPowers(displaySymbols(field.value.slice(0, start)));
  const value = showPowers(displaySymbols(field.value));
  if (value !== field.value) { field.value = value; field.setSelectionRange(before.length, before.length); }
}
function matrixElement(rows, cols, identity) {
  const matrix = document.createElement('span');
  matrix.className = 'inline-matrix';
  matrix.contentEditable = 'false';
  matrix.dataset.rows = String(rows);
  matrix.dataset.cols = String(cols);
  matrix.setAttribute('aria-label', `เมทริกซ์ ${rows} คูณ ${cols}`);
  const grid = document.createElement('span');
  grid.className = 'matrix-cells';
  grid.style.gridTemplateColumns = `repeat(${cols}, auto)`;
  for (let row = 0; row < rows; row++) for (let col = 0; col < cols; col++) {
    const input = document.createElement('input');
    input.className = 'matrix-cell';
    input.type = 'text';
    input.spellcheck = false;
    input.autocomplete = 'off';
    input.value = identity ? (row === col ? '1' : '0') : '';
    input.setAttribute('aria-label', `แถว ${row + 1} คอลัมน์ ${col + 1}`);
    input.addEventListener('input', () => prettifyField(input));
    input.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === 'Tab') {
        if (event.ctrlKey && event.key === 'Enter') { event.preventDefault(); event.stopPropagation(); calculate(); return; }
        event.preventDefault();
        event.stopPropagation();
        const cells = [...grid.querySelectorAll('input')];
        const index = cells.indexOf(input) + (event.shiftKey ? -1 : 1);
        if (cells[index]) cells[index].focus();
        else placeCaretAfter(matrix);
      }
    });
    grid.append(input);
  }
  matrix.append(grid);
  return matrix;
}
function placeCaretAfter(node) {
  let next = node.nextSibling;
  if (!next || next.nodeType !== Node.TEXT_NODE) {
    next = document.createTextNode(' ');
    node.after(next);
  }
  editor.focus();
  const range = document.createRange();
  range.setStart(next, next.textContent.length);
  range.collapse(true);
  const selection = window.getSelection();
  selection.removeAllRanges(); selection.addRange(range);
}
function commandAtCaret() {
  const selection = window.getSelection();
  if (!selection.rangeCount || !selection.isCollapsed) return null;
  const node = selection.anchorNode;
  if (node?.nodeType !== Node.TEXT_NODE || !editor.contains(node)) return null;
  const before = node.textContent.slice(0, selection.anchorOffset);
  const match = before.match(/(?:^|[\s=+*/(,-])(i\(([1-4])\)|mat([1-4])x([1-4]))$/i);
  if (!match) return null;
  return { node, start: selection.anchorOffset - match[1].length, end: selection.anchorOffset,
    rows: match[2] ? Number(match[2]) : Number(match[3]),
    cols: match[2] ? Number(match[2]) : Number(match[4]), identity: Boolean(match[2]) };
}
function expandCommand(command) {
  const range = document.createRange();
  range.setStart(command.node, command.start); range.setEnd(command.node, command.end);
  const matrix = matrixElement(command.rows, command.cols, command.identity);
  range.deleteContents(); range.insertNode(matrix);
  matrix.querySelector('input').focus();
  message.textContent = '';
}
function insertTemplate(template) {
  editor.focus();
  const selection = window.getSelection();
  const range = selection.rangeCount && editor.contains(selection.anchorNode) ? selection.getRangeAt(0) : document.createRange();
  if (!selection.rangeCount || !editor.contains(selection.anchorNode)) { range.selectNodeContents(editor); range.collapse(false); }
  if (template.startsWith('i(') || template.startsWith('mat')) {
    const identity = template.startsWith('i(');
    const dims = identity ? [Number(template.match(/\d+/)[0]), Number(template.match(/\d+/)[0])] : template.match(/\d+/g).map(Number);
    const matrix = matrixElement(dims[0], dims[1], identity);
    range.deleteContents(); range.insertNode(matrix);
    matrix.querySelector('input').focus();
  } else {
    const node = document.createTextNode(template);
    range.deleteContents(); range.insertNode(node);
    const caret = document.createRange();
    caret.setStart(node, Math.max(0, template.length - 1)); caret.collapse(true);
    selection.removeAllRanges(); selection.addRange(caret);
  }
}
function serializeEditor() {
  function read(node) {
    if (node.nodeType === Node.TEXT_NODE) return sourceSymbols(node.textContent);
    if (node.classList?.contains('inline-matrix')) {
      const cols = Number(node.dataset.cols);
      const cells = [...node.querySelectorAll('input')].map(input => {
        if (!input.value.trim()) throw new Error('กรอกค่าเมทริกซ์ให้ครบทุกช่อง');
        return sourceSymbols(input.value.trim());
      });
      const rows = [];
      for (let i = 0; i < cells.length; i += cols) rows.push(`[${cells.slice(i, i + cols).join(', ')}]`);
      return `[${rows.join(', ')}]`;
    }
    if (node.tagName === 'BR') return ' ';
    return [...node.childNodes].map(read).join('');
  }
  return [...editor.childNodes].map(read).join('').trim();
}
async function calculate() {
  message.textContent = '';
  document.querySelector('#variable-message').textContent = '';
  const button = document.querySelector('#calculate');
  button.disabled = true;
  try {
    normalizeExpressionDisplay();
    const formula = serializeEditor();
    if (!formula) return null;
    const response = await fetch('/api/calculate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ formula, variables, angleUnit, symbolValues: substituteValues ? symbolValues : {} }) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'คำนวณไม่ได้');
    lastResult = result;
    result.symbols?.forEach(symbol => knownSymbols.add(symbol));
    saveSymbols();
    if (!document.querySelector('#variable-panel').hidden) renderVariableFields(result.symbols);
    renderSteps(result.steps);
    document.querySelector('#steps-panel').hidden = true;
    document.querySelector('#steps-toggle').setAttribute('aria-expanded', 'false');
    window.katex.render(result.latex, resultMath, { throwOnError: false, displayMode: true, strict: 'ignore' });
    conditions.replaceChildren();
    conditions.hidden = !result.conditions?.length;
    if (result.conditions?.length) {
      conditions.append('เงื่อนไข: ');
      for (const item of result.conditions) {
        const span = document.createElement('span');
        window.katex.render(item.latex, span, { throwOnError: false });
        conditions.append(span, '  ');
      }
    }
    variables.ans = result;
    if (result.assignment) variables[result.assignment] = { ...result.symbolic, conditions: result.conditions };
    document.querySelector('#result-actions').hidden = false;
    return result;
  } catch (error) {
    message.textContent = error.message;
    if (!document.querySelector('#variable-panel').hidden) document.querySelector('#variable-message').textContent = error.message;
    return null;
  }
  finally { button.disabled = false; }
}

editor.addEventListener('keydown', event => {
  if (event.key === ' ' || event.key === 'Enter') {
    const command = commandAtCaret();
    if (command) { event.preventDefault(); expandCommand(command); return; }
  }
  if (event.key === 'Enter') { event.preventDefault(); calculate(); }
  else if ([' ', '+', '-', '*', '/', '^', ',', ')', '='].includes(event.key)) {
    expandTrigInNode(window.getSelection().anchorNode);
  }
});
editor.addEventListener('input', () => {
  const selection = window.getSelection();
  const node = selection.anchorNode;
  if (node?.nodeType !== Node.TEXT_NODE || !editor.contains(node)) return;
  const offset = selection.anchorOffset;
  const before = showPowers(displaySymbols(node.textContent.slice(0, offset)));
  const value = showPowers(displaySymbols(node.textContent));
  if (value !== node.textContent) {
    node.textContent = value;
    const range = document.createRange(); range.setStart(node, before.length); range.collapse(true);
    selection.removeAllRanges(); selection.addRange(range);
  }
});
editor.addEventListener('paste', event => {
  event.preventDefault();
  const text = event.clipboardData.getData('text/plain').replace(/[\r\n]+/g, ' ');
  const selection = window.getSelection();
  const range = selection.getRangeAt(0);
  range.deleteContents();
  const node = document.createTextNode(showPowers(displaySymbols(text)));
  range.insertNode(node);
  range.setStartAfter(node); range.collapse(true);
  selection.removeAllRanges(); selection.addRange(range);
});
document.querySelector('#calculate').addEventListener('click', calculate);
document.querySelectorAll('[data-template]').forEach(button => button.addEventListener('click', () => insertTemplate(button.dataset.template)));
document.querySelector('#copy-input').addEventListener('click', () => {
  if (lastResult) navigator.clipboard.writeText(lastResult.kind === 'matrix' ? `[${lastResult.cells.map(row => `[${row.join(', ')}]`).join(', ')}]` : lastResult.text);
});
document.querySelector('#copy-latex').addEventListener('click', () => { if (lastResult) navigator.clipboard.writeText(lastResult.latex); });
document.querySelector('#substitute-toggle').addEventListener('click', () => {
  substituteValues = !substituteValues;
  updateSubstitutionControl();
  if (editor.textContent.trim() || editor.querySelector('.inline-matrix')) calculate();
});
function closeVariablePanel() {
  document.querySelector('#variable-panel').hidden = true;
  document.querySelector('#variables-toggle').setAttribute('aria-expanded', 'false');
  document.querySelector('#variables-toggle').focus();
}
function collectVariableValues() {
  document.querySelectorAll('#variable-fields input').forEach(input => {
    if (input.value.trim()) symbolValues[input.dataset.symbol] = sourceSymbols(input.value.trim());
    else delete symbolValues[input.dataset.symbol];
  });
  saveSymbols();
}
document.querySelector('#variables-toggle').addEventListener('click', async () => {
  const panel = document.querySelector('#variable-panel');
  if (!panel.hidden) {
    closeVariablePanel();
    return;
  }
  panel.hidden = false;
  document.querySelector('#variables-toggle').setAttribute('aria-expanded', 'true');
  document.querySelector('#variable-message').textContent = '';
  detectedSymbols = new Set();
  renderVariableFields();
  try {
    normalizeExpressionDisplay();
    const formula = serializeEditor();
    document.querySelector('#variables-apply').textContent = formula ? 'คำนวณด้วยค่านี้' : 'บันทึกค่า';
    if (!formula) { document.querySelector('#variable-name').focus(); return; }
    const response = await fetch('/api/calculate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ formula, variables, angleUnit, symbolValues: {} }) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'อ่านตัวแปรไม่ได้');
    renderVariableFields(result.symbols);
    message.textContent = '';
    panel.querySelector('#variable-fields input, #variable-name')?.focus();
  } catch (error) { document.querySelector('#variable-message').textContent = error.message; }
});
document.querySelector('#variable-add').addEventListener('click', () => {
  const field = document.querySelector('#variable-name');
  const raw = sourceSymbols(field.value.trim());
  const name = raw.replace(/^([a-z]+)_?(\d+)$/, '$1_$2');
  const reserved = new Set(['ans', 'I', 'i', 'pi', 'sin', 'cos', 'tan', 'sqrt', 'det', 'transpose', 'inverse', 'trace', 'rref', 'simplify', 'decimal', 'toPi']);
  if (!/^[A-Za-z][A-Za-z0-9_]*$/.test(name) || reserved.has(name)) {
    document.querySelector('#variable-message').textContent = 'ชื่อตัวแปรไม่ถูกต้อง';
    field.focus();
    return;
  }
  collectVariableValues();
  knownSymbols.add(name);
  saveSymbols();
  renderVariableFields();
  document.querySelector('#variable-message').textContent = '';
  field.value = '';
  document.querySelector(`#variable-fields input[data-symbol="${name}"]`)?.focus();
});
document.querySelector('#variable-name').addEventListener('keydown', event => {
  if (event.key === 'Enter') { event.preventDefault(); document.querySelector('#variable-add').click(); }
});
document.querySelector('#variables-close').addEventListener('click', () => {
  closeVariablePanel();
});
document.querySelector('#variable-panel').addEventListener('click', event => {
  if (event.target === event.currentTarget) closeVariablePanel();
});
document.querySelector('#variable-panel').addEventListener('keydown', event => {
  if (event.key === 'Escape') { event.preventDefault(); closeVariablePanel(); }
});
document.querySelector('#variables-apply').addEventListener('click', async () => {
  collectVariableValues();
  if (!editor.textContent.trim() && !editor.querySelector('.inline-matrix')) { closeVariablePanel(); return; }
  substituteValues = true;
  updateSubstitutionControl();
  if (await calculate()) closeVariablePanel();
});
document.querySelector('#variables-clear').addEventListener('click', async () => {
  symbolValues = {};
  saveSymbols();
  document.querySelectorAll('#variable-fields input').forEach(input => { input.value = ''; });
  if (!editor.textContent.trim() && !editor.querySelector('.inline-matrix')) { closeVariablePanel(); return; }
  if (await calculate()) closeVariablePanel();
});
document.querySelector('#steps-toggle').addEventListener('click', () => {
  const panel = document.querySelector('#steps-panel');
  panel.hidden = !panel.hidden;
  document.querySelector('#steps-toggle').setAttribute('aria-expanded', String(!panel.hidden));
});
document.querySelector('#settings-toggle').addEventListener('click', () => {
  const panel = document.querySelector('#settings-panel');
  panel.hidden = !panel.hidden;
  document.querySelector('#settings-toggle').setAttribute('aria-expanded', String(!panel.hidden));
});
document.querySelectorAll('[data-angle]').forEach(button => button.addEventListener('click', () => {
  angleUnit = button.dataset.angle;
  sessionStorage.setItem('matrix-angle-unit', angleUnit);
  updateAngleControls();
  document.querySelector('#settings-panel').hidden = true;
  document.querySelector('#settings-toggle').setAttribute('aria-expanded', 'false');
  if (lastResult) calculate();
}));
document.querySelector('#theme').addEventListener('click', () => {
  theme = theme === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = theme;
  sessionStorage.setItem('matrix-theme-v2', theme);
});
document.documentElement.dataset.theme = theme;
updateAngleControls();
updateSubstitutionControl();
editor.focus();
