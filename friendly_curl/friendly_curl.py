from __future__ import with_statement

__all__ = ['FriendlyCURL', 'threadCURLSingleton', 'url_parameters',
           'CurlHTTPConnection', 'CurlHTTPSConnection', 'CurlHTTPResponse',]

import contextlib
import logging
import os
import os.path
import pickle
import tempfile
import shutil
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
    """Friendly wrapper for a PyCURL Handle object. You probably don't want to
    instantiate this yourself. Instead, use :func:`threadCURLSingleton`."""
    
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
    
    def get_url(self, url, headers = None, use_cache = True, **kwargs):
        """Perform a regular HTTP GET using pycurl. See :meth:`_common_perform`
        for details.
        
        :param use_cache: Defaults to true, will use the cache if cache_dir is\
        set. Pass false or unset cache_dir to ignore cache and not cache the\
        result of the request."""
        headers = headers or {}
        self.curl_handle.setopt(pycurl.HTTPGET, 1)
        cache_base_name = hash(url)
        if not (use_cache and hasattr(self, '_cache_dir')):
            return self._common_perform(url, headers, **kwargs)
        
        response_cache_filename = os.path.join(self.cache_dir,
                                               '%s.response' % cache_base_name)
        body_cache_filename = os.path.join(self.cache_dir,
                                           '%s.body' % cache_base_name)
        temp_buffer_fd, temp_buffer_path = tempfile.mkstemp()
        try:
            if 'body_buffer' in kwargs:
                body_buffer = kwargs['body_buffer']
                del kwargs['body_buffer']
            else:
                body_buffer = StringIO()
            with os.fdopen(temp_buffer_fd, 'w') as temp_buffer:
                cached_response = {}
                if os.path.exists(response_cache_filename):
                    with open(response_cache_filename, 'r') as response_cache:
                        cached_response = pickle.load(response_cache)
                if 'etag' in cached_response:
                    # Retrieved before, do a conditional get.
                    headers['If-None-Match'] = cached_response['etag']
                    response, body = self._common_perform(
                        url, headers, body_buffer=temp_buffer, **kwargs)
                    if response['status'] == 304:
                        with open(body_cache_filename, 'r') as cached_body:
                            shutil.copyfileobj(cached_body, body_buffer)
                        body_buffer.seek(0)
                        return cached_response, body_buffer
                else:
                    # Retrieve the resource for the first time.
                    response, body = self._common_perform(
                        url, headers, body_buffer=temp_buffer, **kwargs)
            with contextlib.nested(open(temp_buffer_path, 'r'),
                                   open(body_cache_filename, 'w'),
                                   open(response_cache_filename, 'w')) as\
                 (temp_buffer, body_cache, response_cache):
                pickle.dump(response, response_cache)
                shutil.copyfileobj(temp_buffer, body_cache)
                temp_buffer.seek(0)
                shutil.copyfileobj(temp_buffer, body_buffer)
                body_buffer.seek(0)
            return response, body_buffer
        finally:
            os.unlink(temp_buffer_path)
    
    def head_url(self, url, headers = None, **kwargs):
        """Performs an HTTP HEAD using pycurl. See :meth:_common_perform`
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
        headers['Transfer-Encoding'] = ''
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
    
    def cache_dir():
        def fget(self):
            return self._cache_dir
        def fset(self, value):
            self._cache_dir = os.path.abspath(value)
        def fdel(self):
            del self._cache_dir
        doc = """Sets the directory to be used to store cache files. Whatever
        value is provided will be run through os.path.abspath."""
        return locals()
    cache_dir = property(**cache_dir())
            
local = _threading.local()
    
def threadCURLSingleton():
    """Creates or returns a single :class:`FriendlyCURL` object per thread. You
    will usually want to call this to obtain a :class:`FriendlyCURL` object."""
    if not hasattr(local, 'fcurl'):
        local.fcurl = FriendlyCURL()
    return local.fcurl

class CurlHTTPConnection(object):
    """A HTTPConncetion-style object that uses pycurl to actually do the work.
    
    Intended for use with httplib2. To use, import friendly_curl and httplib2
    and monkey-patch httplib2 as follows::
    
        httplib2.HTTPConnectionWithTimeout = CurlHTTPConnection
        httplib2.HTTPSConnectionWithTimeout = CurlHTTPSConnection"""
    
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
    """Like :class:`CurlHTTPConnection`, but uses https rather than plain http.
    As with :class:`CurlHTTPConnection`, you probably don't want to use this
    directly."""
    def __init__(self, host, port=None,
             key_file=None, cert_file=None, strict=False,
             timeout=None, proxy_info=None):
        super(CurlHTTPSConnection, self).__init__(host, port, key_file,
                                                  cert_file, strict, timeout,
                                                  proxy_info)
        self.scheme = 'https'

class CurlHTTPResponse(httplib.HTTPResponse):
    """Used by :class:`CurlHTTPConnection` and :class:`CurlHTTPSConnection` to
    return the HTTP response."""
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
        """Read data from the body of the HTTP response."""
        return self.body.read(amt)
    
    def getheader(self, name, default=None):
        """Get a header from the HTTP response.
        
        :param default: The value to return if the header is not present.\
        Defaults to ``None``."""
        value = self.msg.get(name)
        if value is None:
            return default
        return value
    
    def getheaders(self):
        """Get a dictionary of all HTTP response headers."""
        return [(header, self.msg.get(header)) for header in self.msg]
