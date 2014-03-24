import unittest
from unittest import mock

import asyncio
import aiohttp
from aiorest import RESTServer
import json


class RouterTests(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)
        self.server = RESTServer(hostname='example.com', loop=self.loop)

    def tearDown(self):
        self.loop.close()

    def test_add_url(self):
        handler = lambda id: None
        self.server.add_url('post', '/post/{id}', handler)
        self.assertEqual(1, len(self.server._urls))
        entry = self.server._urls[0]
        self.assertEqual('POST', entry.method)
        self.assertIs(handler, entry.handler)
        self.assertEqual('/post/(?P<id>.+)', entry.regex.pattern)

    def test_dispatch_not_found(self):
        m = mock.Mock()
        self.server.add_url('post', '/post/{id}', m)
        self.server.add_url('get', '/post/{id}', m)

        @asyncio.coroutine
        def go():
            with self.assertRaises(aiohttp.HttpException) as ctx:
                yield from self.server.dispatch('POST',
                                                '/not/found', None, None)
            self.assertEqual(404, ctx.exception.code)

        self.assertFalse(m.called)
        self.loop.run_until_complete(go())

    def test_dispatch_method_not_allowed(self):
        m = mock.Mock()
        self.server.add_url('post', '/post/{id}', m)
        self.server.add_url('get', '/post/{id}', m)

        @asyncio.coroutine
        def go():
            with self.assertRaises(aiohttp.HttpException) as ctx:
                yield from self.server.dispatch('DELETE',
                                                '/post/123', None, None)
            self.assertEqual(405, ctx.exception.code)
            self.assertEqual((('Allow', 'GET, POST'),), ctx.exception.headers)

        self.assertFalse(m.called)
        self.loop.run_until_complete(go())

    def test_dispatch(self):
        def f(id):
            return {'a': 1, 'b': 2}
        self.server.add_url('get', '/post/{id}', f)

        ret = self.loop.run_until_complete(self.server.dispatch('GET',
                                                                '/post/123',
                                                                None, None))
        # json.loads is required to avoid items order in dict
        self.assertEqual({"b": 2, "a": 1}, json.loads(ret))

    def test_dispatch_bad_signature(self):
        def f():
            return {'a': 1, 'b': 2}
        self.server.add_url('get', '/post/{id}', f)

        @asyncio.coroutine
        def go():
            with self.assertRaises(aiohttp.HttpException) as ctx:
                yield from self.server.dispatch('GET',
                                                '/post/123', None, None)
            self.assertEqual(500, ctx.exception.code)

        self.loop.run_until_complete(go())

    def test_dispatch_bad_signature2(self):
        def f(unknown_argname):
            return {'a': 1, 'b': 2}
        self.server.add_url('get', '/post/{id}', f)

        @asyncio.coroutine
        def go():
            with self.assertRaises(aiohttp.HttpException) as ctx:
                yield from self.server.dispatch('GET',
                                                '/post/123', None, None)
            self.assertEqual(500, ctx.exception.code)

        self.loop.run_until_complete(go())

    def test_dispatch_http_exception_from_handler(self):
        def f(id):
            raise aiohttp.HttpErrorException(
                401,
                headers=(('WWW-Authenticate', 'Basic'),))
        self.server.add_url('get', '/post/{id}', f)

        @asyncio.coroutine
        def go():
            with self.assertRaises(aiohttp.HttpException) as ctx:
                yield from self.server.dispatch('GET',
                                                '/post/123', None, None)
            self.assertEqual(401, ctx.exception.code)
            self.assertEqual((('WWW-Authenticate', 'Basic'),),
                             ctx.exception.headers)

        self.loop.run_until_complete(go())
