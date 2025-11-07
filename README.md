# Starlink Monitor

A lightweight microservice that continuously monitors metrics from your Starlink dish and exposes them via a Prometheus-compatible HTTP endpoint.

## Quick Start

Assuming you have StarLink and are on the same network with it

### Using Docker (Recommended)

Build the image:
```bash
cd starlink-monitor
docker build -t starlink-pingmon .
```

Run the container:
```bash
docker run -d \
  --name starlink-pingmon \
  --network host \
  -e DISH_IP=192.168.100.1 \
  -e POLL_INTERVAL=2 \
  -e ALERT_THRESHOLD=0.1 \
  --restart unless-stopped \
  starlink-pingmon
```

Check the logs:
```bash
docker logs -f starlink-pingmon
```

### Using Python Directly

Install dependencies:
```bash
pip install -r requirements.txt
```

Run the service:
```bash
python pingmon.py
```

## Configuration

Configure the service using environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DISH_IP` | `192.168.100.1` | Starlink dish IP address |
| `DISH_PORT` | `9200` | Starlink dish gRPC port |
| `POLL_INTERVAL` | `2` | Polling interval in seconds |
| `ALERT_THRESHOLD` | `0.1` | Alert threshold (0.0-1.0, where 0.1 = 10% packet loss) |
| `HTTP_PORT` | `9877` | HTTP server port |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

## HTTP Endpoints

### `/metrics`
Prometheus-compatible metrics endpoint.

**Example response:**
```
# HELP starlink_ping_drop_rate_current Current ping drop rate (0.0-1.0)
# TYPE starlink_ping_drop_rate_current gauge
starlink_ping_drop_rate_current 0.0

# HELP starlink_ping_drop_rate_peak Peak ping drop rate observed (0.0-1.0)
# TYPE starlink_ping_drop_rate_peak gauge
starlink_ping_drop_rate_peak 0.15

# HELP starlink_ping_drop_total_seconds Total time with packet loss in seconds
# TYPE starlink_ping_drop_total_seconds counter
starlink_ping_drop_total_seconds 127.0

# HELP starlink_ping_drop_events_total Number of ping drop events
# TYPE starlink_ping_drop_events_total counter
starlink_ping_drop_events_total 8

# HELP starlink_ping_samples_total Total number of samples processed
# TYPE starlink_ping_samples_total counter
starlink_ping_samples_total 3600

# HELP starlink_monitor_last_update_timestamp Unix timestamp of last successful update
# TYPE starlink_monitor_last_update_timestamp gauge
starlink_monitor_last_update_timestamp 1730992345.67

# HELP starlink_monitor_errors_total Total number of errors
# TYPE starlink_monitor_errors_total counter
starlink_monitor_errors_total 0

# HELP starlink_monitor_scrapes_total Total number of metric scrapes
# TYPE starlink_monitor_scrapes_total counter
starlink_monitor_scrapes_total 42

# HELP starlink_monitor_uptime_seconds Uptime of the monitoring service
# TYPE starlink_monitor_uptime_seconds counter
starlink_monitor_uptime_seconds 7200.5
```

### `/health`
Health check endpoint for monitoring and orchestration.

## Metrics Description

| Metric | Type | Description |
|--------|------|-------------|
| `starlink_ping_drop_rate_current` | gauge | Current ping drop rate (0.0-1.0) |
| `starlink_ping_drop_rate_peak` | gauge | Peak ping drop rate observed since startup |
| `starlink_ping_drop_total_seconds` | counter | Total time with any packet loss |
| `starlink_ping_drop_events_total` | counter | Number of transitions into dropping state |
| `starlink_ping_samples_total` | counter | Total samples processed |
| `starlink_monitor_last_update_timestamp` | gauge | Unix timestamp of last successful update |
| `starlink_monitor_errors_total` | counter | Total communication errors with dish |
| `starlink_monitor_scrapes_total` | counter | Total HTTP scrapes of /metrics |
| `starlink_monitor_uptime_seconds` | counter | Service uptime in seconds |

## Prometheus Integration

Add this to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'starlink-pingmon'
    static_configs:
      - targets: ['localhost:9877']
    scrape_interval: 15s
```

### Example PromQL Queries

**Current ping drop percentage:**
```promql
starlink_ping_drop_rate_current * 100
```

**Average drop rate over 5 minutes:**
```promql
rate(starlink_ping_drop_total_seconds[5m]) * 100
```

**Drop events per hour:**
```promql
rate(starlink_ping_drop_events_total[1h]) * 3600
```

**Percentage of time with drops:**
```promql
(starlink_ping_drop_total_seconds / starlink_ping_samples_total) * 100
```

## Grafana Dashboard

Create visualizations using these queries:

1. **Ping Drop Rate (Time Series)**
   - Query: `starlink_ping_drop_rate_current * 100`
   - Unit: Percent (0-100)

2. **Total Drop Time (Stat Panel)**
   - Query: `starlink_ping_drop_total_seconds`
   - Unit: Seconds

3. **Drop Events (Counter)**
   - Query: `starlink_ping_drop_events_total`

4. **Service Health (Stat Panel)**
   - Query: `time() - starlink_monitor_last_update_timestamp < 10`
   - Threshold: < 1 = red, >= 1 = green

## Requirements

- Python 3.7+
- Network access to Starlink dish (typically 192.168.100.1:9200)
- gRPC dependencies (grpcio, protobuf, yagrc)
