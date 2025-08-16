# Endpoint.py

import requests

class Endpoint:
    def __init__(self,
                 url=None,
                 method='GET',
                 headers=None,
                 payload=None,
                 files=None,
                 post_function=None):

        self.url = url
        self.method = method.upper()
        self.headers = headers or {}
        self.payload = payload or {}
        self.files = files or {}
        self.post_function = post_function

    def __str__(self):
        return (f'Endpoint(url={self.url}, method={self.method}, '
                f'headers={self.headers}, payload={self.payload}, '
                f'files={self.files}, post_function={self.post_function})')

    def __repr__(self):
        return self.__str__()

    def to_dict(self):
        return {
            'url': self.url,
            'method': self.method,
            'headers': self.headers,
            'payload': self.payload,
            'files': self.files,
            'post_function': self.post_function
        }

    def __eq__(self, other):
        if not isinstance(other, Endpoint):
            return False
        return self.to_dict() == other.to_dict()

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.__str__())

    def __copy__(self):
        return Endpoint(
            url=self.url,
            method=self.method,
            headers=self.headers.copy(),
            payload=self.payload.copy(),
            files=self.files.copy(),
            post_function=self.post_function
        )

    def fetch(self):
        request_kwargs = {
            'method': self.method,
            'url': self.url,
            'headers': self.headers,
        }

        if self.files:
            request_kwargs['files'] = self.files
            request_kwargs['data'] = self.payload
        elif self.headers.get('Content-Type') == 'application/json':
            request_kwargs['json'] = self.payload
        else:
            request_kwargs['data'] = self.payload

        response = requests.request(**request_kwargs)

        try:
            response_obj = response.json()
        except Exception:
            response_obj = response.text

        if self.post_function:
            if callable(self.post_function):
                self.post_function(response_obj)
            else:
                raise ValueError('post_function must be callable')

        return response_obj, response.status_code, response
