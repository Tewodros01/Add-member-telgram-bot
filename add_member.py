import logging
from telethon import TelegramClient
from telethon.tl.types import InputPeerChannel, InputPeerUser
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.errors.rpcerrorlist import PeerFloodError, UserPrivacyRestrictedError, FloodWaitError
import time
import traceback
import datetime
import os
import json


def get_group_by_id(groups, group_id):
    for group in groups:
        if group_id == int(group['group_id']):
            return group
    return None


root_path = os.path.dirname(os.path.abspath(__file__))
print(root_path)

start_time = datetime.datetime.now()
logging.basicConfig(level=logging.WARNING)

with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

accounts = config['accounts']
print("Total account: " + str(len(accounts)))
folder_session = 'session/'

# Group target and source
group_target_id = config['group_target']
group_source_id = config['group_source']
from_date_active = config.get('from_date_active', '19700101')

# List of clients
clients = []
for account in accounts:
    api_id = account['api_id']
    api_hash = account['api_hash']
    phone = account['phone']

    client = TelegramClient(folder_session + phone, api_id, api_hash)
    client.connect()

    if client.is_user_authorized():
        print(phone + ' login success')
        clients.append({
            'phone': phone,
            'client': client
        })
    else:
        print(phone + ' login fail')

filter_clients = []

for my_client in clients:
    phone = my_client['phone']
    path_group = os.path.join(root_path, 'data/group', phone + '.json')

    if os.path.isfile(path_group):
        with open(path_group, 'r', encoding='utf-8') as f:
            groups = json.load(f)

        current_target_group = get_group_by_id(groups, group_target_id)

        if current_target_group:
            group_access_hash = int(current_target_group['access_hash'])
            target_group_entity = InputPeerChannel(group_target_id, group_access_hash)

            path_group_user = os.path.join(root_path, 'data/user', f"{phone}_{group_source_id}.json")
            if os.path.isfile(path_group_user):
                my_client['target_group_entity'] = target_group_entity
                with open(path_group_user, encoding='utf-8') as f:
                    my_client['users'] = json.load(f)
                filter_clients.append(my_client)
            else:
                print(f'This account with phone {phone} is not in source group')
        else:
            print(f'This account with phone {phone} is not in target group')
    else:
        print(f'This account with phone does not have data. Please run get_data or init_session')

# Run the adding process
previous_count = 0
count_add = 0

try:
    with open(os.path.join(root_path, 'current_count.txt')) as f:
        previous_count = int(f.read())
except Exception as e:
    pass

print('From index: ' + str(previous_count))
total_client = len(filter_clients)

if total_client > 0:
    total_user = len(filter_clients[0]['users'])
    i = 0
    while i < total_user:
        if i < previous_count:
            i += 1
            continue

        if count_add % (35 * total_client) == (35 * total_client - 1):
            print('Sleeping for 15 minutes')
            time.sleep(15 * 60)

        total_client = len(filter_clients)
        print("Remaining clients: " + str(total_client))
        if total_client == 0:
            with open(os.path.join(root_path, 'current_count.txt'), 'w') as g:
                g.write(str(i))
            print('END: No more clients available')
            break

        current_index = count_add % total_client
        print("Current index: " + str(current_index))
        current_client = filter_clients[current_index]
        client = current_client['client']
        user = current_client['users'][i]

        if user['date_online'] != 'online' and user['date_online'] < from_date_active:
            i += 1
            print(f"User {user['user_id']} has last active time {user['date_online']} which is overdue")
            continue

        target_group_entity = current_client['target_group_entity']

        try:
            print('Adding member: ' + user['username'])
            user_to_add = InputPeerUser(int(user['user_id']), int(user['access_hash']))
            client(InviteToChannelRequest(target_group_entity, [user_to_add]))
            print('Added member ' + user['username'] + ' successfully ;-)')
            count_add += 1
            print('Sleeping for: ' + str(120 / total_client))
            time.sleep(120 / total_client)

        except PeerFloodError:
            print("Encountered a PeerFloodError")
            traceback.print_exc()
            print("Removing client: " + current_client['phone'])
            client.disconnect()
            filter_clients.remove(current_client)
            continue

        except UserPrivacyRestrictedError:
            print("UserPrivacyRestrictedError encountered")

        except FloodWaitError:
            print("Encountered a FloodWaitError")
            traceback.print_exc()
            print("Removing client: " + current_client['phone'])
            client.disconnect()
            filter_clients.remove(current_client)
            continue

        except Exception:
            print("Encountered an unexpected error")
            traceback.print_exc()

        i += 1

    with open(os.path.join(root_path, 'current_count.txt'), 'w') as g:
        g.write(str(i))
else:
    print('No clients available to add members.')

print("Disconnecting clients")
for cli in clients:
    cli['client'].disconnect()

end_time = datetime.datetime.now()
print("Total added: " + str(count_add))
print("Total time: " + str(end_time - start_time))
