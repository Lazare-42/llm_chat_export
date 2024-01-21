from pysqlcipher3 import dbapi2 as sqlcipher
import json
import uuid
import sys
from datetime import datetime

def add_file_name(msg, log):
    if 'attachments' in msg and isinstance(msg['attachments'], list):
        for att in msg['attachments']:
            if 'fileName' not in att or not att['fileName']:
                # Generate a unique file name based on contentType
                extension = determine_extension(att)
                random_name = str(uuid.uuid4())
                att['fileName'] = random_name + extension
                if log:
                    print(f"Generated fileName: {att['fileName']} for attachment in message: {msg.get('id')}")

    return msg  # Return the modified message


def determine_extension(att):
    return '.' + att['contentType'].split('/')[1]


def fetch_data(db_file, key, manual=False, chats=None, conversation_id=None, log=False):
    """Load SQLite data into dicts."""

    contacts = {}
    convos = {}

    db_file_decrypted = db_file.parents[0] / "db-decrypt.sqlite"
    if manual:
        if db_file_decrypted.exists():
            db_file_decrypted.unlink()
        command = (
            f'echo "'
            f"PRAGMA key = \\\"x'{key}'\\\";"
            f"ATTACH DATABASE '{db_file_decrypted}' AS plaintext KEY '';"
            f"SELECT sqlcipher_export('plaintext');"
            f"DETACH DATABASE plaintext;"
            f'" | sqlcipher {db_file}'
        )
        os.system(command)
        db = sqlcipher.connect(str(db_file_decrypted))
        c = db.cursor()
        c2 = db.cursor()
    else:
        db = sqlcipher.connect(str(db_file))
        c = db.cursor()
        c2 = db.cursor()
        # param binding doesn't work for pragmas, so use a direct string concat
        for cursor in [c, c2]:
            cursor.execute(f"PRAGMA KEY = \"x'{key}'\"")
            cursor.execute("PRAGMA cipher_page_size = 4096")
            cursor.execute("PRAGMA kdf_iter = 64000")
            cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512")
            cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512")

    query = "SELECT type, id, e164, name, profileName, members FROM conversations"
    if chats is not None:
        chats = '","'.join(chats)
        query = query + f' WHERE name IN ("{chats}") OR profileName IN ("{chats}")'
    c.execute(query)
    for result in c:
        if log:
            print(f"\tLoading SQL results for: {result[3]}")
        is_group = result[0] == "group"
        cid = result[1]
        contacts[cid] = {
            "id": cid,
            "name": result[3],
            "number": result[2],
            "profileName": result[4],
            "is_group": is_group,
        }
        if contacts[cid]["name"] is None:
            contacts[cid]["name"] = contacts[cid]["profileName"]
        convos[cid] = []

        if is_group:
            usable_members = []
            # Match group members from phone number to name
            if result[5] is None:
                if log:
                    print("\tEmpty group.")
            else:
                for member in result[5].split():
                    c2.execute(
                        "SELECT name, profileName FROM conversations WHERE id=?",
                        [member],
                    )
                    for name in c2:
                        usable_members.append(name[0] if name else member)
                contacts[cid]["members"] = usable_members

    c.execute("SELECT json, conversationId " "FROM messages " "ORDER BY sent_at")
    for result in c:
        content = json.loads(result[0])
        cid = result[1]
        if cid and cid in convos:
            # Process each message to handle attachments
            if not isinstance(content, dict):
                print("NOT A DICT??. Review the data you're loading.")
                exit
            else:
                # Create missing file names
                add_file_name(content, log)
            convos[cid].append(content)

    # Insert the new filtering code here
    if conversation_id is not None:
        filtered_convos = {}
        for cid, messages in convos.items():
            if contacts[cid]["name"] == conversation_id or contacts[cid]["id"] == conversation_id:
                filtered_convos[cid] = messages
        return filtered_convos, contacts

    if db_file_decrypted.exists():
        db_file_decrypted.unlink()

    return convos, contacts

def filter_data(conversations, contacts, year=None, attachments_only=False, log=False):
    print(attachments_only, year)
    exit
    filtered_convos = {}
    for key, messages in conversations.items():
        filtered_messages = []
        for msg in messages:
            # Check for year filter
            timestamp = msg.get("timestamp") or msg.get("sent_at")
            if year is not None and timestamp:
                date = datetime.fromtimestamp(timestamp / 1000.0)
                if date.year != year:
                    continue  # Skip messages not from the specified year

            # Check for attachments-only filter
            if attachments_only and ("attachments" not in msg or not msg["attachments"]):
                continue  # Skip messages without attachments

            # If the message passes all filters, add it to filtered messages
            filtered_messages.append(msg)

        if filtered_messages:
            filtered_convos[key] = filtered_messages
    return filtered_convos, contacts


## examples of sanity checks we should implement
# if attachments_only and ("attachments" not in msg or not msg["attachments"]) and log:
# if log:
#     print(f"Skipping message (No attachments): {date_str if 'date_str' in locals() else 'Unknown Date'} - {sender if 'sender' in locals() else 'Unknown Sender'}")
#     print(f"Message Details: {json.dumps(msg, indent=2)}")
#     print('should not have been here')
#     exit
# continue  # Skip this message if there are no attachments