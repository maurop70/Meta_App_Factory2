/**
 * ═══════════════════════════════════════════════════
 *  DELEGATE AI — PITCH DECK GENERATOR
 *  Google Apps Script | Creative Studio Agent
 *
 *  DEPLOYMENT:
 *  1. Create a new Google Slides presentation
 *  2. Go to Extensions > Apps Script
 *  3. Paste this file into Code.gs
 *  4. Run buildPitchDeck()
 * ═══════════════════════════════════════════════════
 */

function buildPitchDeck() {
  const deck = SlidesApp.getActivePresentation();
  deck.setName("Project Aether & Delegate AI — Pitch Deck");

  // Remove any existing slides
  while (deck.getSlides().length > 0) {
    deck.getSlides()[0].remove();
  }

  // Brand palette
  const BRAND = {
    darkBg: "#0a0f1a",
    emerald: "#1b5e20",
    emeraldLight: "#2e7d32",
    gold: "#ffd54f",
    white: "#ffffff",
    silver: "#c8d6e5",
    charcoal: "#1a1a2e",
    accentBlue: "#0a3d62",
  };

  // ═══════ SLIDE 1: TITLE ═══════
  const s1 = deck.appendSlide(SlidesApp.PredefinedLayout.BLANK);
  s1.getBackground().setSolidFill(BRAND.darkBg);

  s1.insertTextBox("DELEGATE AI", 60, 120, 800, 80)
    .getText().getTextStyle()
    .setFontSize(54).setBold(true).setFontFamily("Inter")
    .setForegroundColor(BRAND.white);

  s1.insertTextBox("AI-Native Task Delegation for Law Firms", 60, 210, 700, 40)
    .getText().getTextStyle()
    .setFontSize(22).setFontFamily("Inter")
    .setForegroundColor(BRAND.gold);

  s1.insertTextBox("Powered by Project Aether  •  Antigravity-AI", 60, 320, 500, 30)
    .getText().getTextStyle()
    .setFontSize(14).setFontFamily("Inter")
    .setForegroundColor(BRAND.silver);

  s1.insertTextBox("Confidential  |  March 2026", 60, 420, 300, 25)
    .getText().getTextStyle()
    .setFontSize(11).setItalic(true).setFontFamily("Inter")
    .setForegroundColor(BRAND.silver);

  // ═══════ SLIDE 2: THE PROBLEM ═══════
  const s2 = deck.appendSlide(SlidesApp.PredefinedLayout.BLANK);
  s2.getBackground().setSolidFill(BRAND.darkBg);

  s2.insertTextBox("THE PROBLEM", 60, 40, 400, 40)
    .getText().getTextStyle()
    .setFontSize(16).setBold(true).setFontFamily("Inter")
    .setForegroundColor(BRAND.gold);

  s2.insertTextBox("Law Firms Lose 8-12% of Billable Hours\nto Broken Delegation", 60, 90, 800, 80)
    .getText().getTextStyle()
    .setFontSize(32).setBold(true).setFontFamily("Inter")
    .setForegroundColor(BRAND.white);

  const problems = [
    "🔴  68% of firms have NO workflow management system",
    "🔴  Task delegation via email/verbal = lost tasks, delayed work",
    "🔴  Associates spend 60-80% of time on administrative routing",
    "🔴  Firms with 10+ attorneys lose $50K-200K/year to delegation friction",
  ];

  problems.forEach((text, i) => {
    s2.insertTextBox(text, 80, 200 + (i * 45), 750, 35)
      .getText().getTextStyle()
      .setFontSize(16).setFontFamily("Inter")
      .setForegroundColor(BRAND.silver);
  });

  s2.insertTextBox("Source: JD Supra (2026), Thomson Reuters Institute", 60, 420, 500, 20)
    .getText().getTextStyle()
    .setFontSize(10).setItalic(true).setFontFamily("Inter")
    .setForegroundColor("#666666");

  // ═══════ SLIDE 3: THE SOLUTION ═══════
  const s3 = deck.appendSlide(SlidesApp.PredefinedLayout.BLANK);
  s3.getBackground().setSolidFill(BRAND.darkBg);

  s3.insertTextBox("THE SOLUTION", 60, 40, 400, 40)
    .getText().getTextStyle()
    .setFontSize(16).setBold(true).setFontFamily("Inter")
    .setForegroundColor(BRAND.gold);

  s3.insertTextBox("Delegate AI: 3-Click Intelligent Delegation", 60, 90, 800, 50)
    .getText().getTextStyle()
    .setFontSize(32).setBold(true).setFontFamily("Inter")
    .setForegroundColor(BRAND.white);

  const features = [
    ["⚡ AI-Powered Routing", "Describe the task → AI classifies, prioritizes, and routes to the right associate automatically."],
    ["📊 Billable Hour Recovery", "Every delegation is tracked, timed, and logged to your matter — no more lost billable work."],
    ["🔒 Attorney-Client Privilege", "5-layer privacy shield. Your client data NEVER touches the AI model. ABA Rule 1.6 compliant."],
    ["🎯 Quality Gate", "Built-in AI review ensures every delegation is complete before it leaves your desk."],
  ];

  features.forEach((feat, i) => {
    const y = 170 + (i * 65);
    s3.insertTextBox(feat[0], 80, y, 300, 25)
      .getText().getTextStyle()
      .setFontSize(18).setBold(true).setFontFamily("Inter")
      .setForegroundColor(BRAND.emeraldLight);

    s3.insertTextBox(feat[1], 80, y + 25, 750, 30)
      .getText().getTextStyle()
      .setFontSize(13).setFontFamily("Inter")
      .setForegroundColor(BRAND.silver);
  });

  // ═══════ SLIDE 4: HOW IT WORKS ═══════
  const s4 = deck.appendSlide(SlidesApp.PredefinedLayout.BLANK);
  s4.getBackground().setSolidFill(BRAND.darkBg);

  s4.insertTextBox("HOW IT WORKS", 60, 40, 400, 40)
    .getText().getTextStyle()
    .setFontSize(16).setBold(true).setFontFamily("Inter")
    .setForegroundColor(BRAND.gold);

  s4.insertTextBox("From Delegation to Completion in 3 Steps", 60, 90, 800, 50)
    .getText().getTextStyle()
    .setFontSize(28).setBold(true).setFontFamily("Inter")
    .setForegroundColor(BRAND.white);

  const steps = [
    ["1️⃣  DELEGATE", "Partner speaks or types:\n\"Draft the Smith discovery response, assign to Sarah, due Friday, bill to matter 2024-0847\""],
    ["2️⃣  AI ROUTES", "Delegate AI classifies → DISCOVERY, priority HIGH,\nassigns to Sarah Chen, logs to matter, notifies via email/Slack"],
    ["3️⃣  TRACK & BILL", "Real-time task board. Associate logs hours.\nPartner sees completion status and billable recovery dashboard."],
  ];

  steps.forEach((step, i) => {
    const y = 160 + (i * 90);
    s4.insertTextBox(step[0], 80, y, 250, 30)
      .getText().getTextStyle()
      .setFontSize(20).setBold(true).setFontFamily("Inter")
      .setForegroundColor(BRAND.gold);

    s4.insertTextBox(step[1], 80, y + 32, 750, 45)
      .getText().getTextStyle()
      .setFontSize(13).setFontFamily("Inter")
      .setForegroundColor(BRAND.silver);
  });

  // ═══════ SLIDE 5: MARKET OPPORTUNITY ═══════
  const s5 = deck.appendSlide(SlidesApp.PredefinedLayout.BLANK);
  s5.getBackground().setSolidFill(BRAND.darkBg);

  s5.insertTextBox("MARKET OPPORTUNITY", 60, 40, 400, 40)
    .getText().getTextStyle()
    .setFontSize(16).setBold(true).setFontFamily("Inter")
    .setForegroundColor(BRAND.gold);

  s5.insertTextBox("440,000+ Law Firms. 68% Have Zero Workflow Tooling.", 60, 90, 800, 50)
    .getText().getTextStyle()
    .setFontSize(28).setBold(true).setFontFamily("Inter")
    .setForegroundColor(BRAND.white);

  const metrics = [
    ["440K+", "US Law Firms"],
    ["$15B+", "Legal Tech Market"],
    ["68%", "No Workflow Tools"],
    ["8-12%", "Lost Billable Hours"],
  ];

  metrics.forEach((m, i) => {
    const x = 60 + (i * 210);
    s5.insertTextBox(m[0], x, 180, 180, 60)
      .getText().getTextStyle()
      .setFontSize(36).setBold(true).setFontFamily("Inter")
      .setForegroundColor(BRAND.emeraldLight);

    s5.insertTextBox(m[1], x, 245, 180, 25)
      .getText().getTextStyle()
      .setFontSize(13).setFontFamily("Inter")
      .setForegroundColor(BRAND.silver);
  });

  s5.insertTextBox("Target Segment: Solo practitioners & small firms (2-25 attorneys)\nPricing: $49-99/seat/month  •  SaaS subscription model", 80, 320, 750, 50)
    .getText().getTextStyle()
    .setFontSize(14).setFontFamily("Inter")
    .setForegroundColor(BRAND.white);

  s5.insertTextBox("Validated by The Critic (Antigravity Systems Audit) — Score: 8.4/10", 80, 400, 600, 25)
    .getText().getTextStyle()
    .setFontSize(11).setItalic(true).setFontFamily("Inter")
    .setForegroundColor(BRAND.gold);

  // ═══════ SLIDE 6: TECHNOLOGY ═══════
  const s6 = deck.appendSlide(SlidesApp.PredefinedLayout.BLANK);
  s6.getBackground().setSolidFill(BRAND.darkBg);

  s6.insertTextBox("TECHNOLOGY", 60, 40, 400, 40)
    .getText().getTextStyle()
    .setFontSize(16).setBold(true).setFontFamily("Inter")
    .setForegroundColor(BRAND.gold);

  s6.insertTextBox("Built on the Aether Runtime — Not a Greenfield Build", 60, 90, 800, 50)
    .getText().getTextStyle()
    .setFontSize(28).setBold(true).setFontFamily("Inter")
    .setForegroundColor(BRAND.white);

  const techStack = [
    ["AI Engine", "Claude Sonnet 4 (Aether Runtime)"],
    ["Database", "Supabase (PostgreSQL + RLS)"],
    ["Workflow", "n8n Cloud (Pro)"],
    ["Encryption", "Fernet AES-128 (Compliance Vault)"],
    ["Frontend", "React + Vite"],
    ["Auth", "Supabase Auth (firm-level tenancy)"],
  ];

  techStack.forEach((item, i) => {
    const y = 170 + (i * 35);
    s6.insertTextBox(item[0], 80, y, 200, 25)
      .getText().getTextStyle()
      .setFontSize(14).setBold(true).setFontFamily("Inter")
      .setForegroundColor(BRAND.emeraldLight);

    s6.insertTextBox(item[1], 300, y, 500, 25)
      .getText().getTextStyle()
      .setFontSize(14).setFontFamily("Inter")
      .setForegroundColor(BRAND.silver);
  });

  s6.insertTextBox("~400 lines of net-new code  •  10-day MVP sprint  •  80% existing infrastructure", 80, 400, 750, 25)
    .getText().getTextStyle()
    .setFontSize(12).setItalic(true).setFontFamily("Inter")
    .setForegroundColor(BRAND.gold);

  // ═══════ SLIDE 7: PRIVACY & COMPLIANCE ═══════
  const s7 = deck.appendSlide(SlidesApp.PredefinedLayout.BLANK);
  s7.getBackground().setSolidFill(BRAND.darkBg);

  s7.insertTextBox("PRIVACY & COMPLIANCE", 60, 40, 400, 40)
    .getText().getTextStyle()
    .setFontSize(16).setBold(true).setFontFamily("Inter")
    .setForegroundColor(BRAND.gold);

  s7.insertTextBox("5-Layer Privacy Shield\nYour Client Data Never Touches the AI", 60, 90, 800, 70)
    .getText().getTextStyle()
    .setFontSize(28).setBold(true).setFontFamily("Inter")
    .setForegroundColor(BRAND.white);

  const layers = [
    ["Layer 1", "Data Minimization", "AI only sees task metadata — never client names, documents, or communications"],
    ["Layer 2", "Compliance Vault", "Fernet AES-128 encryption + tamper-evident audit trail"],
    ["Layer 3", "Row-Level Security", "Firm-level data isolation — your data is invisible to other firms"],
    ["Layer 4", "Transport Security", "TLS 1.3, JWT auth, rate limiting, CORS whitelisting"],
    ["Layer 5", "AI Restrictions", "No training on your data. Stateless inference. Human-in-the-loop always."],
  ];

  layers.forEach((layer, i) => {
    const y = 180 + (i * 48);
    s7.insertTextBox(layer[0] + ": " + layer[1], 80, y, 350, 22)
      .getText().getTextStyle()
      .setFontSize(14).setBold(true).setFontFamily("Inter")
      .setForegroundColor(BRAND.emeraldLight);

    s7.insertTextBox(layer[2], 80, y + 22, 750, 20)
      .getText().getTextStyle()
      .setFontSize(11).setFontFamily("Inter")
      .setForegroundColor(BRAND.silver);
  });

  s7.insertTextBox("✅ ABA Model Rule 1.6 Compliant  •  Cleared by Compliance Officer (PRIVACY-SHIELD-001)", 80, 430, 750, 20)
    .getText().getTextStyle()
    .setFontSize(11).setItalic(true).setFontFamily("Inter")
    .setForegroundColor(BRAND.gold);

  // ═══════ SLIDE 8: FINANCIALS ═══════
  const s8 = deck.appendSlide(SlidesApp.PredefinedLayout.BLANK);
  s8.getBackground().setSolidFill(BRAND.darkBg);

  s8.insertTextBox("FINANCIALS", 60, 40, 400, 40)
    .getText().getTextStyle()
    .setFontSize(16).setBold(true).setFontFamily("Inter")
    .setForegroundColor(BRAND.gold);

  s8.insertTextBox("$2,725 Investment → $62,100 Target ARR", 60, 90, 800, 50)
    .getText().getTextStyle()
    .setFontSize(32).setBold(true).setFontFamily("Inter")
    .setForegroundColor(BRAND.white);

  const finMetrics = [
    ["$1,447-2,725", "Total Pilot Investment"],
    ["$62,100", "Target Year 1 ARR"],
    ["2,178%", "Target ROI"],
    ["Month 4", "Break-Even"],
  ];

  finMetrics.forEach((m, i) => {
    const x = 60 + (i * 210);
    s8.insertTextBox(m[0], x, 175, 190, 55)
      .getText().getTextStyle()
      .setFontSize(28).setBold(true).setFontFamily("Inter")
      .setForegroundColor(BRAND.emeraldLight);

    s8.insertTextBox(m[1], x, 235, 190, 25)
      .getText().getTextStyle()
      .setFontSize(12).setFontFamily("Inter")
      .setForegroundColor(BRAND.silver);
  });

  s8.insertTextBox("Revenue Scenarios", 80, 290, 300, 25)
    .getText().getTextStyle()
    .setFontSize(14).setBold(true).setFontFamily("Inter")
    .setForegroundColor(BRAND.white);

  const scenarios = [
    "Conservative:  5 firms  ×  25 seats  ×  $49/mo  =  $14,700 ARR",
    "Target:           15 firms  ×  75 seats  ×  $69/mo  =  $62,100 ARR",
    "Optimistic:      30 firms  ×  200 seats  ×  $99/mo  =  $237,600 ARR",
  ];

  scenarios.forEach((text, i) => {
    const box = s8.insertTextBox(text, 80, 320 + (i * 30), 750, 25);
    box.getText().getTextStyle()
      .setFontSize(13).setFontFamily("Inter")
      .setForegroundColor(i === 1 ? BRAND.gold : BRAND.silver);
  });

  s8.insertTextBox("Budget approved by CFO (CFO-PILOT-001)", 80, 430, 400, 20)
    .getText().getTextStyle()
    .setFontSize(10).setItalic(true).setFontFamily("Inter")
    .setForegroundColor("#666666");

  // ═══════ SLIDE 9: PILOT PLAN ═══════
  const s9 = deck.appendSlide(SlidesApp.PredefinedLayout.BLANK);
  s9.getBackground().setSolidFill(BRAND.darkBg);

  s9.insertTextBox("PILOT PLAN", 60, 40, 400, 40)
    .getText().getTextStyle()
    .setFontSize(16).setBold(true).setFontFamily("Inter")
    .setForegroundColor(BRAND.gold);

  s9.insertTextBox("90-Day Pilot with 5-10 Law Firms", 60, 90, 800, 50)
    .getText().getTextStyle()
    .setFontSize(32).setBold(true).setFontFamily("Inter")
    .setForegroundColor(BRAND.white);

  const timeline = [
    ["Week 1-2", "10-day MVP build (Schema → API → n8n → UI → Test)"],
    ["Week 2-4", "Beta firm outreach: JD Supra, LinkedIn, direct contact"],
    ["Week 4-6", "Onboard first 3-5 firms (free pilot, DPA signed)"],
    ["Week 6-12", "Collect usage data, iterate on feedback, track billable recovery"],
    ["Week 13+", "Convert to paid subscriptions ($49-99/seat/month)"],
  ];

  timeline.forEach((item, i) => {
    const y = 170 + (i * 50);
    s9.insertTextBox(item[0], 80, y, 150, 25)
      .getText().getTextStyle()
      .setFontSize(16).setBold(true).setFontFamily("Inter")
      .setForegroundColor(BRAND.emeraldLight);

    s9.insertTextBox(item[1], 250, y, 600, 30)
      .getText().getTextStyle()
      .setFontSize(14).setFontFamily("Inter")
      .setForegroundColor(BRAND.silver);
  });

  // ═══════ SLIDE 10: CALL TO ACTION ═══════
  const s10 = deck.appendSlide(SlidesApp.PredefinedLayout.BLANK);
  s10.getBackground().setSolidFill(BRAND.emerald);

  s10.insertTextBox("Ready to Eliminate Delegation Friction?", 60, 100, 800, 60)
    .getText().getTextStyle()
    .setFontSize(36).setBold(true).setFontFamily("Inter")
    .setForegroundColor(BRAND.white);

  s10.insertTextBox("Join our exclusive 90-day pilot program.\nFree for the first 5 firms.", 60, 200, 700, 60)
    .getText().getTextStyle()
    .setFontSize(20).setFontFamily("Inter")
    .setForegroundColor(BRAND.gold);

  s10.insertTextBox("✉  Contact: executive@antigravity.ai\n🌐  delegateai.com (coming soon)\n📞  Schedule a 30-minute demo", 80, 310, 600, 80)
    .getText().getTextStyle()
    .setFontSize(16).setFontFamily("Inter")
    .setForegroundColor(BRAND.white);

  s10.insertTextBox("D E L E G A T E   A I\nPowered by Project Aether  •  Antigravity-AI", 60, 430, 500, 40)
    .getText().getTextStyle()
    .setFontSize(12).setFontFamily("Inter")
    .setForegroundColor(BRAND.silver);

  SpreadsheetApp.getUi ? null :
  SlidesApp.getUi().alert(
    "✅ Pitch Deck Generated!\n\n" +
    "10 slides created:\n" +
    "1. Title\n2. Problem\n3. Solution\n4. How It Works\n" +
    "5. Market\n6. Technology\n7. Privacy\n8. Financials\n" +
    "9. Pilot Plan\n10. Call to Action"
  );
}
