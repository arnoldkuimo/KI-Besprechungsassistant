import { startVitest } from 'vitest/node';

const runner = await startVitest('test', [], {
  config: false,
  run: true,
  pool: 'threads',
  poolOptions: { threads: { singleThread: true } },
});
if (!runner) process.exitCode = 1;
else await runner.close();
