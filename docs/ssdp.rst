================================================
 `greyupnp.ssdp` --- Tools for working with SSDP
================================================ 

.. py:module:: greyupnp.ssdp

This module contains various tools for using SSDP for service discovery. In most cases, the :py:func:`search` function will be the only feature that you will need to import. However, if you need more control over SSDP usage, then there are more basic tools described further down in the module.

High-level usage
================

.. autofunction:: search
.. autoclass:: Discovery
   :members:
   :special-members: __init__

Mid-level usage
===============

Here are some more details.

.. autofunction:: make_socket
.. autofunction:: request_via_socket
.. autofunction:: responses_from_socket

Low-level usage
===============

And lastly....

.. autodata:: MCAST_IP
.. autodata:: MCAST_PORT
.. autodata:: MCAST_IP_PORT
.. autofunction:: encode_request
.. autofunction:: decode_response

Glossary
========

.. glossary::

   resource type
   resource types
       A string identifier which describes a discovered resource, such as
       ``"uuid:device-UUID"`` or ``"urn:schemas-upnp-org:device:deviceType:ver"``.
       It will usually either refer to a UPnP service or device.

.. code-block:: python
    :caption: this.py
    :name: that-py
    
    seen = set()
    timeout = float(timeout) / tries
    type_filter = set(target_types) if target_types else None
    target_types = target_types or [None]
    with contextlib.closing(make_socket()) as sock:
        for i in range(tries):
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

And that is it.
