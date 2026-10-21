from scripts.benchmark_push import summarize


def test_summary_excludes_taps_timeouts_and_retries():
    def row(source='foreground', status='received', attempts=1, ms=100):
        return {'provider': 'fcm', 'receipt_source': source, 'status': status,
                'attempts': attempts, 'timing_ms': {'queue': 10, 'provider_request': 20, 'confirmation': ms,
                                                 'send_to_confirmation': ms - 10}}
    result = summarize([row(), row(ms=300), row(source='tap'), row(status='accepted'), row(attempts=2)])
    assert result['fcm']['sent'] == 5
    assert result['fcm']['foreground_single_attempt'] == 2
    assert result['fcm']['metrics']['confirmation'] == {'mean_ms': 200, 'median_ms': 200,
                                                       'p95_ms': 300, 'min_ms': 100, 'max_ms': 300}
    assert result['fcm']['metrics']['send_to_confirmation']['mean_ms'] == 190
    assert result['fcm']['excluded'] == 3
    assert result['onesignal']['metrics']['confirmation'] is None


def test_p95_uses_nearest_rank_and_excludes_missing_metrics():
    rows = [{'provider': 'fcm', 'receipt_source': 'foreground', 'status': 'received', 'attempts': 1,
             'timing_ms': {'confirmation': value}} for value in range(1, 21)]
    result = summarize(rows)['fcm']['metrics']
    assert result['confirmation']['p95_ms'] == 19
    assert result['confirmation']['median_ms'] == 10.5
    assert result['send_to_confirmation'] is None
