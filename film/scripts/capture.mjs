// Hi-res demo plates for Remotion film. Real console only.
// No Record decision. No synthetic intel. No Start/Stop stream.
import { spawn } from "node:child_process"
import fs from "node:fs"
import os from "node:os"
import path from "node:path"
import { fileURLToPath } from "node:url"

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..")
const out = path.join(root, "public", "captures")
const chromePath = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
const app = "http://127.0.0.1:8080"
const width = 1920
const height = 1080
const dpr = 2

function cdp(ws, method, params, timeoutMs) {
  const id = cdp.next++
  const result = new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      cdp.wait.delete(id)
      reject(new Error("timeout " + method))
    }, timeoutMs || (method.startsWith("Page.capture") ? 120000 : 60000))
    cdp.wait.set(id, (err, value) => {
      clearTimeout(timer)
      if (err) reject(err)
      else resolve(value)
    })
  })
  ws.send(JSON.stringify({ id, method, params: params || {} }))
  return result
}
cdp.next = 1
cdp.wait = new Map()

async function ev(ws, source) {
  const outEv = await cdp(ws, "Runtime.evaluate", {
    expression: source,
    awaitPromise: true,
    returnByValue: true,
  })
  if (outEv.exceptionDetails) throw new Error(outEv.exceptionDetails.exception.description)
  return outEv.result.value
}

async function shot(ws, clip) {
  const cap = await cdp(ws, "Page.captureScreenshot", {
    format: "png",
    fromSurface: true,
    captureBeyondViewport: Boolean(clip),
    clip: clip || { x: 0, y: 0, width, height, scale: 1 },
  })
  return Buffer.from(cap.data, "base64")
}

async function waitText(ws, text) {
  for (let i = 0; i < 120; i++) {
    try {
      const hit = await ev(ws, `!!(document.body && document.body.innerText && document.body.innerText.includes(${JSON.stringify(text)}))`)
      if (hit) return
    } catch {
      /* page navigating */
    }
    await new Promise((r) => setTimeout(r, 250))
  }
  throw new Error("not on screen: " + text)
}

async function clickText(ws, text) {
  const ok = await ev(ws, `(function () {
    const el = [...document.querySelectorAll("button")].find((b) => b.textContent.trim() === ${JSON.stringify(text)})
    if (!el) return false
    el.click()
    return true
  })()`)
  if (!ok) throw new Error("no button " + text)
}

async function clickTab(ws, label) {
  const ok = await ev(ws, `(function () {
    const el = [...document.querySelectorAll("button, a, [role=tab]")].find((b) => b.textContent.trim() === ${JSON.stringify(label)})
    if (!el) return false
    el.click()
    return true
  })()`)
  if (!ok) throw new Error("no tab " + label)
}

async function hideChrome(ws) {
  await ev(ws, `(function () {
    for (const el of document.querySelectorAll("button")) {
      const t = (el.textContent || "").trim()
      if (t === "Start stream" || t === "Stop stream") el.style.display = "none"
    }
    for (const el of document.querySelectorAll(".chip")) {
      const t = (el.textContent || "").toLowerCase()
      if (t.includes("stream:") || t.includes("gemini:")) el.style.visibility = "hidden"
    }
    for (const el of [...document.querySelectorAll("p, div, span, li, pre, code, .muted, .banner, .alert, .toast, .notice")]) {
      const t = (el.textContent || "").trim()
      if (t.length && t.length < 240 && /GEMINI_API_KEY|Gemini failed/i.test(t)) el.remove()
    }
  })()`)
}

async function expand(ws) {
  await ev(ws, `(function () {
    for (const el of [document.documentElement, document.body, document.querySelector(".app-shell"), document.querySelector(".app-main"), document.querySelector(".detail-body")]) {
      if (!el) continue
      el.style.height = "auto"
      el.style.maxHeight = "none"
      el.style.overflow = "visible"
    }
  })()`)
}

async function fullShot(ws, file, minBottom) {
  const meta = await ev(ws, `(function () {
    const bottom = Math.max(
      document.documentElement.scrollHeight,
      document.body.scrollHeight,
      ${Number(minBottom) || 0}
    )
    for (const el of [document.documentElement, document.body, document.querySelector(".app-shell"), document.querySelector(".app-main")]) {
      if (!el) continue
      el.style.height = "auto"
      el.style.minHeight = bottom + "px"
      el.style.overflow = "visible"
    }
    return {
      width: Math.max(document.documentElement.scrollWidth, ${width}),
      height: Math.max(bottom, ${height}),
    }
  })()`)
  await cdp(ws, "Emulation.setDeviceMetricsOverride", {
    width: meta.width, height: meta.height, deviceScaleFactor: dpr, mobile: false,
  })
  await hideChrome(ws)
  await ev(ws, `new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))`)
  const png = await shot(ws, { x: 0, y: 0, width: meta.width, height: meta.height, scale: 1 })
  fs.writeFileSync(file, png)
  await cdp(ws, "Emulation.setDeviceMetricsOverride", {
    width, height, deviceScaleFactor: dpr, mobile: false,
  })
  return meta
}

async function main() {
  fs.mkdirSync(out, { recursive: true })
  const dirs = ["login", "home", "queue", "case", "flow", "verdict", "decision", "patterns"]
  for (const d of dirs) fs.mkdirSync(path.join(out, d), { recursive: true })

  const userData = fs.mkdtempSync(path.join(os.tmpdir(), "cw-film-cap-"))
  const debugPort = 23000 + (process.pid % 10000)
  const chrome = spawn(chromePath, [
    "--headless=new",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--hide-scrollbars",
    "--force-device-scale-factor=" + dpr,
    "--force-color-profile=srgb",
    "--window-size=" + width + "," + height,
    "--user-data-dir=" + userData,
    "--remote-debugging-port=" + debugPort,
    "--remote-allow-origins=*",
    app + "/",
  ], { stdio: ["ignore", "pipe", "pipe"] })
  let chromeErr = ""
  chrome.stderr.on("data", (b) => {
    chromeErr += String(b)
  })

  let page
  for (let i = 0; i < 80; i++) {
    try {
      const list = await (await fetch("http://127.0.0.1:" + debugPort + "/json/list")).json()
      page = list.find((item) => item.type === "page" && item.webSocketDebuggerUrl)
      if (page) break
    } catch {}
    await new Promise((r) => setTimeout(r, 150))
  }
  if (!page) {
    throw new Error("chrome did not open" + (chromeErr ? "\n" + chromeErr.slice(0, 800) : ""))
  }
  const ws = new WebSocket(page.webSocketDebuggerUrl)
  await new Promise((resolve, reject) => {
    ws.addEventListener("open", resolve)
    ws.addEventListener("error", reject)
  })
  ws.addEventListener("message", (msgEv) => {
    const msg = JSON.parse(msgEv.data)
    if (msg.id && cdp.wait.has(msg.id)) {
      const done = cdp.wait.get(msg.id)
      cdp.wait.delete(msg.id)
      if (msg.error) done(new Error(msg.error.message))
      else done(null, msg.result)
    }
  })
  await cdp(ws, "Page.enable")
  await cdp(ws, "Runtime.enable")
  await cdp(ws, "Emulation.setDeviceMetricsOverride", {
    width, height, deviceScaleFactor: dpr, mobile: false,
  })

  const boxes = { viewport: { width, height, dpr }, plates: {} }

  await cdp(ws, "Page.reload")
  await waitText(ws, "Sign In")
  await hideChrome(ws)
  await ev(ws, `new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))`)
  fs.writeFileSync(path.join(out, "login/login.png"), await shot(ws))
  boxes.plates.login = { path: "login/login.png" }
  console.log("login")

  await clickText(ws, "FIU Team Lead")
  for (let i = 0; i < 40; i++) {
    const ready = await ev(ws, `document.querySelector("input") && document.querySelector("input").value === "fiu_lead"`)
    if (ready) break
    if (i === 39) throw new Error("demo role did not fill")
    await new Promise((r) => setTimeout(r, 100))
  }
  await clickText(ws, "Sign In →")
  await waitText(ws, "Partial network")
  await expand(ws)
  await hideChrome(ws)
  const homeMeta = await fullShot(ws, path.join(out, "home/home.png"), 1800)
  const homeBoxes = await ev(ws, `(function () {
    function box(el) {
      if (!el) return null
      const r = el.getBoundingClientRect()
      return { x: r.x + scrollX, y: r.y + scrollY, w: r.width, h: r.height }
    }
    const brand = document.querySelector(".sidenav-brand")
    const head = [...document.querySelectorAll("h3")].find((h) => h.textContent.includes("Partial network"))
    const card = head ? head.closest(".card") : null
    const open = [...document.querySelectorAll("button")].find((b) => b.textContent.includes("Open CW-MID-02"))
    return { brand: box(brand), networkCard: box(card), openMid: box(open), width: ${homeMeta.width}, height: ${homeMeta.height} }
  })()`)
  boxes.plates.home = { path: "home/home.png", ...homeBoxes }
  console.log("home", homeMeta)

  await cdp(ws, "Page.navigate", { url: app + "/investigate" })
  await waitText(ws, "Triage queue")
  await waitText(ws, "CW-MID-02")
  await expand(ws)
  await hideChrome(ws)
  await ev(ws, `new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))`)
  fs.writeFileSync(path.join(out, "queue/queue.png"), await shot(ws))
  const queueBoxes = await ev(ws, `(function () {
    function box(el) {
      if (!el) return null
      const r = el.getBoundingClientRect()
      return { x: r.x + scrollX, y: r.y + scrollY, w: r.width, h: r.height }
    }
    const row = [...document.querySelectorAll("tr, .row, a, button, [class*='alert']")].find((el) => (el.textContent || "").includes("CW-MID-02"))
    return { midRow: box(row) }
  })()`)
  boxes.plates.queue = { path: "queue/queue.png", ...queueBoxes }
  console.log("queue")

  await cdp(ws, "Page.navigate", { url: app + "/investigate/CW-MID-02" })
  await waitText(ws, "CW-MID-02")
  await expand(ws)
  await hideChrome(ws)
  await ev(ws, `new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))`)
  fs.writeFileSync(path.join(out, "case/overview.png"), await shot(ws))
  const caseMeta = await ev(ws, `(function () {
    function box(el) {
      if (!el) return null
      const r = el.getBoundingClientRect()
      return { x: r.x + scrollX, y: r.y + scrollY, w: r.width, h: r.height }
    }
    const body = document.body.textContent || ""
    const vis = (body.match(/(\\d{1,3})\\s*%\\s*(?:visibility|coverage|network)/i) || body.match(/visibility[^\\d]*(\\d{1,3})\\s*%/i) || [])[1]
    const risk = (body.match(/\\b(9[0-9])\\b/) || [])[1]
    return {
      brand: box(document.querySelector(".sidenav-brand")),
      amount: box([...document.querySelectorAll("*")].find((el) => /\\$9,?050/.test(el.textContent || "") && (el.children.length === 0 || el.textContent.trim().length < 40))),
      visibilityText: vis ? Number(vis) : null,
      riskHint: risk ? Number(risk) : null,
    }
  })()`)
  boxes.plates.case = { path: "case/overview.png", ...caseMeta }
  console.log("case", caseMeta.visibilityText)

  await clickTab(ws, "Money flow")
  await waitText(ws, "Money movement")
  await expand(ws)
  await hideChrome(ws)
  const flowMeta = await fullShot(ws, path.join(out, "flow/network.png"), 1250)
  const flowBoxes = await ev(ws, `(function () {
    function box(el) {
      if (!el) return null
      const r = el.getBoundingClientRect()
      return { x: r.x + scrollX, y: r.y + scrollY, w: r.width, h: r.height }
    }
    const svg = document.querySelector("svg[aria-label='Money movement network']") || document.querySelector("svg")
    return { width: ${flowMeta.width}, height: ${flowMeta.height}, graph: box(svg) }
  })()`)
  boxes.plates.flow = { path: "flow/network.png", ...flowBoxes }
  console.log("flow", flowMeta)

  await clickTab(ws, "Verdict")
  await waitText(ws, "Evidence")
  const hasPack = await ev(ws, `!!document.querySelector(".ev-card")`)
  if (!hasPack) {
    await clickText(ws, "Deterministic DAG only")
    for (let i = 0; i < 100; i++) {
      const ok = await ev(ws, `!!document.querySelector(".ev-card")`)
      if (ok) break
      await new Promise((r) => setTimeout(r, 250))
    }
  }
  await expand(ws)
  await hideChrome(ws)
  const packMeta = await fullShot(ws, path.join(out, "verdict/evidence.png"), 1600)
  boxes.plates.evidence = { path: "verdict/evidence.png", ...packMeta }
  console.log("evidence", packMeta)

  // Fixture AI brief plate — deterministic pack only (never surface API_KEY errors).
  await hideChrome(ws)
  const briefMeta = await fullShot(ws, path.join(out, "verdict/brief.png"), 1800)
  const briefText = await ev(ws, `(function () {
    const leftovers = [...document.querySelectorAll(".muted, p, div")].filter((el) => {
      const t = (el.textContent || "").trim()
      if (!t || t.length > 240) return false
      if (!/GEMINI_API_KEY|Gemini failed/i.test(t)) return false
      const s = getComputedStyle(el)
      return s.display !== "none" && s.visibility !== "hidden"
    })
    return {
      hasKeyError: leftovers.length > 0,
      hasEvidence: !!document.querySelector(".ev-card"),
      riskHigh: /high/i.test(document.body.textContent || "") && /91/.test(document.body.textContent || ""),
    }
  })()`)
  if (briefText.hasKeyError) throw new Error("API key error still visible on verdict plate")
  boxes.plates.brief = { path: "verdict/brief.png", ...briefMeta, ...briefText }
  console.log("brief", briefText)

  await clickTab(ws, "Workflow")
  await waitText(ws, "hold_payment")
  await expand(ws)
  await hideChrome(ws)
  const decisionMeta = await fullShot(ws, path.join(out, "decision/workflow.png"), 1120)
  boxes.plates.decision = { path: "decision/workflow.png", ...decisionMeta }
  console.log("decision", decisionMeta)

  await cdp(ws, "Page.navigate", { url: app + "/patterns" })
  await waitText(ws, "Crime Pattern DNA")
  await expand(ws)
  await hideChrome(ws)
  const libMeta = await fullShot(ws, path.join(out, "patterns/library.png"), 1140)
  boxes.plates.patterns = { path: "patterns/library.png", ...libMeta }
  console.log("patterns", libMeta)

  // Multi-case paced plates (Day-2 storyboard: ≥5 distinct case IDs, readable holds).
  const paceMs = Number(process.env.CW_CAPTURE_PACE_MS || 1200)
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
  const cases = [
    { id: "CW-MID-02", folder: "cases/CW-MID-02", tabs: ["Overview", "Money flow", "Verdict", "Workflow"] },
    { id: "CW-MID-03", folder: "cases/CW-MID-03", tabs: ["Overview", "Verdict"] },
    { id: "CW-LOTUS-04", folder: "cases/CW-LOTUS-04", tabs: ["Overview", "Money flow", "Verdict"] },
  ]
  for (const c of cases) {
    fs.mkdirSync(path.join(out, c.folder), { recursive: true })
    await cdp(ws, "Page.navigate", { url: app + "/investigate/" + encodeURIComponent(c.id) })
    try {
      await waitText(ws, c.id)
    } catch {
      console.log("skip missing case", c.id)
      continue
    }
    for (const tab of c.tabs) {
      try {
        await clickTab(ws, tab)
      } catch {
        continue
      }
      await sleep(paceMs)
      await hideChrome(ws)
      await ev(ws, `new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))`)
      const slug = tab.toLowerCase().replace(/\s+/g, "-")
      const file = path.join(out, c.folder, slug + ".png")
      // Viewport shot only — fullShot expand can hang captureScreenshot on tall pages.
      fs.writeFileSync(file, await shot(ws))
      console.log("case-plate", c.id, slug)
    }
  }
  // Safety-test gate-fail plate (seeded CW-MID-03 replay verdict)
  await cdp(ws, "Page.navigate", { url: app + "/investigate/CW-MID-03" })
  try {
    await waitText(ws, "CW-MID-03")
    await clickTab(ws, "Verdict")
    await sleep(paceMs)
    await clickText(ws, "Run investigation (auto)").catch(() => {})
    await sleep(Math.max(paceMs, 1500))
    await hideChrome(ws)
    fs.mkdirSync(path.join(out, "verdict"), { recursive: true })
    fs.writeFileSync(path.join(out, "verdict/gate-fail-safety.png"), await shot(ws))
    boxes.plates.gateFail = { path: "verdict/gate-fail-safety.png", case: "CW-MID-03" }
    console.log("gate-fail-safety")
  } catch (e) {
    console.log("gate-fail plate skipped", String(e.message || e))
  }

  // Measured case fixture for Remotion (visibility from live UI when found).
  const visibility = caseMeta.visibilityText ?? 61
  const caseJson = {
    id: "CW-MID-02",
    amount: 9050,
    corridor: "SG→PH",
    risk: 91,
    pattern: "mule_pass_through",
    home_bank: "BANK_SG",
    observed_path: ["BANK_IN", "BANK_SG", "BANK_PH"],
    unresolved: ["BANK_HK"],
    mule: "D-MID-MULE",
    network_visibility_pct: visibility,
    note: "PARTIAL NETWORK OBSERVED — upstream partial, internal full, downstream partial.",
  }
  fs.mkdirSync(path.join(root, "src", "data"), { recursive: true })
  fs.writeFileSync(
    path.join(root, "src", "data", "case-cw-mid-02.json"),
    JSON.stringify(caseJson, null, 2) + "\n",
  )
  fs.writeFileSync(
    path.join(root, "src", "data", "ai-brief-fixture.json"),
    JSON.stringify(
      {
        mode: "fixture",
        vendor_on_screen: "AI",
        risk: "high",
        score: 91,
        pattern: "mule pass through",
        network_visibility_pct: visibility,
        summary:
          "Observed path BANK_IN → BANK_SG → BANK_PH carries $9,050 with mule device D-MID-MULE on the PH side. Downstream off-ramp BANK_HK remains unresolved. Coverage is incomplete — treat as investigation priority, not guilt confidence.",
        still_unknown: ["Final off-ramp BANK_HK / Bank D", "Beneficial owner of mule account"],
        next: ["Hold payment", "Request corridor counterparties", "Confirm device reuse"],
      },
      null,
      2,
    ) + "\n",
  )

  fs.writeFileSync(path.join(out, "boxes.json"), JSON.stringify(boxes, null, 2) + "\n")
  console.log("captures written →", out)
  ws.close()
  chrome.kill("SIGKILL")
  fs.rmSync(userData, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 })
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
