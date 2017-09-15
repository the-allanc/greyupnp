from mocket import Mocket, MocketEntry
import fcntl
import os.path
import socket
import pytest
import threading
import time

this_dir = os.path.dirname(__file__)

@pytest.yield_fixture()
def mock_ssdp_socket():
    Mocket.enable()

    with open(os.path.join(this_dir, 'ssdpfixtures')) as f:
        lines = f.readlines()

    entry = MocketEntry(("239.255.255.250", 1900), lines)
    Mocket.register(entry)

    assert Mocket.get_entry("239.255.255.250", 1900, None)

    if not hasattr(socket.socket, 'sendto'):
        def sendto(self, string, address):
            entry = Mocket.get_entry(address[0], address[1], string)
            entry.collect(string)
        socket.socket.sendto = sendto

    # This allows us to write to the pipe.
    s = socket.socket()
    fileno = s.fileno() # This give us the Read FD
    bytewrite = s.write

    fl = fcntl.fcntl(fileno, fcntl.F_GETFL, 0)

    #fcntl.fcntl(Mocket.w_fd, fcntl.F_SETFL, fcntl.fcntl(Mocket.w_fd, fcntl.F_GETFL, 0) | os.O_NONBLOCK)
    fcntl.fcntl(fileno, fcntl.F_SETFL, fl | os.O_NONBLOCK)


    def collect_lines():
        for line in lines:
            bytewrite(eval(line))
            #print 'Wrote', line
            time.sleep(0.5)

    assert Mocket.r_fd

    t = threading.Thread(target=collect_lines)
    t.daemon = True
    t.start()

    def talk_then_sleep():
        for line in lines:
            time.sleep(0.5)
            yield line

    yield entry
    Mocket.disable()
