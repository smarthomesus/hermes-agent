import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const execute = vi.hoisted(() => vi.fn())
vi.mock('node:util', () => ({ promisify: () => execute }))
import { runUpdateCommandHook } from './update-command-hook'

let home: string
beforeEach(() => {
  home = fs.mkdtempSync(path.join(os.tmpdir(), 'update-hook-'))
  execute.mockReset()
})
afterEach(() => fs.rmSync(home, { recursive: true, force: true }))
const write = (value: unknown) => fs.writeFileSync(path.join(home, 'update-gate.json'), JSON.stringify(value))

describe('operator-owned update command', () => {
  it('retains the native path only when no handler is configured', async () => {
    expect(await runUpdateCommandHook(home, home, 'main')).toBe(false)
    expect(execute).not.toHaveBeenCalled()
  })
  it('hands off the full update with shell-free argv', async () => {
    write({ argv: ['/operator/update', 'fixed-argument'] })
    execute.mockResolvedValue({ stdout: '{"ok":true,"handled":true}' })
    expect(await runUpdateCommandHook(home, home, 'main')).toBe(true)
    expect(execute).toHaveBeenCalledWith(
      '/operator/update',
      ['fixed-argument', '--install-root', home, '--home', home, '--branch', 'main', '--surface', 'desktop'],
      expect.objectContaining({ shell: false, cwd: home })
    )
  })
  it.each([
    { argv: ['relative-command'] },
    { argv: [] },
    { argv: ['/operator/update'], extra: true },
    { argv: ['/operator/update', '\0'] }
  ])('refuses malformed configuration without a native fallback: %j', async config => {
    write(config)
    await expect(runUpdateCommandHook(home, home, 'main')).rejects.toThrow()
    expect(execute).not.toHaveBeenCalled()
  })
  it.each(['{"ok":false}', '{"ok":true}', 'invalid-json'])('refuses an unhandled result: %s', async stdout => {
    write({ argv: ['/operator/update'] })
    execute.mockResolvedValue({ stdout })
    await expect(runUpdateCommandHook(home, home, 'main')).rejects.toThrow('native updater was not invoked')
    expect(execute).toHaveBeenCalledTimes(1)
  })
  it('does not fall back after a timeout or command failure', async () => {
    write({ argv: ['/operator/update'] })
    execute.mockRejectedValue(new Error('timeout'))
    await expect(runUpdateCommandHook(home, home, 'main')).rejects.toThrow('native updater was not invoked')
    expect(execute).toHaveBeenCalledTimes(1)
  })
  it('refuses symlink configuration', async () => {
    const target = path.join(home, 'target.json')
    fs.writeFileSync(target, '{"argv":["/operator/update"]}')
    fs.symlinkSync(target, path.join(home, 'update-gate.json'))
    await expect(runUpdateCommandHook(home, home, 'main')).rejects.toThrow()
    expect(execute).not.toHaveBeenCalled()
  })
})
