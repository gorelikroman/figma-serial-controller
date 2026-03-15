// Auto Layout Helper + Serial Controller WebSocket bridge
// Полная копия code.js + WebSocket UI для приёма команд от agent.py
// Команда openPadGapController теперь открывает WebSocket-панель.

// Helper to show main WebSocket UI
function showMainUI() {
  figma.showUI(`
    <style>
      * { box-sizing: border-box; margin: 0; padding: 0; }
      body { font: 11px/1.4 -apple-system, BlinkMacSystemFont, sans-serif; padding: 4px; background: var(--figma-color-bg); color: var(--figma-color-text); }
      .icon-btn { width: 100%; padding: 6px; border: none; border-radius: 4px; font-size: 18px; cursor: pointer; transition: all 0.2s; }
      .icon-btn.ok { background: #1b7; }
      .icon-btn.err { background: #d44; }
      .icon-btn.wait { background: #f80; }
      .icon-btn:hover { opacity: 0.8; }
      .flash { animation: flash 0.3s; }
      @keyframes flash { 0%{opacity:1} 50%{opacity:0.3} 100%{opacity:1} }
      .log { font-family: monospace; font-size: 8px; max-height: 100px; overflow-y: auto; background: var(--figma-color-bg-secondary); border-radius: 3px; padding: 3px; margin-top: 4px; display: none; }
      .log.visible { display: block; }
      .log div { padding: 1px 0; }
      .log .enc { color: #4a9; }
      .log .cmd { color: #49a; }
      .log .err { color: #d44; }
    </style>
    <button id="btn" class="icon-btn wait" title="Serial Controller">🎛</button>
    <div class="log" id="log"></div>
    <script>
      const WS_URL = 'ws://127.0.0.1:8765';
      const logEl = document.getElementById('log');
      const btn = document.getElementById('btn');
      let ws = null;
      let reconnTimer = null;

      btn.addEventListener('click', () => {
        logEl.classList.toggle('visible');
      });

      function addLog(text, cls) {
        const d = document.createElement('div');
        d.textContent = text;
        if (cls) d.className = cls;
        logEl.prepend(d);
        while (logEl.children.length > 50) logEl.removeChild(logEl.lastChild);
      }

      function connect() {
        if (ws && ws.readyState <= 1) return;
        try {
          ws = new WebSocket(WS_URL);
        } catch(e) {
          btn.className = 'icon-btn err';
          btn.title = 'Error';
          scheduleReconnect();
          return;
        }

        ws.onopen = () => {
          btn.className = 'icon-btn ok';
          btn.title = 'Connected ✓';
          addLog('Connected', 'cmd');
          parent.postMessage({ pluginMessage: { type: 'ws-connected' } }, '*');
        };

        ws.onclose = () => {
          btn.className = 'icon-btn err';
          btn.title = 'Disconnected';
          addLog('Disconnected', 'err');
          scheduleReconnect();
        };

        ws.onerror = () => {
          btn.className = 'icon-btn err';
          btn.title = 'Error';
        };

        ws.onmessage = (e) => {
          try {
            const msg = JSON.parse(e.data);
            parent.postMessage({ pluginMessage: msg }, '*');

            if (msg.t === 'enc') {
              addLog('ENC ' + msg.id + ' ' + msg.action + ' Δ' + (msg.delta > 0 ? '+' : '') + msg.delta, 'enc');
              btn.title = msg.id + ' ' + msg.action + ' ' + (msg.delta > 0 ? '+' : '') + msg.delta;
              btn.classList.add('flash');
              setTimeout(() => btn.classList.remove('flash'), 300);
            } else if (msg.t === 'cmd') {
              addLog('CMD ' + msg.command, 'cmd');
              btn.title = '⚡ ' + msg.command;
              btn.classList.add('flash');
              setTimeout(() => btn.classList.remove('flash'), 300);
            }
          } catch(_) {}
        };
      }

      function scheduleReconnect() {
        if (reconnTimer) clearTimeout(reconnTimer);
        reconnTimer = setTimeout(connect, 2000);
      }

      connect();
    <\/script>
  `, { width: 48, height: 48, themeColors: true });

  figma.ui.onmessage = async (msg) => {
    if (!msg || !msg.t) {
      if (msg && msg.type === 'pad-delta') adjustPaddingOnSelection(msg.delta || 0);
      if (msg && msg.type === 'gap-delta') adjustGapOnSelection(msg.delta || 0);
      if (msg && msg.type === 'ws-connected') return;
      return;
    }

    if (msg.t === 'enc') {
      handleEncoderAction(msg.action, msg.delta);
      return;
    }

    if (msg.t === 'cmd') {
      await handleCommand(msg.command);
      return;
    }
  };
}

const cmd = figma.command;
const selection = figma.currentPage.selection;

let _activeNotify = null;
function showToast(message, timeout = 900) {
  try {
    if (_activeNotify) _activeNotify.cancel();
  } catch (_) {}
  _activeNotify = figma.notify(message, { timeout });
}

if (!selection.length && !(typeof cmd === 'string' && cmd.indexOf('open') === 0)) {
  figma.notify("Выделите хотя бы один элемент.");
  figma.closePlugin();
} else {
  (async () => {

  // ═══════════════════════════════════════════════════════════════
  // WebSocket Controller UI (replaces old Pad/Gap buttons)
  // ═══════════════════════════════════════════════════════════════
  if (cmd === 'openPadGapController') {
    showMainUI();
    return; // keep plugin open
  }

  // ═══════════════════════════════════════════════════════════════
  // Input dialogs (unchanged)
  // ═══════════════════════════════════════════════════════════════
  if (cmd === 'openPadXInput' || cmd === 'openPadYInput' || cmd === 'openGapInput' || cmd === 'openPadAllInput' || cmd === 'openCornerInput' || cmd === 'openWidthInput' || cmd === 'openHeightInput' || cmd === 'openFontSizeInput') {
    openInputDialog(cmd);
    return;
  }

  // ═══════════════════════════════════════════════════════════════
  // Increment/Decrement commands (unchanged)
  // ═══════════════════════════════════════════════════════════════
  if (cmd === 'padInc' || cmd === 'padDec' || cmd === 'gapInc' || cmd === 'gapDec' || cmd === 'padXInc' || cmd === 'padXDec' || cmd === 'padYInc' || cmd === 'padYDec' || cmd === 'opacityInc' || cmd === 'opacityDec' || cmd === 'cornerInc' || cmd === 'cornerDec' || cmd === 'widthInc' || cmd === 'widthDec' || cmd === 'heightInc' || cmd === 'heightDec') {
    const d = (cmd.endsWith('Inc') ? 1 : -1);
    if (cmd === 'padInc' || cmd === 'padDec') adjustPaddingOnSelection(d, 'all');
    else if (cmd === 'padXInc' || cmd === 'padXDec') adjustPaddingOnSelection(d, 'x');
    else if (cmd === 'padYInc' || cmd === 'padYDec') adjustPaddingOnSelection(d, 'y');
    else if (cmd === 'gapInc' || cmd === 'gapDec') adjustGapOnSelection(d);
    else if (cmd === 'opacityInc' || cmd === 'opacityDec') adjustOpacityOnSelection(d);
    else if (cmd === 'cornerInc' || cmd === 'cornerDec') adjustCornerRadiusOnSelection(d);
    else if (cmd === 'widthInc' || cmd === 'widthDec') adjustSizeOnSelection('width', d);
    else if (cmd === 'heightInc' || cmd === 'heightDec') adjustSizeOnSelection('height', d);
    figma.closePlugin();
    return;
  }

  if (cmd === 'createMultipleComponents') {
    await createMultipleComponents(selection);
    figma.closePlugin();
    return;
  }
  if (cmd === 'alignHorizontalCenter' || cmd === 'alignVerticalCenter') {
    alignNodesToAxis(selection, cmd === 'alignHorizontalCenter' ? 'x' : 'y');
    figma.closePlugin();
    return;
  }
  if (cmd === 'splitTextLines') {
    await splitSelectedTextIntoLines(selection);
    figma.closePlugin();
    return;
  }
  if (cmd === 'createComponentSet') {
    await createComponentSetFromSelection(selection);
    figma.closePlugin();
    return;
  }
  if (cmd === 'wrapEachInAutoLayout') {
    const created = await wrapEachInAutoLayout(selection, 'HORIZONTAL');
    if (created.length) {
      figma.currentPage.selection = created;
      figma.notify(`Создано Auto Layout: ${created.length}`);
    } else {
      figma.notify('Нечего оборачивать в Auto Layout.');
    }
    figma.closePlugin();
    return;
  }

  // ═══════════════════════════════════════════════════════════════
  // Per-selection commands
  // ═══════════════════════════════════════════════════════════════
  for (const node of selection) {
    if (cmd === 'gapAuto') {
      if ("layoutMode" in node && (node.layoutMode === 'HORIZONTAL' || node.layoutMode === 'VERTICAL')) {
        node.primaryAxisAlignItems = 'SPACE_BETWEEN';
        node.itemSpacing = 0;
        figma.notify('Gap → Auto (SPACE_BETWEEN)');
      } else {
        figma.notify(`«${node.name}» не Auto Layout.`);
      }
    } else if (cmd === 'toggleTextResizing') {
      await toggleTextResizing(node);
    } else if (
      cmd === 'alignTopLeft' || cmd === 'alignTopCenter' || cmd === 'alignTopRight' ||
      cmd === 'alignCenterLeft' || cmd === 'alignCenter' || cmd === 'alignCenterRight' ||
      cmd === 'alignBottomLeft' || cmd === 'alignBottomCenter' || cmd === 'alignBottomRight'
    ) {
      applyAlignment(node, cmd);
    } else if ("layoutMode" in node && node.layoutMode !== 'NONE') {
      applySizingToContainerAndChildren(node, cmd);
    } else if ("layoutSizingHorizontal" in node || "layoutSizingVertical" in node) {
      applySizingToChild(node, cmd);
    } else {
      figma.notify(`«${node.name}» не Auto Layout.`);
    }
  }
  figma.closePlugin();
  })();
}


// ═══════════════════════════════════════════════════════════════
//  INPUT DIALOG HELPER
// ═══════════════════════════════════════════════════════════════

function openInputDialog(cmdName) {
  const title = cmdName === 'openPadXInput' ? 'Padding Horizontal (L+R)'
    : cmdName === 'openPadYInput' ? 'Padding Vertical (T+B)'
    : cmdName === 'openPadAllInput' ? 'Padding All (T+R+B+L)'
    : cmdName === 'openCornerInput' ? 'Corner Radius'
    : cmdName === 'openWidthInput' ? 'Width'
    : cmdName === 'openHeightInput' ? 'Height'
    : cmdName === 'openFontSizeInput' ? 'Font Size'
    : 'Gap (itemSpacing)';
  figma.showUI(`
    <style>
      body{font:12px/1.4 -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; margin:10px;}
      h3{margin:0 0 8px;font-size:12px}
      input{width:100%;box-sizing:border-box;padding:6px 8px;font-size:12px}
      .hint{color:#888;margin-top:6px}
    </style>
    <h3>${title}</h3>
    <input id="v" type="number" step="1" min="0" placeholder="Введите значение" autofocus />
    <div class="hint">Enter — применить, Esc — закрыть</div>
    <script>
      const el = document.getElementById('v');
      function focusInput(){ try{ window.focus(); el.focus(); el.select(); }catch(_){} }
      window.addEventListener('load', () => { focusInput(); setTimeout(focusInput, 0); });
      setTimeout(focusInput, 30);
      el.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          const val = parseInt(el.value, 10);
          if (!Number.isNaN(val)) {
            parent.postMessage({ pluginMessage: { type: 'set-single-input', target: '${cmdName}', value: val } }, '*');
            el.value = '';
          }
        }
        if (e.key === 'Escape') parent.postMessage({ pluginMessage: { type: 'close' } }, '*');
      });
    <\/script>
  `, { width: 260, height: 110 });

  figma.ui.onmessage = async (msg) => {
    if (msg && msg.type === 'close') { figma.closePlugin(); return; }
    if (msg && msg.type === 'set-single-input') {
      const v = Math.max(0, Math.round(msg.value || 0));
      if (msg.target === 'openPadXInput') setPaddingOnSelection('x', v);
      else if (msg.target === 'openPadYInput') setPaddingOnSelection('y', v);
      else if (msg.target === 'openPadAllInput') setPaddingOnSelection('all', v);
      else if (msg.target === 'openCornerInput') setCornerOnSelection(v);
      else if (msg.target === 'openGapInput') setGapOnSelection(v);
      else if (msg.target === 'openWidthInput') setSizeOnSelection('width', v);
      else if (msg.target === 'openHeightInput') setSizeOnSelection('height', v);
      else if (msg.target === 'openFontSizeInput') setFontSizeOnSelection(v);
      
      // Return to main WebSocket controller UI
      await showMainUI();
    }
  };
}

// ═══════════════════════════════════════════════════════════════
//  ENCODER → FIGMA ACTION (from WebSocket)
// ═══════════════════════════════════════════════════════════════

function handleEncoderAction(action, delta) {
  const sel = figma.currentPage.selection;
  if (!sel.length) {
    showToast("Выделите элемент");
    return;
  }

  switch (action) {
    case 'gap':
      adjustGapOnSelection(delta);
      break;
    case 'paddingX':
      adjustPaddingOnSelection(delta, 'x');
      break;
    case 'paddingY':
      adjustPaddingOnSelection(delta, 'y');
      break;
    case 'width':
      // delta already includes step & acceleration from agent
      for (const n of sel) {
        try {
          if (typeof n.resizeWithoutConstraints === 'function') {
            if ('layoutSizingHorizontal' in n && n.layoutSizingHorizontal !== 'FIXED') {
              try { n.layoutSizingHorizontal = 'FIXED'; } catch(_) {}
            }
            const next = Math.max(1, Math.round(n.width + delta));
            n.resizeWithoutConstraints(next, n.height);
          }
        } catch(_) {}
      }
      break;
    case 'height':
      for (const n of sel) {
        try {
          if (typeof n.resizeWithoutConstraints === 'function') {
            if ('layoutSizingVertical' in n && n.layoutSizingVertical !== 'FIXED') {
              try { n.layoutSizingVertical = 'FIXED'; } catch(_) {}
            }
            const next = Math.max(1, Math.round(n.height + delta));
            n.resizeWithoutConstraints(n.width, next);
          }
        } catch(_) {}
      }
      break;
    case 'fontSize':
      handleFontSizeDelta(sel, delta);
      break;
    case 'opacity':
      adjustOpacityOnSelection(delta > 0 ? 1 : -1);
      break;
    case 'cornerRadius':
      adjustCornerRadiusOnSelection(delta > 0 ? 1 : -1);
      break;
    case 'strokeWidth':
      adjustStrokeWidthOnSelection(delta);
      break;
    default:
      figma.notify(`Unknown action: ${action}`);
  }
}


// ═══════════════════════════════════════════════════════════════
//  COMMAND HANDLER (from WebSocket — buttons/joystick/matrix)
// ═══════════════════════════════════════════════════════════════

async function handleCommand(command) {
  const sel = figma.currentPage.selection;

  // Commands that don't need selection
  const noSelectionNeeded = ['openPadXInput','openPadYInput','openGapInput','openPadAllInput',
    'openCornerInput','openWidthInput','openHeightInput','openFontSizeInput'];

  if (!sel.length && !noSelectionNeeded.includes(command)) {
    figma.notify("Выделите элемент");
    return;
  }

  switch (command) {
    // Alignment
    case 'alignTopLeft': case 'alignTopCenter': case 'alignTopRight':
    case 'alignCenterLeft': case 'alignCenter': case 'alignCenterRight':
    case 'alignBottomLeft': case 'alignBottomCenter': case 'alignBottomRight':
      for (const n of sel) applyAlignment(n, command);
      break;

    // Auto Layout
    case 'toggleDirection':
      for (const n of sel) {
        if ("layoutMode" in n && n.layoutMode !== 'NONE') toggleDirection(n);
      }
      break;
    case 'gapAuto':
      for (const n of sel) {
        if ("layoutMode" in n && (n.layoutMode === 'HORIZONTAL' || n.layoutMode === 'VERTICAL')) {
          n.primaryAxisAlignItems = 'SPACE_BETWEEN';
          n.itemSpacing = 0;
        }
      }
      figma.notify('Gap → Auto');
      break;
    case 'hugContentWidth':
    case 'fillContentWidth':
    case 'fixedWidth':
    case 'hugContentHeight':
    case 'fillContentHeight':
    case 'fixedHeight':
      for (const n of sel) {
        if ("layoutMode" in n && n.layoutMode !== 'NONE') applySizingToContainerAndChildren(n, command);
        else if ("layoutSizingHorizontal" in n || "layoutSizingVertical" in n) applySizingToChild(n, command);
      }
      break;
    case 'wrapEachInAutoLayout':
      const created = await wrapEachInAutoLayout(sel, 'HORIZONTAL');
      if (created.length) {
        figma.currentPage.selection = created;
        figma.notify(`Auto Layout: ${created.length}`);
      }
      break;

    // Components
    case 'createMultipleComponents':
      await createMultipleComponents(sel);
      break;
    case 'createComponentSet':
      await createComponentSetFromSelection(sel);
      break;

    // Text
    case 'splitTextLines':
      await splitSelectedTextIntoLines(sel);
      break;
    case 'alignCenterText':
      await setTextAlign(sel, 'CENTER');
      break;
    case 'alignLeftText':
      await setTextAlign(sel, 'LEFT');
      break;

    // Input dialogs
    case 'openPadXInput': case 'openPadYInput': case 'openGapInput':
    case 'openPadAllInput': case 'openCornerInput':
    case 'openWidthInput': case 'openHeightInput': case 'openFontSizeInput':
      openInputDialog(command);
      break;

    default:
      figma.notify(`Unknown command: ${command}`);
  }
}


// ═══════════════════════════════════════════════════════════════
//  Font Size
// ═══════════════════════════════════════════════════════════════

async function handleFontSizeDelta(nodes, delta) {
  for (const n of nodes) {
    if (n.type !== 'TEXT') continue;
    try {
      const fonts = n.getRangeAllFontNames(0, n.characters.length);
      await Promise.all(fonts.map(f => figma.loadFontAsync(f)));
      const current = n.fontSize;
      if (typeof current === 'number') {
        n.fontSize = Math.max(1, current + delta);
      }
    } catch(_) {}
  }
}

async function setFontSizeOnSelection(value) {
  const sel = figma.currentPage.selection;
  for (const n of sel) {
    if (n.type !== 'TEXT') continue;
    try {
      const fonts = n.getRangeAllFontNames(0, n.characters.length);
      await Promise.all(fonts.map(f => figma.loadFontAsync(f)));
      n.fontSize = Math.max(1, value);
    } catch(_) {}
  }
  figma.notify(`Font Size = ${value}`);
}

async function setTextAlign(nodes, align) {
  for (const n of nodes) {
    if (n.type !== 'TEXT') continue;
    try {
      const fonts = n.getRangeAllFontNames(0, n.characters.length);
      await Promise.all(fonts.map(f => figma.loadFontAsync(f)));
      n.textAlignHorizontal = align;
    } catch(_) {}
  }
  figma.notify(`Text Align: ${align}`);
}


// ═══════════════════════════════════════════════════════════════
//  ALIGNMENT (unchanged from original)
// ═══════════════════════════════════════════════════════════════

function applyAlignment(node, cmd) {
  if (!("layoutMode" in node) || node.layoutMode === 'NONE') {
    figma.notify(`«${node.name}» не Auto Layout.`);
    return;
  }

  const mappingV = {
    alignTopLeft:      { p: 'MIN',    c: 'MIN' },
    alignTopCenter:    { p: 'MIN',    c: 'CENTER' },
    alignTopRight:     { p: 'MIN',    c: 'MAX' },
    alignCenterLeft:   { p: 'CENTER', c: 'MIN' },
    alignCenter:       { p: 'CENTER', c: 'CENTER' },
    alignCenterRight:  { p: 'CENTER', c: 'MAX' },
    alignBottomLeft:   { p: 'MAX',    c: 'MIN' },
    alignBottomCenter: { p: 'MAX',    c: 'CENTER' },
    alignBottomRight:  { p: 'MAX',    c: 'MAX' }
  };

  const mappingH = {
    alignTopLeft:      { p: 'MIN',    c: 'MIN' },
    alignTopCenter:    { p: 'CENTER', c: 'MIN' },
    alignTopRight:     { p: 'MAX',    c: 'MIN' },
    alignCenterLeft:   { p: 'MIN',    c: 'CENTER' },
    alignCenter:       { p: 'CENTER', c: 'CENTER' },
    alignCenterRight:  { p: 'MAX',    c: 'CENTER' },
    alignBottomLeft:   { p: 'MIN',    c: 'MAX' },
    alignBottomCenter: { p: 'CENTER', c: 'MAX' },
    alignBottomRight:  { p: 'MAX',    c: 'MAX' }
  };

  const map = node.layoutMode === 'HORIZONTAL' ? mappingH : mappingV;
  const target = map[cmd];
  if (!target) return;

  node.primaryAxisAlignItems = target.p;
  node.counterAxisAlignItems = target.c;
}


// ═══════════════════════════════════════════════════════════════
//  ALIGNMENT helpers (unchanged)
// ═══════════════════════════════════════════════════════════════

function alignNodesToAxis(nodes, axis) {
  const targets = nodes.filter(n => n && !n.removed && 'x' in n && 'y' in n);
  if (targets.length < 2) { figma.notify('Выберите минимум 2 слоя.'); return; }
  const parent = targets[0].parent;
  for (const n of targets) { if (n.parent !== parent) { figma.notify('Слои должны иметь одного родителя.'); return; } }
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const n of targets) {
    try {
      minX = Math.min(minX, n.x);
      minY = Math.min(minY, n.y);
      maxX = Math.max(maxX, n.x + (n.width || 0));
      maxY = Math.max(maxY, n.y + (n.height || 0));
    } catch(_) {}
  }
  const centerX = (minX + maxX) / 2;
  const centerY = (minY + maxY) / 2;
  for (const n of targets) {
    try {
      if (axis === 'x') n.x += (centerX - (n.x + n.width / 2));
      else n.y += (centerY - (n.y + n.height / 2));
    } catch(_) {}
  }
  figma.notify(axis === 'x' ? 'Aligned horizontally' : 'Aligned vertically');
}


// ═══════════════════════════════════════════════════════════════
//  PADDING / GAP / OPACITY / CORNER / SIZE (unchanged)
// ═══════════════════════════════════════════════════════════════

function adjustPaddingOnSelection(delta, scope = 'all') {
  if (!delta) return;
  const sel = figma.currentPage.selection;
  if (!sel.length) return;
  let changed = 0;
  for (const n of sel) {
    if ("layoutMode" in n && n.layoutMode !== 'NONE') {
      const sides = scope === 'x' ? ['paddingLeft','paddingRight']
        : scope === 'y' ? ['paddingTop','paddingBottom']
        : ['paddingLeft','paddingRight','paddingTop','paddingBottom'];
      for (const s of sides) {
        try {
          const curr = typeof n[s] === 'number' ? n[s] : 0;
          const baseStep = curr <= 10 ? 1 : 2;
          n[s] = Math.max(0, Math.round(curr + baseStep * delta));
        } catch (_) {}
      }
      changed++;
    }
  }
  if (changed) showToast(`Padding ${delta > 0 ? '+' : ''}${delta} (${changed})`);
}

function adjustGapOnSelection(delta) {
  if (!delta) return;
  const sel = figma.currentPage.selection;
  if (!sel.length) return;
  let changed = 0;
  const values = [];
  for (const n of sel) {
    if ("layoutMode" in n && n.layoutMode !== 'NONE') {
      try {
        const curr = typeof n.itemSpacing === 'number' ? n.itemSpacing : 0;
        n.itemSpacing = Math.max(0, Math.round(curr + delta));
        if (n.primaryAxisAlignItems === 'SPACE_BETWEEN' && n.itemSpacing > 0) {
          n.primaryAxisAlignItems = 'MIN';
        }
        values.push(n.itemSpacing);
        changed++;
      } catch (_) {}
    }
  }
  if (changed) {
    const unique = Array.from(new Set(values));
    if (unique.length === 1) {
      showToast(`Gap ${unique[0]}`);
    } else {
      showToast(`Gap mixed (${changed})`);
    }
  }
}

function adjustOpacityOnSelection(direction) {
  const step = 0.05 * direction;
  const sel = figma.currentPage.selection;
  if (!sel.length) return;
  for (const n of sel) {
    try {
      if ('opacity' in n && typeof n.opacity === 'number') {
        n.opacity = Math.min(1, Math.max(0, Math.round((n.opacity + step) * 100) / 100));
      }
    } catch (_) {}
  }
}

function adjustCornerRadiusOnSelection(direction) {
  const sel = figma.currentPage.selection;
  if (!sel.length) return;
  for (const n of sel) {
    try {
      if ('cornerRadius' in n) {
        const curr = typeof n.cornerRadius === 'number' ? n.cornerRadius : 0;
        const base = curr <= 10 ? 1 : 2;
        n.cornerRadius = Math.max(0, Math.round(curr + base * direction));
      }
    } catch (_) {}
  }
}

function adjustStrokeWidthOnSelection(delta) {
  if (!delta) return;
  const sel = figma.currentPage.selection;
  if (!sel.length) return;

  for (const n of sel) {
    try {
      if ('strokeWeight' in n && typeof n.strokeWeight === 'number') {
        n.strokeWeight = Math.max(0, Math.round((n.strokeWeight + delta) * 10) / 10);
        continue;
      }

      // Fallback for nodes with per-side stroke weights.
      const sideKeys = ['strokeTopWeight', 'strokeRightWeight', 'strokeBottomWeight', 'strokeLeftWeight'];
      for (const key of sideKeys) {
        if (key in n && typeof n[key] === 'number') {
          n[key] = Math.max(0, Math.round((n[key] + delta) * 10) / 10);
        }
      }
    } catch (_) {}
  }
}

function adjustSizeOnSelection(axis, direction) {
  const sel = figma.currentPage.selection;
  if (!sel.length) return;
  for (const n of sel) {
    try {
      if (typeof n.resizeWithoutConstraints !== 'function') continue;
      if (axis === 'width' && 'layoutSizingHorizontal' in n && n.layoutSizingHorizontal !== 'FIXED') {
        try { n.layoutSizingHorizontal = 'FIXED'; } catch(_) {}
      }
      if (axis === 'height' && 'layoutSizingVertical' in n && n.layoutSizingVertical !== 'FIXED') {
        try { n.layoutSizingVertical = 'FIXED'; } catch(_) {}
      }
      const curr = Math.round(axis === 'width' ? n.width : n.height);
      const base = curr <= 20 ? 2 : 4;
      const next = Math.max(0, curr + base * direction);
      if (axis === 'width') n.resizeWithoutConstraints(next, n.height);
      else n.resizeWithoutConstraints(n.width, next);
    } catch (_) {}
  }
}

function setPaddingOnSelection(scope, value) {
  const v = Math.max(0, Math.round(value));
  const sel = figma.currentPage.selection;
  if (!sel.length) return;
  for (const n of sel) {
    if ("layoutMode" in n && n.layoutMode !== 'NONE') {
      try {
        if (scope === 'x') { n.paddingLeft = v; n.paddingRight = v; }
        else if (scope === 'y') { n.paddingTop = v; n.paddingBottom = v; }
        else { n.paddingLeft = v; n.paddingRight = v; n.paddingTop = v; n.paddingBottom = v; }
      } catch (_) {}
    }
  }
}

function setGapOnSelection(value) {
  const sel = figma.currentPage.selection;
  for (const n of sel) {
    if ("layoutMode" in n && n.layoutMode !== 'NONE') {
      try { n.itemSpacing = value; } catch (_) {}
    }
  }
}

function setCornerOnSelection(value) {
  const v = Math.max(0, Math.round(value));
  const sel = figma.currentPage.selection;
  for (const n of sel) {
    try { if ('cornerRadius' in n) n.cornerRadius = v; } catch (_) {}
  }
}

function setSizeOnSelection(axis, value) {
  const v = Math.max(0, Math.round(value));
  const sel = figma.currentPage.selection;
  for (const n of sel) {
    try {
      if (typeof n.resizeWithoutConstraints === 'function') {
        if (axis === 'width' && 'layoutSizingHorizontal' in n && n.layoutSizingHorizontal !== 'FIXED')
          try { n.layoutSizingHorizontal = 'FIXED'; } catch(_) {}
        if (axis === 'height' && 'layoutSizingVertical' in n && n.layoutSizingVertical !== 'FIXED')
          try { n.layoutSizingVertical = 'FIXED'; } catch(_) {}
        if (axis === 'width') n.resizeWithoutConstraints(v, n.height);
        else n.resizeWithoutConstraints(n.width, v);
      }
    } catch (_) {}
  }
}


// ═══════════════════════════════════════════════════════════════
//  AUTO LAYOUT helpers (unchanged)
// ═══════════════════════════════════════════════════════════════

function applySizingToContainerAndChildren(node, cmd) {
  const childrenSizes = node.children.map(c => ({
    c, h: c.layoutSizingHorizontal, v: c.layoutSizingVertical
  }));
  switch (cmd) {
    case 'toggleDirection': toggleDirection(node); break;
    case 'fillContentWidth': node.layoutSizingHorizontal = 'FILL'; setChildSizing(node, 'horizontal', 'FILL'); break;
    case 'hugContentWidth': node.layoutSizingHorizontal = 'HUG'; setChildSizing(node, 'horizontal', 'HUG'); break;
    case 'fixedWidth': node.layoutSizingHorizontal = 'FIXED'; setChildSizing(node, 'horizontal', 'FIXED'); break;
    case 'fillContentHeight': node.layoutSizingVertical = 'FILL'; setChildSizing(node, 'vertical', 'FILL'); break;
    case 'hugContentHeight': node.layoutSizingVertical = 'HUG'; setChildSizing(node, 'vertical', 'HUG'); break;
    case 'fixedHeight': node.layoutSizingVertical = 'FIXED'; setChildSizing(node, 'vertical', 'FIXED'); break;
  }
  for (const { c, h, v } of childrenSizes) {
    if (c.removed) continue;
    if (h) c.layoutSizingHorizontal = h;
    if (v) c.layoutSizingVertical = v;
  }
}

function applySizingToChild(node, cmd) {
  switch (cmd) {
    case 'fillContentWidth': node.layoutSizingHorizontal = 'FILL'; break;
    case 'fixedWidth': node.layoutSizingHorizontal = 'FIXED'; break;
    case 'fillContentHeight': node.layoutSizingVertical = 'FILL'; break;
    case 'fixedHeight': node.layoutSizingVertical = 'FIXED'; break;
  }
}

function setChildSizing(node, axis, mode) {
  for (const c of node.children) {
    if (axis === 'horizontal' && 'layoutSizingHorizontal' in c) c.layoutSizingHorizontal = mode;
    if (axis === 'vertical' && 'layoutSizingVertical' in c) c.layoutSizingVertical = mode;
  }
}

function toggleDirection(node) {
  const prev = node.layoutMode;
  node.layoutMode = prev === "HORIZONTAL" ? "VERTICAL" : "HORIZONTAL";
  const ps = node.primaryAxisSizingMode;
  const cs = node.counterAxisSizingMode;
  node.primaryAxisSizingMode = cs;
  node.counterAxisSizingMode = ps;
}


// ═══════════════════════════════════════════════════════════════
//  TEXT / COMPONENTS / MISC (unchanged)
// ═══════════════════════════════════════════════════════════════

async function toggleTextResizing(node) {
  if (node.type !== "TEXT") return;
  const fonts = node.getRangeAllFontNames(0, node.characters.length);
  await Promise.all(fonts.map(f => figma.loadFontAsync(f)));
  node.textAutoResize = "WIDTH_AND_HEIGHT";
}

async function createMultipleComponents(nodes) {
  const result = [];
  for (let n of nodes) {
    try {
      if (!n || n.removed) continue;
      if (n.type === 'PAGE' || n.type === 'SECTION' || n.type === 'SLICE' || n.type === 'COMPONENT_SET') continue;
      if (n.type === 'COMPONENT') { result.push(n); continue; }
      if (n.type === 'INSTANCE') { n = n.detachInstance(); if (!n) continue; }
      let comp = null;
      if (typeof figma.createComponentFromNodeAsync === 'function') {
        comp = await figma.createComponentFromNodeAsync(n);
      } else {
        const parent = n.parent;
        const idx = parent ? parent.children.indexOf(n) : -1;
        const manual = figma.createComponent();
        try { manual.fills = []; } catch (_) {}
        manual.name = n.name || 'Component';
        if (parent && idx >= 0) parent.insertChild(idx, manual);
        manual.x = n.x; manual.y = n.y;
        manual.resizeWithoutConstraints(Math.max(1, n.width), Math.max(1, n.height));
        manual.appendChild(n);
        try { n.x = 0; n.y = 0; } catch(_) {}
        comp = manual;
      }
      if (comp) result.push(comp);
    } catch (_) {}
  }
  if (result.length) figma.notify(`Компонентов: ${result.length}`);
  return result;
}

async function createComponentSetFromSelection(nodes) {
  let components = nodes.filter(n => n && !n.removed && n.type === 'COMPONENT');
  if (!components.length) components = await createMultipleComponents(nodes);
  components = components.filter(n => n && !n.removed && n.type === 'COMPONENT');
  if (components.length < 2) { figma.notify('Нужно минимум 2 компонента.'); return null; }
  try {
    const set = figma.combineAsVariants(components, components[0].parent);
    figma.notify('Component Set создан');
    return set;
  } catch (e) { figma.notify('Не удалось создать Component Set.'); return null; }
}

async function wrapEachInAutoLayout(nodes, mode = 'HORIZONTAL') {
  const wrappers = [];
  for (const n of nodes) {
    try {
      if (!n || n.removed || !n.parent) continue;
      const parent = n.parent;
      const idx = parent.children.indexOf(n);
      const wrapper = figma.createFrame();
      try { wrapper.fills = []; } catch (_) {}
      try { wrapper.clipsContent = false; } catch (_) {}
      wrapper.name = `${n.name || 'Node'} • AL`;
      parent.insertChild(idx, wrapper);
      wrapper.x = n.x; wrapper.y = n.y;
      wrapper.layoutMode = mode;
      wrapper.primaryAxisSizingMode = 'AUTO';
      wrapper.counterAxisSizingMode = 'AUTO';
      wrapper.itemSpacing = 0;
      wrapper.paddingLeft = wrapper.paddingRight = wrapper.paddingTop = wrapper.paddingBottom = 0;
      if ('layoutSizingHorizontal' in n) n.layoutSizingHorizontal = 'FIXED';
      if ('layoutSizingVertical' in n) n.layoutSizingVertical = 'FIXED';
      wrapper.appendChild(n);
      try { n.x = 0; n.y = 0; } catch (_) {}
      try { wrapper.resizeWithoutConstraints(Math.max(1, n.width), Math.max(1, n.height)); } catch(_) {}
      wrappers.push(wrapper);
    } catch (_) {}
  }
  return wrappers;
}

async function splitSelectedTextIntoLines(nodes) {
  const textNodes = nodes.filter(n => n.type === 'TEXT');
  if (!textNodes.length) { figma.notify('Выберите текстовый слой.'); return; }
  let processed = 0;
  for (const original of textNodes) {
    try {
      const full = original.characters;
      const lines = full.split(/\r?\n/);
      if (lines.length <= 1) continue;

      // Collect font runs
      function collectRuns(node, text) {
        const runs = [];
        let pos = 0;
        while (pos < text.length) {
          let fontName, fontSize;
          try { fontName = node.getRangeFontName(pos, pos+1); } catch(_) {}
          try { fontSize = node.getRangeFontSize(pos, pos+1); } catch(_) {}
          let end = pos + 1;
          while (end < text.length) {
            let same = true;
            try {
              if (JSON.stringify(node.getRangeFontName(end, end+1)) !== JSON.stringify(fontName)) same = false;
              else if (node.getRangeFontSize(end, end+1) !== fontSize) same = false;
            } catch(_) { same = false; }
            if (!same) break; else end++;
          }
          runs.push({ start: pos, end, fontName, fontSize });
          pos = end;
        }
        return runs;
      }

      const styleRuns = collectRuns(original, full);
      const distinctFonts = [];
      const seenFonts = {};
      for (const r of styleRuns) {
        if (r.fontName) {
          const key = JSON.stringify(r.fontName);
          if (!seenFonts[key]) { seenFonts[key] = true; distinctFonts.push(r.fontName); }
        }
      }
      for (const f of distinctFonts) { try { await figma.loadFontAsync(f); } catch(_) {} }

      const parent = original.parent;
      if (!parent) continue;
      const baseX = original.x;
      const baseY = original.y;
      const spacing = 4;
      let yOffset = 0;
      const cumulative = [];
      let acc = 0;
      for (let i = 0; i < lines.length; i++) { cumulative.push(acc); acc += lines[i].length + 1; }

      for (let li = 0; li < lines.length; li++) {
        const lineText = lines[li];
        const t = figma.createText();
        parent.appendChild(t);
        t.x = baseX; t.y = baseY + yOffset;
        try { t.characters = lineText || ' '; } catch(_) {}
        const lineStart = cumulative[li];
        const lineEnd = lineStart + lineText.length;
        for (const run of styleRuns) {
          const os = run.start < lineEnd && run.end > lineStart ? Math.max(run.start, lineStart) : null;
          if (os === null) continue;
          const oe = Math.min(run.end, lineEnd);
          let ls = os - lineStart, le = oe - lineStart;
          if (ls < 0) ls = 0; if (le > t.characters.length) le = t.characters.length;
          if (ls >= le) continue;
          try { if (run.fontName) t.setRangeFontName(ls, le, run.fontName); } catch(_) {}
          try { if (typeof run.fontSize === 'number') t.setRangeFontSize(ls, le, run.fontSize); } catch(_) {}
        }
        try { yOffset += t.height + spacing; } catch(_) { yOffset += 16 + spacing; }
      }
      try { original.remove(); } catch(_) {}
      processed++;
    } catch (_) {}
  }
  if (processed) figma.notify(`Разбито: ${processed}`);
}
