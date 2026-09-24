"""Phase 11a Test Suite F: Multimodal Observability & Metrics (5 tests).

Verifies:
1. Metrics catalog registration: all multimodal and Sarvam metric collectors are registered in the Prometheus registry
2. ApplicationMetrics port protocol and NullApplicationMetrics safe no-op behavior
3. Counter incrementation & Prometheus text rendering for multimodal pipelines
4. Histogram observation & latency distribution rendering
5. Strict Gate 10P-D PHI label blocklist enforcement: attempting to record patient_id, phone, glucose, etc. raises ValueError
"""
from __future__ import annotations

import pytest

from backend.application.ports.metrics import ApplicationMetrics, NullApplicationMetrics
from backend.infrastructure.observability.metrics import (
    FORBIDDEN_LABEL_KEYS,
    CounterMetric,
    HistogramMetric,
    PrometheusMetricsRegistry,
    get_metrics_registry,
)


class TestMultimodalMetrics:
    def test_01_metrics_catalog_registers_all_multimodal_metrics(self):
        """All required multimodal and provider metrics are pre-registered in PrometheusMetricsRegistry."""
        registry = PrometheusMetricsRegistry()
        expected_counters = [
            "sarvam_requests_total",
            "sarvam_errors_total",
            "sarvam_timeouts_total",
            "sarvam_rate_limits_total",
            "sarvam_stt_success_total",
            "sarvam_stt_failure_total",
            "sarvam_translation_success_total",
            "sarvam_translation_failure_total",
            "sarvam_tts_success_total",
            "sarvam_tts_failure_total",
            "image_analysis_success_total",
            "image_analysis_failure_total",
            "voice_pipeline_success_total",
            "voice_pipeline_failure_total",
            "image_pipeline_success_total",
            "image_pipeline_failure_total",
            "multimodal_pipeline_failures_total",
            "multimodal_confirmation_success_total",
        ]
        for name in expected_counters:
            counter = registry.counter(name)
            assert counter is not None
            assert isinstance(counter, CounterMetric)

        # Check histogram
        hist = registry.histogram("sarvam_request_latency_seconds")
        assert hist is not None
        assert isinstance(hist, HistogramMetric)

    def test_02_application_metrics_protocol_and_null_implementation(self):
        """NullApplicationMetrics satisfies ApplicationMetrics protocol without raising or throwing errors."""
        null_metrics = NullApplicationMetrics()
        assert isinstance(null_metrics, ApplicationMetrics)

        # Calls must safely return None without errors
        assert null_metrics.increment_counter("voice_pipeline_success_total", {"kind": "transcribed"}) is None
        assert null_metrics.observe_histogram("sarvam_request_latency_seconds", 0.125, {"operation": "stt"}) is None

    def test_03_counter_increments_and_renders_prometheus_format(self):
        """Counters increment correctly and render conforming Prometheus 0.0.4 text output."""
        registry = PrometheusMetricsRegistry()
        counter = registry.counter("sarvam_requests_total")
        counter.inc(1.0, operation="speech-to-text", result="success")
        counter.inc(2.0, operation="speech-to-text", result="success")
        counter.inc(1.0, operation="chat-completion", result="error")

        rendered = registry.generate_exposition()
        assert 'sarvam_requests_total{operation="speech-to-text",result="success"} 3' in rendered
        assert 'sarvam_requests_total{operation="chat-completion",result="error"} 1' in rendered

    def test_04_histogram_observes_latencies_and_renders_buckets(self):
        """Histograms observe request latencies, update bucket counts, and calculate sums."""
        registry = PrometheusMetricsRegistry()
        hist = registry.histogram("sarvam_request_latency_seconds")
        hist.observe(0.045, operation="stt")
        hist.observe(0.120, operation="stt")

        rendered = registry.generate_exposition()
        assert "sarvam_request_latency_seconds_bucket" in rendered
        assert "sarvam_request_latency_seconds_count" in rendered
        assert "sarvam_request_latency_seconds_sum" in rendered

    def test_05_strict_phi_label_blocklist_enforcement(self):
        """Attempting to include PHI or high-cardinality keys in metric labels raises ValueError immediately."""
        registry = PrometheusMetricsRegistry()
        counter = registry.counter("voice_pipeline_success_total")

        # Prohibited keys: patient_id, phone, glucose, medication, carbs, message, payload
        prohibited_samples = [
            {"patient_id": "12345"},
            {"phone": "+919876543210"},
            {"glucose": "140"},
            {"carbs": "50"},
            {"message": "2 roti"},
            {"payload": "blob"},
            {"jwt": "eyJ..."},
        ]

        for bad_label in prohibited_samples:
            with pytest.raises(ValueError) as exc_info:
                counter.inc(1.0, **bad_label)
            assert "violates Gate 10P-D PHI / low-cardinality policy" in str(exc_info.value)
