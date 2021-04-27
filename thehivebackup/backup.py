import datetime
import json
import os
from multiprocessing import Pool

import urllib3
from thehive4py.api import TheHiveApi
from thehive4py.query import Between

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class Backupper:

    def __init__(self, backupdir: str, url: str, api_key: str, org: str = None, verify: bool = True):
        url = url.strip("/")
        self.api = TheHiveApi(url, api_key, organisation=org)

        if not verify:
            self.api.cert = False

        self.backupdir = f'{backupdir}-{int(datetime.datetime.utcnow().timestamp())}'
        os.makedirs(self.backupdir, exist_ok=True)
        self.case_file = os.path.join(self.backupdir, 'cases.jsonl')
        self.alert_file = os.path.join(self.backupdir, 'alerts.jsonl')

    def get_file(self, attachment_id: str):
        os.makedirs(os.path.join(self.backupdir, 'attachments'), exist_ok=True)
        response = self.api.download_attachment(attachment_id)
        with open(os.path.join(self.backupdir, 'attachments', attachment_id), 'wb') as io:
            io.write(response.content)

    def backup_cases_all(self) -> [dict]:
        cases = self.api.find_cases(query={}, sort=['-createdAt'], range='all').json()
        self._backup_cases(cases)

    def backup_cases_range(self, start, end) -> [dict]:
        query = Between("createdAt", start, end)
        cases = self.api.find_cases(query=query, sort=['-createdAt'], range='all').json()
        self._backup_cases(cases)

    def _backup_cases(self, cases: [dict]):
        with open(self.case_file, 'w+', encoding='utf8') as io:
            with Pool(processes=8) as pool:
                for case in cases:
                    json.dump(case, io)
                    io.write('\n')

                pool.map(self._backup_case, cases)
                pool.close()
                pool.join()

    def _backup_case(self, case: dict):
        self.backup_observables(case['id'])
        self.backup_tasks(case['id'])

    def backup_tasks(self, case_id: str) -> [dict]:
        tasks = self.api.get_case_tasks(case_id=case_id).json()
        if tasks:
            case_path = os.path.join(self.backupdir, 'cases', case_id)
            os.makedirs(case_path, exist_ok=True)
            with open(os.path.join(case_path, 'tasks.jsonl'), 'w+', encoding='utf8') as io:
                for task in tasks:
                    json.dump(task, io)
                    io.write('\n')
                    self.backup_logs(case_id, task['id'])

    def backup_logs(self, case_id: str, task_id: str) -> [dict]:
        logs = self.api.get_task_logs(task_id).json()
        if logs:
            task_path = os.path.join(self.backupdir, 'cases', case_id, 'tasks', task_id)
            os.makedirs(task_path, exist_ok=True)
            with open(os.path.join(task_path, 'logs.jsonl'), 'w+', encoding='utf8') as io:
                for log in logs:
                    json.dump(log, io)
                    io.write('\n')
                    if 'attachment' in log:
                        self.get_file(log['attachment']['id'])

    def backup_observables(self, case_id: str):
        observables = self.api.get_case_observables(case_id).json()
        if observables:
            os.makedirs(os.path.join(self.backupdir, 'cases', case_id), exist_ok=True)
            with open(os.path.join(self.backupdir, 'cases', case_id, 'observables.jsonl'), 'w+', encoding='utf8') as io:
                for observable in observables:
                    json.dump(observable, io)
                    io.write('\n')
                    if 'attachment' in observable:
                        self.get_file(observable['attachment']['id'])

    def backup_alerts_all(self):
        alerts = self.api.find_alerts(query={}, sort=['-createdAt'], range='all').json()
        self._backup_alerts(alerts)

    def backup_alerts_range(self, start, end):
        query = Between("createdAt", start, end)
        alerts = self.api.find_alerts(query=query, sort=['-createdAt'], range='all').json()
        self._backup_alerts(alerts)

    def _backup_alerts(self, alerts):
        with open(self.alert_file, 'w+', encoding='utf8') as io:
            for alert in alerts:
                json.dump(alert, io)
                io.write('\n')
