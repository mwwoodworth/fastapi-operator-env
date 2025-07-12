# Observability

This project exposes Prometheus metrics under `/metrics`. Tracing can be enabled using OpenTelemetry.

## OpenTelemetry setup

Set the `OTEL_EXPORTER_OTLP_ENDPOINT` environment variable to the OTLP collector URL. When defined, `main.py` calls `observability.init_tracing` to configure the OpenTelemetry SDK and patch libraries with `aws-xray-sdk`.

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT="http://grafana-agent.grafana:4318"
```

## Grafana Cloud Agent Helm snippet

Deploy the Grafana Cloud Agent with an OTLP receiver:

```yaml
agent:
  config:
    traces:
      configs:
        - name: default
          receivers:
            otlp:
              protocols:
                grpc:
                http:
          remote_write:
            - endpoint: "https://tempo-us-central1.grafana.net/otlp"
              basic_auth:
                username: "$GRAFANA_CLOUD_ID"
                password: "$GRAFANA_CLOUD_API_KEY"
```

## Sample Grafana dashboard

Import `grafana_dashboard.json` into Grafana to visualize task metrics.
