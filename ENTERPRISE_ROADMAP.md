# SnapDish Enterprise Roadmap - Scale to Millions

## Overview
Enterprise-grade production for SnapDish: 99.99% uptime, auto-scale to millions, SOC2-compliant, cost-optimized (OpenAI batch/flex), zero-downtime deploys.

## Phase 1: Foundation (1 Week)
- [ ] Dockerize backend (`Dockerfile` + `docker-compose.yml`).
- [ ] Deploy staging: AWS ECS/Render + Aurora/ElastiCache.
- [ ] Wire mobile: camera/voice/maps (Mapbox OSM fallback), commerce stubs → Stripe.
- [ ] Colors: Hunger palette (`Colors.ts`).

## Phase 2: Scale & Obs (2-3 Weeks)
- [ ] K8s (EKS): Helm chart, HPA (CPU/reqs), Istio gateway.
- [ ] Obs: OpenTelemetry → Datadog, Prometheus/Grafana.
- [ ] CI/CD: GitHub Actions/ArgoCD blue-green.
- [ ] Commerce: Full endpoints/feed/webhooks, OpenAI certify.

## Phase 3: Prod & Opt (Ongoing)
- [ ] Load test: Locust (10k users).
- [ ] Security: IAM/KMS/WAF/GuardDuty, SOC2 audit.
- [ ] Mobile: EAS prod + CodePush, Firebase analytics.
- [ ] Cost: OpenAI Enterprise, batch jobs.

## Providers
- Cloud: AWS (EKS/Aurora/ElastiCache/API GW).
- Maps: Mapbox Enterprise.
- Commerce: Stripe Connect.
- Obs: Datadog + Grafana.

## Commands
- Local: `docker compose up`
- Deploy: `helm upgrade snapdish ./helm/`
- Mobile: `eas build --profile production --platform all`

