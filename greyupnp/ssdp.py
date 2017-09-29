from __future__ import unicode_literals

import contextlib
from requests.structures import CaseInsensitiveDict
import crookbook
import six
import socket
import struct
import time

#: The IP used to broadcast multicast packets to.
MCAST_IP = "239.255.255.250"

#: The port used to broadcast multicast packets to.
MCAST_PORT = 1900

#: The IP+port used to broadcast multicast packets to.
MCAST_IP_PORT = MCAST_IP + ':' + str(MCAST_PORT)


def make_socket():
    '''Creates a socket suitable for SSDP searches.

    The socket will have a default timeout of 0.2 seconds (this works well for
    the :py:func:search function which interleaves sending requests and reading
    responses.
    '''
    mreq = struct.pack("4sl", socket.inet_aton(MCAST_IP), socket.INADDR_ANY)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('', MCAST_PORT))
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    sock.settimeout(0.2)
    return sock


def encode_request(request_line, **headers):
    '''Creates the data for a SSDP request.

    Args:
        request_line (string): The request line for the request (e.g.
            ``"M-SEARCH * HTTP/1.1"``).
        headers (dict of string -> string): Dictionary of header name - header
            value pairs to present in the request.

    Returns:
        bytes: The encoded request.
    '''
    lines = [request_line]
    lines.extend(['%s: %s' % kv for kv in headers.items()])
    return ('\r\n'.join(lines) + '\r\n\r\n').encode('utf-8')


def decode_response(data):
    '''Decodes the data from a SSDP response.

    Args:
        data (bytes): The encoded response.

    Returns:
        dict of string -> string: Case-insensitive dictionary of header name to
        header value pairs extracted from the response.
    '''
    res = CaseInsensitiveDict()
    for dataline in data.decode('utf-8').splitlines()[1:]:
        dataline = dataline.strip()
        if not dataline:
            continue
        line_parts = dataline.split(':', 1)
        # This is to deal with headers with no value.
        if len(line_parts) < 2:
            line_parts = (line_parts[0], '')
        res[line_parts[0].strip()] = line_parts[1].strip()
    return res


def request_via_socket(sock, search_target):
    '''Send an SSDP search request via the provided socket.

    Args:
        sock: A socket suitable for use to send a broadcast message - preferably
            one created by :py:func:`make_socket`.
        search_target (string): A :term:`resource type` target to search for.
    '''
    msgparts = dict(HOST=MCAST_IP_PORT, MAN='"ssdp:discover"', MX='3', ST=search_target)
    msg = encode_request('M-SEARCH * HTTP/1.1', **msgparts)
    sock.sendto(msg, (MCAST_IP, MCAST_PORT))


def responses_from_socket(sock, timeout=10):
    '''Yield SSDP search responses and advertisements from the provided socket.

    Args:
        sock: A socket suitable for use to send a broadcast message - preferably
            one created by :py:func:`make_socket`.
        timeout (int / float): Overall time in seconds for how long to wait for
            before no longer listening for responses.

    Yields:
        dict of string -> string: Case-insensitive dictionary of header name to
        header value pairs extracted from the response.
    '''
    now = time.time()
    give_up_by = now + timeout

    while now < give_up_by:
        try:
            data = sock.recv(1024)
        except socket.timeout:
            now = time.time()
            continue

        # We handle either search responses or announcements.
        for data_prefix in [
            b'HTTP/1.1 200 OK',
            b'NOTIFY * HTTP/1.1',
        ]:
            if data[:len(data_prefix)] == data_prefix:
                break
        else:
            now = time.time()
            continue

        yield decode_response(data)

        now = time.time()
        continue


@crookbook.essence('location type', mutable=False)
@crookbook.described(inner="{0.type!r} at {0.location}")
class Discovery(object):
    '''This class describes a discovered resource, from either a SSDP search
    response or SSDP advertisement.

    The headers from the response which describes the discovered resource are
    available as the 'headers' attribute.

    You can also access any header (in a case insensitive manner) as an
    attribute on the object.

    You can access the location of the resource via the "location" attribute.

    Attributes:
      headers: Case-insensitive dictionary of header name to header
        value pairs extracted from the response.
    '''

    #: Case-insensitive dictionary of header name to header value pairs
    #: extracted from the response.
    #headers = None

    def __init__(self, headers):
        '''
        Create instance from SSDP response headers.

        Args:
            headers: Dictionary containing header name to header value
                mappings.
        '''
        self.headers = CaseInsensitiveDict(headers)
        for attr in ['location', 'type']:
            try:
                getattr(self, attr)
            except AttributeError:
                msg = 'no header suitable for "{}" in {}'
                raise ValueError(msg.format(attr, self.headers))

    @property
    def type(self):
        '''The :term:`resource type`, describing either a service or device.'''
        return self.headers.get('ST') or self.NT

    def __getattr__(self, name):
        try:
            return self.headers[name]
        except KeyError:
            raise AttributeError(name)

    @property
    def parsed(self):
        '''An urlparsed object (returned by :py:func:`~urllib.parse.urlparse`)
        of the location of the discovery.'''
        return six.moves.urllib.parse.urlparse(self.location)

    def has_host(self, host):
        '''
        Indicates if the discovered resource is on the described host - this is
        determined by looking at the location field.

        Args:
            host: Either a hostname (e.g. `"localhost"`) or a host-port pair
                (e.g. `"localhost:80"`).

        Returns:
            `true` if this resource is on the provided host.
        '''
        parsed = self.parsed
        return host in (parsed.hostname, parsed.netloc)


def search(target_types=None, timeout=12, tries=3):
    '''
    Performs a search via SSDP to discover resources.

    Args:
        target_types (sequence of strings): A sequence of :term:`resource types`
            to search for. For convenience, this can also be a single string. If
            provided, then this function will make individual requests searching
            for specific targets - this is sometimes required as some devices
            will not respond unless they are specifically requested by the search. 
            
            If not given, then a search won't be broadcast, but we will still
            listen for SSDP notification responses.

        timeout (int / float): Overall time in seconds for how long to wait for
            before no longer listening for responses.

        tries (int): How many times to send out a search request - this will be
            spread out over the timeout period.

    Yields:
        :py:class:`Discovery` instances describing each result found - any
        duplicate results will be filtered out by this function.
    '''
    if isinstance(target_types, six.string_types):
        target_types = [target_types]

    seen = set()
    timeout = float(timeout) / tries
    type_filter = set(target_types) if target_types else None
    with contextlib.closing(make_socket()) as sock:
        for i in range(tries):
            if target_types:
                for target_type in target_types:
                    request_via_socket(sock, target_type)
            for response in responses_from_socket(sock, timeout):
                discovery = Discovery(response)
                if discovery in seen:
                    continue
                seen.add(discovery)
                if type_filter and discovery.type not in target_types:
                    continue
                yield discovery
