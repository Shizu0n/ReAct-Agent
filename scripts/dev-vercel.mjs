import { spawn, spawnSync } from 'node:child_process'
import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import net from 'node:net'
import { join } from 'node:path'

const env = { ...process.env }
delete env.VIRTUAL_ENV
delete env.PYTHONHOME
delete env.PYTHONPATH

const isWindows = process.platform === 'win32'
const command = process.platform === 'win32' ? 'npx.cmd' : 'npx'
const forwardedArgs = process.argv.slice(2).filter((arg) => arg !== '--skip-build')
const args = ['vercel', 'dev', ...forwardedArgs]
const defaultListen = '127.0.0.1:3000'
let listenTarget = readListenTarget(args)
if (!listenTarget) {
  listenTarget = defaultListen
  args.push('--listen', listenTarget)
}

const endpoint = parseListenTarget(listenTarget)
if (endpoint && !(await canBind(endpoint.host, endpoint.port))) {
  console.error(
    [
      `[dev:vercel] ${endpoint.host}:${endpoint.port} is already in use.`,
      'Stop the old local Vercel process first:',
      '  npm run dev:vercel:stop',
    ].join('\n'),
  )
  process.exit(1)
}

if (!process.argv.includes('--skip-build')) {
  const npmCommand = process.platform === 'win32' ? 'npm.cmd' : 'npm'
  const build = spawnSync(npmCommand, ['--prefix', 'frontend', 'run', 'build'], {
    env: process.env,
    stdio: 'inherit',
    shell: isWindows,
  })

  if (build.status !== 0) {
    process.exit(build.status ?? 1)
  }
}

if (shouldUseDirectUvicorn()) {
  startUvicornFallback(endpoint, 'Git Bash/MINGW detected; skipping @vercel/python local dev')
} else {
  startVercelDev()
}

function readListenTarget(argv) {
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index]
    if (arg === '--listen') return argv[index + 1]
    if (arg.startsWith('--listen=')) return arg.slice('--listen='.length)
  }
  return null
}

function patchVercelPythonDevRuntime() {
  const runtimePath = join('.vercel', 'python', 'vercel_runtime', 'dev.py')
  if (!existsSync(runtimePath)) return

  const original = readFileSync(runtimePath, 'utf8')
  const patched = original
    .replace('run_simple(host, port, wsgi_app, use_reloader=True, threaded=True)', 'run_simple(host, port, wsgi_app, use_reloader=False, threaded=True)')
    .replaceAll('reload=True,', 'reload=False,')

  if (patched !== original) {
    writeFileSync(runtimePath, patched)
  }
}

function startVercelDev() {
  patchVercelPythonDevRuntime()

  const child = spawn(command, args, {
    env,
    stdio: 'inherit',
    shell: isWindows,
  })

  let childExited = false
  let fallbackStarted = false
  const childStartedAt = Date.now()

  if (endpoint) {
    void monitorVercelHealth(child, endpoint, () => childExited, () => fallbackStarted, () => {
      fallbackStarted = true
    })
  }

  child.on('exit', (code, signal) => {
    childExited = true
    if (fallbackStarted) return

    if (signal) {
      process.kill(process.pid, signal)
      return
    }

    const elapsedMs = Date.now() - childStartedAt
    if (code && shouldFallbackToUvicorn(code, elapsedMs)) {
      fallbackStarted = true
      startUvicornFallback(endpoint, `Vercel Python dev server exited with code ${code}`)
      return
    }

    process.exit(code ?? 1)
  })
}

async function monitorVercelHealth(processHandle, listenEndpoint, hasExited, hasFallback, markFallback) {
  const timeoutMs = Number.parseInt(process.env.VERCEL_DEV_HEALTH_TIMEOUT_MS ?? '30000', 10)
  const deadline = Date.now() + timeoutMs

  while (Date.now() < deadline) {
    if (hasExited() || hasFallback()) return
    if (await isHealthy(listenEndpoint)) return
    await sleep(1000)
  }

  if (hasExited() || hasFallback()) return

  markFallback()
  console.warn(
    [
      `[dev:vercel] /api/health did not become healthy after ${timeoutMs}ms.`,
      '[dev:vercel] Stopping the Vercel dev process and starting FastAPI directly.',
    ].join('\n'),
  )
  stopProcessTree(processHandle.pid)
  startUvicornFallback(listenEndpoint, 'Vercel local proxy did not bind a healthy Python runtime')
}

async function isHealthy(listenEndpoint) {
  try {
    const response = await fetch(`http://${listenEndpoint.host}:${listenEndpoint.port}/api/health`, {
      signal: AbortSignal.timeout(1500),
    })
    return response.ok
  } catch {
    return false
  }
}

function shouldFallbackToUvicorn(code, elapsedMs) {
  if (process.env.VERCEL_DEV_NO_UVICORN_FALLBACK === '1') return false
  return elapsedMs < 90000 && code !== 0
}

function shouldUseDirectUvicorn() {
  if (process.env.VERCEL_DEV_FORCE_VERCEL === '1') return false
  if (process.env.VERCEL_DEV_FORCE_UVICORN === '1') return true
  return process.platform === 'win32' && Boolean(process.env.MSYSTEM)
}

function startUvicornFallback(listenEndpoint, reason) {
  const target = listenEndpoint ?? parseListenTarget(defaultListen)
  const python = localPythonExecutable()

  console.warn(`[dev:vercel] ${reason}.`)
  console.warn('[dev:vercel] Fallback: serving api.index:app with uvicorn.')

  const fallback = spawn(
    python,
    ['-m', 'uvicorn', 'api.index:app', '--host', target.host, '--port', String(target.port)],
    {
      env: process.env,
      stdio: 'inherit',
      shell: false,
    },
  )

  fallback.on('exit', (code, signal) => {
    if (signal) {
      process.kill(process.pid, signal)
      return
    }
    process.exit(code ?? 1)
  })
}

function localPythonExecutable() {
  const windowsPython = join('.venv', 'Scripts', 'python.exe')
  const posixPython = join('.venv', 'bin', 'python')

  if (existsSync(windowsPython)) return windowsPython
  if (existsSync(posixPython)) return posixPython
  return process.platform === 'win32' ? 'python.exe' : 'python'
}

function stopProcessTree(pid) {
  if (!pid) return
  if (process.platform === 'win32') {
    spawnSync('taskkill.exe', ['/PID', String(pid), '/T', '/F'], { stdio: 'ignore' })
    return
  }
  try {
    process.kill(pid, 'SIGTERM')
  } catch {
    // Process already exited.
  }
}

function sleep(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms)
  })
}

function parseListenTarget(value) {
  if (!value) return null

  const target = String(value).trim()
  const portOnly = Number.parseInt(target, 10)
  if (String(portOnly) === target) {
    return { host: '127.0.0.1', port: portOnly }
  }

  const match = target.match(/^(.+):(\d+)$/)
  if (!match) return null

  return { host: match[1], port: Number.parseInt(match[2], 10) }
}

function canBind(host, port) {
  return new Promise((resolve, reject) => {
    const server = net.createServer()

    server.once('error', (error) => {
      if (error.code === 'EADDRINUSE') {
        resolve(false)
        return
      }
      reject(error)
    })

    server.once('listening', () => {
      server.close(() => resolve(true))
    })

    server.listen(port, host)
  })
}
