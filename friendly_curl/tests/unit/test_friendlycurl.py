"""Unit tests for friendly_curl."""

from cStringIO import StringIO
import unittest
import BaseHTTPServer
import threading
import tempfile

import pycurl

import friendly_curl.friendly_curl as friendly_curl

class TestFriendlyCURL(unittest.TestCase):
    def setUp(self):
        self.fcurl = friendly_curl.FriendlyCURL()
    
    def testSuccessfulGet(self):
        """Test a basic get request"""
        class TestRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
            test_object = self
            
            def do_GET(self):
                print "Wheeee?"
                self.test_object.request_handler = self
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write('This is a test line.\n')
        
        runThread = True
        def test_thread():
            server = BaseHTTPServer.HTTPServer(('', 6110), TestRequestHandler)
            while runThread:
                server.handle_request()
            server.server_close()
        
        thread = threading.Thread(target=test_thread)
        thread.start()
        
        # Do this here so test_thread sees it after it drops out of
        #  handle_request after curl makes its request.
        runThread = False
        resp, content = self.fcurl.get_url('http://127.0.0.1:6110/index.html?foo=bar')
        self.assertEqual(resp['status'], 200, 'Unexpected HTTP status.')
        self.assertEqual(resp['content-type'], 'text/html',
                         'Unexpected Content-Type from server.')
        self.assertEqual(content.getvalue(), 'This is a test line.\n',
                         'Incorrect content returned by server.')
        self.assertEqual(self.request_handler.path, '/index.html?foo=bar',
                         'Incorrect path on server.')
            
    def testSuccessfulGetWithHeaders(self):
        """Test a basic get request with headers"""
        class TestRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
            test_object = self
            
            def do_GET(self):
                self.test_object.request_handler = self
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write('This is a test line.\n')
        
        runThread = True
        def test_thread():
            server = BaseHTTPServer.HTTPServer(('', 6110), TestRequestHandler)
            while runThread:
                server.handle_request()
            server.server_close()
        
        thread = threading.Thread(target=test_thread)
        thread.start()
        
        # Do this here so test_thread sees it after it drops out of
        #  handle_request after curl makes its request.
        runThread = False
        resp, content = self.fcurl.get_url('http://127.0.0.1:6110/index.html?foo=bar',
                                           {'SHAZAM': 'Marvellous'})
        self.assertEqual(self.request_handler.headers['SHAZAM'], 'Marvellous',
                         'Test request header not found on server.')
    
    def testErrorGet(self):
        """Test a get request that causes an error"""
        class TestRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
            test_object = self
            
            def do_GET(self):
                self.test_object.request_handler = self
                self.send_error(404)
        
        runThread = True
        def test_thread():
            server = BaseHTTPServer.HTTPServer(('', 6110), TestRequestHandler)
            while runThread:
                server.handle_request()
            server.server_close()
        
        thread = threading.Thread(target=test_thread)
        thread.start()
        
        # Do this here so test_thread sees it after it drops out of
        #  handle_request after curl makes its request.
        runThread = False
        resp, content = self.fcurl.get_url('http://127.0.0.1:6110/index.html?foo=bar')
        self.assertEqual(resp['status'], 404, 'Unexpected HTTP status.')
        self.assertEqual(resp['content-type'], 'text/html',
                         'Unexpected Content-Type from server.')
        self.assert_('<p>Error code 404.' in content.getvalue(),
                     'Unexpected error document from server.')
        self.assertEqual(self.request_handler.path, '/index.html?foo=bar',
                         'Incorrect path on server.')
    
    def testPostData(self):
        """Test a basic post request"""
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
        
        runThread = True
        def test_thread():
            server = BaseHTTPServer.HTTPServer(('', 6110), TestRequestHandler)
            while runThread:
                server.handle_request()
            server.server_close()
        
        thread = threading.Thread(target=test_thread)
        thread.start()
        
        # Do this here so test_thread sees it after it drops out of
        #  handle_request after curl makes its request.
        runThread = False
        resp, content = self.fcurl.post_url('http://127.0.0.1:6110/post_target',
                                            data='foo=bar&baz=garply\r\n')
        self.assertEqual(self.request_handler.headers['content-length'], '20')
        self.assertEqual(self.post_content, 'foo=bar&baz=garply\r\n',
                         'Incorrect data on server.')
        self.assertEqual(self.request_handler.path, '/post_target',
                 'Incorrect path on server.')
    
    def testPostTempFile(self):
        """Test a post request using a TempFile"""
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
        
        runThread = True
        def test_thread():
            server = BaseHTTPServer.HTTPServer(('', 6110), TestRequestHandler)
            while runThread:
                server.handle_request()
            server.server_close()
        
        thread = threading.Thread(target=test_thread)
        thread.start()
        
        # Do this here so test_thread sees it after it drops out of
        #  handle_request after curl makes its request.
        runThread = False
        test_file = tempfile.TemporaryFile()
        test_file.write('foo=bar&baz=garply\r\n')
        test_file.flush()
        test_file.seek(0)
        resp, content = self.fcurl.post_url('http://127.0.0.1:6110/post_target',
                                            upload_file=test_file)
        self.assertEqual(self.request_handler.headers['content-length'], '20')
        self.assertEqual(self.post_content, 'foo=bar&baz=garply\r\n')
        self.assertEqual(self.request_handler.path, '/post_target',
                 'Incorrect path on server.')
    
    def testPutData(self):
        """Test a basic put request"""
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
        
        runThread = True
        def test_thread():
            server = BaseHTTPServer.HTTPServer(('', 6110), TestRequestHandler)
            while runThread:
                server.handle_request()
            server.server_close()
        
        thread = threading.Thread(target=test_thread)
        thread.start()
        
        # Do this here so test_thread sees it after it drops out of
        #  handle_request after curl makes its request.
        runThread = False
        resp, content = self.fcurl.put_url('http://127.0.0.1:6110/put_target',
                                            data='foo=bar&baz=garply\r\n')
        self.assertEqual(self.request_handler.headers['content-length'], '20')
        self.assertEqual(self.put_content, 'foo=bar&baz=garply\r\n',
                         'Incorrect data on server.')
        self.assertEqual(self.request_handler.path, '/put_target',
                 'Incorrect path on server.')
    
    def testPutTempFile(self):
        """Test a put request using a TempFile"""
        class TestRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
            test_object = self
            
            def do_PUT(self):
                self.test_object.request_handler = self
                chunk_size = int(self.rfile.readline(), 16)
                self.test_object.put_content = \
                    self.rfile.read(int(self.headers['content-length']))
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write('This is a test line.\n')
        
        runThread = True
        def test_thread():
            server = BaseHTTPServer.HTTPServer(('', 6110), TestRequestHandler)
            while runThread:
                server.handle_request()
            server.server_close()
        
        thread = threading.Thread(target=test_thread)
        thread.start()
        
        # Do this here so test_thread sees it after it drops out of
        #  handle_request after curl makes its request.
        runThread = False
        test_file = tempfile.TemporaryFile()
        test_file.write('foo=bar&baz=garply\r\n')
        test_file.flush()
        test_file.seek(0)
        resp, content = self.fcurl.put_url('http://127.0.0.1:6110/put_target',
                                            upload_file=test_file)
        self.assertEqual(self.request_handler.headers['content-length'], '20')
        self.assertEqual(self.put_content, 'foo=bar&baz=garply\r\n',
                         'Incorrect data on server.')
        self.assertEqual(self.request_handler.path, '/put_target',
             'Incorrect path on server.')
    
    def testDelete(self):
        """Test a delete request"""
        class TestRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
            test_object = self
            
            def do_DELETE(self):
                self.test_object.request_handler = self
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write('This is a test line.\n')
        
        runThread = True
        def test_thread():
            server = BaseHTTPServer.HTTPServer(('', 6110), TestRequestHandler)
            while runThread:
                server.handle_request()
            server.server_close()
        
        thread = threading.Thread(target=test_thread)
        thread.start()
        
        # Do this here so test_thread sees it after it drops out of
        #  handle_request after curl makes its request.
        runThread = False
        resp, content = self.fcurl.delete_url('http://127.0.0.1:6110/del_target')
        self.assertEqual(self.request_handler.path, '/del_target',
             'Incorrect path on server.')
    
    def testThreadSingleton(self):
        h1 = friendly_curl.threadCURLSingleton()
        h2 = friendly_curl.threadCURLSingleton()
        self.assert_(h1 is h2)
        foo = {}
        def test_thread():
            foo['h3'] = friendly_curl.threadCURLSingleton()
            foo['h4'] = friendly_curl.threadCURLSingleton()
        thread = threading.Thread(target=test_thread)
        thread.start()
        thread.join()
        self.assert_(foo['h3'] is foo['h4'])
        self.assert_(h1 is not foo['h3'])
        self.assert_(h1 is not foo['h4'])
        self.assert_(h2 is not foo['h3'])
        self.assert_(h2 is not foo['h4'])
    
    def testFollowLocation(self):
        """Test a basic get request"""
        self.requests_made = 0
        class TestRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
            test_object = self
            
            def do_GET(self):
                if self.test_object.requests_made == 0:
                    self.test_object.first_request_handler = self
                    self.send_response(302)
                    self.send_header('Content-Type', 'text/html')
                    self.send_header('Location', 'http://127.0.0.1:6110/foo.html')
                    self.end_headers()
                    self.wfile.write('This is a test redirect.\n')
                    self.test_object.requests_made = 1
                elif self.test_object.requests_made == 1:
                    self.test_object.second_request_handler = self
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html')
                    self.end_headers()
                    self.wfile.write('This is a test line.\n')
                    self.test_object.requests_made = 2
        
        def test_thread():
            server = BaseHTTPServer.HTTPServer(('', 6110), TestRequestHandler)
            while self.requests_made != 2:
                server.handle_request()
            server.server_close()
        
        thread = threading.Thread(target=test_thread)
        thread.start()
        
        # Do this here so test_thread sees it after it drops out of
        #  handle_request after curl makes its request.
        resp, content = self.fcurl.get_url('http://127.0.0.1:6110/index.html',
                                           follow_location=True)
        self.assertEqual(resp['status'], 200, 'Unexpected HTTP status.')
        self.assertEqual(resp['content-type'], 'text/html',
                         'Unexpected Content-Type from server.')
        self.assertEqual(resp['location'], 'http://127.0.0.1:6110/foo.html',
                         'Unexpected location from server.')
        self.assertEqual(content.getvalue(), 'This is a test line.\n',
                         'Incorrect content returned by server.')
        self.assertEqual(self.first_request_handler.path, '/index.html',
                         'Incorrect path on server.')
        self.assertEqual(self.second_request_handler.path, '/foo.html',
                         'Incorrect path on server.')
