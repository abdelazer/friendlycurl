"""Unit tests for CurlHTTPConnections."""

from cStringIO import StringIO
import unittest
import BaseHTTPServer
import threading
import tempfile

import pycurl

from friendly_curl import CurlHTTPConnection
from friendly_curl import CurlHTTPResponse

try:
    import httplib2
except ImportError:
    httplib2 = None

class TestCurlHTTPConnection(unittest.TestCase):
    def testSuccessfulGet(self):
        """Test a basic get request"""
        con = CurlHTTPConnection('127.0.0.1', 6110)
        class TestRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
            test_object = self
            
            def do_GET(self):
                self.test_object.request_handler = self
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write('This is a test line.\n')

        started = threading.Event()
        def test_thread():
            server = BaseHTTPServer.HTTPServer(('', 6110), TestRequestHandler)
            started.set()
            server.handle_request()
            server.server_close()
        
        thread = threading.Thread(target=test_thread)
        thread.start()
        started.wait()
        
        con.request('GET', '/index.html?foo=bar')
        resp = con.getresponse()
        self.assertEqual(resp.status, 200, 'Unexpected HTTP status.')
        self.assertEqual(resp.getheader('content-type'), 'text/html',
                         'Unexpected Content-Type from server.')
        self.assertEqual(resp.read(), 'This is a test line.\n',
                         'Incorrect content returned by server.')
        self.assertEqual(self.request_handler.path, '/index.html?foo=bar',
                         'Incorrect path on server.')
        thread.join()
            
    def testSuccessfulGetWithHeaders(self):
        """Test a basic get request with headers"""
        con = CurlHTTPConnection('127.0.0.1', 6110)
        class TestRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
            test_object = self
            
            def do_GET(self):
                self.test_object.request_handler = self
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write('This is a test line.\n')
        
        started = threading.Event()
        def test_thread():
            server = BaseHTTPServer.HTTPServer(('', 6110), TestRequestHandler)
            started.set()
            server.handle_request()
            server.server_close()
        
        thread = threading.Thread(target=test_thread)
        thread.start()
        started.wait()
        
        con.request('GET', '/index.html?foo=bar', headers={'SHAZAM': 'Marvellous'})
        resp = con.getresponse()
        self.assertEqual(self.request_handler.headers['SHAZAM'], 'Marvellous',
                         'Test request header not found on server.')
        thread.join()
    
    def testErrorGet(self):
        """Test a get request that causes an error"""
        con = CurlHTTPConnection('127.0.0.1', 6110)
        class TestRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
            test_object = self
            
            def do_GET(self):
                self.test_object.request_handler = self
                self.send_error(404)

        started = threading.Event()
        def test_thread():
            server = BaseHTTPServer.HTTPServer(('', 6110), TestRequestHandler)
            started.set()
            server.handle_request()
            server.server_close()
        
        thread = threading.Thread(target=test_thread)
        thread.start()
        started.wait()
        
        con.request('GET', '/index.html?foo=bar')
        resp = con.getresponse()
        self.assertEqual(resp.status, 404, 'Unexpected HTTP status.')
        self.assertEqual(resp.getheader('content-type'), 'text/html',
                         'Unexpected Content-Type from server.')
        self.assert_('<p>Error code 404.' in resp.read(),
                     'Unexpected error document from server.')
        self.assertEqual(self.request_handler.path, '/index.html?foo=bar',
                         'Incorrect path on server.')
        thread.join()
    
    def testPostData(self):
        """Test a basic post request"""
        con = CurlHTTPConnection('127.0.0.1', 6110)
        class TestRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
            test_object = self
            
            def do_POST(self):
                self.test_object.request_handler = self
                self.test_object.post_content = \
                    self.rfile.read(int(self.headers['content-length']))
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write('This is a test line.\n')
        
        started = threading.Event()
        def test_thread():
            server = BaseHTTPServer.HTTPServer(('', 6110), TestRequestHandler)
            started.set()
            server.handle_request()
            server.server_close()
        
        thread = threading.Thread(target=test_thread)
        thread.start()
        started.wait()
        
        # Do this here so test_thread sees it after it drops out of
        #  handle_request after curl makes its request.
        runThread = False
        con.request('POST', '/post_target', body='foo=bar&baz=garply\r\n')
        resp = con.getresponse()
        self.assertEqual(self.request_handler.headers['content-length'], '20')
        self.assertEqual(self.post_content, 'foo=bar&baz=garply\r\n',
                         'Incorrect data on server.')
        self.assertEqual(self.request_handler.path, '/post_target',
                 'Incorrect path on server.')
        thread.join()
    
    def testPutData(self):
        """Test a basic put request"""
        con = CurlHTTPConnection('127.0.0.1', 6110)
        class TestRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
            test_object = self
            
            def do_PUT(self):
                self.test_object.request_handler = self
                # CURL's put uses transfer-encoding chunked by default.
                chunk_size = int(self.rfile.readline(), 16)
                self.test_object.put_content = \
                    self.rfile.read(int(self.headers['content-length']))
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write('This is a test line.\n')
        
        started = threading.Event()
        def test_thread():
            server = BaseHTTPServer.HTTPServer(('', 6110), TestRequestHandler)
            started.set()
            server.handle_request()
            server.server_close()
        
        thread = threading.Thread(target=test_thread)
        thread.start()
        started.wait()
        
        con.request('PUT', '/put_target', body='foo=bar&baz=garply\r\n')
        resp = con.getresponse()
        self.assertEqual(self.request_handler.headers['content-length'], '20')
        self.assertEqual(self.put_content, 'foo=bar&baz=garply\r\n',
                         'Incorrect data on server.')
        self.assertEqual(self.request_handler.path, '/put_target',
                 'Incorrect path on server.')
        thread.join()

    def testDelete(self):
        """Test a delete request"""
        con = CurlHTTPConnection('127.0.0.1', 6110)
        class TestRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
            test_object = self
            
            def do_DELETE(self):
                self.test_object.request_handler = self
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write('This is a test line.\n')
        
        started = threading.Event()
        def test_thread():
            server = BaseHTTPServer.HTTPServer(('', 6110), TestRequestHandler)
            started.set()
            server.handle_request()
            server.server_close()
        
        thread = threading.Thread(target=test_thread)
        thread.start()
        started.wait()
        
        con.request('DELETE', '/del_target')
        resp = con.getresponse()
        self.assertEqual(self.request_handler.path, '/del_target',
             'Incorrect path on server.')
        thread.join()
    
    def testHttpLib2GET(self):
        """Test integration with httplib2 when making a GET request."""
        if httplib2:
            httpcon = httplib2.Http()
            class TestRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
                test_object = self
                
                def do_GET(self):
                    self.test_object.request_handler = self
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html')
                    self.end_headers()
                    self.wfile.write('This is a test line.\n')
            
            started = threading.Event()
            def test_thread():
                server = BaseHTTPServer.HTTPServer(('', 6110), TestRequestHandler)
                started.set()
                server.handle_request()
                server.server_close()
            
            thread = threading.Thread(target=test_thread)
            thread.start()
            started.wait()
            
            (resp, content) = httpcon.request(
                uri='http://localhost:6110/index.html?foo=bar',
                method='GET', connection_type=CurlHTTPConnection)
            self.assertEqual(resp.status, 200, 'Unexpected HTTP status.')
            self.assertEqual(resp['content-type'], 'text/html',
                             'Unexpected Content-Type from server.')
            self.assertEqual(content, 'This is a test line.\n',
                             'Incorrect content returned by server.')
            self.assertEqual(self.request_handler.path, '/index.html?foo=bar',
                             'Incorrect path on server.')
            thread.join()
    
    def testHttpLib2GETHeaders(self):
        """Test integration with httplib2 by making a get request with headers."""
        if httplib2:
            httpcon = httplib2.Http()
            class TestRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
                test_object = self
                
                def do_GET(self):
                    self.test_object.request_handler = self
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html')
                    self.end_headers()
                    self.wfile.write('This is a test line.\n')
            
            started = threading.Event()
            def test_thread():
                server = BaseHTTPServer.HTTPServer(('', 6110), TestRequestHandler)
                started.set()
                server.handle_request()
                server.server_close()
            
            thread = threading.Thread(target=test_thread)
            thread.start()
            started.wait()
            
            (resp, content) = httpcon.request(
                uri='http://127.0.0.1:6110/index.html?foo=bar', method='GET', 
                headers={'SHAZAM': 'Marvellous'},
                connection_type=CurlHTTPConnection)
            self.assertEqual(self.request_handler.headers['SHAZAM'], 'Marvellous',
                             'Test request header not found on server.')
            thread.join()

    def testHttpLib2POST(self):
        """Test a post request through httplib2."""
        if httplib2:
            httpcon = httplib2.Http()
            class TestRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
                test_object = self
                
                def do_POST(self):
                    self.test_object.request_handler = self
                    self.test_object.post_content = \
                        self.rfile.read(int(self.headers['content-length']))
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html')
                    self.end_headers()
                    self.wfile.write('This is a test line.\n')
            
            started = threading.Event()
            def test_thread():
                server = BaseHTTPServer.HTTPServer(('', 6110), TestRequestHandler)
                started.set()
                server.handle_request()
                server.server_close()
            
            thread = threading.Thread(target=test_thread)
            thread.start()
            started.wait()
            
            (resp, content) = httpcon.request(
                uri='http://127.0.0.1:6110/post_target', method='POST',
                body='foo=bar&baz=garply\r\n', connection_type=CurlHTTPConnection)
            self.assertEqual(self.request_handler.headers['content-length'], '20')
            self.assertEqual(self.post_content, 'foo=bar&baz=garply\r\n',
                             'Incorrect data on server.')
            self.assertEqual(self.request_handler.path, '/post_target',
                     'Incorrect path on server.')
            thread.join()
    
    def testHttpLib2PUT(self):
        """Test a put request through httplib2"""
        if httplib2:
            httpcon = httplib2.Http()
            class TestRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
                test_object = self
                
                def do_PUT(self):
                    self.test_object.request_handler = self
                    # CURL's put uses transfer-encoding chunked by default.
                    chunk_size = int(self.rfile.readline(), 16)
                    self.test_object.put_content = \
                        self.rfile.read(int(self.headers['content-length']))
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html')
                    self.end_headers()
                    self.wfile.write('This is a test line.\n')
            
            started = threading.Event()
            def test_thread():
                server = BaseHTTPServer.HTTPServer(('', 6110), TestRequestHandler)
                started.set()
                server.handle_request()
                server.server_close()
            
            thread = threading.Thread(target=test_thread)
            thread.start()
            started.wait()
            
            (resp, content) = httpcon.request(
                uri='http://127.0.0.1:6110/put_target', method='PUT',
                body='foo=bar&baz=garply\r\n', connection_type=CurlHTTPConnection)
            self.assertEqual(self.request_handler.headers['content-length'], '20')
            self.assertEqual(self.put_content, 'foo=bar&baz=garply\r\n',
                             'Incorrect data on server.')
            self.assertEqual(self.request_handler.path, '/put_target',
                     'Incorrect path on server.')
            thread.join()

    def testHttpLib2DELETE(self):
        """Test a delete request"""
        if httplib2:
            httpcon = httplib2.Http()
            class TestRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
                test_object = self
                
                def do_DELETE(self):
                    self.test_object.request_handler = self
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html')
                    self.end_headers()
                    self.wfile.write('This is a test line.\n')
            
            started = threading.Event()
            def test_thread():
                server = BaseHTTPServer.HTTPServer(('', 6110), TestRequestHandler)
                started.set()
                server.handle_request()
                server.server_close()
            
            thread = threading.Thread(target=test_thread)
            thread.start()
            started.wait()
            
            # Do this here so test_thread sees it after it drops out of
            #  handle_request after curl makes its request.
            runThread = False
            httpcon.request(
                uri='http://127.0.0.1:6110/del_target', method='DELETE',
                connection_type=CurlHTTPConnection)
            self.assertEqual(self.request_handler.path, '/del_target',
                 'Incorrect path on server.')
            thread.join()
    
    def testSuccessfulGetWithUnicodeUri(self):
        """Test a basic get request with a unicode object passed to con.request."""
        con = CurlHTTPConnection('127.0.0.1', 6110)
        class TestRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
            test_object = self
            
            def do_GET(self):
                self.test_object.request_handler = self
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write('This is a test line.\n')

        started = threading.Event()
        def test_thread():
            server = BaseHTTPServer.HTTPServer(('', 6110), TestRequestHandler)
            started.set()
            server.handle_request()
            server.server_close()
        
        thread = threading.Thread(target=test_thread)
        thread.start()
        started.wait()
        
        con.request('GET', u'/index.html?foo=bar')
        resp = con.getresponse()
        self.assertEqual(resp.status, 200, 'Unexpected HTTP status.')
        self.assertEqual(resp.getheader('content-type'), 'text/html',
                         'Unexpected Content-Type from server.')
        self.assertEqual(resp.read(), 'This is a test line.\n',
                         'Incorrect content returned by server.')
        self.assertEqual(self.request_handler.path, '/index.html?foo=bar',
                         'Incorrect path on server.')
        thread.join()
            
