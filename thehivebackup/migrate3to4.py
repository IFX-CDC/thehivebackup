import csv
import json
import os
import shutil


def ensure_custom_fields(case):
    if "customFields" not in case:
        case["customFields"] = {}
    return case


def add_old_no(case):
    case["customFields"]['old-case-no'] = case['caseId']
    case["customFields"]['old-case-id'] = case['id']
    return case


def migrate_fields(case: dict, field_mapping_file: str) -> dict:
    with open(field_mapping_file, mode='r') as io:
        reader = csv.reader(io)
        field_mapping = dict(reader)

    new_fields = {}
    for field in case["customFields"]:
        if field in field_mapping:
            new_fields[field_mapping[field]] = case["customFields"][field]
    case["customFields"] = new_fields

    return case


def migrate_metrics(case: dict, metrics_mapping_file: str) -> dict:
    with open(metrics_mapping_file, mode='r') as io:
        reader = csv.reader(io)
        metric_mapping = dict(reader)

    new_fields = {}
    if "metrics" in case:
        for metric in case["metrics"]:
            if metric in metric_mapping:
                new_fields[metric_mapping[metric]] = {"integer": case["metrics"][metric]}
            if metrics_mapping_file == "":
                new_fields[metric] = {"integer": case["metrics"][metric]}
        case["customFields"].update(new_fields)
        del case["metrics"]

    return case


def migrate_user(case: dict, user_mapping_file: str, default_user: str) -> dict:
    users = {}
    if user_mapping_file:
        with open(user_mapping_file, mode='r') as io:
            reader = csv.reader(io)
            users = dict(reader)
    if 'owner' in case:
        if case['owner'] in users:
            case['owner'] = users[case['owner']]
        else:
            case['owner'] = default_user
    return case


def replace_user(filename, usermapping, default_user: str):
    if os.path.exists(filename):
        with open(filename) as io, open(filename + '.cpy', 'w+') as writer:
            for line in io:
                task = json.loads(line)
                task = migrate_user(task, usermapping, default_user)
                json.dump(task, writer)
                writer.write('\n')
        shutil.move(filename, filename + '.bak')
        shutil.move(filename + '.cpy', filename)


def migrate(args):
    with open(os.path.join(args.backup, 'cases.jsonl')) as io, \
            open(os.path.join(args.backup, 'cases.jsonl.cpy'), 'w+') as writer:
        for line in io:
            case = json.loads(line)
            case = ensure_custom_fields(case)
            if args.add_old_no:
                case = add_old_no(case)
            if args.fieldmapping:
                case = migrate_fields(case, args.fieldmapping)
            case = migrate_metrics(case, args.metricmapping)
            case = migrate_user(case, args.usermapping, args.default_user)

            json.dump(case, writer)
            writer.write('\n')

    shutil.move(os.path.join(args.backup, 'cases.jsonl'), os.path.join(args.backup, 'cases.jsonl.bak'))
    shutil.move(os.path.join(args.backup, 'cases.jsonl.cpy'), os.path.join(args.backup, 'cases.jsonl'))

    users = args.usermapping
    for casefolder in os.listdir(os.path.join(args.backup, 'cases')):
        replace_user(os.path.join(args.backup, 'cases', casefolder, 'tasks.jsonl'), users, args.default_user)
        replace_user(os.path.join(args.backup, 'cases', casefolder, 'observables.jsonl'), users, args.default_user)

        taskdir = os.path.join(args.backup, 'cases', casefolder, "tasks")
        if os.path.exists(taskdir):
            for taskfolder in os.listdir(taskdir):
                replace_user(os.path.join(taskdir, taskfolder, 'logs.jsonl'), users, args.default_user)
