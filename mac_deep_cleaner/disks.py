"""Disk inventory and fail-closed plans; this module never executes a disk change."""
import hashlib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .common import IS_MAC
from .errors import APIError

DISKUTIL = '/usr/sbin/diskutil'
FORMATS = {'APFS': 'APFS', 'APFSX': 'APFS (case-sensitive)',
           'ExFAT': 'ExFAT (Mac and Windows)', 'JHFS+': 'Mac OS Extended (Journaled)'}
DISK_ACTIONS = {'verify-volume', 'verify-disk', 'mount', 'unmount', 'eject',
                'rename', 'add-volume', 'erase', 'partition'}


def whole(identifier):
    match = re.fullmatch(r'(disk\d+)(?:s\d+)*', identifier or '')
    return match.group(1) if match else ''


def volume_name(value):
    if (not isinstance(value, str) or not value.strip() or value != value.strip()
            or len(value.encode('utf-8')) > 64 or value.startswith(('-', '.'))
            or any(ord(c) < 32 or c in '/:\\' or ord(c) == 127 for c in value)
            or value == '%noformat%'):
        raise APIError(400, 'Use a volume name of 1–64 bytes without slashes, colons, '
                       'leading dots/dashes, or surrounding spaces.')
    return value


def format_name(value):
    if not isinstance(value, str) or value not in FORMATS:
        raise APIError(400, 'Choose APFS, case-sensitive APFS, ExFAT, or Mac OS Extended.')
    return value


def inventory(runner):
    if not IS_MAC:
        return {'supported': False, 'checked_at': time.time(), 'devices': [],
                'warnings': ['Disk management requires macOS.'], 'formats': FORMATS}
    listing = runner.plist([DISKUTIL, 'list', '-plist'])
    physical = runner.plist([DISKUTIL, 'list', '-plist', 'physical'])
    apfs = runner.plist([DISKUTIL, 'apfs', 'list', '-plist'])
    startup = runner.plist([DISKUTIL, 'info', '-plist', '/'])
    # diskutil accepts mount points, not arbitrary folders (including ~/ on APFS).
    home_df = runner.text(['/bin/df', '-P', str(Path.home())]).splitlines()
    home_device = home_df[-1].split()[0] if home_df else ''
    if not re.fullmatch(r'/dev/disk\d+(?:s\d+)*', home_device):
        raise APIError(400, 'Could not identify the home filesystem. Disk changes are unavailable.')
    home = runner.plist([DISKUTIL, 'info', '-plist', home_device])
    warnings = []
    try:
        destinations = runner.plist(['/usr/bin/tmutil', 'destinationinfo', '-X'])
    except APIError:
        destinations = {}
        warnings.append('Time Machine destinations could not be checked. Disk changes are disabled.')
    backup_text = json.dumps(destinations)
    physical_ids = {d['DeviceIdentifier'] for d in physical.get('AllDisksAndPartitions', [])}
    nodes = {}

    def collect(node, parent=''):
        identifier = node.get('DeviceIdentifier', '')
        if not whole(identifier):
            return
        nodes[identifier] = {**node, '_parent': parent}
        for child in node.get('Partitions', []) + node.get('APFSVolumes', []):
            collect(child, identifier)

    for node in listing.get('AllDisksAndPartitions', []):
        collect(node)
    containers = {c['ContainerReference']: c for c in apfs.get('Containers', [])}
    roles = {v['DeviceIdentifier']: v.get('Roles', []) for c in containers.values()
             for v in c.get('Volumes', [])}

    def read(identifier):
        try:
            return identifier, runner.plist([DISKUTIL, 'info', '-plist', identifier])
        except APIError:
            return identifier, {}

    with ThreadPoolExecutor(max_workers=6) as pool:
        info = dict(pool.map(read, nodes))
    if any(not v for v in info.values()):
        warnings.append('Some devices could not be inspected. Refresh before changing any disk.')

    def roots(identifier):
        base = whole(identifier)
        if base in containers:
            return {whole(s.get('DeviceIdentifier', ''))
                    for s in containers[base].get('PhysicalStores', [])} - {''}
        return {base} if base in physical_ids else set()

    protected_roots = roots(startup.get('DeviceIdentifier')) | roots(home.get('DeviceIdentifier'))
    if not roots(startup.get('DeviceIdentifier')) or not roots(home.get('DeviceIdentifier')):
        warnings.append('Startup or home disk topology is unknown. Disk changes are disabled.')
    for identifier in containers:
        if len(roots(identifier)) != 1:
            protected_roots |= roots(identifier)
    known_stores = {s.get('DeviceIdentifier') for c in containers.values()
                    for s in c.get('PhysicalStores', [])}
    for identifier, node in nodes.items():
        if (node.get('Content', '').startswith('Apple_APFS')
                and identifier not in containers and identifier not in known_stores):
            protected_roots |= roots(identifier)
        if info[identifier].get('RAIDMaster') or info[identifier].get('RAIDSlice'):
            protected_roots |= roots(identifier)
    devices = []
    for identifier, node in nodes.items():
        data = info[identifier]
        kind = ('disk' if identifier in physical_ids else 'container' if identifier in containers
                else 'volume' if data.get('FilesystemType') else 'partition')
        mount = data.get('MountPoint', '')
        uuid = data.get('VolumeUUID') or data.get('DiskUUID') or node.get('DiskUUID', '')
        backup = ('Backup' in roles.get(identifier, []) or bool(uuid and uuid in backup_text)
                  or bool(mount and mount in backup_text)
                  or bool(mount and (Path(mount) / 'Backups.backupdb').exists()))
        if (backup or roles.get(identifier) or data.get('Bootable')
                or mount == '/' or mount.startswith('/System/')
                or (mount and (str(Path.home()) == mount or str(Path.home()).startswith(mount + '/')))):
            protected_roots |= roots(identifier)
        container = containers.get(identifier) or containers.get(whole(identifier), {})
        total = container.get('CapacityCeiling') or data.get('TotalSize') or node.get('Size', 0)
        free = container.get('CapacityFree', data.get('VolumeFreeSpace'))
        used = data.get('CapacityInUse', node.get('CapacityInUse'))
        if used is None and kind == 'volume' and free is not None:
            used = max(0, total - free)
        devices.append({'id': identifier, 'name': data.get('VolumeName') or data.get('MediaName')
                        or node.get('VolumeName') or identifier, 'kind': kind,
                        'parent': node['_parent'], 'roots': sorted(roots(identifier)),
                        'total': total, 'free': free, 'used': used,
                        'other': max(0, total - (free or 0) - (used or 0)) if free is not None else None,
                        'mount': mount, 'format': data.get('FilesystemUserVisibleName')
                        or node.get('Content', ''), 'internal': data.get('Internal'),
                        'encrypted': data.get('Encrypted', data.get('FileVault', False)),
                        'writable': data.get('Writable') is True,
                        'protocol': data.get('BusProtocol', 'Unknown'),
                        'smart': data.get('SMARTStatus', 'Not supported'),
                        'uuid': uuid, 'roles': roles.get(identifier, []),
                        'backup': backup, 'snapshot': data.get('APFSSnapshot', False),
                        'identity': {k: data.get(k) for k in ('DeviceTreePath', 'MediaUUID',
                            'DiskUUID', 'VolumeUUID', 'MediaName', 'TotalSize', 'Internal',
                            'WholeDisk', 'Content', 'IORegistryEntryName')},
                        'container_uuid': container.get('APFSContainerUUID', '')})
    by_id = {d['id']: d for d in devices}
    for device in devices:
        roots_for_device = device['roots']
        external = bool(roots_for_device) and all(info.get(r, {}).get('Internal') is False
                       and info.get(r, {}).get('WholeDisk') is True for r in roots_for_device)
        related = [d for d in devices if set(d['roots']) & set(roots_for_device)]
        identified = any(d['uuid'] for d in related)
        reason = ''
        if warnings:
            reason = 'Disk safety checks are incomplete. Refresh or use Disk Utility.'
        elif not external:
            reason = 'Internal, virtual, and unidentified disks are protected.'
        elif set(roots_for_device) & protected_roots:
            reason = 'Startup, home, system-role, and detected backup disks are protected.'
        elif len(roots_for_device) != 1:
            reason = 'Multi-disk containers must be managed in Disk Utility.'
        elif not identified:
            reason = 'No stable disk identity is available. Use Disk Utility to initialize this disk.'
        elif not device['writable']:
            reason = 'This device is read-only or locked. Use Disk Utility to unlock it.'
        device['protected_reason'] = reason
        # Presentation is independent from eligibility: hidden OS records still
        # participate in every safety check and remain inspectable on demand.
        os_roles = set(device['roles']) - {'Backup'}
        device['system_managed'] = bool(os_roles or device['mount'].startswith('/System/')
            or device['kind'] == 'partition'
            or (device['kind'] == 'container' and device['internal'] is not False)
            or info[device['id']].get('OSInternal') or info[device['id']].get('OSInternalMedia'))
        device['visible'] = (device['id'] == startup.get('DeviceIdentifier')
                             or device['kind'] == 'disk'
                             or (not device['system_managed'] and not device['snapshot']))
        device['actions'] = []
        if info[device['id']]:
            if device['kind'] == 'disk':
                device['actions'].append('verify-disk')
            if device['kind'] == 'volume' and not device['snapshot']:
                device['actions'].append('verify-volume')
        if not reason:
            if device['kind'] == 'disk':
                device['actions'] += ['eject', 'erase', 'partition']
            if device['kind'] == 'container':
                device['actions'] += ['add-volume']
            if device['kind'] == 'volume' and not device['snapshot']:
                device['actions'] += ['unmount' if device['mount'] else 'mount', 'rename']
        # Only stable topology and identity fields: free space changes constantly.
        stable = [{k: d[k] for k in ('id', 'identity', 'uuid', 'parent', 'roles',
                   'container_uuid', 'name')} for d in related] or [device['identity']]
        device['fingerprint'] = hashlib.sha256(json.dumps(stable, sort_keys=True).encode()).hexdigest()
    startup_device = by_id.get(startup.get('DeviceIdentifier'))
    return {'supported': True, 'checked_at': time.time(), 'devices': devices,
            'startup_id': startup_device['id'] if startup_device else '',
            'warnings': warnings, 'formats': FORMATS}


def disk_plan(body, report):
    action, identifier = body.get('action'), body.get('target')
    if not isinstance(action, str) or action not in DISK_ACTIONS:
        raise APIError(400, 'Choose an available disk operation.')
    if not isinstance(identifier, str) or not whole(identifier):
        raise APIError(400, 'Choose a disk from the current inventory.')
    target = next((d for d in report['devices'] if d['id'] == identifier), None)
    if not target:
        raise APIError(409, 'This disk is no longer connected. Refresh the disk list.')
    if action not in target['actions']:
        raise APIError(400, target['protected_reason'] or 'This operation is not available for this device.')
    destructive = action in ('erase', 'partition')
    titles = {'verify-volume': 'Verify filesystem', 'verify-disk': 'Verify partition map',
              'mount': 'Mount volume', 'unmount': 'Unmount volume', 'eject': 'Eject disk',
              'rename': 'Rename volume', 'add-volume': 'Add APFS volume',
              'erase': 'Erase disk', 'partition': 'Repartition disk'}
    descriptions = {
        'verify-volume': 'Check the filesystem without repairing it. Verification may briefly pause access to files. Use Disk Utility First Aid for repairs.',
        'verify-disk': 'Check the partition map without repairing it. Use Disk Utility First Aid for repairs.',
        'mount': 'Make this volume available in Finder.',
        'unmount': 'Close files on this volume first. No forced unmount will be attempted.',
        'eject': 'Unmount all volumes on this external disk so it can be disconnected. Close open files first.',
        'rename': 'Change this volume’s name. Paths used by scripts and apps may need updating.',
        'add-volume': 'Create a new APFS volume sharing free space in this container. Existing volumes are kept.',
        'erase': 'Permanently erase EVERY volume and file on this physical disk and create a new GUID partition map. This bypasses Trash and cannot be undone. This is a format, not a secure data wipe.',
        'partition': 'Permanently erase EVERY volume and file on this physical disk, then create the layout below. This is a full repartition, not an in-place resize. It bypasses Trash and cannot be undone.',
    }
    verbs = {'verify-volume': 'verifyVolume', 'verify-disk': 'verifyDisk',
             'mount': 'mount', 'unmount': 'unmount', 'eject': 'eject'}
    layout = []
    if action in verbs:
        command = [DISKUTIL, verbs[action], identifier]
    elif action == 'rename':
        command = [DISKUTIL, 'renameVolume', identifier, volume_name(body.get('name'))]
    elif action == 'add-volume':
        fs = format_name(body.get('format'))
        if fs not in ('APFS', 'APFSX'):
            raise APIError(400, 'A shared APFS volume must use an APFS format.')
        command = [DISKUTIL, 'apfs', 'addVolume', identifier, fs, volume_name(body.get('name'))]
    elif action == 'erase':
        fs, name = format_name(body.get('format')), volume_name(body.get('name'))
        command = [DISKUTIL, 'eraseDisk', fs, name, 'GPT', identifier]
        layout = [{'name': name, 'format': fs, 'size': 'All available space'}]
    else:
        partitions = body.get('partitions')
        if not isinstance(partitions, list) or not 2 <= len(partitions) <= 4:
            raise APIError(400, 'Choose between two and four partitions.')
        command = [DISKUTIL, 'partitionDisk', identifier, str(len(partitions)), 'GPT']
        allocated = 0
        for index, part in enumerate(partitions):
            if not isinstance(part, dict):
                raise APIError(400, 'Invalid partition layout.')
            name, fs = volume_name(part.get('name')), format_name(part.get('format'))
            if index == len(partitions) - 1:
                size = 'R'
            else:
                gb = part.get('size_gb')
                if type(gb) is not int or not 1 <= gb <= 100000:
                    raise APIError(400, 'Each fixed partition needs a whole number of GB, at least 1.')
                allocated += gb * 1_000_000_000
                size = f'{gb}G'
            command += [fs, name, size]
            layout.append({'name': name, 'format': fs, 'size': 'Remaining space' if size == 'R' else size})
        if allocated + 2_000_000_000 > target['total']:
            raise APIError(400, 'Leave at least 2 GB for the final partition and partition-map overhead.')
        if len({p['name'].casefold() for p in layout}) != len(layout):
            raise APIError(400, 'Give each partition a different name.')
    return {'title': titles[action], 'description': descriptions[action],
            'commands': [command], 'changes': action not in ('verify-volume', 'verify-disk'),
            'danger': destructive, 'phrase': f'ERASE {identifier}' if destructive else '',
            'target': target, 'layout': layout, 'fingerprint': target['fingerprint']}
