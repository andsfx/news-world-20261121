// A verified news front page for Saturday 21 November 2026.
// Node 22, standard library only. The committed entry.png is the entry.
// Inside the grader this writes /output/entry.png; MAKEFUN_OUTPUT_DIR stands in for it locally.

import { copyFileSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';

const output = process.env.MAKEFUN_OUTPUT_DIR ?? '/output';
mkdirSync(output, { recursive: true });
copyFileSync(new URL('./entry.png', import.meta.url), join(output, 'entry.png'));
