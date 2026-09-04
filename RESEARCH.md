# ServiceMap v2: Proper Research & Planning

## Phase 1: Understanding Real Kubernetes Logs

### Research Questions
1. What log formats do K8s clusters actually produce?
2. How do services log their outbound calls?
3. What's the most common format in production?
4. What tools already parse these successfully?

---

## Log Format Research

### Format 1: kubectl logs (CRI-O/containerd format)
**Source:** `kubectl logs pod-name`

**Structure:**
```json
{
  "log": "<actual log line from container>\\n",
  "stream": "stdout|stderr",
  "time": "2026-09-03T17:30:01.234567890Z"
}
```

**Key insight:** 
- The actual log is INSIDE the `log` field as a string
- Could be JSON, plaintext, or anything
- Need to parse TWICE: outer wrapper, then inner content

**Example:**
```json
{"log":"2026-09-03 INFO calling service foo:8080\\n","stream":"stdout","time":"2026-09-03T17:30:01Z"}
```

### Format 2: Application JSON logs (inside container)
**Source:** Application using structured logging (pino, winston, python-json-logger)

**Structure:**
```json
{
  "timestamp": "2026-09-03T17:30:01.123",
  "severity": "INFO",
  "name": "servicename",
  "message": "doing something"
}
```

**Key insight:**
- Service calls are in `message` field as text
- No structured `target` or `destination` field
- Need to extract from natural language

**Example:**
```json
{"timestamp":"...","severity":"INFO","name":"checkout","message":"calling payment service at payment.default.svc.cluster.local:8080"}
```

### Format 3: Plain text logs
**Source:** Legacy apps, simple logging

**Structure:**
```
2026-09-03 17:30:01 INFO [servicename] message here
```

**Key insight:**
- No structure at all
- Regex only option
- Service name might be in brackets, might not be

### Format 4: Istio/Envoy sidecar logs
**Source:** Service mesh

**Structure:**
```
[2026-09-03T17:30:01Z] "GET /path HTTP/1.1" 200 - via_upstream - "-" 0 1234 15 14 "-" "user-agent" "request-id" "destination.namespace.svc.cluster.local:8080" "10.0.1.5:8080"
```

**Key insight:**
- Fixed positional format
- Destination service in specific position
- Very reliable for dependency mapping
- Only if Istio/service mesh deployed

---

## Service Naming Research

### Kubernetes FQDN format
**Full:** `servicename.namespace.svc.cluster.local`
**Short:** `servicename` (within same namespace)
**With port:** `servicename.namespace.svc.cluster.local:8080`

**Extraction strategy:**
- Split by `.` → take first part
- Example: `payment.default.svc.cluster.local` → `payment`
- Example: `api-gateway-v2.prod.svc.cluster.local` → `api-gateway-v2`

### Common variations:
- `servicename:port` → `servicename`
- `servicename-abc123` (pod name) → `servicename` (strip hash)
- `http://servicename/path` → `servicename`
- IP addresses → skip (can't map to service)

---

## How Services Actually Log Calls

### Researching actual logging patterns

**Question:** Do apps log "calling service X"?

**Answer from research:**
- ❌ Most apps DON'T explicitly log service calls
- ✅ They log business logic: "processing order", "fetching product"
- ✅ Service mesh (Istio/Linkerd) DOES log all calls (sidecar)
- ✅ Some frameworks auto-log HTTP requests

**Implication:**
- Can't rely on application logs alone
- Service mesh logs are better source
- OR need to parse HTTP client libraries' debug logs

### Common logging patterns found:

**Pattern A: Explicit service call (rare)**
```
INFO calling payment service at payment.svc.cluster.local:8080
```

**Pattern B: HTTP client logs (common with debug)**
```
DEBUG HTTP GET http://payment.svc.cluster.local:8080/charge
```

**Pattern C: gRPC client logs**
```
INFO grpc.Dial: connecting to payment.svc.cluster.local:9000
```

**Pattern D: Service mesh (most reliable)**
```
[Envoy] upstream_cluster=payment.default.svc.cluster.local:8080
```

---

## Competing Tools Analysis

### How do existing tools solve this?

**Jaeger/Zipkin:**
- Require instrumentation (OpenTelemetry)
- Trace propagation in code
- NOT log-based

**Datadog/New Relic:**
- Agents installed in cluster
- Parse logs + metrics + traces
- Proprietary parsers

**Kiali (Istio UI):**
- Reads Istio metrics
- Service graph from Envoy data
- Requires service mesh

**Our gap:**
- No tool parses plain K8s logs without instrumentation
- Gap is real BUT logs aren't designed for dependency tracking
- Service mesh is the "right" solution

---

## Reality Check

### Can log-based dependency mapping actually work?

**Challenges discovered:**
1. Apps don't log service calls consistently
2. Logs are designed for debugging, not architecture discovery
3. Service mesh exists specifically for this problem
4. Plain logs are ambiguous (which "payment" service?)

**When it CAN work:**
- ✅ Service mesh deployed (parse Envoy logs)
- ✅ Apps use structured logging with explicit call logs
- ✅ Debugging specific issue (manual log inspection)

**When it WON'T work:**
- ❌ Plain application logs without call logging
- ❌ Teams that don't log outbound calls
- ❌ Need real-time accurate dependency graph

---

## Revised Target Users

### Who actually needs log-based dependency mapping?

**NOT:**
- Teams with service mesh (already solved)
- Teams with APM tools (Datadog, etc.)
- Greenfield projects (can instrument from start)

**YES:**
- Brownfield clusters without instrumentation
- Incident debugging ("what was calling what?")
- Historical analysis of old logs
- Quick ad-hoc dependency check

**Market size:** Smaller than I thought

---

## Decision Point

### Is ServiceMap worth building?

**Arguments FOR:**
- Gap exists for non-instrumented clusters
- Useful for debugging specific incidents
- Simple tool, low maintenance

**Arguments AGAINST:**
- Service mesh is the "right" solution
- Limited accuracy without structured logs
- Small market (teams between "nothing" and "service mesh")
- 2+ days work for uncertain value

### Honest assessment:
- Problem is real
- Solution is hacky (logs aren't designed for this)
- Better solution exists (service mesh)
- Might be useful but not "must-have"

---

## Next: Architecture Design (IF proceeding)

If we build this, here's the right architecture:

### Multi-stage parser

```
┌─────────────────────┐
│   Input: Log File   │
└──────────┬──────────┘
           │
    ┌──────▼──────┐
    │ Stage 1:    │
    │ Detect      │ 
    │ Format      │
    └──────┬──────┘
           │
    ┌──────▼──────────────────────┐
    │ Stage 2: Extract Log Lines  │
    │                              │
    │ K8s wrapper? → unwrap        │
    │ JSON? → parse                │
    │ Plain text? → as-is          │
    └──────┬───────────────────────┘
           │
    ┌──────▼──────────────────────┐
    │ Stage 3: Find Service Calls │
    │                              │
    │ - Regex patterns             │
    │ - Known formats              │
    │ - Custom patterns            │
    └──────┬───────────────────────┘
           │
    ┌──────▼──────────────────────┐
    │ Stage 4: Extract Names      │
    │                              │
    │ - FQDN → short name          │
    │ - host:port → host           │
    │ - IPs → (skip)               │
    └──────┬───────────────────────┘
           │
    ┌──────▼──────────────────────┐
    │ Stage 5: Build Graph        │
    └──────────────────────────────┘
```

### Test each stage independently

**Stage 1 tests:**
- Detect K8s JSON wrapper: ✓/✗
- Detect app JSON: ✓/✗
- Detect plain text: ✓/✗

**Stage 2 tests:**
- Unwrap K8s format: correct inner log?
- Parse app JSON: correct fields?
- Handle malformed: graceful?

... etc for each stage

---

## Status: Research Complete

### What I learned:
1. K8s logs have 4+ formats, need multi-stage parsing
2. Apps rarely log service calls explicitly
3. Service mesh logs are most reliable source
4. Market is smaller than expected (gap between nothing and service mesh)
5. Tool can work but won't be 100% accurate

### Go/No-Go Decision Needed

**Proceed if:**
- We target service mesh logs (Envoy/Istio)
- We accept 60-80% accuracy on app logs
- We position as "debugging tool" not "production monitoring"

**Stop if:**
- Trying to compete with Datadog/service mesh
- Need 90%+ accuracy
- Want large market

**Your call:** Should I proceed with proper architecture, or shelve this?

