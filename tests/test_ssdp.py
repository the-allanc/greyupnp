from greyupnp import ssdp
import pytest
from six.moves import queue
import socket

@pytest.fixture
def ssdp_responses():
    import os.path
    with open(os.path.join(os.path.dirname(__file__), 'ssdp_fixtures'), 'r') as f:
        return map(eval, f.readlines())


class Mocket(object):

    def __init__(self):
        self._requests = queue.Queue()
        self._responses = queue.Queue()

    def sendto(self, msg, address):
        self._requests.append((msg, address))

    def recv(self, bytes):
        try:
            return self._responses.get(timeout=0.2)
        except queue.Empty:
            raise socket.timeout

    def close(self):
        pass


class TestSearch(object):

    def test_ssdp_responses(self, monkeypatch, ssdp_responses):
        m = Mocket()
        [m._responses.put(r) for r in ssdp_responses]
        monkeypatch.setattr('greyupnp.ssdp.make_socket', lambda: m)

        # There's 8 entries here - this should filter out one of the duplicates from the SSDP
        # responses file.
        expected = [
            ssdp.Discovery({
                'Location': 'http://10.11.12.21:8008/ssdp/device-desc.xml',
                'ST': 'upnp:rootdevice',
            }),
            ssdp.Discovery({
                'Location': 'http://10.11.12.23:7676/smp_2_',
                'ST': 'upnp:rootdevice',
            }),
            ssdp.Discovery({
                'Location': 'http://10.11.12.23:7676/smp_7_',
                'ST': 'upnp:rootdevice',
            }),
            ssdp.Discovery({
                'Location': 'http://10.11.12.24:49153/description7.xml',
                'ST': 'upnp:rootdevice',
            }),
            ssdp.Discovery({
                'Location': 'http://10.11.12.24:49153/description8.xml',
                'ST': 'upnp:rootdevice',
            }),
            ssdp.Discovery({
                'Location': 'http://10.11.12.24:49153/description9.xml',
                'ST': 'upnp:rootdevice',
            }),
            ssdp.Discovery({
                'Location': 'http://10.11.12.32:41870/rootDesc.xml',
                'NT': 'urn:schemas-upnp-org:service:Layer3Forwarding:1',
            }),
            ssdp.Discovery({
                'Location': 'http://10.11.12.32:41870/rootDesc.xml',
                'NT': 'urn:schemas-upnp-org:service:WANPPPConnection:1',
            }),
        ]

        # Execute a search, we should get our fixtures back.
        results = list(ssdp.search(timeout=0.5, tries=1))
        assert sorted(results) == expected
