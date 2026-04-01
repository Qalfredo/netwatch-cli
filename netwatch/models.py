"""Shared data models for netwatch-cli."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MeasurementRow:
    """One complete measurement row written to measurements_v1.csv."""

    # Timestamps
    timestamp_utc: str
    timestamp_local: str
    timestamp_vet: str  # Venezuela Standard Time (UTC-4, no DST)

    # Speed
    download_mbps: float | None
    upload_mbps: float | None

    # Latency
    ping_ms: float | None
    jitter_ms: float | None
    packet_loss_pct: float | None

    # DNS
    isp_dns_ms: float | None
    cloudflare_dns_ms: float | None
    google_dns_ms: float | None

    # Enrichment
    public_ip: str | None
    isp_name: str | None
    isp_asn: str | None
    gateway_ip: str | None
    gateway_vendor: str | None
    topology: str | None

    # Speed-test metadata
    test_server: str | None
    test_server_dist_km: float | None
    speed_backend: str

    # Contract
    contracted_down_mbps: float
    contracted_up_mbps: float
    below_contract: bool

    # Collection metadata
    collection_duration_s: float
    error_message: str | None


# Ordered list of CSV column names — must match MeasurementRow field order.
CSV_FIELDNAMES: list[str] = [
    "timestamp_utc",
    "timestamp_local",
    "timestamp_vet",
    "download_mbps",
    "upload_mbps",
    "ping_ms",
    "jitter_ms",
    "packet_loss_pct",
    "isp_dns_ms",
    "cloudflare_dns_ms",
    "google_dns_ms",
    "public_ip",
    "isp_name",
    "isp_asn",
    "gateway_ip",
    "gateway_vendor",
    "topology",
    "test_server",
    "test_server_dist_km",
    "speed_backend",
    "contracted_down_mbps",
    "contracted_up_mbps",
    "below_contract",
    "collection_duration_s",
    "error_message",
]
