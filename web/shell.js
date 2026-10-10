// Runs the loader (MONOPOLY.COM) and, after Chain, the game (MONOCODE.CHN) on one runtime,
// like DOS would: the screen, window, colours and memory carry over the chain.
import { ChainSignal, HaltSignal, RuntimeErrorSignal } from './runtime.js';
import { RunError } from './pasrt.js';

const PROGRAMS = { 'MONOPOLY.COM': 'loader', 'MONOCODE.CHN': 'game' };

export async function runPrograms(R, loadModule, first = 'MONOPOLY.COM') {
  let prog = first;
  for (;;) {
    const mod = await loadModule(PROGRAMS[prog]);
    R.program = PROGRAMS[prog];
    R.programStart();
    try {
      await mod.main(R);
      return { kind: 'end' };                     // reached 'end.' of the main program
    } catch (e) {
      if (e instanceof ChainSignal) {
        if (!PROGRAMS[e.file]) return { kind: 'error', text: 'cannot chain to ' + e.file };
        prog = e.file; continue;
      }
      if (e instanceof HaltSignal) return { kind: 'halt' };
      if (e instanceof RuntimeErrorSignal) return { kind: 'error', text: e.text };
      if (e instanceof RunError) { const s = R.reportError(e); return { kind: 'error', text: s ? s.text : '' }; }
      throw e;
    }
  }
}
