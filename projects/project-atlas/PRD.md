# Project Atlas — Physical Asset Intelligence Platform

*Product Requirements Document*

## Framing

If I were starting this company today, I would not build a scraper or an arbitrage tool. I would build **Palantir meets Bloomberg meets Zillow — for physical assets.**

The equipment vertical is the beachhead, not the business. The real company becomes the operating system for buying, selling, financing, transporting, valuing, and managing every physical asset in the world.

## Executive Summary

Project Atlas is an AI-native intelligence platform that continuously ingests, normalizes, values, predicts, and recommends profitable transactions across global physical asset markets.

Unlike marketplace aggregators or auction websites, Atlas becomes an autonomous decision engine that answers one question:

> **What should I buy today to maximize risk-adjusted profit?**

The platform continuously analyzes millions of listings, historical sales, freight costs, repair estimates, macroeconomic indicators, regional demand, seasonality, dealer inventory, financing costs, and user behavior to produce actionable investment recommendations.

The long-term vision is to become the **Bloomberg Terminal for alternative physical assets.**

## Vision Statement

Every physical asset has a market value. Very few have an accurate market value.

Atlas continuously discovers, predicts, and monetizes pricing inefficiencies before the market recognizes them.

## Mission

Help every dealer, contractor, investor, rental company, auction house, fleet operator, and entrepreneur make dramatically better purchasing decisions through predictive intelligence.

## North Star Metric

**Annual Gross Merchandise Value (GMV) influenced by Atlas recommendations.**

Not page views. Not searches. Money moved.

## Success Metrics

### Year One
- 100,000 listings/day
- 25 marketplaces
- 100,000 sold transactions
- 5,000 active users
- $50M influenced purchases

### Year Three
- 12 million listings/day
- 150 marketplaces
- 50 countries
- $5B influenced purchases
- Marketplace launched
- Embedded financing

### Year Five
- Every major equipment category: vehicle markets, industrial equipment, medical equipment, aircraft, marine, commercial kitchens, manufacturing, construction, farm, military surplus
- Global valuation index

## Customer Personas

| Persona | Needs |
|---|---|
| Professional Flippers | Highest ROI, fast turnover, low risk |
| Equipment Dealers | Inventory sourcing, pricing, market intelligence |
| Contractors | Lowest acquisition cost, replacement recommendations, lifecycle forecasting |
| Rental Companies | Fleet optimization, disposition timing, residual value prediction |
| Investors | Alternative asset opportunities, portfolio optimization, yield forecasting |
| Banks | Collateral valuation, recovery estimates, risk analysis |
| Auction Houses | Reserve recommendations, expected hammer price, buyer targeting |

## User Journey

Morning → Atlas scans 4.8 million listings overnight → AI identifies 17 opportunities → user opens dashboard → three BUY NOW alerts → one-click transportation quote → financing pre-approved → inspection scheduled → purchase completed → platform creates resale listing → asset sold → platform records realized profit → model retrains.

## Core Platform Modules

### 1. Global Listing Intelligence
**Purpose:** Collect every listing.
**Features:** Marketplace crawlers, dealer inventory, government auctions, liquidations, rental fleet sales, private listings, international exchanges, VIN decoding, duplicate detection, image fingerprinting, language translation, currency normalization.

### 2. Market Intelligence Engine
**Purpose:** Understand the market.
**Inputs:** Historical sales, inventory, weather, interest rates, housing permits, crop prices, freight, fuel, Google Trends, dealer inventory age, regional demand, construction starts, economic indicators.
**Outputs:** Demand forecasts, supply forecasts, seasonality, regional pricing, future value.

### 3. AI Valuation Engine
**Purpose:** Predict true value.
**Outputs:** Expected resale, forced liquidation, dealer wholesale, retail, confidence interval, depreciation curve, price history, future value.

### 4. Opportunity Engine
**Purpose:** Generate recommendations.
**Produces:** Buy Score, ROI, profit, expected sale time, capital efficiency, risk, confidence, regional arbitrage, exit strategy.

### 5. Autonomous Agent
**Purpose:** Execute transactions.
**Can:** Negotiate, request inspection, book transport, arrange financing, generate listings, respond to buyers, schedule pickup, update CRM.

### 6. Portfolio Intelligence
**Purpose:** Optimize capital.
**Shows:** Cash utilization, inventory aging, expected profit, exposure, geographic diversification, category diversification, portfolio VaR.

### 7. Transportation Intelligence
**Purpose:** Lowest shipping cost.
**Features:** Carrier marketplace, backhaul optimization, hotshot, LTL, FTL, international, live pricing.

### 8. Repair Intelligence
**Purpose:** Estimate refurbishment.
**Uses:** Vision AI, known failures, labor databases, parts catalogs, repair history.
**Outputs:** Repair estimate, ROI, recommended repairs.

### 9. Marketplace (Phase Four)
Users buy, sell, finance, transport, insure, inspect — one ecosystem.

## AI Architecture

**Computer Vision** — detect rust, leaks, wear (tire, cab, bucket), hydraulic leaks, frame damage, engine smoke.

**NLP** — reads descriptions, maintenance logs, titles, invoices, PDFs, service history, dealer comments.

**Time Series** — predicts future pricing, demand, seasonality, inventory, residual value.

**Graph AI** — models relationships between dealers, owners, fleets, rental companies, manufacturers, and geographic movement.

**Reinforcement Learning** — learns best bid, best timing, best negotiation, best exit.

## Competitive Landscape

Today's market is fragmented across marketplaces, auction houses, dealer inventory systems, valuation software, freight brokers, inspection services, financing providers, and CRMs.

Atlas is all of the above, plus prediction, plus execution, plus automation.

## Revenue Model

**Subscription tiers**
- Consumer: $49/month
- Professional: $199/month
- Dealer: $999/month
- Enterprise: custom

**Transaction & referral fees**
- Marketplace fees: 1%
- Transport referral
- Insurance referral
- Inspection referral
- Financing referral
- Advertising

**Data & licensing**
- API access
- Market Intelligence
- Residual Value Index
- Dealer Analytics
- OEM licensing
- Bank licensing
- Fleet licensing
- Government licensing

## Flywheel

Listings → predictions → users buy → users repair → users transport → users sell → real transaction data → better models → better predictions → more users → more data → better models. Repeat forever.

## Technical Stack

**Frontend**
- React + Next.js
- Native iOS and Android apps
- Interactive maps and portfolio dashboards

**Backend**
- Kubernetes microservices
- Python + Go
- GraphQL API
- Event-driven architecture with Kafka

**Data Platform**
- PostgreSQL for transactional data
- ClickHouse for analytics
- Neo4j for relationship graphs
- Object storage for images and documents
- Vector database for semantic search and AI retrieval

**AI Layer**
- Vision models for image assessment
- Large language models for document understanding
- Gradient-boosted trees and time-series models for valuation
- Reinforcement learning for bidding and pricing strategies

## Long-Term Vision

Deliberately avoid branding this as an "equipment flipping" application — that's the first use case, not the business. The business is Physical Asset Intelligence.

Today it predicts the best skid steer to buy. Tomorrow it predicts the best commercial aircraft lease, construction crane liquidation, MRI resale, restaurant kitchen acquisition, or data center GPU refresh.

If executed well, Atlas becomes the default intelligence layer for any organization that buys, sells, finances, insures, transports, or manages physical assets. The long-term value comes not from being another marketplace, but from owning the decision engine that participants trust before they commit capital — a more defensible and potentially much larger business than an arbitrage tool alone.

### The Global Physical Asset Index (GPAI)

The most valuable long-run asset Atlas builds may not be the marketplace or the transaction flow — it's the index: an authoritative, continuously updated answer to questions like "are skid steer prices rising faster than inflation," "which regions have the cheapest compact tractors this month," or "which manufacturers hold value best after five years." That index is a natural aggregation of data already schematized here (`regional_demand` over time, `sold_transaction` history) rather than new infrastructure — it becomes buildable once enough of both accumulate, not before. It is explicitly a future direction, not a near-term deliverable: no separate schema exists for it yet, and it should only get one once there's enough real transaction volume flowing through `regional_demand`/`sold_transaction` for an index to mean anything. Its eventual customers — banks, manufacturers, insurers, leasing companies, governments, investment funds, auction houses — are a different buyer than the flippers and dealers the platform serves first.
