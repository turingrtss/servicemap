# ServiceMap: Design Document
**Version:** 1.0  
**Date:** 2026-09-03  
**Status:** Research & Architecture Phase

---

## 1. Problem Research

### 1.1 The Core Problem
Teams with 10+ microservices face a critical knowledge gap: **no one knows what calls what**.

**Real-world pain points** (from research):
- Engineers join, can't understand system architecture
- Changes break unexpected services (hidden dependencies)
- Incident response: "Which services are affected?"
- Circular dependencies discovered during outages
- Orphaned services running (burning money)
- Security audits: "What has database access?"

### 1.2 Current Solutions & Gaps

**Enterprise Tools:**
- **Datadog APM:** $35/host/month + data charges
- **Dynatrace:** $58/host/month (memory-based)
- **New Relic:** Usage-based, complex pricing

**Problems:**
1. **Cost:** $500-5,000+/month for 10-20 services
2. **Requires agents:** Must instrument every service
3. **Setup complexity:** OpenTelemetry, Jaeger config
4. **Vendor lock-in:** Data trapped in proprietary systems

**Open Source Tools:**
- **Jaeger + custom viz** - Requires distributed tracing setup
- **Prometheus service graph** - Needs metrics exporters
- **Manual documentation** - Always out of date

**The Gap:** No tool that works with logs teams already have.

### 1.3 Target Users

**Primary:**
- **Mid-size startups** (10-50 microservices)
- **Cost-conscious teams** (can't afford Datadog)
- **Brownfield systems** (no instrumentation budget)

**Secondary:**
- **DevOps during incidents** (quick dependency check)
- **New engineers onboarding**
- **Security teams** (audit data access)

**Not for:**
- Enterprise with Datadog budget
- Teams with <5 services (not complex enough)
- Greenfield projects (can use Jaeger from day 1)

### 1.4 Market Validation

**Indicators problem is real:**
- Reddit threads: 500+ upvotes on "circular dependency hell"
- Stack Overflow: 3,000+ questions on microservice dependencies
- Blog posts: "Dependency mapping" = top 10 microservice challenges
- Existing tools: 7+ commercial products (market exists)

**What people are paying:**
- Datadog: Thousands of companies at $35-100/host/month
- DIY solutions: 1-2 engineer-weeks building custom tools
- Manual documentation: 5-10 hours/month keeping updated

---

## 2. Solution Design

### 2.1 Core Value Proposition

**"Zero-setup dependency mapping from logs you already have"**

- No agents
- No instrumentation
- No configuration
- Works retroactively (analyze old logs)

### 2.2 Architecture

```
┌─────────────────────────────────────────────────┐
│              ServiceMap CLI                      │
│  (Python 3.8+, stdlib only, single file)        │
└──────────────────┬──────────────────────────────┘
                   │
         ┌─────────▼─────────┐
         │   Log Parser       │
         │                    │
         │ - JSON logs        │
         │ - Structured text  │
         │ - Plain text       │
         │ - K8s logs         │
         └─────────┬──────────┘
                   │
         ┌─────────▼─────────┐
         │  Call Extractor    │
         │                    │
         │ - HTTP (regex)     │
         │ - gRPC (regex)     │
         │ - DB queries       │
         │ - Message queues   │
         └─────────┬──────────┘
                   │
         ┌─────────▼─────────┐
         │  Graph Builder     │
         │                    │
         │ - Node: service    │
         │ - Edge: dependency │
         │ - Weight: call cnt │
         └─────────┬──────────┘
                   │
         ┌─────────▼─────────┐
         │  Output Generator  │
         │                    │
         │ - Text (terminal)  │
         │ - HTML (vis.js)    │
         │ - JSON (CI/CD)     │
         │ - DOT (Graphviz)   │
         └────────────────────┘
```

### 2.3 Technical Decisions

**Language:** Python 3.8+
- **Why:** Ubiquitous on servers, no compilation, easy log parsing
- **Not:** Go (harder regex), Node (not default on servers)

**Dependencies:** None (stdlib only)
- **Why:** `pip install servicemap` works everywhere
- **Not:** vis.js (bundled in HTML output), pandas (overkill)

**Data Storage:** In-memory only
- **Why:** Fast, simple, no database setup
- **Limitation:** Max ~100k log lines per run (sufficient for most)

**Output Formats:**
1. **Text** - Quick CLI check
2. **HTML** - Interactive graph (vis.js CDN)
3. **JSON** - CI/CD integration
4. **DOT** - Graphviz for presentations

### 2.4 Detection Algorithms

**HTTP Calls:**
```python
# Pattern: GET/POST http://service-name:port/path
HTTP_PATTERN = r'(GET|POST|PUT|DELETE)\s+https?://([^:/\s]+)(?::(\d+))?'
```

**gRPC Calls:**
```python
# Pattern: grpc://service-name:port/Method
GRPC_PATTERN = r'grpc://([^:/\s]+)(?::(\d+))?/([^\s]+)'
```

**Database Queries:**
```python
# Extract table names from SQL
DB_PATTERN = r'(SELECT|INSERT|UPDATE|DELETE).+?FROM\s+(\w+)'
# Node: db:table_name
```

**Message Queues:**
```python
# RabbitMQ/Kafka patterns
QUEUE_PATTERN = r'(publish|consume|send|receive).+?(queue|topic):\s*(\w+)'
```

### 2.5 Edge Cases & Limitations

**What it handles:**
- ✅ HTTP/HTTPS calls
- ✅ gRPC
- ✅ Database queries
- ✅ Common log formats (JSON, K8s, syslog)
- ✅ Service name extraction from hostnames

**What it doesn't:**
- ❌ Real-time streaming (batch only)
- ❌ Performance metrics (call latency)
- ❌ Error rates (just dependency graph)
- ❌ AWS Lambda/serverless (no logs to parse)
- ❌ Non-logged calls (code instrumentation needed)

**Assumptions:**
- Services log their outbound calls
- Log format is somewhat structured
- Service names are in hostnames/logs

---

## 3. Validation Plan

### 3.1 Testing Strategy

**Phase 1: Synthetic Tests**
- ✅ Demo logs (already done)
- Parse 10 different log formats
- Handle edge cases (malformed logs, missing fields)

**Phase 2: Real-World Logs** (CRITICAL - not done yet)
1. **Open-source projects with public logs**
   - Kubernetes example logs
   - Istio service mesh logs
   - Spring Boot microservice demos

2. **Ask for real logs** (anonymized)
   - Reddit: /r/devops, /r/microservices
   - HN: "Show HN: Need sample microservice logs for testing"
   - Discord: DevOps communities

3. **Run on production** (with permission)
   - Offer free analysis to 5 companies
   - Generate their dependency graphs
   - Get feedback

### 3.2 Success Metrics

**Functional:**
- Detects 90%+ of actual service calls (vs ground truth)
- <5% false positives (fake dependencies)
- Works on 5+ different log formats

**Usability:**
- Install + run < 2 minutes
- Output is immediately useful
- No configuration needed

**Market:**
- 10+ companies say "this solves my problem"
- 3+ willing to pay if it was SaaS
- 100+ GitHub stars in first month

### 3.3 Validation Checklist

**Before any launch announcement:**
- [ ] Tested on 5+ real production log sources
- [ ] Accuracy >90% vs manual dependency audit
- [ ] Handles at least 3 log formats (JSON, plaintext, K8s)
- [ ] HTML output renders correctly
- [ ] README has real screenshots (not demo)
- [ ] 2-3 case studies: "Found X unknown dependencies"

---

## 4. Risks & Mitigations

### 4.1 Technical Risks

**Risk:** Log formats too varied to parse reliably
**Mitigation:** Start with JSON (most common), add formats iteratively
**Backup:** Let users specify regex patterns in config file

**Risk:** Service names not in logs
**Mitigation:** Document requirement, provide examples of good logging
**Backup:** Manual service name mapping via config

**Risk:** Performance on large log files
**Mitigation:** Stream processing, don't load all in memory
**Backup:** Chunk processing with progress bar

### 4.2 Market Risks

**Risk:** Teams already have solutions
**Mitigation:** Research shows gap exists, but verify with real users
**Backup:** Pivot to complementary tool (enrich Jaeger with log analysis)

**Risk:** Problem not painful enough to adopt
**Mitigation:** Test with 10 companies before heavy investment
**Backup:** Position as onboarding tool, not ops tool

**Risk:** Hard to monetize (seems too simple)
**Mitigation:** Start open source, build credibility
**Backup:** SaaS version with real-time + alerting

---

## 5. Next Steps

### Immediate (before coding more):
1. **Get real logs** - Reddit/HN post asking for samples
2. **Test accuracy** - Parse 3-5 real log sources
3. **Interview users** - 5 companies with 10+ microservices
4. **Document gaps** - What doesn't work?

### Only after validation:
5. Build missing features (based on feedback)
6. Create launch materials (with real proof)
7. Post to HN/Reddit (with case studies)
8. Consider monetization (if adoption high)

---

## 6. Decision Gate

**Go/No-Go criteria:**
- **GO if:** 3+ real companies say "this works and is useful"
- **NO-GO if:** Accuracy <80% or logs too inconsistent
- **PIVOT if:** Problem exists but solution approach wrong

**Current status:** ⚠️ BLOCKED on real-world validation

---

**Next action:** Get real microservice logs to test against.

