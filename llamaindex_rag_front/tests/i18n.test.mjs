import test from 'node:test'
import assert from 'node:assert/strict'
import { nextTick } from 'vue'

const stored = new Map([['enterprise_assets_locale', 'en']])
globalThis.localStorage = {
  getItem: (key) => stored.get(key) ?? null,
  setItem: (key, value) => stored.set(key, value),
}
globalThis.document = { documentElement: { lang: '' }, title: '' }
const { locale, intlLocale, setLocale, t, displayWorkspace, LOCALE_KEY } = await import('../src/i18n/index.js')

test('restores the selected language and updates accessible document metadata', () => {
  assert.equal(locale.value, 'en')
  assert.equal(intlLocale.value, 'en-US')
  assert.equal(document.documentElement.lang, 'en')
  assert.equal(document.title, 'Enterprise Digital Asset Library')
})

test('switches reactively and persists only valid supported languages', async () => {
  setLocale('zh')
  await nextTick()
  assert.equal(t('企业数字资产库'), '企业数字资产库')
  assert.equal(intlLocale.value, 'zh-CN')
  assert.equal(document.documentElement.lang, 'zh-CN')
  assert.equal(document.title, '企业数字资产库')
  assert.equal(stored.get(LOCALE_KEY), 'zh')
  setLocale('fr')
  assert.equal(locale.value, 'zh')
  setLocale('en')
  await nextTick()
  assert.equal(document.title, 'Enterprise Digital Asset Library')
  assert.equal(stored.get(LOCALE_KEY), 'en')
})

test('interpolates UI messages without translating user data', () => {
  assert.equal(t('确认删除会话“{title}”吗？', { title: '九月策划' }), 'Delete the chat “九月策划”?')
  assert.equal(displayWorkspace('公共知识库', 'global'), t('公共知识库'))
  assert.equal(displayWorkspace('创作部门', '12'), '创作部门')
  assert.equal(t('未知原始文案'), '未知原始文案')
  assert.equal(t('constructor'), 'constructor')
  assert.equal(t('{constructor}'), '{constructor}')
})

test('keeps switching functional when preference storage is unavailable', async () => {
  const save = localStorage.setItem
  localStorage.setItem = () => { throw new Error('storage unavailable') }
  try {
    assert.doesNotThrow(() => setLocale('zh'))
    await nextTick()
    assert.equal(locale.value, 'zh')
    assert.equal(document.documentElement.lang, 'zh-CN')
  } finally { localStorage.setItem = save }
})

test('English dictionaries preserve placeholders and do not contain untranslated Chinese UI copy', async () => {
  const modules = await Promise.all(['core', 'assets', 'admin', 'chat'].map(name => import(`../src/i18n/messages/${name}.js`)))
  const placeholders = text => [...text.matchAll(/\{(\w+)\}/g)].map(match => match[1]).sort()
  const seen = new Map()
  for (const { default: messages } of modules) {
    for (const [source, english] of Object.entries(messages)) {
      if (seen.has(source)) assert.equal(english, seen.get(source), `Conflicting translation: ${source}`)
      seen.set(source, english)
      assert.equal(typeof english, 'string', source)
      assert.ok(english.trim(), source)
      assert.deepEqual(placeholders(english), placeholders(source), source)
      assert.equal(/[\u3400-\u9fff]/.test(english), false, source)
    }
  }
})


test('visible static template copy uses translations outside the bilingual language picker', async () => {
  const { parse: parseSFC } = await import('@vue/compiler-sfc')
  const { parse: parseTemplate } = await import('@vue/compiler-dom')
  const { readFileSync, readdirSync } = await import('node:fs')
  const untranslated = []
  for (const dir of ['components', 'views']) {
    const folder = new URL(`../src/${dir}/`, import.meta.url)
    for (const filename of readdirSync(folder).filter(name => name.endsWith('.vue') && name !== 'LanguageSwitcher.vue')) {
      const { descriptor } = parseSFC(readFileSync(new URL(filename, folder), 'utf8'))
      if (!descriptor.template) continue
      const visit = (node) => {
        if (node.type === 2 && /[\u3400-\u9fff]/.test(node.content)) untranslated.push(`${filename}: ${node.content.trim()}`)
        for (const prop of node.props || []) {
          if (prop.type === 6 && prop.value && /[\u3400-\u9fff]/.test(prop.value.content)) untranslated.push(`${filename} ${prop.name}: ${prop.value.content}`)
        }
        for (const child of node.children || []) visit(child)
      }
      visit(parseTemplate(descriptor.template.content))
    }
  }
  assert.deepEqual(untranslated, [], 'Visible UI copy must be translated')
})
