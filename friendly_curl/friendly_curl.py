__all__ = ['FriendlyCURL', 'url_parameters']

import logging
import os
try:
    import threading as _threading
except ImportError:
    import dummy_threading as _threading

import pycurl
from cStringIO import StringIO

import urllib

log = logging.getLogger(__name__)

def url_parameters(base_url, **kwargs):
    """Uses any extra keyword arguments to create a "query string" and
    append it to base_url."""
    if kwargs:
        base_url += '?' + urllib.urlencode(kwargs, doseq=True)
    return base_url

class FriendlyCURL(object):
    """Friendly wrapper for a PyCURL Handle object."""
    
    def __init__(self, accept_self_signed_SSL = False):
        """
        Creates a friendly CURL object.
        
        accept_self_signed_SSL - Should the object accept self-signed SSL certs?
        """
        self.curl_handle = pycurl.Curl()
        if accept_self_signed_SSL == True:
            self.accept_self_signed_SSL = accept_self_signed_SSL
            self.curl_handle.setopt(pycurl.SSL_VERIFYPEER, 0)
    
    def _common_perform(self, url, request_headers):
        """
        Perform activities common to all FriendlyCURL operations.
        """
        self.curl_handle.setopt(pycurl.HTTPHEADER, ['%s: %s' % (header, str(value)) for
                                                    header, value in
                                                    request_headers.iteritems()])
        self.curl_handle.setopt(pycurl.URL, url)
        body = StringIO()
        self.curl_handle.setopt(pycurl.WRITEFUNCTION, body.write)
        header = StringIO()
        self.curl_handle.setopt(pycurl.HEADERFUNCTION, header.write)
        self.curl_handle.perform()
        self.curl_handle.setopt(pycurl.HTTPHEADER, [])
        body.seek(0)
        headers = [hdr.split(': ') for hdr in header.getvalue().strip().split('\r\n') if
                   hdr and not hdr.startswith('HTTP/')]
        response = dict((header[0].lower(), header[1]) for header in headers)
        response['status'] = self.curl_handle.getinfo(pycurl.HTTP_CODE)
        log.debug("Response object: %r", response)
        return (response, body)
    
    def get_url(self, url, headers = None):
        """
        Fetches a URL using pycurl, returning a tuple containing a response
        object (httplib-style) and the content as a buffer.
        
        Can optionally provide additional headers as a dictionary.
        """
        headers = headers or {}
        log.debug("CURL GET for %s" % url)
        self.curl_handle.setopt(pycurl.HTTPGET, 1)
        return self._common_perform(url, headers)
    
    def post_url(self, url, data=None, upload_file=None, upload_file_length=None,
                 content_type='application/x-www-form-urlencoded',
                 headers = None):
        """
        POSTs data of content_type to a URL using pycurl. Returns a tuple
        containing a response object (httplib-style) and the content as a buffer.
        
        Can also provide a file to upload and the length of that file. If
        length is not determined, friendly_curl will try to use os.fstat to
        find it.
        
        Can optionally provide additional headers as a dictionary.
        """
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
        result = self._common_perform(url, headers)
        self.reset()
        return result
        
    def put_url(self, url, data=None, upload_file=None, upload_file_length=None,
                content_type='application/x-www-form-urlencoded',
                headers = None):
        """
        PUTs data of content_type to a URL using pycurl. Returns a tuple
        containing a response object (httplib-style) and the content as a buffer.
        
        Can also provide a file to upload and the length of that file. If
        length is not determined, friendly_curl will try to use os.fstat to
        find it.
        
        Can optionally provide additional headers as a dictionary.
        """
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
        result = self._common_perform(url, headers)
        self.reset()
        return result
    
    def delete_url(self, url, headers = None):
        """
        DELETEs a URL using pycurl. Returns a tuple containing a response object
        (httplib-style) and the content as a buffer.
        
        Can optionally provide additional headers as a dictionary.
        """
        headers = headers or {}
        self.curl_handle.setopt(pycurl.CUSTOMREQUEST, 'DELETE')
        result = self._common_perform(url, headers)
        self.reset()
        return result
    
    def reset(self):
        """
        Resets the CURL handle after a put, post, or delete.
        
        If reset is available, it uses that to maintain the handle's connection
        pool. Otherwise, it replaces the handle.
        """
        if hasattr(self.curl_handle, 'reset'):
            self.curl_handle.reset()
        else:
            self.curl_handle = pycurl.Curl()
        if self.accept_self_signed_SSL:
            self.curl_handle.setopt(pycurl.SSL_VERIFYPEER, 0)            
            
local = _threading.local()
    
def threadCURLSingleton(*args, **kwargs):
    """Returns a CURL object that is a singleton per thread."""
    if not hasattr(local, 'fcurl'):
        local.fcurl = FriendlyCURL(*args, **kwargs)
    return local.fcurl
