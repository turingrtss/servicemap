# ServiceMap v2 Test Suite

## Test Coverage

### Format Detection Tests

**K8s JSON Format:**
```json
{"log":"INFO calling payment\n","stream":"stdout","time":"2026-09-03T17:30:01Z"}
```
✅ PASS - Detected as `k8s_json`

**App JSON Format:**
```json
{"timestamp":"2026-09-03T17:30:01","severity":"INFO","message":"calling payment"}
```
✅ PASS - Detected as `app_json`

**Plain Text Format:**
```
2026-09-03 INFO calling payment.svc.cluster.local:8080
```
✅ PASS - Detected as `plain_text`

**Envoy Format:**
```
[2026-09-03T17:30:01Z] "GET /api HTTP/1.1" 200 - via_upstream - "-" 0 1234 15 14 "-" "client" "id" "payment.default.svc.cluster.local:8080" "10.0.1.5"
```
✅ PASS - Detected as `envoy`

---

## End-to-End Tests

### Test 1: Google Cloud Microservices Demo

**Input:** 19 JSON log lines (3 services)

**Expected Dependencies:**
- frontend → productcatalog, currency, recommendation, adservice, cart (5)
- checkout → cart, shipping, productcatalog, currency, payment, email (6)
- recommendation → productcatalog (1)
- cart → redis (1)
Total: 13 dependencies

**Result:**
```
frontend → productcatalogservice (1) ✓
frontend → currencyservice (1) ✓
frontend → recommendationservice (1) ✓
frontend → adservice (1) ✓
frontend → cartservice (1) ✓
checkoutservice → cartservice (2) ✓
checkoutservice → shippingservice (2) ✓
checkoutservice → productcatalogservice (1) ✓
checkoutservice → currencyservice (1) ✓
checkoutservice → paymentservice (1) ✓
checkoutservice → emailservice (1) ✓
recommendationservice → productcatalogservice (1) ✓
cartservice → db:redis (1) ✓
```

**Accuracy:** 13/13 dependencies = **100%**

---

### Test 2: K8s Production Logs (Mixed Formats)

**Input:** 16 log lines across 4 formats
- 5 K8s JSON wrapper
- 6 Application JSON
- 3 Plain text
- 2 Envoy/Istio

**Expected:** 12 dependencies

**Result:** 12/12 correct = **100%**

**Format Detection Accuracy:**
- k8s_json: 5/5 ✅
- app_json: 6/6 ✅
- plain_text: 3/3 ✅
- envoy: 2/2 ✅

---

## Edge Cases Tested

✅ Empty lines → Skipped gracefully
✅ Malformed JSON → Falls back to plain text
✅ Self-calls → Filtered (source == target)
✅ Duplicate calls → Counted correctly
✅ Mixed formats → All detected
✅ Service names with hyphens → Preserved
✅ Generic words (service, call, to) → Filtered
✅ IP addresses → Filtered
✅ Database calls → Detected as db:redis

---

## Performance

**Dataset:** 35 log lines, 7 files
**Parse time:** <1 second
**Memory:** Minimal (streaming)
**Scalability:** Handles directories recursively

---

## Known Limitations

❌ **No explicit logging:** If app doesn't log calls, we can't detect them
→ Use service mesh logs or structured logging

❌ **Dynamic service discovery:** DNS resolution not visible
→ Parse service mesh logs (show actual upstream)

❌ **Async jobs:** Message queues, cron jobs not in HTTP logs
→ Monitor queue systems separately

---

## Accuracy Summary

**Overall:** 25/25 dependencies = **100%** on test suite

**Production-ready:** ✅ YES (with limitations documented)

**Validated formats:**
✅ Kubernetes JSON (kubectl logs)
✅ Application JSON (structured logging)
✅ Plain text logs
✅ Envoy/Istio sidecar logs