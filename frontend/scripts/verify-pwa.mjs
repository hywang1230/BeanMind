import { access, readFile } from 'node:fs/promises'
import { resolve } from 'node:path'

const dist = resolve(import.meta.dirname, '..', 'dist')
const manifest = JSON.parse(await readFile(resolve(dist, 'manifest.webmanifest'), 'utf8'))
const serviceWorker = await readFile(resolve(dist, 'sw.js'), 'utf8')

function assert(condition, message) {
  if (!condition) throw new Error(message)
}

assert(manifest.name === 'BeanMind', 'Manifest 缺少应用名称')
assert(manifest.lang === 'zh-CN', 'Manifest 语言必须为 zh-CN')
assert(manifest.display === 'standalone', 'Manifest 必须使用 standalone 显示模式')
assert(manifest.start_url === '/', 'Manifest start_url 必须为 /')

const requiredIcons = new Map([
  ['192x192', 'pwa-192x192.png'],
  ['512x512', 'pwa-512x512.png'],
])
for (const [sizes, source] of requiredIcons) {
  const icon = manifest.icons?.find((candidate) => candidate.sizes === sizes)
  assert(icon?.src === source && icon?.type === 'image/png', `Manifest 缺少 ${sizes} PNG 图标`)
  await access(resolve(dist, source))
}

assert(serviceWorker.includes('precacheAndRoute'), 'Service Worker 未生成静态资源预缓存')
assert(serviceWorker.includes('api') && serviceWorker.includes('health'), 'Service Worker 未排除 API/health 导航回退')
assert(!/BackgroundSync|backgroundSync|NetworkFirst|NetworkOnly/.test(serviceWorker), 'Service Worker 不得包含 API 缓存或后台同步策略')

console.log('PWA 产物检查通过：Manifest、安装图标、静态预缓存和 API 缓存边界符合预期。')
