__all__ = ['FriendlyCURL', 'threadCURLSingleton', 'url_parameters',
           'CurlHTTPConnection', 'CurlHTTPSConnection', 'CurlHTTPResponse',]

import logging
import os
try:
    import threading as _threading
except ImportError:
    import dummy_threading as _threading

import pycurl
from pycurl import error as PyCURLError
from cStringIO import StringIO

import urllib
import urlparse
import mimetools
import httplib
from httplib2 import iri2uri

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
log.addHandler(logging.StreamHandler())

DEFAULT_URI_ENCODING = 'utf'

def url_parameters(base_url, **kwargs):
    """Uses any extra keyword arguments to create a "query string" and
    append it to base_url."""
    if kwargs:
        for k, v in kwargs.items():
            if isinstance(v, list):
                kwargs[k] = [unicode(e).encode(DEFAULT_URI_ENCODING) for e in v]
            else:
                kwargs[k] = unicode(v).encode(DEFAULT_URI_ENCODING)
        base_url += '?' + urllib.urlencode(kwargs, doseq=True)
    return base_url

def debugfunction(curl_info, data):
    if curl_info == pycurl.INFOTYPE_TEXT:
        log.debug("Info: %r", data)
    elif curl_info == pycurl.INFOTYPE_HEADER_IN:
        log.debug("Header From Peer: %r", data)
    elif curl_info == pycurl.INFOTYPE_HEADER_OUT:
        log.debug("Header Sent to Peer: %r", data)
    elif curl_info == pycurl.INFOTYPE_DATA_IN:
        log.debug("Data From Peer: %r", data)
    elif curl_info == pycurl.INFOTYPE_DATA_OUT:
        log.debug("Data To Peer: %r", data)
    return 0

class FriendlyCURL(object):
    """Friendly wrapper for a PyCURL Handle object."""
    
    def __init__(self):
        self.curl_handle = pycurl.Curl()
    
    def _common_perform(self, url, headers,
                        accept_self_signed_SSL=False,
                        follow_location=True,
                        body_buffer=None, debug=False):
        """Perform activities common to all FriendlyCURL operations. Several
        parameters are passed through and processed identically for all of the
        \*_url functions, and all produce the same return type.
        
        :param url: The URL to access. If a unicode string, it will be treated\
        as an IRI and converted to a URI.
        :type url: str or unicode
        :param headers: Additional headers to add to the request.
        :type headers: dict
        :param accept_self_signed_SSL: Whether to accept self-signed SSL certs.
        :type accept_self_signed_SSL: bool
        :param follow_location: If True, FriendlyCURL will follow location\
        headers on HTTP redirects. If False, the redirect will be returned.
        :type follow_location: bool
        :param body_buffer: A buffer to write body content into.
        :type body_buffer: ``.write(str)``-able file-like object
        :param debug: Turn on debug logging for this request.
        :type debug: bool
        :returns: A tuple containing a dictionary of response headers, including\
        the HTTP status as an int in 'status' and a buffer containing the body\
        of the response."""
        self.curl_handle.setopt(
            pycurl.HTTPHEADER,
            ['%s: %s' % (header, str(value)) for header, value in headers.iteritems()])
        if isinstance(url, unicode):
            url = str(iri2uri(url))
        self.curl_handle.setopt(pycurl.URL, url)
        if body_buffer:
            body = body_buffer
        else:
            body = StringIO()
        self.curl_handle.setopt(pycurl.WRITEFUNCTION, body.write)
        header = StringIO()
        self.curl_handle.setopt(pycurl.HEADERFUNCTION, header.write)
        if accept_self_signed_SSL == True:
            self.curl_handle.setopt(pycurl.SSL_VERIFYPEER, 0)
        if follow_location == True:
            self.curl_handle.setopt(pycurl.FOLLOWLOCATION, 1)
        if debug:
            self.curl_handle.setopt(pycurl.VERBOSE, 1)
            self.curl_handle.setopt(pycurl.DEBUGFUNCTION, debugfunction)
        self.curl_handle.perform()
        body.seek(0)
        headers = [hdr.split(': ') for hdr in header.getvalue().strip().split('\r\n') if
                   hdr and not hdr.startswith('HTTP/')]
        response = dict((header[0].lower(), header[1]) for header in headers)
        response['status'] = self.curl_handle.getinfo(pycurl.HTTP_CODE)
        return (response, body)
    
    def get_url(self, url, headers = None, **kwargs):
        """Perform a regular HTTP GET using pycurl. See :meth:`_common_perform`
        for details."""
        headers = headers or {}
        self.curl_handle.setopt(pycurl.HTTPGET, 1)
        return self._common_perform(url, headers, **kwargs)
    
    def head_url(self, url, headers = None, **kwargs):
        """Performs an HTTP HEAD using pycurl. See :meth:`_common_perform`
        for details."""
        headers = headers or {}
        self.curl_handle.setopt(pycurl.NOBODY, 1)
        result = self._common_perform(url, headers, **kwargs)
        self.reset()
        return result
    
    def post_url(self, url, data=None, upload_file=None, upload_file_length=None,
                 content_type='application/x-www-form-urlencoded',
                 headers = None, **kwargs):
        """Performs an HTTP POST using pycurl. If ``headers`` is provided, it
        will have Content-Type and Content-Length added to it.  See
        :meth:`_common_perform` for further details.
        
        :param data: The data to use as the POST body. Will over-ride\
        ``upload_file`` and ``upload_file_length`` if provided.
        :type data: str or unicode
        :param upload_file: The data to use as the POST body.
        :type upload_file: ``.read()``-able file-like object
        :param upload_file_length: The length of ``upload_file``. If\
        ``upload_file`` is provided and this is not, ``friendly_curl`` will use\
        ``os.fstat`` to calculate it.
        :param content_type: The type of the data being POSTed."""
        headers = headers or {}
        self.curl_handle.setopt(pycurl.POST, 1)
        if data:
            upload_file = StringIO(data)
            upload_file_length = len(data)
        if not upload_file_length and hasattr(upload_file, 'fileno'):
            upload_file_length = os.fstat(upload_file.fileno()).st_size
        self.curl_handle.setopt(pycurl.READFUNCTION, upload_file.read)
        headers['Content-Type'] = content_type
        headers['Content-Length'] = upload_file_length
        result = self._common_perform(url, headers, **kwargs)
        self.reset()
        return result
        
    def put_url(self, url, data=None, upload_file=None, upload_file_length=None,
                content_type='application/x-www-form-urlencoded',
                headers = None, **kwargs):
        """Perform an HTTP PUT using pycurl. See :meth:`post_url` and
        :meth:`_common_perform` for further details."""
        headers = headers or {}
        self.curl_handle.setopt(pycurl.UPLOAD, 1)
        if data:
            upload_file = StringIO(data)
            upload_file_length = len(data)
        if not upload_file_length and hasattr(upload_file, 'fileno'):
            upload_file_length = os.fstat(upload_file.fileno()).st_size
        self.curl_handle.setopt(pycurl.READFUNCTION, upload_file.read)
        headers['Content-Type'] = content_type
        headers['Content-Length'] = upload_file_length
        result = self._common_perform(url, headers, **kwargs)
        self.reset()
        return result
    
    def delete_url(self, url, headers = None, **kwargs):
        """Perform an HTTP DELETE using pycurl. See :meth:`_common_perform` for
        further details."""
        headers = headers or {}
        self.curl_handle.setopt(pycurl.CUSTOMREQUEST, 'DELETE')
        result = self._common_perform(url, headers, **kwargs)
        self.reset()
        return result
    
    def reset(self):
        """Resets the CURL handle to its base state. Automatically called after
        a HEAD, POST, PUT, or DELETE.
        
        Will use the pycurl handle's ``reset()`` method if available. Otherwise
        discards and replaces the pycurl handle."""
        if hasattr(self.curl_handle, 'reset'):
            self.curl_handle.reset()
        else:
            self.curl_handle = pycurl.Curl()
            
local = _threading.local()
    
def threadCURLSingleton():
    """Creates or returns a single :class:`FriendlyCURL` object per thread. You
    will usually want to call this to obtain a :class:`FriendlyCURL` object."""
    if not hasattr(local, 'fcurl'):
        local.fcurl = FriendlyCURL()
    return local.fcurl

class CurlHTTPConnection(object):
    """DuckTyped httplib.HTTPConnection.
    
    Does its own thing, rather than using a FriendlyCURL object."""
    
    def __init__(self, host, port=None,
                 key_file=None, cert_file=None, strict=False,
                 timeout=None, proxy_info=None):
        self.host = host
        self.port = port
        self.key_file = key_file
        self.cert_file = cert_file
        self.strict = strict
        self.timeout = timeout
        self.proxy_info = proxy_info
        self.handle = None
        self.scheme = 'http'
    
    def request(self, method, uri, body=None, headers=None):
        if not self.handle:
            self.connect()
        handle = self.fcurl.curl_handle
        if headers is None:
            headers = {}
        if method == 'GET':
            handle.setopt(pycurl.HTTPGET, 1)
        elif method == 'HEAD':
            handle.setopt(pycurl.NOBODY, 1)
        elif method == 'POST':
            handle.setopt(pycurl.POST, 1)
            if body:
                headers['Content-Length'] = len(body)
                body_IO = StringIO(body)
                handle.setopt(pycurl.READFUNCTION, body_IO.read)
        elif method == 'PUT':
            handle.setopt(pycurl.UPLOAD, 1)
            if body:
                headers['Content-Length'] = len(body)
                body_IO = StringIO(body)
                handle.setopt(pycurl.READFUNCTION, body_IO.read)
        elif body is not None:
            # Custom method and body provided, error.
            raise Exception("body not supported with custom method %s." % method)
        else:
            # Custom method and no body provided, pretend to do a GET.
            handle.setopt(pycurl.CUSTOMREQUEST, method)
        if self.port:
            netloc = '%s:%s' % (self.host, self.port)
        else:
            netloc = self.host
        url = urlparse.urlunparse((self.scheme, netloc, uri, '', '', ''))
        self.url = str(iri2uri(url))
        handle.setopt(pycurl.URL, self.url)
        if headers:
            handle.setopt(pycurl.HTTPHEADER, ['%s: %s' % (header, str(value)) for
                                                header, value in
                                                headers.iteritems()])
        handle.setopt(pycurl.SSL_VERIFYPEER, 0)
        handle.setopt(pycurl.NOSIGNAL, 1)
        if self.key_file:
            handle.setopt(pycurl.SSLKEY, self.key_file)
        if self.cert_file:
            handle.setopt(pycurl.SSLCERT, self.cert_file)
        if self.timeout:
            handle.setopt(pycurl.TIMEOUT, self.timeout)
        # Proxy not supported yet.
    
    def getresponse(self):
        handle = self.fcurl.curl_handle
        body = StringIO()
        handle.setopt(pycurl.WRITEFUNCTION, body.write)
        headers = StringIO()
        handle.setopt(pycurl.HEADERFUNCTION, headers.write)
        handle.perform()
        self.fcurl.reset()
        return CurlHTTPResponse(body, headers)
    
    def set_debuglevel(self, level):
        pass
    
    def connect(self):
        self.fcurl = threadCURLSingleton()
        self.fcurl.reset()
    
    def close(self):
        """Also doesn't actually do anything."""
        self.fcurl = None
    
    def putrequest(self, request, selector, skip_host, skip_accept_encoding):
        raise NotImplementedError()
    
    def putheader(self, header, argument, **kwargs):
        raise NotImplementedError()
    
    def endheaders(self):
        raise NotImplementedError()
    
    def send(self, data):
        raise NotImplementedError()

class CurlHTTPSConnection(CurlHTTPConnection):
    def __init__(self, host, port=None,
             key_file=None, cert_file=None, strict=False,
             timeout=None, proxy_info=None):
        super(CurlHTTPSConnection, self).__init__(host, port, key_file,
                                                  cert_file, strict, timeout,
                                                  proxy_info)
        self.scheme = 'https'

class CurlHTTPResponse(httplib.HTTPResponse):
    def __init__(self, body, headers):
        self.body = body
        self.body.seek(0)
        headers.seek(0)
        status_line = headers.readline()
        (http_version, sep, status_line) = status_line.partition(' ')
        (status, sep, reason) = status_line.partition(' ')
        self.version = int(''.join(ch for ch in http_version if ch.isdigit()))
        self.status = int(status)
        self.reason = reason.strip()
        self.msg = mimetools.Message(headers)
    
    def read(self, amt=-1):
        return self.body.read(amt)
    
    def getheader(self, name, default=None):
        value = self.msg.get(name)
        if value is None:
            return default
        return value
    
    def getheaders(self):
        return [(header, self.msg.get(header)) for header in self.msg]
