# ServiceMap

**Auto-generate service dependency graphs from Kubernetes logs**

No instrumentation. No agents. Just parse your existing logs.

## Quick Start

```bash
# Install
pip install servicemap  # TODO: publish to PyPI

# Or run directly
python3 servicemap.py /path/to/logs/

# Generate interactive HTML
python3 servicemap.py /path/to/logs/ --format html -o deps.html
```

## What It Does

ServiceMap analyzes Kubernetes and microservice logs to discover service dependencies:

```
frontend → productcatalog, cart, checkout
checkout → payment, shipping, email
cart → redis
```

**No code changes. No agents. Just logs.**

## Supported Log Formats

✅ **Kubernetes JSON** (`kubectl logs` output)
```json
{"log":"calling payment.svc.cluster.local:8080\n","stream":"stdout","time":"2026-09-03T17:30:01Z"}
```

✅ **Application JSON** (structured logging)
```json
{"timestamp":"2026-09-03T17:30:01","severity":"INFO","message":"calling payment service"}
```

✅ **Plain Text**
```
2026-09-03 INFO [frontend] calling payment.svc.cluster.local:8080
```

✅ **Envoy/Istio** (service mesh sidecar logs)
```
[2026-09-03T17:30:01Z] "GET /api HTTP/1.1" 200 ... "payment.default.svc.cluster.local:8080" ...
```

## Validation Results

**Test Suite:** Google Cloud microservices demo + Kubernetes production logs

**Accuracy:** 25/25 dependencies detected = **100%**

**Formats Tested:** K8s JSON (5 logs), App JSON (6 logs), Plain Text (3 logs), Envoy (2 logs)

See [TEST_RESULTS.md](TEST_RESULTS.md) for full validation.

## How It Works

ServiceMap uses a multi-stage parser:

1. **Detect Format** → Identify log type (K8s/App/Plain/Envoy)
2. **Extract Content** → Unwrap K8s JSON, parse application JSON
3. **Find Calls** → Regex patterns for service calls
4. **Extract Names** → `payment.default.svc.cluster.local:8080` → `payment`
5. **Build Graph** → Dependencies + call counts

## Output Formats

**Text (default):**
```
=== SERVICE DEPENDENCIES ===
frontend → productcatalog (5 calls)
frontend → cart (3 calls)
checkout → payment (10 calls)
```

**HTML (interactive):**
```bash
python3 servicemap.py logs/ --format html -o deps.html
```

Opens interactive graph with:
- Drag-and-drop nodes
- Call count labels
- Service statistics

## Use Cases

✅ **Incident debugging** - "What was calling the failed service?"
✅ **Legacy clusters** - No instrumentation? No problem.
✅ **Historical analysis** - Analyze old logs from S3/archives
✅ **Quick checks** - Ad-hoc dependency verification

## Limitations

ServiceMap works best when:
- Services log their outbound calls
- Logs use structured formats (JSON)
- Service mesh deployed (for 100% accuracy)

It **won't** detect:
- Calls not logged by the application
- Dynamic DNS resolution (only sees DNS names)
- Message queues and async jobs

For production monitoring, use service mesh (Istio/Linkerd) or APM (Datadog).

ServiceMap is for **debugging** and **brownfield discovery**.

## Architecture

See [DESIGN.md](DESIGN.md) for problem research and architecture.

See [RESEARCH.md](RESEARCH.md) for Kubernetes log format analysis.

## Contributing

Found a log format we don't support? Open an issue with a sample!

## License

MIT

---

## Why ServiceMap?

**The Problem:** Teams with 20+ microservices lose track of dependencies. Existing tools require instrumentation (Jaeger), agents (Datadog), or service mesh (Kiali).

**The Gap:** No tool works with plain Kubernetes logs.

**ServiceMap:** Parse existing logs. No setup. No agents. Just discovery.

**When to use:**
- Brownfield clusters without instrumentation
- Debugging specific incidents from logs
- Historical dependency analysis
- Quick ad-hoc checks

**When NOT to use:**
- Production monitoring → Use service mesh or APM
- Real-time accuracy → Use distributed tracing
- Greenfield projects → Instrument from day 1

ServiceMap fills the gap between "nothing" and "full observability platform."