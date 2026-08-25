# CCTV / Security Business — Automation Roadmap

A staged blueprint for taking a CCTV sales, installation and AMC business from
Excel + WhatsApp to a single operating system with automation and an AI layer on top.

**Governing rule: don't automate a bad process.** Simplify the process first, then
automate it. Automating today's messy manual flow only produces a messy automated flow.

The target spine every module hangs off:

```
Lead → Quotation → Order → Installation → Invoice → Payment → AMC
```

---

## Phase 0 — Map the business (Week 0, before any software)

Nothing gets built until these thirteen things are written down. This document is the
input to the schema, so vagueness here becomes rework later.

| # | Area | What to capture | Output artefact |
|---|------|-----------------|-----------------|
| 1 | Products | Every camera/DVR/NVR/accessory model, brand, specs | Product master sheet |
| 2 | Suppliers | Vendor list, credit terms, lead times, price lists | Vendor master |
| 3 | Customer types | Residential / shop / office / society / industrial / govt | Segment list |
| 4 | Sales process | How an enquiry becomes an order, stage by stage | Stage diagram |
| 5 | Quotation format | Line items, taxes, terms, validity, approval limits | Quote template |
| 6 | Purchase process | Reorder trigger, PO approval, GRN, returns | PO flow |
| 7 | Installation | Site survey → material issue → install → handover | Job checklist |
| 8 | Service / AMC | Contract types, coverage, response SLA, visit frequency | AMC matrix |
| 9 | Payment collection | Advance %, milestones, credit days, follow-up ladder | Collection policy |
| 10 | Employee structure | Roles, reporting, technician skill levels, territories | Org chart |
| 11 | Accounting | Current books, GST filing, who does what, tools in use | Finance SOP |
| 12 | Marketing | Channels running today, spend, who handles them | Channel list |
| 13 | WhatsApp workflow | Which numbers, who replies, what templates exist | Message inventory |

**Deliverable:** a single "as-is" document plus a "to-be" version where every step that
exists only out of habit has been deleted. Build against the to-be version.

The discovery questionnaire in [Appendix A](#appendix-a--discovery-questionnaire) turns
this table into questions you can answer in a sitting.

---

## Phase 1 — One master database

Replace the parallel Excel files with one database and many modules. Every module reads
the same customer, the same product, the same employee.

### Entity map

```
                    ┌───────────┐
                    │ CUSTOMERS │
                    └─────┬─────┘
                          │
   LEADS ──▶ QUOTATIONS ──▶ ORDERS ──▶ INVOICES ──▶ PAYMENTS
                               │
                               ├──▶ INVENTORY (stock issue / serials)
                               │
                               ├──▶ INSTALLATION (job card)
                               │
                               └──▶ AMC / SERVICE (contract, tickets)

   EMPLOYEES ──▶ ATTENDANCE ──▶ LEAVE ──▶ PAYROLL

   MARKETING ──▶ CAMPAIGN ──▶ LEAD ──▶ SALE ──▶ REVENUE
```

### Core tables and the fields that actually matter

| Table | Key fields | Notes |
|-------|-----------|-------|
| `customers` | id, name, type, phone, whatsapp, gstin, billing_addr, site_addrs[], source_campaign_id | One customer may have many sites |
| `products` | sku, brand, model, category, spec_json, purchase_price, mrp, sale_price, hsn, gst_rate, warranty_months | HSN + GST rate live here, not in the invoice |
| `vendors` | id, name, gstin, credit_days, contact, price_list_ref | |
| `leads` | id, customer_id, source, channel, campaign_id, stage, owner_id, next_action_at, lost_reason | `next_action_at` drives every follow-up automation |
| `quotations` | id, lead_id, version, line_items[], subtotal, gst, total, valid_till, status, approved_by | Version, never overwrite |
| `orders` | id, quotation_id, customer_id, site_id, value, advance_received, status | Created only from an accepted quote |
| `inventory` | sku, warehouse, qty_on_hand, qty_reserved, reorder_level | Reservation on order, deduction on issue |
| `serials` | serial_no, sku, status, order_id, site_id, warranty_end | Per-unit traceability for warranty claims |
| `installations` | id, order_id, technician_id, scheduled_at, checklist_json, photos[], completed_at, handover_signed | |
| `invoices` | id, order_id, number, date, line_items[], gst_split, total, due_date, status | |
| `payments` | id, invoice_id, mode, amount, received_at, ref | Partial payments allowed |
| `amc_contracts` | id, customer_id, site_id, type, start, end, visits_per_year, value, status | Expiry drives renewal automation |
| `service_tickets` | id, contract_id/site_id, raised_at, issue, priority, technician_id, sla_due_at, closed_at | |
| `employees` | id, name, role, skills[], territory, doj, salary_structure_json | |
| `attendance` / `leave` / `payroll` | employee_id, date/period, status, computed components | |
| `campaigns` | id, channel, name, spend, start, end, utm | Joined to leads for attribution |

**Non-negotiables:** one customer record (dedupe on phone), one product master, serial
number tracking on every installed device, and an immutable audit trail on quotations,
invoices and payments.

---

## Phase 2 — The first five automations

Start here, not with the full platform. These five give operational benefit in weeks.

### 1. Lead → Quotation

- **Trigger:** new lead created (web form, WhatsApp, call log, walk-in).
- **Actions:** dedupe against existing customers → assign owner by territory/round-robin
  → send WhatsApp acknowledgement within 60 seconds → set `next_action_at = +1 day`
  → offer a package template (e.g. "4-camera 2MP shop kit") that pre-fills the quote.
- **Manual step kept:** the salesperson confirms the site requirement before sending.
- **Result:** quote out the same day instead of two days later.

### 2. Quotation → Follow-up

- **Trigger:** quotation sent, no status change after 2 days.
- **Ladder:** Day 2 WhatsApp nudge → Day 5 call task to owner → Day 10 revised offer
  → Day 15 mark `lost` with a mandatory reason.
- **Escalation:** any quote above your approval threshold that is idle 7 days pings the owner.
- **Result:** no quotation dies silently; lost reasons become real data.

### 3. Order → Installation

- **Trigger:** order confirmed + advance received.
- **Actions:** reserve stock → generate material issue list with serials → schedule a
  technician by skill, territory and load → WhatsApp the customer the date and technician
  name → push a checklist to the technician's phone (site photos, camera angles, DVR
  config, customer signature) → on completion, auto-create the warranty record and the
  AMC opportunity dated `install_date + 12 months`.
- **Result:** installation quality becomes verifiable, not anecdotal.

### 4. Invoice → Payment reminder

- **Trigger:** invoice due date approaching or crossed.
- **Ladder:** T-3 days polite WhatsApp → due date reminder with payment link →
  T+7 escalation to sales owner → T+15 to management, with an outstanding statement attached.
- **Guardrail:** reminders stop instantly on part-payment and re-calculate on the balance.
- **Result:** receivable days fall without anyone maintaining a follow-up diary.

### 5. AMC → Renewal reminder

- **Trigger:** `amc_contracts.end` minus 45 / 30 / 7 days, and warranty expiry minus 30 days.
- **Actions:** create a renewal lead pre-filled with last year's value → WhatsApp the
  customer → task to the account owner → if not renewed by expiry, move the site to a
  "lapsed" list for a quarterly win-back campaign.
- **Result:** AMC becomes recurring revenue instead of a lucky renewal.

**Design rule for all five:** every automation is `trigger → condition → action → owner
→ escalation`. If no human owns the outcome, the automation just generates noise.

---

## Phase 3 — Finance and HR

Only once sales and operations run on the system.

### Finance

| Area | Automate | Keep manual |
|------|----------|-------------|
| Sales | Invoice from order, GST split by HSN, e-invoice/e-way where applicable | Credit-note approvals |
| Purchases | PO from reorder level, GRN matching, vendor bill capture | Vendor negotiation, price revisions |
| Expenses | Category rules, recurring entries, technician travel claims | Approval above threshold |
| Receivables | Ageing buckets, reminder ladder, statement generation | Settlement decisions, write-offs |
| Payables | Due-date calendar, payment batching | Payment release |
| Cash / bank | Statement import, auto-reconciliation of matched refs | Unmatched item resolution |
| P&L | Monthly close pack, product-wise and segment-wise margin | Provisions, adjustments |
| GST | GSTR-1 / 3B data prep, ITC mismatch flags | Filing sign-off by the accountant |

The accountant validates the chart of accounts, tax rates and payroll rules **before**
the first automated entry is posted. Retro-fixing books is far more expensive than a
week of upfront validation.

### HR

Employee master → attendance (geo-tagged check-in at site for technicians) → leave →
payroll (with incentive rules from actual closed orders) → performance (jobs completed,
SLA hit rate, revenue attributed) → document expiry alerts (ID, licences, training certs).

Technician productivity is the metric that matters: jobs per day, first-time-fix rate,
revisit rate, SLA compliance.

---

## Phase 4 — Marketing and attribution

Connect Instagram, Facebook, YouTube, Google Business Profile and WhatsApp to the CRM.

```
Content → Campaign → Social channel → Enquiry → CRM lead → Quotation → Sale → Revenue
```

The mechanism that makes this real: every ad, post, listing and WhatsApp entry point
carries a distinct source tag (UTM, WhatsApp deep-link keyword, or a channel-specific
number). The tag rides on the lead, survives into the order, and lands on the invoice.
Without that tag, attribution is guesswork.

**What you can then answer honestly:** cost per lead and cost per *closed customer* by
channel, which content produces enquiries that actually convert, and which channel
brings the higher-value AMC customers rather than just the most enquiries.

Google Business Profile reviews deserve their own automation: a review request goes out
automatically 3 days after a completed installation, and any review below 4 stars raises
a service ticket instead of a reply.

---

## Phase 5 — The AI layer

AI goes on top of clean business data, never instead of it. Each question below is
answerable only if the data listed beside it is being captured correctly.

| Question you want to ask | Data it depends on |
|--------------------------|--------------------|
| "What is my sales today?" | Invoices with reliable dates and statuses |
| "Who needs a payment reminder?" | Invoice due dates + payments, including partials |
| "Which quotation has not been followed up?" | `quotations.status` + `leads.next_action_at` |
| "Which technician is overloaded?" | Installation + ticket assignments with time estimates |
| "Which CCTV product is selling the most?" | Invoice line items against the product master |
| "Which AMC expires this month?" | `amc_contracts.end` maintained on every contract |
| "How much did social media generate?" | Campaign tag carried lead → order → invoice |
| "What is my estimated profit this month?" | Purchase price on products + expenses booked |

Practical shape: a natural-language layer over read-only views of the database, returning
a number *and* the underlying rows so answers can be checked. Give it read access first.
Only after it has been trusted for a quarter should AI be allowed to trigger actions
(drafting a follow-up message, proposing a technician schedule) — and then with a human
approving each action.

A separate track, once the above is stable: AI on the CCTV footage itself (intrusion
alerts, people counting, camera-health monitoring) sold as a value-added service. That is
a product line, not a back-office automation — don't let it compete for Phase 1 attention.

---

## The 30-day MVP

Build an MVP, not the whole platform. Each week ships something usable.

| Week | Build | Done when |
|------|-------|-----------|
| **1** | Database, user accounts and roles, product/customer/employee masters, dashboard shell | Real master data is loaded and two users can log in with different permissions |
| **2** | CRM: leads, quotation builder with GST, WhatsApp send + follow-up ladder | A real enquiry goes from lead to sent quotation entirely in the system |
| **3** | Inventory with serials, order → installation job card, service tickets, AMC records | One real installation is executed and handed over through the app |
| **4** | Invoicing, payments, payment reminders, AMC renewal alerts, core reports | A month's sales, outstanding and AMC expiry list can be pulled without Excel |

**Acceptance rule for every week:** the team uses it for real work that week. A module
nobody used is not finished, however complete the code looks.

Then expand: HR and payroll, deeper finance and GST, marketing attribution, AI queries,
and finally CCTV video AI.

---

## Who you need

You do not need an IT department to start. You need five roles, one of which is external.

| Role | Responsibility | Commitment |
|------|----------------|------------|
| Owner / manager | Decides workflows, approves the to-be process, breaks ties | Weekly, decisive |
| Data / operations owner | Owns product, customer and employee master data quality | Daily, this is the make-or-break role |
| Accountant | Validates accounts, GST and payroll rules before go-live | Part-time, front-loaded |
| Developer (software + AI) | Builds and integrates | Full-time for the MVP |
| Employees and technicians | Use the system **instead of** parallel manual records | Every day |

The single most common cause of failure is the last row: staff keeping their own
notebook or WhatsApp list "just in case". Parallel records must be actively stopped, not
merely discouraged.

---

## Build vs. buy

| Option | Fits when | Watch out for |
|--------|-----------|---------------|
| Off-the-shelf CRM + accounting, stitched together | You want speed and your process is close to standard | Two customer masters that drift apart; attribution breaks at the seam |
| Open-source ERP (e.g. a CRM/inventory/accounting suite you self-host) with customisation | You want one database and can fund a developer | Customisation debt at upgrade time |
| Fully custom build | Your installation/AMC flow is genuinely unusual | Cost and timeline; you also own the maintenance forever |

Recommendation for a business this shape: one system of record for customers, orders,
stock and invoices; specialised tools only where they clearly win (WhatsApp Business API,
ad platforms, e-invoicing) and always integrated back into the master database. Never let
a second customer master exist.

---

## What should stay manual

Automating these usually costs more than it saves, and damages the customer relationship:

- Site survey and technical requirement design.
- Price negotiation and discount approval beyond a set band.
- Complaint handling for an unhappy customer — automate the *ticket*, not the *conversation*.
- Vendor selection and credit-term negotiation.
- Payroll exceptions, disciplinary matters, and final GST filing sign-off.

---

## KPIs the system should show from day one

| Area | Metric |
|------|--------|
| Sales | Leads by source, lead-to-quote %, quote-to-order %, average order value |
| Operations | Installations per technician per day, first-time-fix rate, SLA compliance |
| Finance | Receivable days, overdue ageing, gross margin by product category |
| Recurring | AMC renewal rate, active contract value, lapsed sites |
| Marketing | Cost per lead and cost per closed customer, by channel |

---

## Anti-patterns to avoid

1. **Automating the mess.** Simplify first (Phase 0), then build.
2. **Big-bang launch.** Ship weekly; a module nobody used is not finished.
3. **Two masters.** The moment customer or product data lives in two places, every report becomes arguable.
4. **Automations without an owner.** Every trigger needs a human accountable for the outcome.
5. **AI before clean data.** AI on inconsistent data produces confident wrong answers, which is worse than no answer.
6. **Skipping the accountant.** Tax and payroll rules validated after go-live means re-doing the books.

---

## Appendix A — Discovery questionnaire

Answer these and the blueprint above becomes a concrete build plan: exactly what to
automate, what to buy, what to keep manual, and in what order.

**Sales**
1. How many enquiries per month, and through which channels?
2. Who prepares quotations today, and how long does it take?
3. What is your quote-to-order conversion, even roughly?
4. What discount can a salesperson give without approval?

**Operations**
5. How many installations per month, and how many technicians?
6. Do you track serial numbers of installed devices today?
7. What is the installation handover process — is anything signed?
8. How many service calls per month, and what response time do you promise?

**AMC**
9. How many active AMC contracts, and what is the renewal rate?
10. How is an AMC priced — flat, per camera, or per visit?

**Finance**
11. What advance do you take, and what credit days do you give?
12. What is your current outstanding, and the oldest unpaid invoice?
13. Who files GST, and using which software?

**People**
14. How many employees, by role?
15. How is technician attendance recorded today?
16. Are there incentives linked to sales or job completion?

**Systems**
17. Which tools are in use today (Excel, Tally, WhatsApp, anything else)?
18. Whose WhatsApp number do customers message, and who replies?
19. What is your monthly marketing spend, by channel?
20. What is the one report you wish you could see every morning?
