// Day-2 capture via Playwright Chromium (fallback when system Chrome CDP hangs).
import { chromium } from "playwright"
import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..")
const out = path.join(root, "public", "captures")
const app = process.env.CW_APP_URL || "http://127.0.0.1:8080"
const paceMs = Number(process.env.CW_CAPTURE_PACE_MS || 800)
const width = 1920
const height = 1080

async function shot(page, file) {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  await page.screenshot({ path: file, type: "png" })
  console.log("wrote", path.relative(out, file))
}

async function main() {
  fs.mkdirSync(out, { recursive: true })
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({
    viewport: { width, height },
    deviceScaleFactor: 2,
  })

  await page.goto(app + "/", { waitUntil: "networkidle" })
  await page.getByText("Sign In").first().waitFor({ timeout: 30000 })
  await shot(page, path.join(out, "login/login.png"))

  await page.getByRole("button", { name: "FIU Team Lead" }).click()
  await page.getByRole("button", { name: /Sign In/ }).click()
  await page.getByText(/Partial network|Triage queue|Corridor/).first().waitFor({ timeout: 45000 })
  await page.waitForTimeout(paceMs)
  await shot(page, path.join(out, "home/home.png"))

  await page.goto(app + "/investigate", { waitUntil: "networkidle" })
  await page.getByText("CW-MID-02").first().waitFor({ timeout: 30000 })
  await page.waitForTimeout(paceMs)
  await shot(page, path.join(out, "queue/queue.png"))

  const cases = [
    { id: "CW-MID-02", tabs: ["Overview", "Money flow", "Verdict", "Workflow"] },
    { id: "CW-MID-03", tabs: ["Overview", "Verdict"] },
    { id: "CW-LOTUS-04", tabs: ["Overview", "Money flow", "Verdict"] },
  ]
  for (const c of cases) {
    await page.goto(app + "/investigate/" + encodeURIComponent(c.id), { waitUntil: "networkidle" })
    await page.getByText(c.id).first().waitFor({ timeout: 20000 }).catch(() => null)
    for (const tab of c.tabs) {
      await page.getByRole("tab", { name: tab }).click().catch(async () => {
        await page.getByRole("button", { name: tab }).click().catch(() => {})
      })
      await page.waitForTimeout(paceMs)
      const slug = tab.toLowerCase().replace(/\s+/g, "-")
      await shot(page, path.join(out, "cases", c.id, slug + ".png"))
    }
  }

  // Canonical plates used by Remotion scenes
  await page.goto(app + "/investigate/CW-MID-02", { waitUntil: "networkidle" })
  await page.waitForTimeout(paceMs)
  await shot(page, path.join(out, "case/overview.png"))
  await page.getByRole("tab", { name: "Money flow" }).click().catch(() => {})
  await page.waitForTimeout(paceMs)
  await shot(page, path.join(out, "flow/network.png"))
  await page.getByRole("tab", { name: "Verdict" }).click().catch(() => {})
  await page.waitForTimeout(paceMs)
  await page.getByRole("button", { name: /Run investigation|Force Gemini|Deterministic/ }).first().click().catch(() => {})
  await page.waitForTimeout(paceMs * 2)
  await shot(page, path.join(out, "verdict/evidence.png"))
  await shot(page, path.join(out, "verdict/brief.png"))
  await page.getByRole("tab", { name: "Workflow" }).click().catch(() => {})
  await page.waitForTimeout(paceMs)
  await shot(page, path.join(out, "decision/workflow.png"))

  await page.goto(app + "/investigate/CW-MID-03", { waitUntil: "networkidle" })
  await page.getByRole("tab", { name: "Verdict" }).click().catch(() => {})
  await page.waitForTimeout(paceMs)
  await page.getByRole("button", { name: /Run investigation \(auto\)/ }).click().catch(() => {})
  await page.waitForTimeout(paceMs * 2)
  await shot(page, path.join(out, "verdict/gate-fail-safety.png"))

  await page.goto(app + "/patterns", { waitUntil: "networkidle" })
  await page.getByText(/Pattern DNA|Crime Pattern/).first().waitFor({ timeout: 20000 }).catch(() => {})
  await page.waitForTimeout(paceMs)
  await shot(page, path.join(out, "patterns/library.png"))

  await browser.close()
  console.log("captures written →", out)
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
