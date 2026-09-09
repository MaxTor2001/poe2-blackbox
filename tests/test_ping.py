import socket
from datetime import datetime, timedelta

from blackbox.journal import summarize_pings
from blackbox.ping import tcp_rtt


def test_tcp_rtt_measures_open_port():
    with socket.socket() as srv:
        srv.bind(("127.0.0.1", 0))
        srv.listen()
        rtt = tcp_rtt("127.0.0.1", srv.getsockname()[1])
    assert rtt is not None and rtt < 100


def test_tcp_rtt_none_on_refused():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    assert tcp_rtt("127.0.0.1", port, timeout=0.5) is None


def test_summary_window():
    t = datetime(2026, 9, 9, 14, 5, 10)
    pings = [(t - timedelta(seconds=90), 500.0), (t - timedelta(seconds=30), 40.0), (t - timedelta(seconds=10), 80.0), (t - timedelta(seconds=2), None)]
    s = summarize_pings(pings, t)
    assert (s.avg_ms, s.max_ms, s.lost, s.count) == (60.0, 80.0, 1, 3)
    assert summarize_pings([], t) is None
