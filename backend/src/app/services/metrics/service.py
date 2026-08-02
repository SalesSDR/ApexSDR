from prometheus_client import Counter, Gauge, Histogram

# Latency metrics (in seconds)
decision_engine_latency = Histogram(
    "decision_engine_latency_seconds", 
    "Time spent making a decision",
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0]
)

voice_latency = Histogram(
    "voice_ai_latency_seconds", 
    "Time spent generating a voice response",
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0]
)

queue_processing_latency = Histogram(
    "queue_processing_latency_seconds", 
    "Time spent processing a background task",
    ["task_name"],
    buckets=[0.1, 0.5, 1.0, 5.0, 30.0]
)

# Operational counters
compliance_blocks_total = Counter(
    "compliance_blocks_total", 
    "Total number of actions blocked by compliance",
    ["policy_type", "severity"]
)

buying_signal_processing_total = Counter(
    "buying_signal_processing_total", 
    "Total number of buying signals processed",
    ["signal_type", "status"]
)

crm_sync_failures_total = Counter(
    "crm_sync_failures_total", 
    "Total number of CRM sync failures",
    ["provider"]
)

calendar_sync_failures_total = Counter(
    "calendar_sync_failures_total", 
    "Total number of Calendar sync failures"
)

# Gauges
queue_depth = Gauge(
    "background_queue_depth", 
    "Number of jobs waiting in the background queue"
)

# A small background task or metric setup function could be used to poll redis for queue depth, 
# but for now we expose the object to be updated by a cron or middleware.
