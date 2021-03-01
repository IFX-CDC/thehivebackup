import datetime
import http.client
import json
import logging
import os
import ssl
from multiprocessing import Pool


class Backupper:

    def __init__(self, backupdir: str, host: str, api_key: str,
                 org: str = "", port: int = 80, use_ssl: bool = True, verify: bool = True):
        self.host = host
        self.port = port
        self.ssl = use_ssl
        self.verify = verify
        self.api_key = api_key

        self.org = org

        self.backupdir = f'{backupdir}-{int(datetime.datetime.utcnow().timestamp())}'
        os.makedirs(self.backupdir, exist_ok=True)
        self.case_file = os.path.join(self.backupdir, 'cases.jsonl')
        self.alert_file = os.path.join(self.backupdir, 'alerts.jsonl')

    def _conn(self):
        if self.ssl:
            if self.verify:
                return http.client.HTTPSConnection(self.host, self.port)
            return http.client.HTTPSConnection(self.host, self.port, context=ssl._create_unverified_context())
        return http.client.HTTPConnection(self.host, self.port)

    def request(self, method: str, url: str, api_key: str, data: dict = None) -> bytes:
        conn = self._conn()
        headers = {'Authorization': 'Bearer ' + api_key}
        if self.org != "":
            headers['X-Organisation'] = self.org
        if data is not None:
            headers['Content-type'] = 'application/json'
            data = json.dumps(data)
        conn.request(method, url, data, headers=headers)
        response = conn.getresponse()
        resp = response.read()
        if response.status != 200 and response.status != 201:
            logging.warning(url)
            logging.warning(resp)
        return resp

    def get_file(self, file_id: str, api_key: str):
        os.makedirs(os.path.join(self.backupdir, 'attachments'), exist_ok=True)
        response = self.request('GET', f'/api/datastore/{file_id}', api_key)
        with open(os.path.join(self.backupdir, 'attachments', file_id), 'wb') as io:
            io.write(response)

    def backup_cases_all(self) -> [dict]:
        cases = self.request('GET', '/api/case?range=all', self.api_key)
        self._backup_cases(json.loads(cases))

    def backup_cases_range(self, start, end) -> [dict]:
        query = {'query': {'_between': {'_field': 'createdAt', '_from': start, '_to': end}}}
        cases = self.request('POST', '/api/case/_search?range=all', self.api_key, query)
        self._backup_cases(json.loads(cases))

    def _backup_cases(self, cases):
        with open(self.case_file, 'w+', encoding='utf8') as io:
            pool = Pool(processes=8)
            for case in cases:
                json.dump(case, io)
                io.write('\n')
                # self.backup_observables(case['id'])
                # self.backup_tasks(case['id'])

            pool.map(self._backup_case, cases)
            pool.close()
            pool.join()

    def _backup_case(self, case):
        self.backup_observables(case['id'])
        self.backup_tasks(case['id'])

    def backup_tasks(self, case_id: str) -> [dict]:
        query = {'query': {'_parent': {'_type': 'case', '_query': {'_id': case_id}}}}
        tasks = self.request('POST', '/api/case/task/_search?range=all', self.api_key, query)
        tasks = json.loads(tasks)
        if tasks:
            case_path = os.path.join(self.backupdir, 'cases', case_id)
            os.makedirs(case_path, exist_ok=True)
            with open(os.path.join(case_path, 'tasks.jsonl'), 'w+', encoding='utf8') as io:
                for task in tasks:
                    json.dump(task, io)
                    io.write('\n')
                    self.backup_logs(case_id, task['id'])

    def backup_logs(self, case_id: str, task_id: str) -> [dict]:
        logs = self.request('GET', f'/api/case/task/{task_id}/log', self.api_key)
        logs = json.loads(logs)
        if logs:
            task_path = os.path.join(self.backupdir, 'cases', case_id, 'tasks', task_id)
            os.makedirs(task_path, exist_ok=True)
            with open(os.path.join(task_path, 'logs.jsonl'), 'w+', encoding='utf8') as io:
                for log in logs:
                    json.dump(log, io)
                    io.write('\n')
                    if 'attachment' in log:
                        self.get_file(log['attachment']['id'], self.api_key)

    def backup_observables(self, case_id: str):
        query = {'query': {'_parent': {'_type': 'case', '_query': {'_id': case_id}}}}
        observables = self.request('POST', '/api/case/artifact/_search?range=all', self.api_key, query)
        observables = json.loads(observables)
        if observables:
            os.makedirs(os.path.join(self.backupdir, 'cases', case_id), exist_ok=True)
            with open(os.path.join(self.backupdir, 'cases', case_id, 'observables.jsonl'), 'w+', encoding='utf8') as io:
                for observable in observables:
                    json.dump(observable, io)
                    io.write('\n')
                    if 'attachment' in observable:
                        self.get_file(observable['attachment']['id'], self.api_key)

    def backup_alerts_all(self):
        alerts = self.request('GET', '/api/alert?range=all', self.api_key)
        alerts = json.loads(alerts)
        self._backup_alerts(alerts)

    def backup_alerts_range(self, start, end):
        query = {'query': {'_between': {'_field': 'createdAt', '_from': start, '_to': end}}}
        alerts = self.request('POST', '/api/alert/_search?range=all', self.api_key, query)
        alerts = json.loads(alerts)
        self._backup_alerts(alerts)

    def _backup_alerts(self, alerts):
        with open(self.alert_file, 'w+', encoding='utf8') as io:
            for alert in alerts:
                json.dump(alert, io)
                io.write('\n')
