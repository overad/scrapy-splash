# -*- coding: utf-8 -*-
from __future__ import absolute_import

import json
import base64

from scrapy.http.headers import Headers

from scrapy.http import Response, TextResponse
from scrapy import Selector


class _SplashResponseMixin(object):
    """
    This mixin fixes response.url and adds response.real_url
    """
    def __init__(self, url, *args, **kwargs):
        real_url = kwargs.pop('real_url', None)
        if real_url is not None:
            self.real_url = real_url
        else:
            self.real_url = None
            # FIXME: create a .request @property with a setter?
            # Scrapy doesn't pass request to Response constructor;
            # it is worked around in SplashMiddleware.
            request = kwargs['request']
            splash_args = self._splash_args(request)
            _url = splash_args.get('url')
            if _url is not None:
                self.real_url = url
                url = _url
        super(_SplashResponseMixin, self).__init__(url, *args, **kwargs)

    def replace(self, *args, **kwargs):
        """Create a new Response with the same attributes except for those
        given new values.
        """
        for x in ['url', 'status', 'headers', 'body', 'request', 'flags',
                  'real_url']:
            kwargs.setdefault(x, getattr(self, x))
        cls = kwargs.pop('cls', self.__class__)
        return cls(*args, **kwargs)

    def _splash_options(self, request=None):
        if request is None:
            request = self.request
        return request.meta.get("_splash_processed", {})

    def _splash_args(self, request=None):
        return self._splash_options(request).get('args', {})


class SplashResponse(_SplashResponseMixin, Response):
    """
    This Response subclass sets response.url to the URL of a remote website
    instead of an URL of Splash server. "Real" response URL is still available
    as ``response.real_url``.
    """


class SplashTextResponse(_SplashResponseMixin, TextResponse):
    """
    This TextResponse subclass sets response.url to the URL of a remote website
    instead of an URL of Splash server. "Real" response URL is still available
    as ``response.real_url``.
    """
    def replace(self, *args, **kwargs):
        kwargs.setdefault('encoding', self.encoding)
        return _SplashResponseMixin.replace(self, *args, **kwargs)


class SplashJsonResponse(SplashResponse):
    """
    Splash Response with JSON data. It provides a convenient way to access
    parsed JSON response using ``response.data`` attribute.

    If Scrapy-Splash response magic is enabled in request
    (['splash']['magic_response'] is not False), several other response
    attributes (headers, body, url, status code) are set automatically:

    * response.headers are filled from 'headers' and 'cookies' keys;
    * response.url is set to the value of 'url' key;
    * response.body is set to the value of 'html' key,
      or to base64-decoded value of 'body' key;
    * response.status is set from the value of 'http_status' key.
    """
    def __init__(self, *args, **kwargs):
        self._cached_ubody = None
        self._cached_data = None
        self._cached_selector = None
        kwargs.pop('encoding', None)  # encoding is always utf-8
        super(SplashJsonResponse, self).__init__(*args, **kwargs)

        # FIXME: it assumes self.request is set
        if self._splash_options().get('magic_response', True):

            # response.status
            if 'http_status' in self.data:
                self.status = int(self.data['http_status'])

            # response.url
            if 'url' in self.data:
                self._url = self.data['url']

            # response.body
            if 'body' in self.data:
                self._body = base64.b64decode(self.data['body'])
                self._cached_ubody = self._body.decode(self.encoding)
            elif 'html' in self.data:
                self._cached_ubody = self.data['html']
                self._body = self._cached_ubody.encode(self.encoding)

            # response.headers
            if 'headers' in self.data:
                self.headers = self._build_headers(self.data['headers'])
            if 'cookies' in self.data:
                raise NotImplementedError("TODO: add Set-Cookie header")

    @classmethod
    def _build_headers(cls, headers):
        """
        Return Headers instance from headers data.
        3 data formats are supported:

        * {name: value, ...} dict;
        * [(name, value), ...] list;
        * [{'name': name, 'value': value'}, ...] list (HAR headers format).
        """
        if isinstance(headers or {}, dict):
            return Headers(headers or {})

        if isinstance(headers[0], dict):
            return Headers([
                (d['name'], d.get('value', ''))
                for d in headers
            ])

        return Headers(headers)

    @property
    def data(self):
        if self._cached_data is None:
            self._cached_data = json.loads(self._ubody)
        return self._cached_data

    @property
    def text(self):
        return self._ubody

    def body_as_unicode(self):
        return self._ubody

    @property
    def _ubody(self):
        if self._cached_ubody is None:
            self._cached_ubody = self.body.decode(self.encoding)
        return self._cached_ubody

    @property
    def encoding(self):
        return 'utf8'

    @property
    def selector(self):
        if self._cached_selector is None:
            self._cached_selector = Selector(text=self.text, type='html')
        return self._cached_selector

    def xpath(self, query):
        return self.selector.xpath(query)

    def css(self, query):
        return self.selector.css(query)
