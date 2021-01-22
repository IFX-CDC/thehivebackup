# Backup and Restore TheHive

This tool can be used to back up and restore [TheHive](https://github.com/TheHive-Project/TheHive) via its API.

It can also be used to migrate TheHive.

## Install

```
pip install thehivebackup
```

## Usage

``` bash
# Backup a single day remotely
thehivebackup backup --host="thehive3.mycompany.com" --key="1234567890ABCDEF" --year 2020 --month 8 --day 1

# Migrate a backup from 3 to 4
thehivebackup migrate3to4 backup-2020-8-1-1608320637

# Clear the local TheHive
# THIS WILL REMOVE ALL CASES AND ALERTS, USE WITH CAUTION!
# thehivebackup clear --host="localhost:8080" --key="FEDCBA0987654321"

# Recover a backup locally
thehivebackup recover --host="localhost:8080" --key="FEDCBA0987654321" backup-2020-8-1-1608320637
```

For larger setups you might want to run this in the background:
```
nohup thehivebackup backup --host="thehive3.mycompany.com" --key="1234567890ABCDEF" &
tail -f nohup.out
nohup thehivebackup recover --host="localhost:8080" --key="FEDCBA0987654321" --no-ssl backup-full-1608335519 &
```