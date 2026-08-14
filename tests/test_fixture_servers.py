import socket
import threading
import time

from scripts.demos.fixture_servers import wait_for_port, SERVERS


def test_wait_for_port_returns_true_once_listener_is_up():
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]

    def _close_later():
        time.sleep(0.3)
        listener.close()

    threading.Thread(target=_close_later, daemon=True).start()
    assert wait_for_port("127.0.0.1", port, timeout_s=2.0) is True


def test_wait_for_port_returns_false_on_timeout():
    # Port 1 is a reserved low port nothing will be listening on in this env.
    assert wait_for_port("127.0.0.1", 1, timeout_s=0.3) is False


def test_servers_registry_has_three_unique_ports_and_existing_scripts():
    ports = [s.port for s in SERVERS]
    assert len(ports) == len(set(ports)) == 3
    for s in SERVERS:
        assert s.script_path.exists(), f"{s.name} script missing: {s.script_path}"
