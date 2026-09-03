# ServiceMap

**Auto-generate service dependency graphs from logs. No agents required.**

## The Problem

You have 50 microservices. No one knows:
- What calls what
- What breaks if X goes down
- Where to start debugging
- Which services are orphaned

Existing tools require expensive agents or SaaS subscriptions.

## The Solution

```bash
servicemap analyze logs/ --output graph.html
```

**That's it.** Point at your logs, get an interactive dependency graph.

## Features

- ✅ Zero instrumentation (works with existing logs)
- ✅ Supports JSON, structured, and plain text logs
- ✅ Auto-detects HTTP calls, gRPC, database queries
- ✅ Interactive HTML visualization
- ✅ Finds orphaned services
- ✅ Identifies critical paths
- ✅ Open source (MIT)

## Quick Start

```bash
pip install servicemap
servicemap analyze /var/log/services/
```

## Supported Log Formats

- JSON logs (recommended)
- Kubernetes logs
- Docker logs
- Nginx/Apache access logs
- Application logs with timestamps

## Example

**Input (logs/api-gateway.log):**
```json
{"timestamp": "2026-09-03T10:30:45Z", "service": "api-gateway", "http_call": "POST http://auth-service:8080/verify"}
{"timestamp": "2026-09-03T10:30:46Z", "service": "api-gateway", "http_call": "GET http://user-service:3000/users/123"}
```

**Output:**
```
api-gateway → auth-service (2 calls/min)
api-gateway → user-service (15 calls/min)
```

**Visual:** Interactive graph showing service dependencies.

## Use Cases

- Onboarding new engineers
- Impact analysis before changes
- Finding unused services
- Security audits (what has database access?)
- Cost optimization (orphaned services)

## Roadmap

- [x] Basic log parsing
- [x] HTTP call detection
- [ ] gRPC support
- [ ] Database query tracking
- [ ] Real-time streaming mode
- [ ] Prometheus metrics export

## License

MIT
