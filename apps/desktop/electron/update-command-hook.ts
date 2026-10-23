import fs from 'node:fs'
import path from 'node:path'
import { execFile } from 'node:child_process'
import { promisify } from 'node:util'

const execute = promisify(execFile)

/** Full update handoff: configured handlers never authorize a second native update. */
export async function runUpdateCommandHook(installRoot: string, home: string, branch: string): Promise<boolean> {
  const configPath = path.join(home, 'update-gate.json')
  const stat = fs.lstatSync(configPath, { throwIfNoEntry: false })
  if (!stat) return false
  if (!stat.isFile() || stat.isSymbolicLink() || stat.size > 65536) throw new Error('Invalid update hook configuration')
  try {
    const config = JSON.parse(fs.readFileSync(configPath, 'utf8'))
    const argv = config.argv
    if (
      Object.keys(config).length !== 1 ||
      !Array.isArray(argv) ||
      !argv.length ||
      !argv.every((v: unknown) => typeof v === 'string' && v.length > 0 && !v.includes('\0')) ||
      !path.isAbsolute(argv[0])
    )
      throw new Error('Invalid argv')
    const { stdout } = await execute(
      argv[0],
      [
        ...argv.slice(1),
        '--install-root',
        path.resolve(installRoot),
        '--home',
        path.resolve(home),
        '--branch',
        branch,
        '--surface',
        'desktop'
      ],
      { cwd: installRoot, timeout: 1_800_000, maxBuffer: 1048576, shell: false }
    )
    const reply = JSON.parse(stdout)
    if (!reply || reply.ok !== true || reply.handled !== true) throw new Error('Refused')
    return true
  } catch {
    throw new Error('Configured update handler refused; native updater was not invoked')
  }
}
