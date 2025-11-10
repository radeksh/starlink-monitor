#!/usr/bin/env python3
"""
Starlink Ping Drop Monitoring Microservice

Continuously monitors ping_drop metrics from Starlink dish and exposes
Prometheus-compatible metrics via HTTP endpoint.
"""

import os
import sys
import time
import signal
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime
from typing import Optional

from starlink_client import StarlinkClient


# Configuration from environment variables
DISH_IP = os.getenv("DISH_IP", "192.168.100.1")
DISH_PORT = os.getenv("DISH_PORT", "9200")
POLL_INTERVAL = float(os.getenv("POLL_INTERVAL", "2"))
ALERT_THRESHOLD = float(os.getenv("ALERT_THRESHOLD", "0.1"))
HTTP_PORT = int(os.getenv("HTTP_PORT", "9877"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MetricsCollector:
    """Collects and stores ping drop metrics."""

    def __init__(self):
        self.lock = threading.Lock()
        self.reset_metrics()
        self.last_counter: Optional[int] = None
        self.start_time = time.time()

    def reset_metrics(self):
        """Reset all metrics to initial state."""
        self.current_drop_rate = 0.0
        self.peak_drop_rate = 0.0
        self.total_drop_time = 0.0
        self.total_samples = 0
        self.drop_events = 0
        self.last_update = time.time()
        self.last_was_dropping = False
        self.errors_total = 0
        self.scrapes_total = 0

        # New metrics
        self.pop_ping_latency_ms = 0.0
        self.downlink_throughput_bps = 0.0
        self.uplink_throughput_bps = 0.0
        self.gps_sats = 0
        self.gps_valid = False
        self.obstruction_fraction = 0.0
        self.obstruction_time = 0.0
        self.snr_above_noise_floor = False
        self.boresight_azimuth_deg = 0.0
        self.boresight_elevation_deg = 0.0
        self.uptime_seconds = 0
        self.eth_speed_mbps = 0
        self.hardware_version = "unknown"
        self.software_version = "unknown"
        self.country_code = "unknown"

    def update(self, drop_rate: float, history_drops: list, status: dict = None):
        """
        Update metrics with new data.

        Args:
            drop_rate: Current drop rate (0.0-1.0)
            history_drops: List of historical drop rates
            status: Dictionary with additional status metrics
        """
        with self.lock:
            self.current_drop_rate = drop_rate
            self.last_update = time.time()

            # Update peak
            if drop_rate > self.peak_drop_rate:
                self.peak_drop_rate = drop_rate

            # Process history samples
            for rate in history_drops:
                self.total_samples += 1

                # Add to total drop time (each sample is 1 second)
                if rate > 0:
                    self.total_drop_time += 1.0

                # Count drop events (transitions from no-drop to drop)
                is_dropping = rate > 0
                if is_dropping and not self.last_was_dropping:
                    self.drop_events += 1
                self.last_was_dropping = is_dropping

            # Update additional metrics from status
            if status:
                self.pop_ping_latency_ms = status.get("pop_ping_latency_ms", 0.0)
                self.downlink_throughput_bps = status.get("downlink_throughput_bps", 0.0)
                self.uplink_throughput_bps = status.get("uplink_throughput_bps", 0.0)
                self.gps_sats = status.get("gps_sats", 0)
                self.gps_valid = status.get("gps_valid", False)
                self.obstruction_fraction = status.get("obstruction_fraction", 0.0)
                self.obstruction_time = status.get("obstruction_time", 0.0)
                self.snr_above_noise_floor = status.get("snr_above_noise_floor", False)
                self.boresight_azimuth_deg = status.get("boresight_azimuth_deg", 0.0)
                self.boresight_elevation_deg = status.get("boresight_elevation_deg", 0.0)
                self.uptime_seconds = status.get("uptime_s", 0)
                self.eth_speed_mbps = status.get("eth_speed_mbps", 0)
                self.hardware_version = status.get("hardware_version", "unknown")
                self.software_version = status.get("software_version", "unknown")
                self.country_code = status.get("country_code", "unknown")

            # Check for alerts
            if drop_rate > ALERT_THRESHOLD:
                logger.warning(
                    f"ALERT: High ping drop detected: {drop_rate*100:.2f}% "
                    f"(threshold: {ALERT_THRESHOLD*100:.1f}%)"
                )

    def increment_errors(self):
        """Increment error counter."""
        with self.lock:
            self.errors_total += 1

    def increment_scrapes(self):
        """Increment scrape counter."""
        with self.lock:
            self.scrapes_total += 1

    def get_metrics(self) -> str:
        """
        Generate Prometheus-format metrics.

        Returns:
            Metrics in Prometheus text format
        """
        with self.lock:
            uptime = time.time() - self.start_time
            gps_valid_int = 1 if self.gps_valid else 0
            snr_int = 1 if self.snr_above_noise_floor else 0

            metrics = f"""# HELP starlink_ping_drop_rate_current Current ping drop rate (0.0-1.0)
# TYPE starlink_ping_drop_rate_current gauge
starlink_ping_drop_rate_current {self.current_drop_rate}

# HELP starlink_ping_drop_rate_peak Peak ping drop rate observed (0.0-1.0)
# TYPE starlink_ping_drop_rate_peak gauge
starlink_ping_drop_rate_peak {self.peak_drop_rate}

# HELP starlink_ping_drop_total_seconds Total time with packet loss in seconds
# TYPE starlink_ping_drop_total_seconds counter
starlink_ping_drop_total_seconds {self.total_drop_time}

# HELP starlink_ping_drop_events_total Number of ping drop events (transitions to dropping state)
# TYPE starlink_ping_drop_events_total counter
starlink_ping_drop_events_total {self.drop_events}

# HELP starlink_ping_samples_total Total number of samples processed
# TYPE starlink_ping_samples_total counter
starlink_ping_samples_total {self.total_samples}

# HELP starlink_pop_ping_latency_ms Round-trip latency to Starlink Point of Presence in milliseconds
# TYPE starlink_pop_ping_latency_ms gauge
starlink_pop_ping_latency_ms {self.pop_ping_latency_ms}

# HELP starlink_downlink_throughput_bps Current downlink (download) throughput in bits per second
# TYPE starlink_downlink_throughput_bps gauge
starlink_downlink_throughput_bps {self.downlink_throughput_bps}

# HELP starlink_uplink_throughput_bps Current uplink (upload) throughput in bits per second
# TYPE starlink_uplink_throughput_bps gauge
starlink_uplink_throughput_bps {self.uplink_throughput_bps}

# HELP starlink_gps_satellites Number of GPS satellites currently tracked
# TYPE starlink_gps_satellites gauge
starlink_gps_satellites {self.gps_sats}

# HELP starlink_gps_valid GPS lock status (1=valid, 0=invalid)
# TYPE starlink_gps_valid gauge
starlink_gps_valid {gps_valid_int}

# HELP starlink_obstruction_fraction Fraction of time the dish view is obstructed (0.0-1.0)
# TYPE starlink_obstruction_fraction gauge
starlink_obstruction_fraction {self.obstruction_fraction}

# HELP starlink_obstruction_time_seconds Total time obstructed in seconds
# TYPE starlink_obstruction_time_seconds gauge
starlink_obstruction_time_seconds {self.obstruction_time}

# HELP starlink_snr_above_noise_floor Signal-to-noise ratio quality indicator (1=good, 0=poor)
# TYPE starlink_snr_above_noise_floor gauge
starlink_snr_above_noise_floor {snr_int}

# HELP starlink_boresight_azimuth_degrees Dish boresight azimuth angle in degrees
# TYPE starlink_boresight_azimuth_degrees gauge
starlink_boresight_azimuth_degrees {self.boresight_azimuth_deg}

# HELP starlink_boresight_elevation_degrees Dish boresight elevation angle in degrees
# TYPE starlink_boresight_elevation_degrees gauge
starlink_boresight_elevation_degrees {self.boresight_elevation_deg}

# HELP starlink_uptime_seconds Device uptime in seconds
# TYPE starlink_uptime_seconds gauge
starlink_uptime_seconds {self.uptime_seconds}

# HELP starlink_eth_speed_mbps Ethernet link speed in Mbps
# TYPE starlink_eth_speed_mbps gauge
starlink_eth_speed_mbps {self.eth_speed_mbps}

# HELP starlink_info Static device information
# TYPE starlink_info gauge
starlink_info{{hardware_version="{self.hardware_version}",software_version="{self.software_version}",country_code="{self.country_code}"}} 1

# HELP starlink_monitor_last_update_timestamp Unix timestamp of last successful update
# TYPE starlink_monitor_last_update_timestamp gauge
starlink_monitor_last_update_timestamp {self.last_update}

# HELP starlink_monitor_errors_total Total number of errors communicating with dish
# TYPE starlink_monitor_errors_total counter
starlink_monitor_errors_total {self.errors_total}

# HELP starlink_monitor_scrapes_total Total number of metric scrapes
# TYPE starlink_monitor_scrapes_total counter
starlink_monitor_scrapes_total {self.scrapes_total}

# HELP starlink_monitor_uptime_seconds Uptime of the monitoring service in seconds
# TYPE starlink_monitor_uptime_seconds counter
starlink_monitor_uptime_seconds {uptime}
"""
            return metrics


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP handler for serving metrics."""

    def log_message(self, format, *args):
        """Override to use our logger."""
        logger.debug(f"{self.address_string()} - {format % args}")

    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/metrics":
            self.server.collector.increment_scrapes()
            metrics = self.server.collector.get_metrics()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.end_headers()
            self.wfile.write(metrics.encode())

        elif self.path == "/health":
            # Check if we've received data recently (within 3x poll interval)
            collector = self.server.collector
            with collector.lock:
                time_since_update = time.time() - collector.last_update
                healthy = time_since_update < (POLL_INTERVAL * 3)

            if healthy:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"healthy"}')
            else:
                self.send_response(503)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"unhealthy","reason":"no recent updates"}')

        else:
            self.send_response(404)
            self.end_headers()


def monitoring_loop(collector: MetricsCollector, shutdown_event: threading.Event):
    """
    Main monitoring loop that polls Starlink dish.

    Args:
        collector: MetricsCollector instance
        shutdown_event: Event to signal shutdown
    """
    dish_target = f"{DISH_IP}:{DISH_PORT}"
    logger.info(f"Starting monitoring loop for {dish_target}")
    logger.info(f"Poll interval: {POLL_INTERVAL}s, Alert threshold: {ALERT_THRESHOLD*100}%")

    client = StarlinkClient(target=dish_target)

    while not shutdown_event.is_set():
        try:
            # Connect if needed
            if client.channel is None:
                logger.info("Connecting to Starlink dish...")
                client.connect()

            # Fetch current status
            status = client.get_status()
            current_drop_rate = status["pop_ping_drop_rate"]

            # Fetch history (only new samples if we have a counter)
            general, bulk = client.get_history(
                samples=-1,
                start_counter=collector.last_counter
            )

            # Update counter for next iteration
            collector.last_counter = general["end_counter"]

            # Update metrics
            collector.update(current_drop_rate, bulk["pop_ping_drop_rate"], status)

            logger.debug(
                f"Updated metrics: current_drop={current_drop_rate*100:.2f}%, "
                f"latency={status.get('pop_ping_latency_ms', 0):.2f}ms, "
                f"down={status.get('downlink_throughput_bps', 0)/1e6:.2f}Mbps, "
                f"up={status.get('uplink_throughput_bps', 0)/1e6:.2f}Mbps, "
                f"gps_sats={status.get('gps_sats', 0)}, "
                f"new_samples={general['samples']}"
            )

        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
            break
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")
            collector.increment_errors()
            # Try to reconnect on next iteration
            try:
                client.close()
            except:
                pass
            client.channel = None

        # Wait for next poll or shutdown
        shutdown_event.wait(POLL_INTERVAL)

    # Cleanup
    logger.info("Shutting down monitoring loop")
    try:
        client.close()
    except:
        pass


def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("Starlink Ping Drop Monitor Starting")
    logger.info("=" * 60)
    logger.info(f"Dish target: {DISH_IP}:{DISH_PORT}")
    logger.info(f"HTTP endpoint: http://0.0.0.0:{HTTP_PORT}")
    logger.info(f"Poll interval: {POLL_INTERVAL}s")
    logger.info(f"Alert threshold: {ALERT_THRESHOLD*100}%")
    logger.info("=" * 60)

    # Create metrics collector
    collector = MetricsCollector()

    # Create shutdown event
    shutdown_event = threading.Event()

    # Start monitoring thread
    monitor_thread = threading.Thread(
        target=monitoring_loop,
        args=(collector, shutdown_event),
        daemon=True
    )
    monitor_thread.start()

    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        shutdown_event.set()
        httpd.shutdown()

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Start HTTP server
    httpd = ThreadingHTTPServer(("0.0.0.0", HTTP_PORT), MetricsHandler)
    httpd.collector = collector

    logger.info(f"HTTP server listening on port {HTTP_PORT}")
    logger.info("Endpoints:")
    logger.info(f"  - http://0.0.0.0:{HTTP_PORT}/metrics (Prometheus metrics)")
    logger.info(f"  - http://0.0.0.0:{HTTP_PORT}/health (Health check)")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        shutdown_event.set()
        logger.info("Waiting for monitoring thread to finish...")
        monitor_thread.join(timeout=5)
        logger.info("Shutdown complete")


if __name__ == "__main__":
    main()
