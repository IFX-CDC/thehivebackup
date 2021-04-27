import http.client
import json
import ssl
from multiprocessing import Pool


class Deletor:

    def __init__(self, host, api_key, port=None, use_ssl=True, verify=True, connections=32):
        self.host = host
        self.port = port
        self.ssl = use_ssl
        self.verify = verify
        self.connections = connections

        self.api_key = api_key

    def _conn(self):
        if self.ssl:
            if self.verify:
                return http.client.HTTPSConnection(self.host, self.port)
            return http.client.HTTPSConnection(self.host, self.port, context=ssl._create_unverified_context())
        return http.client.HTTPConnection(self.host, self.port)

    def delete_alert(self, alert):
        conn = self._conn()
        conn.request("DELETE", "/api/alert/" + alert['id'], headers={'Authorization': 'Bearer ' + self.api_key})
        conn.getresponse()

    def delete_alerts(self):
        conn = self._conn()
        conn.request("GET", "/api/alert?range=all", headers={'Authorization': 'Bearer ' + self.api_key})
        response = conn.getresponse()
        resp = response.read()

        alerts = json.loads(resp)

        with Pool(processes=self.connections) as pool:
            pool.map(self.delete_alert, alerts)

    def delete_case(self, case):
        conn = self._conn()
        conn.request("DELETE", "/api/case/" + case['id'], headers={'Authorization': 'Bearer ' + self.api_key})
        conn.getresponse()

    def delete_cases(self):
        conn = self._conn()
        conn.request("GET", "/api/case?range=all", headers={'Authorization': 'Bearer ' + self.api_key})
        response = conn.getresponse()
        resp = response.read()

        cases = json.loads(resp)

        with Pool(processes=self.connections) as pool:
            pool.map(self.delete_case, cases)
