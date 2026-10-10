// On-screen PC keyboard for touch screens. Each key is delivered exactly as the physical PC key
// would be (through biosKey), so the program sees the same characters and scan codes.
import { biosKey } from './runtime.js';

// [code, label or [normal, shifted], width]
const ROWS = [
  [['Escape', 'Esc', 1.5], ['F1', 'F1 Sound', 2], ['F2', 'F2 Save/Load', 2.5], null, ['Backspace', '← Bksp', 2]],
  [['Digit1', ['1', '!']], ['Digit2', ['2', '@']], ['Digit3', ['3', '#']], ['Digit4', ['4', '$']],
    ['Digit5', ['5', '%']], ['Digit6', ['6', '^']], ['Digit7', ['7', '&']], ['Digit8', ['8', '*']],
    ['Digit9', ['9', '(']], ['Digit0', ['0', ')']], ['Minus', ['-', '_']], ['Equal', ['=', '+']]],
  [...'qwertyuiop'.split('').map((c) => ['Key' + c.toUpperCase(), [c, c.toUpperCase()]]), ['Backslash', ['\\', '|']]],
  [...'asdfghjkl'.split('').map((c) => ['Key' + c.toUpperCase(), [c, c.toUpperCase()]]),
    ['Semicolon', [';', ':']], ['Quote', ["'", '"']]],
  [['Shift', 'Shift', 1.5], ...'zxcvbnm'.split('').map((c) => ['Key' + c.toUpperCase(), [c, c.toUpperCase()]]),
    ['Comma', [',', '<']], ['Period', ['.', '>']], ['Slash', ['/', '?']]],
  [['CapsLock', 'Caps', 1.5], ['Space', 'Space', 6], ['Enter', 'Enter ↵', 3]],
];
const NAMED = { Escape: 'Escape', F1: 'F1', F2: 'F2', Backspace: 'Backspace', Space: ' ', Enter: 'Enter' };

export function createKeyboard(container, onKey) {
  let shift = false, caps = false;
  const keys = [];
  for (const row of ROWS) {
    const r = document.createElement('div'); r.className = 'krow';
    for (const k of row) {
      if (!k) { const s = document.createElement('span'); s.className = 'kgap'; r.appendChild(s); continue; }
      const [code, label, w = 1] = k;
      const b = document.createElement('button'); b.type = 'button'; b.className = 'key'; b.tabIndex = -1;
      b.style.flexGrow = w; b.dataset.code = code;
      r.appendChild(b); keys.push({ b, code, label });
    }
    container.appendChild(r);
  }
  const isLetter = (code) => code.startsWith('Key');
  // A letter is upper case with Shift or Caps Lock (not both), other characters with Shift only, as on a PC.
  const upper = (code) => (isLetter(code) ? shift !== caps : shift);
  function paint() {
    for (const { b, code, label } of keys) {
      b.textContent = Array.isArray(label) ? label[upper(code) ? 1 : 0] : label;
      b.classList.toggle('on', (code === 'Shift' && shift) || (code === 'CapsLock' && caps));
    }
  }
  container.addEventListener('pointerdown', (e) => {
    const b = e.target.closest('.key'); if (!b) return;
    e.preventDefault();
    const { code, label } = keys.find((k) => k.b === b);
    if (code === 'Shift') shift = !shift;
    else if (code === 'CapsLock') caps = !caps;
    else {
      const key = Array.isArray(label) ? label[upper(code) ? 1 : 0] : NAMED[code];
      const k = biosKey({ code, key, shiftKey: shift, ctrlKey: false, altKey: false });
      if (k) onKey(k);
      shift = false;
    }
    paint();
  });
  container.addEventListener('contextmenu', (e) => e.preventDefault());
  paint();
}
