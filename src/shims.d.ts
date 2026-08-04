// 零运行时依赖硬约束：不安装 @types/node，这里声明引擎所需的最小 node 内置模块类型。
// 引擎只允许使用 node:fs / node:path / node:crypto（结算随机走 rng.ts，不用 crypto）；
// 测试额外使用 node:test 与 node:assert/strict（均为 node 内置）。

declare module 'node:fs' {
  export function readFileSync(path: string, options: { encoding: 'utf8' } | 'utf8'): string;
  export function writeFileSync(path: string, data: string): void;
  export function appendFileSync(path: string, data: string): void;
  export function renameSync(oldPath: string, newPath: string): void;
  export function mkdirSync(path: string, options?: { recursive?: boolean }): string | undefined;
  export function existsSync(path: string): boolean;
  export function rmSync(path: string, options?: { recursive?: boolean; force?: boolean }): void;
}

declare module 'node:path' {
  export function join(...segments: string[]): string;
  export function dirname(p: string): string;
  export function resolve(...segments: string[]): string;
}

declare module 'node:crypto' {
  export function randomUUID(): string;
  export interface Hash {
    update(data: string): Hash;
    digest(encoding: 'hex'): string;
  }
  /** 仅用于 CLI 默认种子的确定性派生（sha256），不参与任何结算随机（结算走 rng.ts）。 */
  export function createHash(algorithm: string): Hash;
}

declare module 'node:url' {
  export function pathToFileURL(p: string): { href: string };
}

/** CLI 所需最小全局对象（types:[] 下无 node 全局类型）。 */
declare const process: {
  argv: string[];
  exitCode: number | undefined;
  env: Record<string, string | undefined>;
};
declare const console: {
  log(...args: unknown[]): void;
  error(...args: unknown[]): void;
};

/** ESM 模块元信息（cli.ts 主入口判定用）。 */
interface ImportMeta {
  url: string;
}

declare module 'node:test' {
  export function test(name: string, fn: () => void | Promise<void>): void;
  export function before(fn: () => void | Promise<void>): void;
  export function after(fn: () => void | Promise<void>): void;
}

declare module 'node:assert/strict' {
  export function ok(value: unknown, message?: string): void;
  export function equal(actual: unknown, expected: unknown, message?: string): void;
  export function notEqual(actual: unknown, expected: unknown, message?: string): void;
  export function deepStrictEqual(actual: unknown, expected: unknown, message?: string): void;
}
