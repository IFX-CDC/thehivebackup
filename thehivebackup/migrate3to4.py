import json
import os
import shutil


def migrate_case(old_case):
    new_case = {}
    for key, values in old_case.items():
        if key == 'metrics':
            for value in values:
                new_case['customFields'][value] = values[value]
        else:
            new_case[key] = values
    new_case['customFields']['old-case-no'] = old_case['caseId']
    new_case['customFields']['old-case-id'] = old_case['id']
    return new_case


def migrate(backup):
    with open(os.path.join(backup, 'cases.jsonl')) as io, \
            open(os.path.join(backup, 'cases.jsonl.cpy'), 'w+') as writer:
        for line in io:
            case = json.loads(line)
            case = migrate_case(case)
            json.dump(case, writer)
            writer.write('\n')
    shutil.move('cases.jsonl.cpy', 'cases.jsonl')
