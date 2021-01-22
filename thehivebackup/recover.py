import datetime
import json
import logging
import os
from multiprocessing import Pool

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class Restorer:

    def __init__(self, backupdir: str, host: str, port: int, api_key: str, mapping: dict, connections: int = 32,
                 ssl=True, verify=True):
        self.host = host
        self.port = port
        self.ssl = ssl
        self.verify = verify
        self.api_key = api_key
        self.mapping = mapping
        self.connections = connections

        self.backupdir = backupdir
        self.case_file = os.path.join(backupdir, 'cases.jsonl')
        self.alert_file = os.path.join(backupdir, 'alerts.jsonl')

    def request(self, method: str, url: str, api_key: str, data: dict, files: dict = None) -> requests.Response:
        headers = {'Authorization': 'Bearer ' + api_key}
        url_str = f"http://{self.host}:{self.port}{url}"
        if self.ssl:
            url_str = f"https://{self.host}:{self.port}{url}"
        if files is None:
            response = requests.request(method, url_str, headers=headers, verify=self.verify, json=data)
        else:
            data = {"_json": json.dumps(data)}
            response = requests.request(method, url_str, headers=headers, verify=self.verify, data=data, files=files)
        if response.status_code != 200 and response.status_code != 201:
            if "id" in data:
                logging.warning("id: %s", data['id'])
            logging.warning(url_str)
            logging.warning(data)
            logging.warning(response.text)
        return response

    def restore_file(self, url: str, api_key: str, case_object: dict) -> requests.Response:
        filename = case_object['attachment']['name']
        file_id = case_object['attachment']['id']
        with open(os.path.join(self.backupdir, 'attachments', file_id), 'rb') as io:
            file_data = io.read()
        del case_object['attachment']
        return self.request('POST', url, api_key, case_object, {'attachment': (filename, file_data)})

    def get_api_key(self, case_object: dict):
        api_key = self.api_key
        if case_object['createdBy'] in self.mapping:
            api_key = self.mapping[case_object['createdBy']]['key']
        return api_key

    def update_user(self, case_object: dict) -> dict:
        new_data = {}
        if 'owner' in case_object:
            if case_object['owner'] in self.mapping:
                new_data['owner'] = self.mapping[case_object['owner']]['mail']
        if 'updatedBy' in case_object:
            if case_object['updatedBy'] in self.mapping:
                new_data['updatedBy'] = self.mapping[case_object['updatedBy']]['mail']
        return new_data

    def store_cases(self):
        with open(self.case_file, 'r') as io:
            pool = Pool(processes=self.connections)
            pool.map(self.restore_case_line, io)

    def restore_case_line(self, line):
        case = json.loads(line)
        old_case_id = case['id']
        api_key = self.get_api_key(case)
        response = self.request('POST', '/api/case', api_key, case)
        if response.status_code == 200 or response.status_code == 201:
            # new_case_id = json.loads(response.read())['id']
            new_case_id = response.json()['id']

            new_data = self.update_user(case)
            if new_data:
                self.request('PATCH', f'/api/case/{new_case_id}', api_key, new_data)

            if os.path.exists(os.path.join(self.backupdir, 'cases', old_case_id)):
                self.restore_observables(old_case_id, new_case_id)
                self.restore_tasks(old_case_id, new_case_id)

    def restore_observables(self, old_case_id: str, new_case_id: str):
        observables_path = os.path.join(self.backupdir, 'cases', old_case_id, 'observables.jsonl')
        if os.path.exists(observables_path):
            with open(observables_path) as io:
                for line in io:
                    observable = json.loads(line)
                    if 'attachment' in observable:
                        self.restore_file(f'/api/case/{new_case_id}/artifact', self.api_key, observable)
                    else:
                        self.request('POST', f'/api/case/{new_case_id}/artifact', self.api_key, observable)

    def restore_tasks(self, old_case_id: str, new_case_id: str):
        task_path = os.path.join(self.backupdir, 'cases', old_case_id, 'tasks.jsonl')
        if os.path.exists(task_path):
            with open(task_path) as io:
                for line in io:
                    task = json.loads(line)
                    api_key = self.get_api_key(task)
                    new_data = self.update_user(task)
                    task.update(new_data)

                    response = self.request('POST', f'/api/case/{new_case_id}/task', api_key, task)

                    if response.status_code == 200 or response.status_code == 201:
                        # new_task_id = json.loads(response.read())['id']
                        new_task_id = response.json()['id']
                        new_data = self.update_user(task)
                        self.request('PATCH', f'/api/case/task/{new_task_id}', api_key, new_data)

                        if os.path.exists(os.path.join(self.backupdir, 'cases', old_case_id, 'tasks', task['id'])):
                            self.restore_logs(old_case_id, task['id'], new_task_id)

    def restore_logs(self, old_case_id: str, old_task_id: str, new_task_id: str):
        logs_path = os.path.join(self.backupdir, 'cases', old_case_id, 'tasks', old_task_id, 'logs.jsonl')
        if os.path.exists(logs_path):
            with open(logs_path) as io:
                for line in io:
                    log = json.loads(line)
                    api_key = self.get_api_key(log)
                    timestamp = datetime.datetime.fromtimestamp(log['createdAt'] / 1000).isoformat()
                    log['message'] = f'Original log by: {log["owner"]} Created at: {timestamp}\n\n{log["message"]}'
                    if 'attachment' in log:
                        response = self.restore_file(f'/api/case/task/{new_task_id}/log', api_key, log)
                    else:
                        response = self.request('POST', f'/api/case/task/{new_task_id}/log', api_key, log)
                    if response.status_code == 200 or response.status_code == 201:
                        log_id = response.json()['id']
                        new_data = self.update_user(log)
                        self.request('PATCH', f'/api/case/task/log/{log_id}', api_key, new_data)

    def restore_alerts(self):
        with open(self.alert_file, 'r') as io:
            pool = Pool(processes=self.connections)
            pool.map(self.restore_alert_line, io)

    def restore_alert_line(self, line):
        self.request('POST', '/api/alert/', self.api_key, json.loads(line))
