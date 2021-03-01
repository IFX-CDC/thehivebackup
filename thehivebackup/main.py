import argparse
import csv
import datetime
import logging
import sys
import time

import urllib3

from thehivebackup.backup import Backupper
from thehivebackup.empty import Deletor
from thehivebackup.migrate3to4 import migrate
from thehivebackup.recover import Restorer

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(prog="thehivebackup", description="Backup and restore TheHive remotely.")
    parser.add_argument("-v", "--verbose", help="Show logging.", dest='verbose', action="store_true", default=False)

    subparsers = parser.add_subparsers(title="subcommands", dest="subcommand", required=True)

    parser_backup = subparsers.add_parser('backup', description='Backup TheHive')
    parser_backup.add_argument('--key', type=str, required=True, help='TheHive api key')
    parser_backup.add_argument('--org', type=str, required=False, help='Organisation')
    parser_backup.add_argument('--year', type=int, help='Pass --year and --month to backup a single month')
    parser_backup.add_argument('--month', type=int, help='Pass --year and --month to backup a single month')
    parser_backup.add_argument('--day', type=int, help='Pass --year and --month to backup a single month')
    parser_backup.add_argument("--no-verify", help="Set to false to disable ssl verification", dest='verify',
                               action="store_false", default=True)
    parser_backup.add_argument('host', type=str, help='host of TheHive api')

    parser_migrate = subparsers.add_parser('migrate3to4', description='Migrate TheHive')
    parser_migrate.add_argument('--mapping', type=str, help='User mapping csv file')
    parser_migrate.add_argument('backup', type=str, help='TheHive backup')

    parser_restore = subparsers.add_parser('restore', description='Restore TheHive')
    parser_restore.add_argument('--key', type=str, required=True, help='TheHive api key')
    parser_restore.add_argument('--org', type=str, required=False, help='Organisation')
    parser_restore.add_argument('--connections', type=int, help='maximum connections')
    parser_restore.add_argument('--mapping', type=str, help='User mapping csv file')
    parser_restore.add_argument("--no-verify", help="Set to false to disable ssl verification", dest='verify',
                                action="store_false", default=True)
    parser_restore.add_argument('backup', type=str, help='TheHive backup')
    parser_restore.add_argument('host', type=str, help='host of TheHive api')

    parser_clear = subparsers.add_parser('clear', description='Clean TheHive')
    parser_clear.add_argument('--key', type=str, required=True, help='TheHive api key')
    parser_clear.add_argument('--org', type=str, required=False, help='Organisation')
    parser_clear.add_argument('--connections', type=int, help='maximum connections')
    parser_clear.add_argument("--no-verify", help="Set to false to disable ssl verification", dest='verify',
                              action="store_false", default=True)
    parser_clear.add_argument('host', type=str, help='host of TheHive api')

    if len(sys.argv) < 2:
        parser.print_usage()
        sys.exit(1)

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    if args.subcommand == "backup":
        backup(args)
    elif args.subcommand == "migrate3to4":
        migrate(args.backup)
    elif args.subcommand == "restore":
        mapping = dict()
        if args.mapping:
            mapping = load_mapping(args.mapping)
        restore(args, mapping)
    elif args.subcommand == "clear":
        clear(args)


def load_mapping(mapping_path: str) -> dict:
    mapping = dict()
    with open(mapping_path, mode='r') as infile:
        reader = csv.reader(infile)
        for row in reader:
            mapping[row[0]] = {'mail': row[1], 'key': row[2]}
    return mapping


def parse_url(url_str: str) -> (bool, str, int):
    url = urllib3.util.parse_url(url_str)
    ssl = True
    if url.scheme is not None and url.scheme == "http":
        ssl = False
    if url.host is None:
        print("Host invalid.")
        sys.exit(1)
    port = url.port
    if port is None:
        port = 443
    return ssl, url.host, port


def clear(args):
    ssl, host, port = parse_url(args.host)
    deletor = Deletor(host, args.key, port, ssl, args.verify, args.connections)
    deletor.delete_cases()
    deletor.delete_alerts()


def restore(args, mapping):
    start_time = time.time()
    ssl, host, port = parse_url(args.host)
    print(f'Start at {datetime.datetime.now().isoformat()}')
    recoverer = Restorer(args.backup, host, port, args.key, mapping, args.connections, ssl, args.verify)
    recoverer.store_cases()
    recoverer.restore_alerts()
    print(f'Restore done in {time.time() - start_time} seconds')


def utc_nano_timestamp(year: int, month: int, day: int) -> int:
    return int(datetime.datetime(year, month, day, tzinfo=datetime.timezone.utc).timestamp() * 1000)


def backup(args):
    start_time = time.time()
    ssl, host, port = parse_url(args.host)
    if args.year is None and args.month is None:
        migration = Backupper(f"backup-{args.org}-full", host, args.key, args.org, port, ssl, args.verify)
        migration.backup_cases_all()
        migration.backup_alerts_all()
    elif args.year is not None and args.month is not None:
        if args.day is None:
            name = f"backup-{args.org}-{args.year}-{args.month}"
            start = utc_nano_timestamp(args.year, args.month, 1)
            next_month = args.month + 1
            if next_month == 13:
                next_month = 1
            end = utc_nano_timestamp(args.year, next_month, 1) - 1
        else:
            name = f"backup-{args.org}-{args.year}-{args.month}-{args.day}"
            start = utc_nano_timestamp(args.year, args.month, args.day)
            end = start + 60 * 60 * 24 * 1000 - 1
        migration = Backupper(name, host, args.org, args.key, port, ssl, args.verify)
        migration.backup_cases_range(start, end)
        migration.backup_alerts_range(start, end)
    else:
        print("Either --year and --month need to be given or none of both.")
        sys.exit(1)
    print(f'Backup done in {time.time() - start_time:.2f} seconds')


if __name__ == '__main__':
    main()
